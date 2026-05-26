"""
Endpoints para Evaluación RAGAS
Integración de Mock Server con Backend API
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import List, Optional
from datetime import datetime, timedelta
import os

from ..services import (
    RAGEvaluationService,
    RAGEvaluationRequest,
    RAGEvaluationResult,
    get_rag_service
)

router = APIRouter(
    prefix="/api/v1/ragas",
    tags=["RAGAS Evaluation"]
)

# State management
_evaluation_jobs = {}  # { job_id: { status, results, error, created_at } }
_job_counter = 0

@router.post("/evaluate", response_model=RAGEvaluationResult)
async def evaluate_single(
    request: RAGEvaluationRequest,
    service: RAGEvaluationService = Depends(get_rag_service)
):
    """
    Evalúa una sola instancia de Q&A con RAGAS
    
    **Metrics:**
    - **faithfulness** (0-1): ¿Qué tan fiel es la respuesta al contexto?
    - **answer_relevancy** (-1 to 1): ¿Qué tan relevante es la respuesta a la pregunta?
    - **context_precision** (0-1): Precisión del contexto recuperado
    - **context_recall** (0-1): Cobertura del contexto recuperado
    """
    try:
        result = await service.evaluate_single(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/evaluate-batch", response_model=List[RAGEvaluationResult])
async def evaluate_batch(
    requests: List[RAGEvaluationRequest],
    background_tasks: BackgroundTasks,
    service: RAGEvaluationService = Depends(get_rag_service)
):
    """
    Evalúa múltiples instancias de Q&A
    Retorna resultados una vez disponibles
    """
    try:
        results = await service.evaluate_batch(requests)
        
        # Guardar resultados en background
        background_tasks.add_task(
            service.save_results,
            results,
            f"batch_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/evaluate-batch/{job_id}")
async def get_batch_result(job_id: str):
    """
    Obtiene el resultado de una evaluación batch
    Los resultados se mantienen durante 24 horas
    """
    if job_id not in _evaluation_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = _evaluation_jobs[job_id]
    
    # Limpiar jobs antiguos
    if datetime.now() - job["created_at"] > timedelta(hours=24):
        del _evaluation_jobs[job_id]
        raise HTTPException(status_code=404, detail="Job expired")
    
    return job

@router.get("/status")
async def get_status(service: RAGEvaluationService = Depends(get_rag_service)):
    """
    Estado de la integración RAGAS
    Verifica conexión con Mock Server
    """
    try:
        import httpx
        
        llm_endpoint = os.getenv("LLM_ENDPOINT", "http://127.0.0.1:8501")
        
        # Intentar conectar con mock server
        async with httpx.AsyncClient(timeout=5) as client:
            health_response = await client.get(f"{llm_endpoint}/health")
            stats_response = await client.get(f"{llm_endpoint}/stats")
        
        stats = stats_response.json() if stats_response.status_code == 200 else {}
        
        return {
            "status": "healthy" if health_response.status_code == 200 else "unhealthy",
            "llm_endpoint": llm_endpoint,
            "mock_server": health_response.status_code == 200,
            "statistics": {
                "total_calls": stats.get("total_calls", 0),
                "calls_by_metric": stats.get("calls_by_metric", {})
            }
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "llm_endpoint": os.getenv("LLM_ENDPOINT", "http://127.0.0.1:8501"),
            "mock_server": False
        }

@router.get("/health")
async def health_check():
    """
    Health check del servicio RAGAS
    Verifica disponibilidad y configuración
    """
    try:
        import httpx
        
        llm_endpoint = os.getenv("LLM_ENDPOINT", "http://127.0.0.1:8501")
        
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{llm_endpoint}/health")
        
        return {
            "service": "ragas_integration",
            "available": response.status_code == 200,
            "llm_endpoint": llm_endpoint,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        return {
            "service": "ragas_integration",
            "available": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.get("/metrics")
async def get_metrics():
    """
    Obtiene métricas de evaluaciones realizadas
    Estadísticas de llamadas al mock server
    """
    try:
        import httpx
        
        llm_endpoint = os.getenv("LLM_ENDPOINT", "http://127.0.0.1:8501")
        
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{llm_endpoint}/stats")
        
        if response.status_code == 200:
            stats = response.json()
            return {
                "timestamp": datetime.now().isoformat(),
                "total_calls": stats.get("total_calls", 0),
                "calls_by_metric": stats.get("calls_by_metric", {}),
                "endpoint": llm_endpoint
            }
        else:
            raise HTTPException(status_code=500, detail="Could not reach mock server")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/validate-config")
async def validate_configuration():
    """
    Valida que la configuración sea correcta para RAGAS
    Verifica variables de entorno y dependencias
    """
    checks = {
        "LLM_ENDPOINT": os.getenv("LLM_ENDPOINT", "http://127.0.0.1:8501"),
        "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
        "ragas_installed": _check_ragas_installed(),
        "openai_installed": _check_openai_installed(),
        "datasets_installed": _check_datasets_installed()
    }
    
    try:
        import httpx
        import asyncio
        
        llm_endpoint = checks["LLM_ENDPOINT"]
        
        async def check_mock_server():
            async with httpx.AsyncClient(timeout=5) as client:
                try:
                    response = await client.get(f"{llm_endpoint}/health")
                    return response.status_code == 200
                except:
                    return False
        
        mock_available = asyncio.run(check_mock_server())
        checks["mock_server_available"] = mock_available
    
    except:
        checks["mock_server_available"] = False
    
    all_ok = all([
        checks["OPENAI_API_KEY"],
        checks["ragas_installed"],
        checks["openai_installed"],
        checks["datasets_installed"],
        checks["mock_server_available"]
    ])
    
    return {
        "configured": all_ok,
        "checks": checks,
        "timestamp": datetime.now().isoformat()
    }

def _check_ragas_installed() -> bool:
    """Verifica si RAGAS está instalado"""
    try:
        import ragas
        return True
    except:
        return False

def _check_openai_installed() -> bool:
    """Verifica si OpenAI client está instalado"""
    try:
        import openai
        return True
    except:
        return False

def _check_datasets_installed() -> bool:
    """Verifica si datasets está instalado"""
    try:
        import datasets
        return True
    except:
        return False
