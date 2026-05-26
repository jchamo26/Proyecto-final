import json
from typing import Any, Dict, List

import redis.asyncio as redis
from app.config import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
_session_cache: Dict[str, List[Dict[str, Any]]] = {}
SESSION_TTL = 3600
MAX_TURNS = 20

class SessionMemory:
    @staticmethod
    async def add(session_id: str, turn: Dict[str, Any]) -> None:
        key = f"agent:session:{session_id}"
        try:
            await redis_client.rpush(key, json.dumps(turn))
            await redis_client.ltrim(key, -MAX_TURNS, -1)
            await redis_client.expire(key, SESSION_TTL)
        except Exception:
            _session_cache.setdefault(session_id, []).append(turn)
            if len(_session_cache[session_id]) > MAX_TURNS:
                _session_cache[session_id] = _session_cache[session_id][-MAX_TURNS:]

    @staticmethod
    async def get(session_id: str) -> List[Dict[str, Any]]:
        key = f"agent:session:{session_id}"
        try:
            entries = await redis_client.lrange(key, 0, -1)
            return [json.loads(item) for item in entries]
        except Exception:
            return _session_cache.get(session_id, [])

    @staticmethod
    async def clear(session_id: str) -> None:
        key = f"agent:session:{session_id}"
        try:
            await redis_client.delete(key)
        except Exception:
            _session_cache.pop(session_id, None)

class LongTermMemory:
    @staticmethod
    def save(db, patient_id: str, summary: str, session_id: str | None = None) -> None:
        from app.db.models import AgentSummary

        record = AgentSummary(patient_id=patient_id, summary=summary, session_id=session_id)
        db.add(record)
        db.commit()
        db.refresh(record)

    @staticmethod
    def list(db, patient_id: str) -> List[Dict[str, Any]]:
        from app.db.models import AgentSummary

        summaries = db.query(AgentSummary).filter(AgentSummary.patient_id == patient_id).order_by(AgentSummary.created_at.desc()).all()
        return [
            {
                "id": summary.id,
                "patient_id": summary.patient_id,
                "session_id": summary.session_id,
                "summary": summary.summary,
                "created_at": summary.created_at.isoformat(),
            }
            for summary in summaries
        ]

    @staticmethod
    def save_interaction(
        db,
        patient_id: str,
        session_id: str,
        query: str,
        response: str,
        context_used: List[str] | None = None,
    ) -> None:
        from app.db.models import AgentMemoryRecord

        record = AgentMemoryRecord(
            patient_id=patient_id,
            session_id=session_id,
            user_query=query,
            agent_response=response,
            context_used=json.dumps(context_used or [], ensure_ascii=False),
        )
        db.add(record)
        db.commit()
        db.refresh(record)

    @staticmethod
    def history(db, patient_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        from app.db.models import AgentMemoryRecord

        rows = (
            db.query(AgentMemoryRecord)
            .filter(AgentMemoryRecord.patient_id == patient_id)
            .order_by(AgentMemoryRecord.created_at.desc())
            .limit(limit)
            .all()
        )
        rows = list(reversed(rows))

        history: List[Dict[str, Any]] = []
        for row in rows:
            try:
                context_used = json.loads(row.context_used) if row.context_used else []
            except Exception:
                context_used = []
            history.append(
                {
                    "date": row.created_at.isoformat(),
                    "query": row.user_query,
                    "response_summary": row.agent_response[:220],
                    "session_id": row.session_id,
                    "context_used": context_used,
                }
            )
        return history

    @staticmethod
    def format_history_context(history: List[Dict[str, Any]]) -> str:
        if not history:
            return "No hay historial previo para este paciente."
        lines = ["=== HISTORIAL PREVIO DEL PACIENTE ==="]
        for item in history:
            day = item.get("date", "")[:10]
            lines.append(f"[{day}] Consulta: {item.get('query', '')}")
            lines.append(f"  -> Respuesta: {item.get('response_summary', '')}")
        return "\n".join(lines)
