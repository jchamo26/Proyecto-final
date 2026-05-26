"""
Módulo de Integración: Backend + Mock Server + RAGAS
Permite que el backend ejecute evaluaciones RAGAS usando el mock server OpenAI local
"""

import os
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import json
import asyncio
from pathlib import Path

class RAGEvaluationRequest(BaseModel):
    """Solicitud de evaluación RAGAS"""
    user_input: str = Field(..., description="Pregunta del usuario")
    retrieved_contexts: List[str] = Field(..., description="Contexto recuperado")
    response: str = Field(..., description="Respuesta generada")
    reference: Optional[str] = Field(None, description="Referencia/Verdad base")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_input": "¿Cuál es el riesgo de diabetes?",
                "retrieved_contexts": ["Glucosa en ayunas 130 mg/dL", "BMI 32"],
                "response": "El paciente presenta riesgo alto de diabetes",
                "reference": "Riesgo alto según criterios"
            }
        }

class RAGEvaluationResult(BaseModel):
    """Resultado de evaluación RAGAS"""
    user_input: str
    response: str
    faithfulness: float = Field(..., ge=0, le=1)
    answer_relevancy: float = Field(..., ge=-1, le=1)
    context_precision: float = Field(..., ge=0, le=1)
    context_recall: float = Field(..., ge=0, le=1)
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_input": "¿Cuál es el riesgo?",
                "response": "Riesgo alto...",
                "faithfulness": 1.0,
                "answer_relevancy": -0.34,
                "context_precision": 1.0,
                "context_recall": 1.0,
                "timestamp": "2026-05-18T14:30:00"
            }
        }

class RAGEvaluationService:
    """Servicio de evaluación RAGAS"""
    
    def __init__(self):
        self.llm_endpoint = os.getenv("LLM_ENDPOINT", "http://127.0.0.1:8501")
        self.api_key = os.getenv("OPENAI_API_KEY", "local_dummy_key")
        self.results_dir = Path("ragas_results")
        self.results_dir.mkdir(exist_ok=True)
    
    async def evaluate_single(self, request: RAGEvaluationRequest) -> RAGEvaluationResult:
        """Evalúa una sola instancia"""
        try:
            from openai import OpenAI
            from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
            from ragas.llm import llm_factory
            from datasets import Dataset
            
            # Crear cliente OpenAI
            client = OpenAI(
                api_key=self.api_key,
                base_url=self.llm_endpoint
            )
            
            # Crear LLM
            llm = llm_factory(model="mock-model", client=client)
            
            # Crear adapter para embeddings
            class EmbeddingsAdapter:
                def __init__(self, client):
                    self.client = client
                
                def embed_query(self, text: str) -> list:
                    response = self.client.embeddings.create(
                        input=text,
                        model="mock-model"
                    )
                    return response.data[0].embedding
                
                def embed_documents(self, texts: list) -> list:
                    response = self.client.embeddings.create(
                        input=texts,
                        model="mock-model"
                    )
                    return [item.embedding for item in response.data]
            
            embeddings = EmbeddingsAdapter(client)
            
            # Crear dataset
            dataset = Dataset.from_dict({
                "question": [request.user_input],
                "contexts": [request.retrieved_contexts],
                "answer": [request.response],
                "ground_truth": [request.reference or request.response]
            })
            
            # Configurar métricas
            for metric in [faithfulness, answer_relevancy, context_precision, context_recall]:
                metric.llm = llm
                metric.embeddings = embeddings
            
            # Evaluar
            scores = await asyncio.to_thread(
                self._evaluate_dataset,
                dataset,
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall
            )
            
            # Crear resultado
            result = RAGEvaluationResult(
                user_input=request.user_input,
                response=request.response,
                faithfulness=scores.get("faithfulness", 0.0),
                answer_relevancy=scores.get("answer_relevancy", 0.0),
                context_precision=scores.get("context_precision", 0.0),
                context_recall=scores.get("context_recall", 0.0)
            )
            
            return result
            
        except Exception as e:
            raise ValueError(f"Error en evaluación RAGAS: {str(e)}")
    
    def _evaluate_dataset(self, dataset, *metrics):
        """Evalúa dataset (síncrono)"""
        from ragas import evaluate
        
        eval_metrics = list(metrics)
        result = evaluate(dataset, metrics=eval_metrics)
        
        return {
            "faithfulness": result["faithfulness"][0],
            "answer_relevancy": result["answer_relevancy"][0],
            "context_precision": result["context_precision"][0],
            "context_recall": result["context_recall"][0]
        }
    
    async def evaluate_batch(self, requests: List[RAGEvaluationRequest]) -> List[RAGEvaluationResult]:
        """Evalúa múltiples instancias"""
        results = []
        for request in requests:
            try:
                result = await self.evaluate_single(request)
                results.append(result)
            except Exception as e:
                print(f"Error evaluando: {str(e)}")
                continue
        
        return results
    
    def save_results(self, results: List[RAGEvaluationResult], filename: Optional[str] = None):
        """Guarda resultados en archivo"""
        if not filename:
            filename = f"ragas_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        filepath = self.results_dir / filename
        
        data = [
            {
                "user_input": r.user_input,
                "response": r.response,
                "faithfulness": r.faithfulness,
                "answer_relevancy": r.answer_relevancy,
                "context_precision": r.context_precision,
                "context_recall": r.context_recall,
                "timestamp": r.timestamp.isoformat()
            }
            for r in results
        ]
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return str(filepath)

# Instancia singleton
_service_instance: Optional[RAGEvaluationService] = None

def get_rag_service() -> RAGEvaluationService:
    """Obtiene instancia del servicio RAGAS"""
    global _service_instance
    if _service_instance is None:
        _service_instance = RAGEvaluationService()
    return _service_instance
