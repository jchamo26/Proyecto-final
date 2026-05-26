# Checklist Final de Entrega

## Estado de reconstrucción (Mayo 2026)
- [x] Rate limiting implementado en backend y agente (SlowAPI)
- [x] Hash de contraseñas SuperUser con bcrypt (12 rounds)
- [x] Dataset RAGAS ampliado a 20+ preguntas clínicas
- [x] Motor de recuperación RAG con estrategias bm25, dense, hybrid y multi_query
- [x] Script de benchmark de inferencia (`scripts/benchmark_inference.py`)
- [x] Script de verificación rápida de rúbrica (`scripts/rubric_readiness_check.py`)

## Infraestructura y despliegue
- [ ] Sistema desplegado en VPS público con URL HTTPS accesible
- [ ] Cloudflare configurado como proxy activo (DNS naranja)
- [ ] SSL/TLS Full Strict en Cloudflare y Nginx
- [ ] `docker-compose.yml` funcional levanta todos los servicios
- [ ] PostgreSQL con volúmenes Docker nombrados
- [ ] Variables sensibles en `.env.example` sin valores reales
- [ ] Redis desplegado para memoria del agente
- [ ] README con instrucciones de despliegue

## FHIR e interoperabilidad
- [ ] HAPI FHIR R4 con PostgreSQL backend operativo
- [ ] Recursos Patient, Observation, DiagnosticReport, RiskAssessment implementados
- [ ] API SuperUser con JWT y endpoints documentados
- [ ] Soft delete implementado (`active: false`)
- [ ] Versioning habilitado en HAPI (`_history`)
- [ ] Probado con al menos 1 sistema externo
- [ ] AuditEvent registrado para accesos externos

## Modelos ML / DL
- [ ] Modelo tabular en ONNX INT8 con F1 ≥ 0.75
- [ ] Modelo imagen en ONNX INT8 con F1 ≥ 0.75
- [ ] Calibración isotónica aplicada
- [ ] Resultados vinculados a DiagnosticReport FHIR y RiskAssessment
- [ ] MLflow tracking con métricas y artefactos
- [ ] Latencia de inferencia documentada

## Agente RAG
- [ ] ≥3 tipos de RAG implementados
- [ ] ≥20 documentos clínicos indexados
- [ ] Búsqueda híbrida BM25 + dense
- [ ] Memoria de sesión funcional
- [ ] Memoria histórica por paciente en PostgreSQL
- [ ] Tool query_fhir funcional
- [ ] Tool invoke_ml_model funcional
- [ ] RAGAS evaluado con ≥20 preguntas
- [ ] Faithfulness RAGAS ≥ 0.75

## Seguridad
- [ ] WAF Cloudflare con reglas anti-prompt injection
- [ ] Rate limiting en `/agent/*` y `/superuser/*`
- [ ] Cifrado AES-256/Fernet de documento de identidad en DB
- [ ] Contraseñas con bcrypt factor ≥ 12
- [ ] Tokens y API keys en variables de entorno
- [ ] Middleware anti-injection en FastAPI
- [ ] Output filtering de PII en respuestas del agente
- [ ] Pruebas adversariales documentadas

## Entregables documentales
- [ ] Repositorio GitHub público con commits de todos los integrantes
- [ ] Reporte RAGAS incluido
- [ ] Documento técnico PDF o MD
- [ ] Capturas de evidencia de cifrado
- [ ] Colección Postman / OpenAPI completa
