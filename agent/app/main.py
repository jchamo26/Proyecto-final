import uuid
from typing import Any, Dict, List

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy.orm import Session

from app.clinical_agent import ClinicalRAGAgent
from app.config import settings
from app.db.models import Base
from app.db.session import engine, get_db
from app.memory import LongTermMemory, SessionMemory
from app.rag import retrieve_contexts, retrieval_stats
from app.rate_limit import limiter
from app.security import mask_pii_in_response, sanitize_user_input
from app.tools import create_diagnostic_report, invoke_ml_model, query_fhir, query_patient_clinical_data

app = FastAPI(
    title="Agente RAG Clínico",
    description="Microservicio RAG con memoria a corto y largo plazo.",
    version="1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
clinical_agent = ClinicalRAGAgent()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    patient_id: str | None = None


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    alpha: float = 0.6


@app.on_event("startup")
async def startup_event():
    Base.metadata.create_all(bind=engine)
    await clinical_agent.initialize()


@app.middleware("http")
async def pii_response_middleware(request: Request, call_next):
    response = await call_next(request)
    if response.headers.get("content-type", "").startswith("application/json"):
        # Some responses are streaming and do not expose a body attribute.
        # In those cases, keep the original response to avoid breaking the request.
        if not hasattr(response, "body"):
            return response
        body = response.body
        if body is None:
            return response
        try:
            import json
            payload = json.loads(body.decode("utf-8"))
            safe_payload = mask_pii_in_response(payload)
            return JSONResponse(status_code=response.status_code, content=safe_payload)
        except Exception:
            return response
    return response


@app.get("/healthz")
async def health():
    rag_chunks = 0
    try:
        rag_chunks = len(clinical_agent.rag_index.chunks)
    except Exception:
        rag_chunks = 0
    return {"status": "ok", "rag_index_loaded": clinical_agent._initialized, "chunks_indexed": rag_chunks}


@app.get("/health")
async def health_alias():
    return await health()


@app.post("/chat")
@limiter.limit("60/minute")
async def chat_endpoint(request: Request, payload: ChatRequest, db: Session = Depends(get_db)):
    session_id = payload.session_id or uuid.uuid4().hex
    result = await clinical_agent.chat(
        db=db,
        session_id=session_id,
        user_message=payload.message,
        patient_id=payload.patient_id,
    )
    return {"response": result["response"], "session_id": session_id, "meta": {"used_tools": result["used_tools"]}}


@app.post("/search")
@limiter.limit("80/minute")
async def search_endpoint(request: Request, payload: SearchRequest):
    query = sanitize_user_input(payload.query)
    try:
        return clinical_agent.rag_index.search(query=query, top_k=payload.top_k, alpha=payload.alpha)
    except Exception:
        retrieval = retrieve_contexts(query=query, top_k=payload.top_k, alpha=payload.alpha)
        return [
            {
                "id": item.get("id"),
                "texto": item.get("text"),
                "fuente": item.get("source", "clinical_corpus"),
                "score_combined": item.get("score", 0.0),
            }
            for item in retrieval.get("contexts", [])
        ]


@app.delete("/sessions/{session_id}")
@limiter.limit("30/minute")
async def clear_session(request: Request, session_id: str):
    await SessionMemory.clear(session_id)
    return {"message": f"Sesion {session_id} eliminada"}


def _extract_ext_value(extension: Dict[str, Any]) -> str:
    if "valueString" in extension:
        return str(extension.get("valueString"))
    if "valueDecimal" in extension:
        return str(extension.get("valueDecimal"))
    if "valueInteger" in extension:
        return str(extension.get("valueInteger"))
    if "valueCode" in extension:
        return str(extension.get("valueCode"))
    return ""


def _build_patient_context_documents(patient_id: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []

    patient_resource = context.get("patient", {}) if isinstance(context, dict) else {}
    if isinstance(patient_resource, dict) and patient_resource:
        name_obj = (patient_resource.get("name") or [{}])[0] if isinstance(patient_resource.get("name"), list) else {}
        given = " ".join(name_obj.get("given", [])) if isinstance(name_obj, dict) else ""
        family = name_obj.get("family", "") if isinstance(name_obj, dict) else ""
        full_name = f"{given} {family}".strip() or f"Paciente {patient_id}"
        birth_date = patient_resource.get("birthDate", "desconocida")
        gender = patient_resource.get("gender", "unknown")

        extension_notes: List[str] = []
        extensions = patient_resource.get("extension", [])
        if isinstance(extensions, list):
            for ext in extensions:
                if not isinstance(ext, dict):
                    continue
                url = str(ext.get("url", ""))
                value = _extract_ext_value(ext)
                if not value:
                    continue
                if "heart-disease-pathology" in url:
                    extension_notes.append(f"Patologia cardiaca del dataset: {value}.")
                elif "heart-disease-target" in url:
                    extension_notes.append(f"Nivel de severidad del dataset (num): {value}.")
                elif "uci-feature-" in url:
                    feature = url.rsplit("uci-feature-", 1)[-1]
                    extension_notes.append(f"Feature UCI {feature}: {value}.")

        summary = (
            f"Paciente {full_name}. ID {patient_id}. Genero {gender}. Fecha de nacimiento {birth_date}. "
            + " ".join(extension_notes)
        ).strip()

        docs.append(
            {
                "id": f"patient-{patient_id}",
                "title": f"Resumen clinico del paciente {patient_id}",
                "text": summary,
                "tags": ["patient", "dataset", "cardiologia"],
                "source": "fhir_patient",
            }
        )

    conditions_bundle = context.get("conditions_bundle", {}) if isinstance(context, dict) else {}
    entries = conditions_bundle.get("entry", []) if isinstance(conditions_bundle, dict) else []
    if isinstance(entries, list):
        for idx, entry in enumerate(entries):
            resource = entry.get("resource", {}) if isinstance(entry, dict) else {}
            if not isinstance(resource, dict):
                continue
            code = resource.get("code", {})
            text = ""
            if isinstance(code, dict):
                text = code.get("text", "") or ""
                coding = code.get("coding", [])
                if not text and isinstance(coding, list) and coding:
                    text = coding[0].get("display", "") or coding[0].get("code", "")
            clinical_status = resource.get("clinicalStatus", {})
            status_code = ""
            if isinstance(clinical_status, dict):
                coding = clinical_status.get("coding", [])
                if isinstance(coding, list) and coding:
                    status_code = coding[0].get("code", "")
            note_text = ""
            notes = resource.get("note", [])
            if isinstance(notes, list) and notes:
                note_text = notes[0].get("text", "")

            condition_text = f"Condicion cardiaca: {text}. Estado clinico: {status_code}. {note_text}".strip()
            if condition_text:
                docs.append(
                    {
                        "id": f"condition-{patient_id}-{idx + 1}",
                        "title": f"Condicion registrada {idx + 1}",
                        "text": condition_text,
                        "tags": ["condition", "cardiologia", "patient"],
                        "source": "fhir_condition",
                    }
                )

    observations_bundle = context.get("observations_bundle", {}) if isinstance(context, dict) else {}
    obs_entries = observations_bundle.get("entry", []) if isinstance(observations_bundle, dict) else []
    if isinstance(obs_entries, list):
        for idx, entry in enumerate(obs_entries[:25]):
            resource = entry.get("resource", {}) if isinstance(entry, dict) else {}
            if not isinstance(resource, dict):
                continue
            code = resource.get("code", {})
            loinc = ""
            label = ""
            if isinstance(code, dict):
                coding = code.get("coding", [])
                if isinstance(coding, list) and coding:
                    loinc = coding[0].get("code", "")
                    label = coding[0].get("display", "")
                label = label or code.get("text", "")
            value_quantity = resource.get("valueQuantity", {})
            value_text = ""
            if isinstance(value_quantity, dict):
                value = value_quantity.get("value")
                unit = value_quantity.get("unit", "")
                if value is not None:
                    value_text = f"{value} {unit}".strip()

            obs_text = f"Observacion {label or 'sin descripcion'} (LOINC {loinc}): {value_text}."
            docs.append(
                {
                    "id": f"observation-{patient_id}-{idx + 1}",
                    "title": f"Observacion clinica {idx + 1}",
                    "text": obs_text,
                    "tags": ["observation", "patient", "loinc"],
                    "source": "fhir_observation",
                }
            )

    return docs


def _build_clinical_answer(question: str, ml_result: Dict[str, Any], retrieval_contexts: List[Dict[str, Any]], warnings: Dict[str, Any]) -> str:
    prediction = ml_result.get("prediction") if isinstance(ml_result, dict) else "sin prediccion"
    probability = ml_result.get("probability") if isinstance(ml_result, dict) else None
    probability_text = f"{round(float(probability) * 100)}%" if isinstance(probability, (int, float)) else "no disponible"

    recommendations = [
        "Correlacionar con signos y sintomas actuales del paciente.",
        "Verificar ECG de 12 derivaciones y biomarcadores segun criterio clinico.",
        "Reevaluar factores de riesgo cardiovascular y adherencia terapeutica.",
    ]

    if isinstance(prediction, str) and "alto" in prediction.lower():
        recommendations.insert(0, "Priorizar valoracion por cardiologia y definir necesidad de manejo urgente.")

    evidence = []
    for item in retrieval_contexts[:3]:
        text = str(item.get("text", "")).strip()
        if text:
            evidence.append(f"- {text}")

    warning_text = ""
    if warnings.get("fhir"):
        warning_text = "\n\nNota operativa: no fue posible consultar FHIR en esta ejecucion; la respuesta usa el contexto clinico disponible."

    return (
        f"Pregunta clinica: {question}\n"
        f"Resultado estimado: {prediction} (probabilidad {probability_text}).\n\n"
        f"Recomendaciones iniciales:\n- " + "\n- ".join(recommendations) +
        ("\n\nEvidencia contextual recuperada:\n" + "\n".join(evidence) if evidence else "") +
        warning_text
    )


@app.post("/agent/query")
@limiter.limit("60/minute")
async def query_agent(request: Request, payload: dict, db: Session = Depends(get_db)):
    session_id = payload.get("session_id") or uuid.uuid4().hex
    patient_id = payload.get("patient_id")
    question = payload.get("question", "")
    model_type = payload.get("model_type", "tabular")
    if model_type == "images":
        model_type = "image"
    loinc_code = payload.get("loinc_code")
    rag_strategy = payload.get("rag_strategy", settings.RAG_DEFAULT_STRATEGY)
    rag_alpha = float(payload.get("rag_alpha", settings.RAG_HYBRID_ALPHA))
    rag_top_k = int(payload.get("rag_top_k", settings.RAG_TOP_K))

    if not patient_id or not question:
        raise HTTPException(status_code=400, detail="patient_id y question son obligatorios.")

    try:
        question = sanitize_user_input(question)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    fhir_warning = None
    patient_context_warning = None
    try:
        fhir_result = await query_fhir(patient_id=patient_id, loinc_code=loinc_code)
    except Exception as exc:
        fhir_warning = str(exc)
        fhir_result = {
            "request_url": "unavailable",
            "status_code": 503,
            "data": {"warning": "FHIR no disponible", "patient_id": patient_id},
        }

    try:
        patient_context = await query_patient_clinical_data(patient_id=patient_id)
    except Exception as exc:
        patient_context_warning = str(exc)
        patient_context = {
            "patient": {},
            "observations_bundle": fhir_result.get("data", {}),
            "conditions_bundle": {},
        }

    patient_documents = _build_patient_context_documents(patient_id, patient_context)

    retrieval = retrieve_contexts(
        query=question,
        strategy=rag_strategy,
        top_k=rag_top_k,
        alpha=rag_alpha,
        extra_documents=patient_documents,
    )

    ml_payload = {
        "patient_id": patient_id,
        "question": question,
        "rag_contexts": retrieval["contexts"],
        "fhir_data": fhir_result["data"],
        "patient_context": patient_context,
    }
    ml_warning = None
    try:
        ml_result = await invoke_ml_model(model_type=model_type, payload=ml_payload)
    except Exception as exc:
        ml_warning = str(exc)
        ml_result = {
            "model": model_type,
            "prediction": "sin resultado de inferencia",
            "probability": None,
            "warning": "Servicio ML/DL no disponible",
        }

    answer = {
        "patient_id": patient_id,
        "question": question,
        "prediction": ml_result,
        "assistant_response": _build_clinical_answer(
            question=question,
            ml_result=ml_result if isinstance(ml_result, dict) else {},
            retrieval_contexts=retrieval.get("contexts", []),
            warnings={"fhir": fhir_warning, "ml_dl": ml_warning},
        ),
        "retrieved_contexts": [item["text"] for item in retrieval["contexts"]],
        "rag_metadata": {
            "strategy": retrieval["strategy"],
            "alpha": retrieval["alpha"],
            "top_k": retrieval["top_k"],
            "total_documents": retrieval["total_documents"],
            "patient_documents": len(patient_documents),
        },
        "fhir_metadata": {
            "request_url": fhir_result["request_url"],
            "status_code": fhir_result["status_code"],
            "patient_context_warning": patient_context_warning,
        },
        "warnings": {
            "fhir": fhir_warning,
            "ml_dl": ml_warning,
        },
    }

    await SessionMemory.add(session_id, {"role": "user", "content": question})
    await SessionMemory.add(session_id, {"role": "agent", "content": answer})

    LongTermMemory.save(
        db,
        patient_id=patient_id,
        session_id=session_id,
        summary=f"Pregunta: {question}. Respuesta: {ml_result.get('prediction', 'sin predicción')}",
    )
    LongTermMemory.save_interaction(
        db,
        patient_id=patient_id,
        session_id=session_id,
        query=question,
        response=str(answer),
        context_used=[ctx.get("source", "clinical_corpus") for ctx in retrieval.get("contexts", [])],
    )

    return {
        "session_id": session_id,
        "answer": answer,
        "sources": ["rag", "fhir", "ml_inference"],
    }


@app.get("/agent/memory/session/{session_id}")
@limiter.limit("60/minute")
async def read_session_memory(request: Request, session_id: str):
    return {"session_id": session_id, "history": await SessionMemory.get(session_id)}


@app.get("/agent/memory/summary/{patient_id}")
@limiter.limit("60/minute")
async def read_long_term_memory(request: Request, patient_id: str, db: Session = Depends(get_db)):
    return {"patient_id": patient_id, "summaries": LongTermMemory.list(db, patient_id)}


@app.post("/agent/tools/fhir/query")
@limiter.limit("40/minute")
async def fhir_tool(request: Request, payload: dict):
    patient_id = payload.get("patient_id")
    if not patient_id:
        raise HTTPException(status_code=400, detail="patient_id es obligatorio.")
    loinc_code = payload.get("loinc_code")
    return await query_fhir(patient_id=patient_id, loinc_code=loinc_code)


@app.post("/agent/tools/ml/infer")
@limiter.limit("40/minute")
async def ml_tool(request: Request, payload: dict):
    model_type = payload.get("model_type", "tabular")
    if model_type == "images":
        model_type = "image"
    if model_type not in {"tabular", "image"}:
        raise HTTPException(status_code=400, detail="model_type debe ser 'tabular' o 'image'.")
    return await invoke_ml_model(model_type=model_type, payload=payload)


@app.post("/agent/tools/fhir/report")
@limiter.limit("30/minute")
async def create_report(request: Request, payload: dict):
    if not payload:
        raise HTTPException(status_code=400, detail="payload es obligatorio.")
    return await create_diagnostic_report(payload)


@app.post("/agent/retrieval/search")
@limiter.limit("60/minute")
async def retrieval_search(request: Request, payload: dict):
    question = payload.get("question", "")
    if not question:
        raise HTTPException(status_code=400, detail="question es obligatorio.")
    strategy = payload.get("strategy", settings.RAG_DEFAULT_STRATEGY)
    alpha = float(payload.get("alpha", settings.RAG_HYBRID_ALPHA))
    top_k = int(payload.get("top_k", settings.RAG_TOP_K))
    return retrieve_contexts(question, strategy=strategy, alpha=alpha, top_k=top_k)


@app.get("/agent/retrieval/stats")
@limiter.limit("60/minute")
async def retrieval_info(request: Request):
    return retrieval_stats()
