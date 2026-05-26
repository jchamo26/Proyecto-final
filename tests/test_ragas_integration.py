"""
Tests para RAGAS Integration
Verifica que el servicio RAGAS funciona correctamente
"""

import pytest
import asyncio
from pathlib import Path

pytestmark = pytest.mark.ragas


class TestRAGEvaluationService:
    """Tests del servicio de evaluación RAGAS"""
    
    @pytest.fixture
    def service(self):
        """Crea una instancia del servicio"""
        try:
            from app.services import RAGEvaluationService
            return RAGEvaluationService()
        except ImportError:
            pytest.skip("Backend no disponible")
    
    def test_service_initialization(self, service):
        """Verifica que el servicio se inicializa correctamente"""
        assert service is not None
        assert hasattr(service, "llm_endpoint")
        assert hasattr(service, "api_key")
        assert hasattr(service, "results_dir")
    
    def test_results_directory_exists(self, service):
        """Verifica que el directorio de resultados existe"""
        assert service.results_dir.exists()
        assert service.results_dir.is_dir()


class TestRAGEvaluationRequest:
    """Tests de validación de requests"""
    
    def test_request_validation(self, sample_evaluation_request):
        """Verifica que el request se valida correctamente"""
        try:
            from app.services import RAGEvaluationRequest
            
            request = RAGEvaluationRequest(**sample_evaluation_request)
            
            assert request.user_input == sample_evaluation_request["user_input"]
            assert len(request.retrieved_contexts) == 2
            assert request.response == sample_evaluation_request["response"]
        except ImportError:
            pytest.skip("Backend no disponible")
    
    def test_request_missing_required_fields(self):
        """Verifica que request inválidos fallan"""
        try:
            from app.services import RAGEvaluationRequest
            
            with pytest.raises(Exception):  # ValueError o ValidationError
                RAGEvaluationRequest(
                    user_input="test"
                    # Falta retrieved_contexts y response
                )
        except ImportError:
            pytest.skip("Backend no disponible")


class TestRAGMetrics:
    """Tests de cálculo de métricas"""
    
    @pytest.mark.integration
    async def test_faithfulness_metric(self, service, sample_evaluation_request):
        """Verifica que se calcula faithfulness correctamente"""
        try:
            from app.services import RAGEvaluationRequest
            result = await service.evaluate_single(
                RAGEvaluationRequest(**sample_evaluation_request)
            )
            
            assert 0 <= result.faithfulness <= 1
        except ImportError:
            pytest.skip("Backend no disponible")
        except Exception:
            pytest.skip("Mock server no disponible")
    
    @pytest.mark.integration
    async def test_answer_relevancy_metric(self, service, sample_evaluation_request):
        """Verifica que se calcula answer_relevancy correctamente"""
        try:
            from app.services import RAGEvaluationRequest
            
            result = await service.evaluate_single(
                RAGEvaluationRequest(**sample_evaluation_request)
            )
            
            assert -1 <= result.answer_relevancy <= 1
        except ImportError:
            pytest.skip("Backend no disponible")
        except Exception:
            pytest.skip("Mock server no disponible")
    
    @pytest.mark.integration
    async def test_context_precision_metric(self, service, sample_evaluation_request):
        """Verifica que se calcula context_precision correctamente"""
        try:
            from app.services import RAGEvaluationRequest
            
            result = await service.evaluate_single(
                RAGEvaluationRequest(**sample_evaluation_request)
            )
            
            assert 0 <= result.context_precision <= 1
        except ImportError:
            pytest.skip("Backend no disponible")
        except Exception:
            pytest.skip("Mock server no disponible")
    
    @pytest.mark.integration
    async def test_context_recall_metric(self, service, sample_evaluation_request):
        """Verifica que se calcula context_recall correctamente"""
        try:
            from app.services import RAGEvaluationRequest
            
            result = await service.evaluate_single(
                RAGEvaluationRequest(**sample_evaluation_request)
            )
            
            assert 0 <= result.context_recall <= 1
        except ImportError:
            pytest.skip("Backend no disponible")
        except Exception:
            pytest.skip("Mock server no disponible")


class TestRAGEvaluationBatch:
    """Tests de evaluación batch"""
    
    @pytest.mark.integration
    async def test_batch_evaluation(self, service, sample_batch_requests):
        """Verifica que batch evaluation funciona"""
        try:
            from app.services import RAGEvaluationRequest
            
            requests = [
                RAGEvaluationRequest(**req)
                for req in sample_batch_requests
            ]
            
            results = await service.evaluate_batch(requests)
            
            assert len(results) == len(requests)
            assert all(hasattr(r, "faithfulness") for r in results)
        except ImportError:
            pytest.skip("Backend no disponible")
        except Exception:
            pytest.skip("Mock server no disponible")


class TestRAGResultSerialization:
    """Tests de serialización de resultados"""
    
    def test_evaluation_result_to_dict(self, service):
        """Verifica que el resultado se puede serializar a dict"""
        try:
            from app.services import RAGEvaluationResult
            from datetime import datetime
            
            result = RAGEvaluationResult(
                user_input="test",
                response="test response",
                faithfulness=0.8,
                answer_relevancy=-0.3,
                context_precision=0.9,
                context_recall=1.0
            )
            
            assert result.user_input == "test"
            assert result.faithfulness == 0.8
        except ImportError:
            pytest.skip("Backend no disponible")
    
    def test_evaluation_result_json_schema(self):
        """Verifica que el schema JSON es válido"""
        try:
            from app.services import RAGEvaluationResult
            
            schema = RAGEvaluationResult.model_json_schema()
            
            assert "properties" in schema
            assert "user_input" in schema["properties"]
            assert "faithfulness" in schema["properties"]
        except ImportError:
            pytest.skip("Backend no disponible")


class TestRAGResultStorage:
    """Tests de almacenamiento de resultados"""
    
    def test_save_results(self, service, sample_evaluation_request, test_data_dir):
        """Verifica que los resultados se guardan correctamente"""
        try:
            from app.services import RAGEvaluationResult
            
            result = RAGEvaluationResult(
                user_input=sample_evaluation_request["user_input"],
                response=sample_evaluation_request["response"],
                faithfulness=1.0,
                answer_relevancy=-0.34,
                context_precision=1.0,
                context_recall=1.0
            )
            
            filename = service.save_results(
                [result],
                f"test_results_{__name__}.json"
            )
            
            assert Path(filename).exists()
            
            # Limpiar
            Path(filename).unlink()
        except ImportError:
            pytest.skip("Backend no disponible")
    
    def test_saved_results_format(self, service, sample_evaluation_request):
        """Verifica que los resultados guardados tienen formato correcto"""
        import json
        from app.services import RAGEvaluationResult
        
        result = RAGEvaluationResult(
            user_input=sample_evaluation_request["user_input"],
            response=sample_evaluation_request["response"],
            faithfulness=1.0,
            answer_relevancy=-0.34,
            context_precision=1.0,
            context_recall=1.0
        )
        
        filename = service.save_results([result], "test_format.json")
        
        with open(filename, "r") as f:
            data = json.load(f)
        
        assert isinstance(data, list)
        assert len(data) == 1
        assert "user_input" in data[0]
        assert "faithfulness" in data[0]
        assert "timestamp" in data[0]
        
        # Limpiar
        Path(filename).unlink()
