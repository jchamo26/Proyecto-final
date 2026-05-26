"""
Configuración de pytest y fixtures compartidas
"""

import pytest
import sys
import os
from pathlib import Path

# Agregar proyecto al path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(PROJECT_ROOT / "agent"))

# Variables de entorno de test
os.environ["OPENAI_API_KEY"] = "test_key"
os.environ["LLM_ENDPOINT"] = "http://127.0.0.1:8501"
os.environ["SECRET_KEY"] = "test_secret_key"
os.environ["FERNET_KEY"] = "R2pUXBafZ5-Xtqw3RlIscgDSwIT9WsoBUKIYr0MBtRc="


@pytest.fixture(scope="session")
def test_data_dir():
    """Directorio para datos de prueba"""
    test_dir = PROJECT_ROOT / "tests" / "data"
    test_dir.mkdir(exist_ok=True)
    return test_dir


@pytest.fixture
def sample_evaluation_request():
    """Solicitud de evaluación de ejemplo"""
    return {
        "user_input": "¿Cuál es el riesgo de diabetes?",
        "retrieved_contexts": [
            "Glucosa en ayunas 130 mg/dL",
            "Índice de masa corporal (BMI) 32"
        ],
        "response": "El paciente presenta riesgo alto de diabetes tipo 2",
        "reference": "Riesgo alto según criterios diagnósticos"
    }


@pytest.fixture
def sample_batch_requests():
    """Batch de solicitudes de evaluación"""
    return [
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
        },
        {
            "user_input": "¿Qué vitaminas son importantes?",
            "retrieved_contexts": ["Vitamina D, B12, Ácido fólico"],
            "response": "Las vitaminas importantes son D, B12 y ácido fólico",
            "reference": "Vitaminas esenciales"
        }
    ]


@pytest.fixture
def mock_server_url():
    """URL del mock server"""
    return "http://127.0.0.1:8501"


@pytest.fixture
def backend_url():
    """URL del backend"""
    return "http://127.0.0.1:9100"


@pytest.fixture
def service():
    """Fixture para crear el servicio de evaluación RAGAS si está disponible."""
    try:
        from app.services import RAGEvaluationService
        return RAGEvaluationService()
    except ImportError:
        pytest.skip("Backend no disponible")


# Markers personalizados
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: marcar test como integration test"
    )
    config.addinivalue_line(
        "markers", "slow: marcar test como lento"
    )
    config.addinivalue_line(
        "markers", "mock_server: pruebas de mock server"
    )
    config.addinivalue_line(
        "markers", "ragas: pruebas de RAGAS"
    )
    config.addinivalue_line(
        "markers", "backend: pruebas de backend"
    )
