# Scripts de Evaluación RAGAS

Directorio con scripts auxiliares para ejecutar y validar el sistema de evaluación RAGAS.

## Descripción de Scripts

### `run_evaluation.py` ⭐ RECOMENDADO
**Propósito:** Ejecutor principal que inicia mock server y evaluación automáticamente.

**Uso:**
```bash
python run_evaluation.py
```

**Características:**
- ✓ Valida sistema antes de ejecutar
- ✓ Inicia mock server automáticamente
- ✓ Ejecuta evaluación RAGAS
- ✓ Manejo limpio de procesos
- ✓ Detalle de resultados

---

### `mock_openai_server.py`
**Propósito:** Servidor Flask que simula OpenAI API de forma local.

**Uso:**
```bash
python mock_openai_server.py
```

**Endpoints:**
- `POST /v1/chat/completions` — LLM chat completions
- `POST /v1/embeddings` — Generación de embeddings determinísticos
- `GET /v1/models` — Listar modelos disponibles
- `GET /health` — Health check
- `GET /stats` — Estadísticas de llamadas

**Variables de Entorno:**
```powershell
$env:OPENAI_API_KEY='local_dummy_key'     # API key requerida
$env:MOCK_PORT='8501'                     # Puerto (default: 8501)
$env:MOCK_HOST='127.0.0.1'                # Host (default: 127.0.0.1)
$env:MOCK_LOG_LEVEL='INFO'                # Nivel de logging (default: INFO)
```

**Características:**
- ✓ Detección automática de métricas RAGAS
- ✓ Embeddings determinísticos (SHA256)
- ✓ Soporte multi-generación (n_completions)
- ✓ Logging detallado
- ✓ Estadísticas de llamadas
- ✓ Error handling robusto

---

### `validate_system.py`
**Propósito:** Valida que todos los componentes estén correctamente instalados.

**Uso:**
```bash
python validate_system.py
```

**Validaciones:**
1. ✓ RAGAS instalado (v0.4.3+)
2. ✓ Cliente OpenAI funcionando
3. ✓ Notebooks presentes
4. ✓ Mock server implementado
5. ✓ Reportes generados
6. ✓ Documentación completa

**Salida:** Resumen de PASS/FAIL/NEUTRAL para cada componente

---

### `validate_mock_responses.py`
**Propósito:** Verifica que el mock server devuelve JSON válido para cada tipo de métrica.

**Uso:**
```bash
python validate_mock_responses.py
```

**Pruebas:**
- ✓ Verification (NLI output)
- ✓ Response Relevance
- ✓ Context Recall
- ✓ Statement Generator
- ✓ Fallback (desconocido)

**Salida:** Para cada test, muestra el JSON crudo, parseado y si es válido

---

### `inspect_ragas_metrics.py`
**Propósito:** Extrae y muestra los prompts exactos usados por RAGAS para cada métrica.

**Uso:**
```bash
python inspect_ragas_metrics.py
```

**Información extraída:**
- Prompts de cada métrica
- Ejemplos de salida esperada
- Estructura Pydantic de cada modelo

**Útil para:** Entender qué espera cada métrica y ajustar el mock server

---

### `benchmark_inference.py`
**Propósito:** Medir latencia real de inferencia en servicios ML y DL.

**Uso:**
```bash
python benchmark_inference.py
```

**Salida:** promedio, p95, mínimo y máximo en milisegundos para cada servicio.
Además genera `docs/inference_latency_report.json` (incluye errores si un servicio no está disponible).

---

### `rubric_readiness_check.py`
**Propósito:** Generar un reporte rápido de preparación de rúbrica (seguridad + RAG).

**Uso:**
```bash
python rubric_readiness_check.py
```

**Salida:**
- JSON en consola
- Archivo `docs/rubric_readiness_report.json`

---

### `verify_cloudflare.py`
**Propósito:** Verificar DNS proxied, modo SSL, reglas WAF y rate limits en Cloudflare.

**Uso:**
```bash
set CLOUDFLARE_API_TOKEN=<token>
set CLOUDFLARE_ZONE_ID=<zone_id>
python verify_cloudflare.py
```

**Salida:**
- JSON en consola
- Archivo `docs/cloudflare_verification.json`

---

### `verify_public_deployment.py`
**Propósito:** Verificar disponibilidad publica por HTTPS, salud del backend y agente, y datos del certificado TLS.

**Uso:**
```bash
python verify_public_deployment.py https://tu-dominio.com
```

**Salida:**
- JSON en consola
- Archivo `docs/public_deployment_verification.json`

---

### `generate_evidence_bundle.py`
**Propósito:** Ejecutar en cadena validaciones clave y consolidar artefactos de evidencia en un solo resumen.

**Uso:**
```bash
python generate_evidence_bundle.py
```

**Salida:**
- `docs/evidence_bundle_summary.json`
- Referencias a `rubric_readiness_report.json`, `inference_latency_report.json` y otros artefactos.

---

## Flujo de Ejecución Recomendado

### 1. Validar Sistema
```bash
python validate_system.py
```
Verifica que todas las dependencias estén instaladas.

### 2. Ejecutar Evaluación (Opción A: Integrada)
```bash
python run_evaluation.py
```
Ejecuta todo automáticamente.

### 3. Ejecutar Evaluación (Opción B: Manual)
```bash
# Terminal 1
$env:OPENAI_API_KEY='local_dummy_key'
python mock_openai_server.py

# Terminal 2
$env:LLM_ENDPOINT='http://127.0.0.1:8501'
$env:OPENAI_API_KEY='local_dummy_key'
python ../notebooks/ragas_evaluation.py
```

### 4. Validar Resultados
```bash
# Verificar JSON del mock
python validate_mock_responses.py

# Ver estadísticas
Invoke-RestMethod -Uri 'http://127.0.0.1:8501/stats'

# Inspeccionar prompts (opcional)
python inspect_ragas_metrics.py
```

---

## Troubleshooting

### Error: "Module not found"
```bash
pip install flask openai ragas datasets
```

### Error: "Port already in use"
```powershell
# Encontrar proceso
netstat -ano | Select-String ':8501'

# Matar proceso
taskkill /PID <PID> /F
```

### Error: "Connection refused"
Asegurar que mock server está corriendo en Terminal 1

### Error: "Pydantic validation error"
Ejecutar `python validate_mock_responses.py` para diagnosticar

---

## Configuración

### Archivo `.env.mock.example`
Ejemplo de configuración del mock server. Copiar y renombrar a `.env.local`.

```bash
cp .env.mock.example .env.local
```

---

## Salidas Esperadas

### `ragas_report.json`
```json
[
  {
    "user_input": "¿Cuál es el diagnóstico?",
    "retrieved_contexts": ["Síntoma 1", "Síntoma 2"],
    "response": "El diagnóstico es...",
    "reference": "Referencia del diagnóstico",
    "faithfulness": 1.0,
    "answer_relevancy": -0.34,
    "context_precision": 1.0,
    "context_recall": 1.0
  }
]
```

### Mock Server Stats
```json
{
  "total_calls": 32,
  "calls_by_metric": {
    "response_relevance": 8,
    "context_recall": 8,
    "verification": 8,
    "statement_generator": 8
  }
}
```

---

## Referencias

- Documentación técnica: `../docs/mock_server_y_ragas.md`
- Guía de ejecución: `../docs/GUIA_EJECUCION.md`
- Notebook: `../notebooks/ragas_evaluation.py`

---

**Versión:** 1.0  
**Última actualización:** Mayo 18, 2026  
**Estado:** ✓ Operacional
