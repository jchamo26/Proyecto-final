"""Compatibility shim exposing the backend services as `app.services`.

This module forwards exports from `backend.app.services` so tests that
import `app.services` work without changing their import paths.
"""

from backend.app.services import (
    RAGEvaluationService,
    get_rag_service,
    RAGEvaluationRequest,
    RAGEvaluationResult,
)

__all__ = [
    "RAGEvaluationService",
    "get_rag_service",
    "RAGEvaluationRequest",
    "RAGEvaluationResult",
]
