# Evidencia de Entrega Final (Objetivo >= 4.5)

Esta guia centraliza la evidencia que debe adjuntarse para maximizar la nota de rubrica.

## Ejecucion rapida (un solo comando)

```powershell
python scripts\generate_evidence_bundle.py
```

Esto actualiza:
- `docs/rubric_readiness_report.json`
- `docs/inference_latency_report.json`
- `docs/evidence_bundle_summary.json`

## 1. Infraestructura y Nube

1. Captura del VPS publico con dominio resolviendo por HTTPS.
2. Salida de verificacion publica:
   - `python scripts/verify_public_deployment.py https://tu-dominio.com`
   - Guardar `docs/public_deployment_verification.json`.
3. Evidencia Docker:
   - `docker compose ps`
   - `docker compose logs --tail=100 nginx backend agent`

## 2. Cloudflare y Seguridad Perimetral

1. Ejecutar:
   - `set CLOUDFLARE_API_TOKEN=<token>`
   - `set CLOUDFLARE_ZONE_ID=<zone_id>`
   - `python scripts/verify_cloudflare.py`
2. Adjuntar `docs/cloudflare_verification.json`.
3. Capturas en panel Cloudflare:
   - DNS proxied (nube naranja)
   - SSL/TLS mode = Full (Strict)
   - WAF rules activas
   - Rate limiting rules

## 3. FHIR e Interoperabilidad

1. Pruebas de endpoints SuperUser y FHIR con Postman.
2. Registrar evidencia de:
   - Patient, Observation, DiagnosticReport, RiskAssessment
   - Soft delete y `_history`
   - AuditEvent generado
3. Adjuntar export de coleccion y respuestas exitosas.

## 4. Modelos ML/DL

1. Ejecutar benchmark:
   - `python scripts/benchmark_inference.py`
2. Guardar evidencia de latencia (avg/p95) para ML y DL.
3. Adjuntar metricas de entrenamiento (F1/AUC) y export ONNX INT8.
4. Adjuntar evidencia de trazabilidad en MLflow (runs, metrics, artifacts).

## 5. Agente RAG y RAGAS

1. Verificar readiness:
   - `python scripts/rubric_readiness_check.py`
2. Ejecutar evaluacion RAGAS:
   - `python scripts/run_evaluation.py`
3. Adjuntar:
   - `ragas_report.json`
   - evidencia de Faithfulness >= 0.75
   - evidencia de estrategias RAG (bm25, dense, hybrid/multi_query)

## 6. Calidad y Documentacion

1. Revisar que no haya secretos reales en ejemplos.
2. Confirmar README y docs de despliegue actualizados.
3. Adjuntar documento tecnico final y capturas de cifrado en DB.

## Criterios criticos para >=4.5

- VPS publico funcional + Cloudflare Full Strict demostrado.
- RAGAS con 20+ preguntas y faithfulness >= 0.75 (ideal >=0.80).
- Rate limiting activo + anti-injection + cifrado PII.
- Evidencia medible de ML/DL: F1/AUC y latencia real.
- Entregables completos con pruebas reproducibles.

## Estado local actual (Mayo 2026)

- Readiness tecnico interno: cumple (`ready_minimum_targets: true`).
- Benchmark de inferencia: script funcional, pero servicios ML/DL apagados localmente al momento del reporte.
- Validacion general: PASS con dependencias RAGAS/OpenAI marcadas como NEUTRAL en este entorno Python 3.14.
