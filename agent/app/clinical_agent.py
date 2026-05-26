from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.knowledge_base import HybridRAGIndexer
from app.memory import LongTermMemory, SessionMemory
from app.security import mask_pii_in_response, sanitize_user_input
from app.tools import create_diagnostic_report, invoke_ml_model, query_fhir

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_fhir_paciente",
            "description": "Consulta datos clinicos de un paciente en el servidor FHIR R4.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "loinc_code": {"type": "string"},
                },
                "required": ["patient_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "predecir_modelo_tabular",
            "description": "Ejecuta el modelo ML tabular con payload compatible.",
            "parameters": {
                "type": "object",
                "properties": {
                    "payload": {"type": "object"},
                },
                "required": ["payload"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_guias_clinicas",
            "description": "Busca en base de conocimiento clinica con indice hibrido.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "default": 5},
                    "alpha": {"type": "number", "default": 0.6},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crear_reporte_clinico",
            "description": "Genera DiagnosticReport en FHIR.",
            "parameters": {
                "type": "object",
                "properties": {
                    "report": {"type": "object"},
                },
                "required": ["report"],
            },
        },
    },
]


class ClinicalRAGAgent:
    def __init__(self):
        self.rag_index = HybridRAGIndexer(index_path=settings.RAG_INDEX_PATH)
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return

        try:
            self.rag_index.load_indexes()
        except Exception:
            docs_path = settings.RAG_DOCS_PATH
            if docs_path and os.path.isdir(docs_path):
                self.rag_index.index_directory(docs_path)
        self._initialized = True

    async def _execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        try:
            if name == "consultar_fhir_paciente":
                result = await query_fhir(
                    patient_id=str(args.get("patient_id", "")),
                    loinc_code=args.get("loinc_code"),
                )
                return json.dumps(result.get("data", {}), ensure_ascii=False)[:3000]

            if name == "predecir_modelo_tabular":
                payload = args.get("payload", {})
                result = await invoke_ml_model("tabular", payload)
                return json.dumps(result, ensure_ascii=False)

            if name == "buscar_guias_clinicas":
                results = self.rag_index.search(
                    query=str(args.get("query", "")),
                    top_k=int(args.get("top_k", 5)),
                    alpha=float(args.get("alpha", 0.6)),
                )
                return json.dumps(results, ensure_ascii=False)[:3500]

            if name == "crear_reporte_clinico":
                report = args.get("report", {})
                result = await create_diagnostic_report(report)
                return json.dumps(result, ensure_ascii=False)

            return f"Tool no reconocida: {name}"
        except Exception as exc:
            return f"Error ejecutando {name}: {exc}"

    async def _llm_chat(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        endpoint = settings.LLM_ENDPOINT.rstrip("/")
        if not endpoint.endswith("/v1"):
            endpoint = f"{endpoint}/v1"

        payload = {
            "model": settings.LLM_MODEL,
            "messages": messages,
            "tools": TOOLS,
            "tool_choice": "auto",
            "temperature": 0.2,
            "max_tokens": 1200,
        }
        headers = {"Content-Type": "application/json"}
        api_key = settings.LLM_API_KEY or os.environ.get("OPENAI_API_KEY", "")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(f"{endpoint}/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            return response.json()

    async def chat(self, db, session_id: str, user_message: str, patient_id: Optional[str] = None) -> Dict[str, Any]:
        question = sanitize_user_input(user_message)

        prior_turns = await SessionMemory.get(session_id)
        message_history: List[Dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "Eres un asistente clinico. Responde en espanol y fundamenta con contexto recuperado. "
                    "No expongas PII. Si necesitas datos usa tools."
                ),
            }
        ]

        for turn in prior_turns[-10:]:
            role = turn.get("role", "assistant")
            content = turn.get("content", "")
            if isinstance(content, dict):
                content = json.dumps(content, ensure_ascii=False)
            message_history.append({"role": role if role in {"user", "assistant", "tool"} else "assistant", "content": str(content)})

        historical_context = ""
        if patient_id:
            history = LongTermMemory.history(db, patient_id=patient_id, limit=6)
            historical_context = LongTermMemory.format_history_context(history)

        rag_hits = []
        try:
            rag_hits = self.rag_index.search(question, top_k=settings.RAG_TOP_K, alpha=settings.RAG_HYBRID_ALPHA)
        except Exception:
            rag_hits = []

        rag_context = "\n---\n".join(
            [f"[Fuente: {PathLike(hit.get('source'))}] {hit.get('text', '')}" for hit in rag_hits]
        )

        user_prompt = (
            f"{question}\n\n"
            f"Contexto historico:\n{historical_context or 'Sin historial previo.'}\n\n"
            f"Contexto RAG:\n{rag_context or 'Sin resultados de indice local.'}"
        )
        message_history.append({"role": "user", "content": user_prompt})

        final_answer = ""
        executed_tools: List[Dict[str, Any]] = []

        for _ in range(settings.AGENT_MAX_ITERATIONS):
            llm_data = await self._llm_chat(message_history)
            choice = (llm_data.get("choices") or [{}])[0]
            msg = choice.get("message", {}) if isinstance(choice, dict) else {}

            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                final_answer = msg.get("content") or "No pude generar una respuesta confiable."
                break

            message_history.append({"role": "assistant", "content": msg.get("content", ""), "tool_calls": tool_calls})

            for tool_call in tool_calls:
                function_obj = tool_call.get("function", {})
                tool_name = function_obj.get("name", "")
                raw_args = function_obj.get("arguments", "{}")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                except Exception:
                    args = {}
                tool_output = await self._execute_tool(tool_name, args)
                executed_tools.append({"tool": tool_name, "args": args})
                message_history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", "tool-call"),
                        "content": tool_output,
                    }
                )

        if not final_answer:
            context_text = " ".join([hit.get("text", "") for hit in rag_hits[:2]])
            final_answer = f"Respuesta preliminar basada en contexto recuperado: {context_text[:600]}"

        final_answer = mask_pii_in_response(final_answer)

        await SessionMemory.add(session_id, {"role": "user", "content": question})
        await SessionMemory.add(session_id, {"role": "assistant", "content": final_answer})

        if patient_id:
            LongTermMemory.save_interaction(
                db,
                patient_id=patient_id,
                session_id=session_id,
                query=question,
                response=final_answer,
                context_used=[str(hit.get("source", "")) for hit in rag_hits],
            )

        return {
            "response": final_answer,
            "session_id": session_id,
            "used_tools": executed_tools,
            "retrieved_contexts": rag_hits,
        }


class PathLike(str):
    def __new__(cls, value: Any):
        if not value:
            return super().__new__(cls, "documento")
        text = str(value).replace("\\", "/")
        return super().__new__(cls, text.split("/")[-1] or "documento")
