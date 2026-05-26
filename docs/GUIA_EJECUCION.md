# RAGAS Evaluation System - Guía de Ejecución

Este documento explica cómo ejecutar el sistema completo de evaluación RAGAS con el mock server OpenAI local.

## Requisitos Previos

- Python 3.12+
- Dependencias instaladas: `flask`, `openai`, `ragas`, `datasets`
- Sistema operativo: Windows, Linux, o macOS

## 1. Instalación de Dependencias

```bash
# Instalar paquetes requeridos
pip install flask openai ragas datasets
```

## 2. Estructura del Proyecto

```
ProyectoFinal_SSD/
├── scripts/
│   ├── mock_openai_server.py        # Servidor mock OpenAI
│   ├── validate_system.py           # Script de validación del sistema
│   ├── validate_mock_responses.py   # Validador de respuestas del mock
│   └── inspect_ragas_metrics.py     # Inspector de métricas RAGAS
├── notebooks/
│   └── ragas_evaluation.py          # Notebook de evaluación RAGAS
├── docs/
│   ├── mock_server_y_ragas.md       # Documentación completa
│   └── GUIA_EJECUCION.md           # Este archivo
└── ragas_report.json               # Reporte generado (salida)
```

## 3. Pasos de Ejecución

### Opción A: Ejecución Rápida (Recomendado)

#### En PowerShell (Windows):

```powershell
# Terminal 1: Iniciar Mock Server
cd 'c:\Users\JOSE ANGEL CHAMORRO\Desktop\ProyectoFinal_SSD\ProyectoFinal_SSD'
$env:OPENAI_API_KEY='local_dummy_key'
python scripts\mock_openai_server.py
# Esperada: "Running on http://127.0.0.1:8501"

# Terminal 2: Ejecutar Evaluación RAGAS
cd 'c:\Users\JOSE ANGEL CHAMORRO\Desktop\ProyectoFinal_SSD\ProyectoFinal_SSD'
$env:LLM_ENDPOINT='http://127.0.0.1:8501'
$env:OPENAI_API_KEY='local_dummy_key'
python notebooks\ragas_evaluation.py
# Esperado: "Evaluating: 100%|████████████| 8/8 [...]"
```

#### En Bash (Linux/macOS):

```bash
# Terminal 1: Iniciar Mock Server
cd ~/ProyectoFinal_SSD/ProyectoFinal_SSD
export OPENAI_API_KEY='local_dummy_key'
python scripts/mock_openai_server.py

# Terminal 2: Ejecutar Evaluación RAGAS
cd ~/ProyectoFinal_SSD/ProyectoFinal_SSD
export LLM_ENDPOINT='http://127.0.0.1:8501'
export OPENAI_API_KEY='local_dummy_key'
python notebooks/ragas_evaluation.py
```

### Opción B: Con Validación Previa

```powershell
# Terminal 1: Validar sistema antes de ejecutar
python scripts\validate_system.py

# Si todo pasa, continuar con pasos de la Opción A
```

## 4. Salidas Esperadas

### Mock Server (Terminal 1)
```
[2026-05-18 14:30:00,123] mock_openai_server - INFO - Iniciando Mock OpenAI Server en 127.0.0.1:8501
[2026-05-18 14:30:00,234] mock_openai_server - INFO - Endpoints disponibles:
[2026-05-18 14:30:00,234] mock_openai_server - INFO -   - POST /v1/chat/completions (LLM completions)
[2026-05-18 14:30:00,234] mock_openai_server - INFO -   - POST /v1/embeddings (Embeddings determinísticos)
[2026-05-18 14:30:00,234] mock_openai_server - INFO -   - GET /v1/models (Listar modelos)
[2026-05-18 14:30:00,234] mock_openai_server - INFO -   - GET /health (Health check)
[2026-05-18 14:30:00,234] mock_openai_server - INFO -   - GET /stats (Estadísticas de llamadas)
 * Running on http://127.0.0.1:8501
```

### Evaluación RAGAS (Terminal 2)
```
Evaluating:   0%|                                        | 0/8 [00:00<?, ?it/s]
LLM returned 1 generations instead of requested 3. Proceeding with 1 generations.
LLM returned 1 generations instead of requested 3. Proceeding with 1 generations.
Evaluating: 100%|████████████████████████████████| 8/8 [00:00<00:00, 14.26it/s]
{'faithfulness': 1.0000, 'answer_relevancy': -0.3409, 'context_precision': 1.0000, 'context_recall': 1.0000}
```

### Archivo Generado: `ragas_report.json`
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

## 5. Verificación del Sistema

### Ver Estadísticas del Mock Server

```powershell
# En PowerShell
Invoke-RestMethod -Uri 'http://127.0.0.1:8501/stats' | ConvertTo-Json

# Salida esperada:
# {
#   "total_calls": 32,
#   "calls_by_metric": {
#     "response_relevance": 8,
#     "context_recall": 8,
#     "verification": 8,
#     "statement_generator": 8
#   }
# }
```

### Health Check del Mock Server

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8501/health'

# Salida esperada:
# {
#   "status": "healthy",
#   "service": "mock-openai-server"
# }
```

## 6. Configuración Avanzada

### Variables de Entorno del Mock Server

```powershell
$env:OPENAI_API_KEY = 'local_dummy_key'   # API key (requerida)
$env:MOCK_PORT = '8501'                   # Puerto (default: 8501)
$env:MOCK_HOST = '127.0.0.1'              # Host (default: 127.0.0.1)
$env:MOCK_LOG_LEVEL = 'DEBUG'             # Nivel de log (default: INFO)
```

### Variables de Entorno de Evaluación

```powershell
$env:LLM_ENDPOINT = 'http://127.0.0.1:8501'   # Endpoint del LLM
$env:OPENAI_API_KEY = 'local_dummy_key'       # API key
```

## 7. Troubleshooting

### Problema: "Connection refused" en puerto 8501

**Solución:**
```powershell
# Verificar qué proceso usa el puerto
netstat -ano | Select-String ':8501'

# Matar el proceso (reemplazar PID)
taskkill /PID <PID> /F

# Reiniciar mock server
python scripts\mock_openai_server.py
```

### Problema: "ModuleNotFoundError"

**Solución:**
```powershell
# Instalar dependencia faltante
pip install flask
pip install openai
pip install ragas
```

### Problema: Reporte vacío o con valores NaN

**Soluciones:**
1. Verificar que el mock server está corriendo
2. Verificar logs del mock server
3. Ejecutar `python scripts\validate_mock_responses.py`
4. Revisar `docs/mock_server_y_ragas.md` sección Troubleshooting

### Problema: "Answer Relevancy" negativo

Este es un resultado válido del cálculo de RAGAS. Indica baja similaridad entre pregunta y respuesta usando embeddings. No es un error.

## 8. Scripts Auxiliares

### validate_system.py
Valida que todos los componentes están correctamente instalados y configurados.

```powershell
python scripts\validate_system.py
```

### validate_mock_responses.py
Prueba que el mock server devuelve JSON válido para todos los tipos de prompts RAGAS.

```powershell
python scripts\validate_mock_responses.py
```

### inspect_ragas_metrics.py
Extrae los prompts exactos usados por cada métrica RAGAS.

```powershell
python scripts\inspect_ragas_metrics.py
```

## 9. Próximos Pasos

1. **Integración con Backend**: Conectar evaluaciones RAGAS al endpoint del backend
2. **Persistencia**: Guardar resultados en base de datos
3. **API REST**: Exponer evaluaciones a través de API
4. **Dashboard**: Crear visualización de métricas
5. **LLM Real**: Integrar con modelo real de lenguaje en producción

## 10. Referencias

- [RAGAS Documentation](https://docs.ragas.io/)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [Flask Documentation](https://flask.palletsprojects.com/)
- Documento: `docs/mock_server_y_ragas.md`

---

**Versión:** 1.0  
**Última actualización:** Mayo 18, 2026  
**Estado:** ✓ Sistema funcional y validado
