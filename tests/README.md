# Test Suite - Sistema Clínico Inteligente

## Estructura de Tests

```
tests/
├── __init__.py
├── conftest.py              # Configuración y fixtures de pytest
├── test_mock_server.py      # Tests del mock OpenAI server
├── test_ragas_integration.py # Tests del servicio RAGAS
├── test_backend_api.py      # Tests de endpoints del backend
└── data/                    # Datos de prueba
```

## Instalación de Dependencias

```bash
# Tests
pip install pytest pytest-asyncio pytest-cov httpx

# Adicionales
pip install pytest-xdist  # Ejecución paralela
pip install pytest-timeout  # Timeout de tests
```

## Ejecutar Tests

### Todos los tests

```bash
pytest tests/
```

### Tests específicos

```bash
# Solo mock server
pytest tests/test_mock_server.py -v

# Solo RAGAS
pytest tests/test_ragas_integration.py -v

# Solo backend
pytest tests/test_backend_api.py -v
```

### Por marcador

```bash
# Tests de integración (requieren servicios corriendo)
pytest -m integration

# Tests lentos
pytest -m slow

# Tests sin lentos
pytest -m "not slow"

# Tests de mock server
pytest -m mock_server

# Tests de RAGAS
pytest -m ragas

# Tests de backend
pytest -m backend
```

### Con cobertura

```bash
pytest tests/ --cov=app --cov=scripts --cov-report=html
# Abre htmlcov/index.html para ver resultados
```

### Ejecución paralela

```bash
pytest tests/ -n auto  # Usa todos los cores
pytest tests/ -n 4     # Usa 4 workers
```

### Con timeout

```bash
pytest tests/ --timeout=30  # Timeout de 30s por test
```

## Configuración Pre-Requisitos

Antes de ejecutar tests de integración, asegúrate de que:

### 1. Mock Server está corriendo

```bash
python scripts/mock_openai_server.py &
# O en otra terminal:
python start_system.py --mode mock
```

### 2. Backend está corriendo (para tests de API)

```bash
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 9000 &
# O:
python start_system.py
```

### 3. Variables de entorno configuradas

```bash
export OPENAI_API_KEY="local_dummy_key"
export LLM_ENDPOINT="http://127.0.0.1:8501"
```

## Tipos de Tests

### Tests de Mock Server (`test_mock_server.py`)

- **Health Check**: Verifica endpoints de healthz
- **Stats**: Verifica que se registran estadísticas
- **Embeddings**: Verifica generación de embeddings
  - Determinismo (mismo input = mismo output)
  - Batch processing
  - Formato de respuesta
- **Chat Completions**: Verifica respuestas LLM
  - Formato correcto
  - Multi-generación (n > 1)
  - Parámetros aceptados (temperature, etc.)
- **Metric Detection**: Verifica que se detectan tipos de métricas
- **Error Handling**: Verifica manejo de errores
- **Concurrency**: Verifica múltiples solicitudes simultáneas

### Tests de RAGAS (`test_ragas_integration.py`)

- **Service Init**: Verifica inicialización del servicio
- **Request Validation**: Valida estructura de requests
- **Metric Calculation**: Verifica cálculo de métricas
  - Faithfulness (0-1)
  - Answer Relevancy (-1 a 1)
  - Context Precision (0-1)
  - Context Recall (0-1)
- **Batch Evaluation**: Evalúa múltiples instancias
- **Result Serialization**: Verifica serialización JSON
- **Result Storage**: Verifica guardado a archivo

### Tests de Backend API (`test_backend_api.py`)

- **Endpoint Availability**: Verifica que existen endpoints
- **Valid Data Processing**: Procesa datos correctos
- **Error Handling**: Rechaza datos inválidos
- **Integration Flow**: Flujo completo de evaluación
- **Performance**: Respuesta en tiempo
- **Concurrency**: Múltiples solicitudes
- **Documentation**: OpenAPI docs disponible

## Fixtures Disponibles

Definidas en `conftest.py`:

```python
@pytest.fixture
def sample_evaluation_request():
    """Solicitud simple de evaluación"""
    return {
        "user_input": "¿Cuál es el riesgo de diabetes?",
        "retrieved_contexts": ["Glucosa 130 mg/dL", "BMI 32"],
        "response": "Riesgo alto de diabetes tipo 2",
        "reference": "Riesgo alto"
    }

@pytest.fixture
def sample_batch_requests():
    """Batch de 3 solicitudes"""
    return [...]

@pytest.fixture
def mock_server_url():
    """URL del mock server: http://127.0.0.1:8501"""
    return "http://127.0.0.1:8501"

@pytest.fixture
def backend_url():
    """URL del backend: http://127.0.0.1:9000"""
    return "http://127.0.0.1:9000"
```

## Ejemplos de Ejecución

### Ejecutar solo tests no-lentos

```bash
pytest tests/ -m "not slow" -v
```

### Ejecutar mock server tests con salida detallada

```bash
pytest tests/test_mock_server.py -v --tb=short
```

### Ejecutar tests de integración (requieren servicios)

```bash
# Necesita mock server + backend corriendo
pytest -m integration -v --timeout=60
```

### Generar reporte de cobertura HTML

```bash
pytest tests/ --cov --cov-report=html
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

## Debugging Tests

### Ver output de test

```bash
pytest tests/test_mock_server.py::TestMockServerHealth::test_health_endpoint -s
```

### Ver variables en failure

```bash
pytest tests/ -vv  # Extra verbose
```

### Pausar en error

```bash
pytest tests/ --pdb  # Abre debugger en error
pytest tests/ --pdbcls=IPython.terminal.debugger:TerminalPygmentsDebugger  # Con IPython
```

### Ejecutar solo un test

```bash
pytest tests/test_mock_server.py::TestMockServerHealth::test_health_endpoint
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt pytest pytest-cov
      - run: pytest tests/ --cov --cov-report=xml
      - uses: codecov/codecov-action@v2
```

## Mantenimiento de Tests

### Agregar nuevo test

```python
# tests/test_new_feature.py
import pytest

@pytest.mark.new_feature
def test_my_feature():
    """Descripción del test"""
    assert True
```

### Saltarse un test temporalmente

```python
@pytest.mark.skip(reason="En desarrollo")
def test_incomplete():
    pass

@pytest.mark.skipif(sys.version_info < (3, 12), reason="Requiere Python 3.12+")
def test_new_feature():
    pass
```

### Marcar test como esperado fallar

```python
@pytest.mark.xfail(reason="Bug conocido")
def test_known_bug():
    pass
```

## Métricas de Cobertura

Objetivo: >80% cobertura

```
tests/test_mock_server.py      - 100% (todos los endpoints)
tests/test_ragas_integration.py - 85% (métodos del servicio)
tests/test_backend_api.py       - 90% (endpoints API)
```

## Solución de Problemas

### "Connection refused"

Mock server o backend no está corriendo. Inicia con:
```bash
python start_system.py
```

### "No module named 'app'"

Asegúrate de estar en la raíz del proyecto:
```bash
cd /ruta/a/ProyectoFinal_SSD
pytest tests/
```

### Tests timeout

Aumenta el timeout:
```bash
pytest tests/ --timeout=120  # 2 minutos
```

### Memory issues con test suite

Ejecuta con menos workers:
```bash
pytest tests/ -n 2
```

---

**Última actualización:** Mayo 18, 2026  
**Python:** 3.12+  
**Pytest:** 7.0+  
**Estado:** ✓ Ready for CI/CD
