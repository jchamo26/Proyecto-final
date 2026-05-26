import json
from typing import Any, Dict, List

import redis.asyncio as redis
from app.config import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
_session_cache: Dict[str, List[Dict[str, Any]]] = {}

class SessionMemory:
    @staticmethod
    async def add(session_id: str, turn: Dict[str, Any]) -> None:
        key = f"agent:session:{session_id}"
        try:
            await redis_client.rpush(key, json.dumps(turn))
            await redis_client.expire(key, 3600)
        except Exception:
            _session_cache.setdefault(session_id, []).append(turn)

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
