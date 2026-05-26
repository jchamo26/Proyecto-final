# Proyecto Final Integrador — Sistema Clínico Inteligente

## Resumen del proyecto
Sistema clínico integrado desplegado en nube pública con:
- Interoperabilidad HL7 FHIR R4
- API SuperUser para médicos externos
- Modelos ML/DL ONNX INT8 calibrados
- Agente RAG clínico inteligente
- Seguridad Cloudflare + cifrado AES-256
- Despliegue Docker Compose en VPS

## Arquitectura Objetivo
- Cloudflare WAF + proxy
- Nginx reverse proxy + TLS
- Frontend SPA (React/Vue/Svelte)
- Backend FastAPI
- HAPI FHIR R4 con PostgreSQL
- Agente RAG con memoria y herramientas
- Microservicios ML/DL con ONNX Runtime
- MinIO para almacenamiento de artefactos
- MLflow tracking
- Redis para memoria temporal
- Mailhog para pruebas de correo

## Requisitos cubiertos
1. Interoperabilidad HL7 FHIR R4
2. API SuperUser (médico)
3. Soft delete y versioning de recursos
4. Modelos ML y DL ONNX INT8 calibrados
5. Agente RAG con memoria corta y larga
6. Seguridad Cloudflare + anti prompt injection
7. Cifrado AES-256 de datos sensibles
8. Despliegue en nube con Docker Compose

## Entregables incluidos
- `README.md`
- `docker-compose.yml`
- `.env.example`
- Backend FastAPI con endpoints de SuperUser
- Agente RAG esqueleto de microservicio
- Microservicios ML/DL esqueleto
- `docs/documento_tecnico.md`
- `docs/checklist_final.md`
- `notebooks/ragas_evaluation.py`
- `postman_collection.json`

## Uso rápido
1. Copiar `.env.example` a `.env` y completar variables.
2. Instalar dependencias del frontend:
   - `cd frontend`
   - `npm install`
3. Generar la aplicación React:
   - `npm run build`
4. Volver al root del proyecto y levantar la arquitectura:
   - `cd ..`
   - `docker compose up -d --build`
5. Acceder al frontend SPA en `http://localhost` o `https://tu-dominio.com`.
6. Acceder al backend en `http://localhost:8000`.
7. Acceder a HAPI FHIR en `http://localhost:8080/hapi-fhir-jpaserver`.
8. Utilizar los endpoints de SuperUser en `/api/v1/superuser/`.

## Endpoints SuperUser
- `POST /api/v1/auth/superuser/login`
- `GET /api/v1/superuser/patients`
- `POST /api/v1/superuser/patients`
- `GET /api/v1/superuser/patients/{patient_id}/observations`
- `POST /api/v1/superuser/patients/{patient_id}/observations`
- `POST /api/v1/superuser/inference/{model_type}`
- `DELETE /api/v1/superuser/patients/{patient_id}`

## Endpoints ML / DL
- `POST http://localhost:8100/infer` (ML tabular)
- `POST http://localhost:8200/infer` (DL imagen)

## Endpoints Agente RAG
- `POST /agent/query`
- `GET /agent/memory/session/{session_id}`
- `GET /agent/memory/summary/{patient_id}`
- `POST /agent/tools/fhir/query`
- `POST /agent/tools/ml/infer`
- `POST /agent/tools/fhir/report`
- `POST /agent/retrieval/search`
- `GET /agent/retrieval/stats`

### Estrategias RAG implementadas
- `bm25` (recuperación léxica)
- `dense` (similitud vectorial hash-embedding)
- `hybrid` (BM25 + dense con `alpha=0.6` por defecto)
- `multi_query` (expansión de consulta + fusión híbrida)

El corpus clínico embebido incluye 22 documentos temáticos para evaluación local.

## Notas de seguridad
- Middleware de anti-prompt injection con patrones personalizados.
- Output filtering PII para correo, teléfono y cédula.
- Cifrado transparente AES-256/Fernet en SQLAlchemy.
- Rate limiting activo en `/agent/*` y `/api/v1/superuser/*`.
- Contraseñas de SuperUser con `bcrypt` (12 rounds).
- Uso obligatorio de Cloudflare Full Strict en producción.

## Documentación adicional
- `docs/documento_tecnico.md`
- `docs/checklist_final.md`
- `docs/EVIDENCIA_ENTREGA.md`
- `postman_collection.json`

## Verificación para entrega

```powershell
# Readiness técnico interno
python scripts\rubric_readiness_check.py

# Verificación pública HTTPS (VPS + certificado)
python scripts\verify_public_deployment.py https://tu-dominio.com

# Verificación Cloudflare (requiere token y zone id)
$env:CLOUDFLARE_API_TOKEN='tu_token'
$env:CLOUDFLARE_ZONE_ID='tu_zone_id'
python scripts\verify_cloudflare.py
```

---

## Evaluación RAGAS del Sistema RAG

### Descripción
El sistema incluye un módulo de evaluación RAGAS (RAG Assessment) que valida la calidad del agente RAG clínico sin depender de APIs externas.

### Características
- ✓ Mock server OpenAI compatible local
- ✓ Métricas RAGAS: Faithfulness, Answer Relevancy, Context Precision, Context Recall
- ✓ Embeddings determinísticos para reproducibilidad
- ✓ Evaluación offline sin costo de API
- ✓ Logging detallado y estadísticas de llamadas

### Ejecución Rápida

**Opción 1: Ejecución integrada (recomendado)**
```powershell
python scripts\run_evaluation.py
```

**Opción 2: Manual (dos terminales)**
```powershell
# Terminal 1: Iniciar mock server
$env:OPENAI_API_KEY='local_dummy_key'
python scripts\mock_openai_server.py

# Terminal 2: Ejecutar evaluación
$env:LLM_ENDPOINT='http://127.0.0.1:8501'
$env:OPENAI_API_KEY='local_dummy_key'
python notebooks\ragas_evaluation.py
```

### Resultados
Genera `ragas_report.json` con métricas de evaluación para cada ejemplo.
El dataset de evaluación incluido en `notebooks/ragas_evaluation.py` contiene 20+ preguntas clínicas.

### Documentación
- `docs/mock_server_y_ragas.md` — Documentación técnica completa
- `docs/GUIA_EJECUCION.md` — Guía paso a paso
- `scripts/validate_system.py` — Validador del sistema

### Scripts Auxiliares
```powershell
# Validar sistema
python scripts\validate_system.py

# Validar respuestas del mock
python scripts\validate_mock_responses.py

# Inspeccionar métricas RAGAS
python scripts\inspect_ragas_metrics.py

# Ver estadísticas del mock server
Invoke-RestMethod -Uri 'http://127.0.0.1:8501/stats'
```

---

## Arquitectura detallada
Ver `docs/documento_tecnico.md` para la arquitectura completa y la justificación regulatoria.
