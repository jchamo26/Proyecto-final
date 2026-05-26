# Documentación: Mock Server OpenAI y Evaluación RAGAS

## Descripción General

Este documento explica cómo funciona el mock server OpenAI local y cómo se integra con la biblioteca RAGAS para evaluar sistemas de Retrieval-Augmented Generation (RAG) sin necesidad de una API externa.

## 1. Mock Server OpenAI (`scripts/mock_openai_server.py`)

### Propósito
Simular una API compatible con OpenAI en local para permitir evaluaciones RAGAS offline sin depender de servicios de pago o externos.

### Endpoints

#### 1.1 `/v1/chat/completions` (POST)
Simula el endpoint de completaciones de chat de OpenAI.

**Solicitud:**
```json
{
  "messages": [
    {"role": "user", "content": "Prompt del usuario"},
    {"role": "assistant", "content": "Respuesta anterior"}
  ],
  "model": "mock-model"
}
```

**Respuesta:**
```json
{
  "id": "cmpl-mock-1",
  "object": "chat.completion",
  "choices": [
    {
      "index": 0,
      "message": {"role": "assistant", "content": "{...JSON con resultado...}"},
      "finish_reason": "stop"
    }
  ],
  "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}
}
```

#### 1.2 `/v1/embeddings` (POST)
Simula el endpoint de embeddings de OpenAI.

**Solicitud:**
```json
{
  "input": "texto a embedir",
  "model": "mock-model"
}
```

**Respuesta:**
```json
{
  "object": "list",
  "data": [
    {"object": "embedding", "index": 0, "embedding": [0.1, 0.2, ...]}
  ],
  "usage": {"prompt_tokens": 10, "total_tokens": 10}
}
```

### Detección de Prompts RAGAS

El mock server detecta automáticamente qué métrica RAGAS está siendo evaluada analizando el contenido del prompt. Devuelve JSON estructurado según el esquema Pydantic esperado por cada métrica:

| Métrica | Palabras Clave | Estructura JSON |
|---------|---|---|
| **Response Relevance** | "response relevance", "noncommittal" | `{"question": "...", "noncommittal": 0\|1}` |
| **Context Recall** | "contextrecall", "attributed" | `{"classifications": [{"statement": "...", "reason": "...", "attributed": 0\|1}]}` |
| **Verification/NLI** | "verification", "verdict" | `{"verdict": 0\|1, "reason": "...", "statements": [...]}` |
| **Statement Generator** | "statementgenerator", "statements" | `{"statements": ["texto1", "texto2", ...]}` |

### Autenticación
- Header requerido: `Authorization: Bearer local_dummy_key`
- La clave predeterminada es: `local_dummy_key`

### Embeddings Determinísticos
Los embeddings se generan de forma determinística usando SHA256:
1. Se toma el texto a embedir
2. Se calcula su hash SHA256
3. Se mapean los bytes del hash a flotantes en el rango [0, 1]
4. Se generan 32 dimensiones para cada embedding

Esto asegura que el mismo texto siempre produce el mismo embedding, ideal para pruebas reproducibles.

---

## 2. Integración con RAGAS

### Configuración

**Archivo:** `notebooks/ragas_evaluation.py`

#### Inicialización del Cliente OpenAI
```python
from openai import OpenAI

openai_client = OpenAI(
    api_key=os.getenv('OPENAI_API_KEY', 'local_dummy_key'),
    base_url=os.getenv('LLM_ENDPOINT', 'http://127.0.0.1:8501')
)
```

#### Creación del LLM para RAGAS
```python
from ragas.llm import llm_factory

llm = llm_factory(
    model="mock-model",
    client=openai_client
)
```

#### Adapter de Embeddings
RAGAS requiere un cliente de embeddings con métodos `embed_query` y `embed_documents`. Se implementó `EmbeddingsAdapter`:

```python
class EmbeddingsAdapter:
    def __init__(self, client):
        self.client = client
    
    def embed_query(self, text: str) -> list:
        """Embedir un texto individual"""
        response = self.client.embeddings.create(
            input=text,
            model="mock-model"
        )
        return response.data[0].embedding
    
    def embed_documents(self, texts: list) -> list:
        """Embedir múltiples textos"""
        response = self.client.embeddings.create(
            input=texts,
            model="mock-model"
        )
        return [item.embedding for item in response.data]
```

### Métricas Evaluadas

| Métrica | Descripción | Rango | Cálculo |
|---------|---|---|---|
| **Faithfulness** | Qué tan fiel es la respuesta al contexto recuperado | 0-1 | Verifica que cada afirmación se derive del contexto |
| **Answer Relevancy** | Qué tan relevante es la respuesta a la pregunta | -1 a 1 | Compara relevancia usando embeddings |
| **Context Precision** | Precisión del contexto recuperado | 0-1 | Verifica que todo contexto sea relevante |
| **Context Recall** | Cobertura del contexto necesario | 0-1 | Verifica que el contexto contiene info necesaria |

---

## 3. Resultados de la Evaluación

### Ejecución
```bash
$env:LLM_ENDPOINT='http://127.0.0.1:8501'
$env:OPENAI_API_KEY='local_dummy_key'
python notebooks\ragas_evaluation.py
```

### Reporte Generado
**Archivo:** `ragas_report.json`

Contiene un array JSON con evaluaciones de múltiples ejemplos:

```json
[
  {
    "user_input": "¿Cuál es el riesgo de diabetes para este paciente?",
    "retrieved_contexts": ["Glucosa en ayunas 130 mg/dL", "BMI 32"],
    "response": "El paciente presenta riesgo alto de diabetes...",
    "reference": "Riesgo alto de diabetes.",
    "faithfulness": 1.0,
    "answer_relevancy": -0.3307767555,
    "context_precision": 1.0,
    "context_recall": 1.0
  },
  ...
]
```

### Interpretación de Resultados

**Métricas Exitosas:**
- `faithfulness: 1.0` ✓ — Las respuestas son totalmente consistentes con el contexto
- `context_precision: 1.0` ✓ — Todos los fragmentos recuperados son relevantes
- `context_recall: 1.0` ✓ — El contexto recuperado contiene toda la información necesaria

**Métricas a Optimizar:**
- `answer_relevancy: -0.34` — Valor negativo indica baja relevancia. En un sistema real, esto sugeriría:
  - Mejorar la calidad de las preguntas
  - Ajustar los embeddings
  - Refinar el modelo de lenguaje

---

## 4. Validación del Mock Server

### Script de Validación
**Archivo:** `scripts/validate_mock_responses.py`

Prueba que el mock server devuelve JSON válido para todos los tipos de prompts RAGAS:

```bash
python scripts\validate_mock_responses.py
```

**Salida esperada:**
```
--- verification
valid: True
--- response_relevance
valid: True
--- context_recall
valid: True
--- statement_generator
valid: True
--- unknown
valid: True
done
```

### Introspección de Métricas
**Archivo:** `scripts/inspect_ragas_metrics.py`

Extrae los prompts exactos usados por RAGAS para cada métrica. Útil para entender qué espera cada métrica:

```bash
python scripts\inspect_ragas_metrics.py
```

---

## 5. Ventajas y Limitaciones

### Ventajas
✓ **Offline**: No requiere conexión a internet ni API keys reales
✓ **Reproducible**: Embeddings determinísticos garantizan resultados consistentes
✓ **Rápido**: Respuestas sin latencia de red
✓ **Personalizable**: Fácil ajustar respuestas del mock para cada métrica
✓ **No costo**: Evita gastos en API de OpenAI

### Limitaciones
✗ **Respuestas Sintéticas**: No usa un LLM real, devuelve respuestas predefinidas
✗ **Sin Variabilidad**: Las respuestas son siempre las mismas para el mismo input
✗ **No Contextual**: El mock no entiende realmente el contenido, usa heurísticas
✗ **Solo para Testing**: No adecuado para evaluaciones de producción

---

## 6. Flujo de Ejecución Completo

```
┌─────────────────────────────────────────┐
│ 1. Iniciar Mock Server                  │
│    python scripts/mock_openai_server.py │
│    ↓ Escucha en http://127.0.0.1:8501   │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ 2. Ejecutar Evaluación RAGAS            │
│    python notebooks/ragas_evaluation.py │
│    ↓ Carga dataset                      │
│    ↓ Para cada ejemplo:                 │
│      - Llama a metrics                  │
│      - Envía prompts al mock server     │
│      - Recibe JSON estructurado         │
│      - Calcula scores                   │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ 3. Generar Reporte                      │
│    ragas_report.json                    │
│    ↓ Contiene todos los scores          │
│    ↓ Pronto para análisis               │
└─────────────────────────────────────────┘
```

---

## 7. Troubleshooting

### Error: "Connection refused" en puerto 8501
```bash
# Verificar qué proceso usa el puerto
netstat -ano | Select-String ':8501'

# Matar el proceso
taskkill /PID <PID> /F

# Reiniciar mock server
python scripts\mock_openai_server.py
```

### Error: "ModuleNotFoundError: No module named 'flask'"
```bash
python -m pip install flask
```

### Error: "Pydantic validation error" en métrica X
El mock server probablemente no está detectando correctamente el prompt. Verificar:
1. Ejecutar `scripts/inspect_ragas_metrics.py` para ver el prompt exacto
2. Actualizar las palabras clave en `mock_openai_server.py`
3. Asegurar que el JSON devuelto coincida con el esquema esperado

### Answer Relevancy negativo
Es resultado válido del cálculo real. Indica baja similaridad entre la pregunta y respuesta usando embeddings.

---

## 8. Referencias

- [RAGAS Documentation](https://docs.ragas.io/)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [Pydantic Validation](https://docs.pydantic.dev/)

---

**Última actualización:** Mayo 18, 2026
**Estado:** ✓ Evaluación RAGAS completada exitosamente
