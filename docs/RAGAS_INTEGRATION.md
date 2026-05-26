# Integración Backend + Mock Server + RAGAS

## 1. Arquitectura de Integración

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (React)                  │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│        Backend API (FastAPI) - Puerto 9000           │
│  ┌────────────────────────────────────────────────┐  │
│  │  /api/v1/ragas/evaluate                        │  │
│  │  /api/v1/ragas/evaluate-batch                  │  │
│  │  /api/v1/ragas/status                          │  │
│  │  /api/v1/ragas/health                          │  │
│  │  /api/v1/ragas/metrics                         │  │
│  │  /api/v1/ragas/validate-config                 │  │
│  └────────────┬───────────────────────────────────┘  │
│               │                                        │
│      RAGEvaluationService                             │
│  (ragas_integration.py)                               │
└───────────────┼───────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────┐
│   Mock OpenAI Server - Puerto 8501                   │
│  ┌────────────────────────────────────────────────┐  │
│  │  POST /v1/chat/completions                     │  │
│  │  POST /v1/embeddings                           │  │
│  │  GET /health                                   │  │
│  │  GET /stats                                    │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

## 2. Endpoints de Evaluación RAGAS

### 2.1 Evaluación Individual

**POST /api/v1/ragas/evaluate**

Evalúa una sola instancia de pregunta-contexto-respuesta.

```bash
curl -X POST "http://localhost:9000/api/v1/ragas/evaluate" \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "¿Cuál es el riesgo de diabetes?",
    "retrieved_contexts": [
      "Glucosa en ayunas 130 mg/dL",
      "Índice de masa corporal (BMI) 32"
    ],
    "response": "El paciente presenta riesgo alto de diabetes tipo 2",
    "reference": "Riesgo alto según criterios diagnósticos"
  }'
```

**Response (200 OK):**
```json
{
  "user_input": "¿Cuál es el riesgo de diabetes?",
  "response": "El paciente presenta riesgo alto de diabetes tipo 2",
  "faithfulness": 1.0,
  "answer_relevancy": -0.34,
  "context_precision": 1.0,
  "context_recall": 1.0,
  "timestamp": "2026-05-18T14:30:00.123456"
}
```

**Métricas Explicadas:**
- **faithfulness** (0-1): Fidelidad de la respuesta al contexto. 1.0 = totalmente fiel
- **answer_relevancy** (-1 a 1): Relevancia de respuesta a pregunta. Puede ser negativa si es muy irrelevante
- **context_precision** (0-1): Precisión del contexto recuperado. 1.0 = todo el contexto es relevante
- **context_recall** (0-1): Cobertura del contexto. 1.0 = contexto completo para responder

### 2.2 Evaluación Batch

**POST /api/v1/ragas/evaluate-batch**

Evalúa múltiples instancias en una sola solicitud.

```bash
curl -X POST "http://localhost:9000/api/v1/ragas/evaluate-batch" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "user_input": "¿Cuál es el riesgo de diabetes?",
      "retrieved_contexts": ["Glucosa 130 mg/dL", "BMI 32"],
      "response": "Riesgo alto de diabetes tipo 2",
      "reference": "Riesgo alto"
    },
    {
      "user_input": "¿Cuál es la presión arterial normal?",
      "retrieved_contexts": ["PA normal: <120/80 mmHg"],
      "response": "Presión arterial normal es menor a 120/80 mmHg",
      "reference": "PA normal <120/80"
    }
  ]'
```

**Response (200 OK):**
```json
[
  {
    "user_input": "...",
    "response": "...",
    "faithfulness": 1.0,
    "answer_relevancy": -0.34,
    "context_precision": 1.0,
    "context_recall": 1.0,
    "timestamp": "2026-05-18T14:30:00"
  },
  ...
]
```

### 2.3 Estado del Servicio

**GET /api/v1/ragas/status**

Obtiene el estado de la integración y estadísticas del mock server.

```bash
curl "http://localhost:9000/api/v1/ragas/status"
```

**Response:**
```json
{
  "status": "healthy",
  "llm_endpoint": "http://127.0.0.1:8501",
  "mock_server": true,
  "statistics": {
    "total_calls": 25,
    "calls_by_metric": {
      "response_relevance": 5,
      "context_recall": 5,
      "faithfulness": 5,
      "statement_generator": 10
    }
  }
}
```

### 2.4 Health Check

**GET /api/v1/ragas/health**

Verifica disponibilidad del servicio.

```bash
curl "http://localhost:9000/api/v1/ragas/health"
```

### 2.5 Métricas de Evaluación

**GET /api/v1/ragas/metrics**

Obtiene estadísticas de evaluaciones realizadas.

```bash
curl "http://localhost:9000/api/v1/ragas/metrics"
```

### 2.6 Validar Configuración

**POST /api/v1/ragas/validate-config**

Verifica que todo esté configurado correctamente.

```bash
curl -X POST "http://localhost:9000/api/v1/ragas/validate-config"
```

**Response:**
```json
{
  "configured": true,
  "checks": {
    "LLM_ENDPOINT": "http://127.0.0.1:8501",
    "OPENAI_API_KEY": true,
    "ragas_installed": true,
    "openai_installed": true,
    "datasets_installed": true,
    "mock_server_available": true
  },
  "timestamp": "2026-05-18T14:30:00"
}
```

## 3. Uso desde Cliente Python

```python
import httpx
from typing import List

class RAGSClient:
    def __init__(self, base_url: str = "http://localhost:9000"):
        self.base_url = base_url
        self.client = httpx.Client()
    
    def evaluate(self, user_input: str, contexts: List[str], response: str):
        """Evalúa una sola instancia"""
        data = {
            "user_input": user_input,
            "retrieved_contexts": contexts,
            "response": response,
            "reference": response
        }
        
        result = self.client.post(
            f"{self.base_url}/api/v1/ragas/evaluate",
            json=data
        )
        
        return result.json()
    
    def evaluate_batch(self, evaluations: List[dict]):
        """Evalúa múltiples instancias"""
        result = self.client.post(
            f"{self.base_url}/api/v1/ragas/evaluate-batch",
            json=evaluations
        )
        
        return result.json()
    
    def get_status(self):
        """Obtiene estado del servicio"""
        result = self.client.get(
            f"{self.base_url}/api/v1/ragas/status"
        )
        
        return result.json()

# Uso
client = RAGSClient()

result = client.evaluate(
    user_input="¿Cuál es el riesgo de diabetes?",
    contexts=["Glucosa 130 mg/dL", "BMI 32"],
    response="Riesgo alto de diabetes tipo 2"
)

print(f"Faithfulness: {result['faithfulness']}")
print(f"Answer Relevancy: {result['answer_relevancy']}")
```

## 4. Integración en FastAPI

### 4.1 Uso dentro del Backend

```python
from fastapi import FastAPI, Depends
from app.services import get_rag_service, RAGEvaluationRequest

app = FastAPI()

@app.post("/analyze-response")
async def analyze_response(
    query: str,
    response: str,
    context: str,
    service = Depends(get_rag_service)
):
    """Endpoint que evalúa usando RAGAS"""
    
    evaluation_request = RAGEvaluationRequest(
        user_input=query,
        retrieved_contexts=[context],
        response=response
    )
    
    result = await service.evaluate_single(evaluation_request)
    
    # Usar resultados para tomar decisiones
    if result.faithfulness < 0.7:
        return {"warning": "Low faithfulness", "evaluation": result}
    
    return {"status": "ok", "evaluation": result}
```

### 4.2 Middleware de Evaluación

```python
from starlette.middleware.base import BaseHTTPMiddleware

class RAGEvaluationMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, service):
        super().__init__(app)
        self.service = service
    
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        
        # Evaluar respuestas de ciertos endpoints
        if request.url.path.startswith("/api/v1/clinical"):
            # Guardar respuesta para evaluación
            pass
        
        return response

# Registrar en main.py
from app.services import get_rag_service

service = get_rag_service()
app.add_middleware(RAGEvaluationMiddleware, service=service)
```

## 5. Variables de Entorno Requeridas

```bash
# En .env o docker-compose.yml
LLM_ENDPOINT=http://127.0.0.1:8501  # URL del mock server
OPENAI_API_KEY=local_dummy_key      # Para cliente OpenAI

# Opcionales
RAGAS_LOG_LEVEL=INFO                 # Logging level
RAGAS_CACHE_DIR=/tmp/ragas_cache    # Cache para embeddings
```

## 6. Troubleshooting

### Error: "Connection refused" a Mock Server

```bash
# Verificar que mock server esté corriendo
curl http://127.0.0.1:8501/health

# Si no responde, iniciar con:
python scripts/mock_openai_server.py
```

### Error: "No module named 'ragas'"

```bash
# Instalar dependencias
pip install ragas openai datasets
```

### Evaluaciones lentasls

```python
# Usar caché para embeddings
import os
os.environ["RAGAS_CACHE_DIR"] = "/tmp/ragas_cache"

# O evaluación asíncrona
results = await service.evaluate_batch(requests)
```

### Mock Server no responde como se espera

```bash
# Ver logs del mock server
curl http://127.0.0.1:8501/stats

# Verificar prompts detectados
python scripts/inspect_ragas_metrics.py
```

## 7. Flujo Completo de Integración

1. **Usuario hace solicitud al Backend**
   ```bash
   POST /api/v1/ragas/evaluate
   ```

2. **Backend recibe solicitud**
   - Valida formato del request
   - Crea RAGEvaluationRequest

3. **RAGEvaluationService procesa**
   - Prepara cliente OpenAI con base_url del mock
   - Crea dataset con la información
   - Configura métricas RAGAS

4. **Mock Server responde**
   - Recibe llamadas a /v1/chat/completions
   - Detecta qué métrica se necesita
   - Retorna JSON válido según schema Pydantic

5. **Backend retorna resultado**
   - Parsea respuesta del mock
   - Calcula métricas
   - Retorna RAGEvaluationResult

6. **Frontend muestra resultados**
   - Grafica metrics (faithfulness, relevancy, etc.)
   - Permite tomar decisiones basadas en scores

## 8. Monitoreo

```bash
# Ver todas las evaluaciones
tail -f ragas_results/*.json

# Estadísticas en tiempo real
watch 'curl -s http://localhost:9000/api/v1/ragas/metrics | jq'

# Verificar salud completa
curl -s http://localhost:9000/api/v1/ragas/validate-config | jq
```

---

**Versión:** 1.0  
**Última actualización:** Mayo 18, 2026  
**Estado:** ✓ Operational
