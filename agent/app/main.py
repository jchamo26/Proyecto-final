import uuid

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Base
from app.db.session import engine, get_db
from app.memory import LongTermMemory, SessionMemory
from app.rag import retrieve_contexts, retrieval_stats
from app.rate_limit import limiter
from app.security import mask_pii_in_response, sanitize_user_input
from app.tools import create_diagnostic_report, invoke_ml_model, query_fhir

app = FastAPI(
    title="Agente RAG Clínico",
    description="Microservicio RAG con memoria a corto y largo plazo.",
    version="1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


@app.on_event("startup")
async def startup_event():
    Base.metadata.create_all(bind=engine)


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
    return {"status": "ok"}


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

    retrieval = retrieve_contexts(
        query=question,
        strategy=rag_strategy,
        top_k=rag_top_k,
        alpha=rag_alpha,
    )

    fhir_warning = None
    try:
        fhir_result = await query_fhir(patient_id=patient_id, loinc_code=loinc_code)
    except Exception as exc:
        fhir_warning = str(exc)
        fhir_result = {
            "request_url": "unavailable",
            "status_code": 503,
            "data": {"warning": "FHIR no disponible", "patient_id": patient_id},
        }

    ml_payload = {
        "patient_id": patient_id,
        "question": question,
        "rag_contexts": retrieval["contexts"],
        "fhir_data": fhir_result["data"],
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
        "retrieved_contexts": [item["text"] for item in retrieval["contexts"]],
        "rag_metadata": {
            "strategy": retrieval["strategy"],
            "alpha": retrieval["alpha"],
            "top_k": retrieval["top_k"],
            "total_documents": retrieval["total_documents"],
        },
        "fhir_metadata": {
            "request_url": fhir_result["request_url"],
            "status_code": fhir_result["status_code"],
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
