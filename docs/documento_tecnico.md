# Documento Técnico — Sistema Clínico Inteligente

## 1. Introducción
Este documento describe la arquitectura, las decisiones de diseño y el cumplimiento normativo del Proyecto Final Integrador de Salud Digital 2026-1.

## 2. Arquitectura
La solución está compuesta por los siguientes módulos:
- Frontend SPA servido por Nginx
- Backend FastAPI con endpoints de SuperUser
- HAPI FHIR R4 para recursos Patient, Observation, DiagnosticReport y RiskAssessment
- Microservicio de agente RAG
- Microservicios ML/DL en ONNX INT8
- Almacenamiento de objetos en MinIO
- Seguimiento de experimentos con MLflow
- Redis para memoria de sesión del agente

### 2.1 Cloudflare y seguridad
- Cloudflare como proxy inverso y WAF
- SSL/TLS Full Strict obligatorio
- Regla de rate limiting: 60 req/min en `/agent/*` y `/api/v1/superuser/*`
- Bot Fight Mode activado
- Protección contra prompt injection en el backend
- Output filtering para PII (cédula, email, teléfono)

## 3. Interoperabilidad HL7 FHIR R4
Se implementa una API SuperUser que permite:
- Autenticación JWT para médicos externos
- Búsqueda de pacientes por identificador
- Creación de pacientes en formato FHIR
- Consulta y creación de Observations
- Invocación de inferencias ML con resultado persistido en FHIR
- Soft delete de pacientes con justificación clínica

## 4. Modelos ML y DL
- Modelo tabular en ONNX con quantización INT8 y calibración isotónica
- Modelo de imagen en ONNX INT8 con inferencia en microservicio separado
- Métricas de aprobación: F1 ≥ 0.75, AUC ≥ 0.80
- Bonificación: F1/AUC ≥ 0.85 en ambos modelos

## 5. Agente RAG clínico
Capacidades implementadas:
- Memoria de sesión (corto plazo)
- Memoria histórica por paciente (largo plazo)
- Base de conocimiento RAG con documentos clínicos
- Acceso a FHIR mediante API
- Invocación de servicios ML/DL como herramientas
- Generación y persistencia de `RiskAssessment` y `DiagnosticReport` en FHIR
- Endpoints: `/agent/query`, `/agent/memory/session/{session_id}`, `/agent/memory/summary/{patient_id}`, `/agent/tools/*`
- Soporte de modelos locales ONNX mediante `TABULAR_MODEL_PATH` y `IMAGE_MODEL_PATH`
- Evaluación RAGAS con métricas de faithfulness y relevancia

## 6. Seguridad adicional
- Cifrado AES-256/Fernet en base de datos para PII
- Contraseñas con bcrypt
- Tokens y credenciales en variables de entorno
- Middleware anti-prompt injection en FastAPI

## 7. Despliegue en nube
Docker Compose levanta todos los servicios necesarios. La infraestructura de nube pública debe contener:
- VPS con Nginx y Docker Compose
- IP pública oculta tras Cloudflare
- Volúmenes Docker nombrados para PostgreSQL, MinIO, Redis y MLflow

## 8. Cumplimiento regulatorio
- Resolución 866/2021: FHIR R4 interoperabilidad
- Ley 1581/2012: protección de datos personales y cifrado
- Resolución 1995/1999: soft delete y conservación de registros
- Ley 2015/2020: historia clínica electrónica interoperable

## 9. Evidencia requerida
- Capturas de pantalla de datos cifrados en PostgreSQL
- Logs de SSL/TLS Full Strict
- Resultados de RAGAS
- Archivo `docker-compose.yml` y `.env.example`

## 10. Conclusiones
Este proyecto entrega una arquitectura integrada, desplegable en nube y compatible con los requerimientos del curso, con énfasis en interoperabilidad, seguridad y agentes inteligentes.
