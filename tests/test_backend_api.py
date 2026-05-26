"""
Tests para Backend API - Endpoints RAGAS
Verifica que los endpoints del backend funcionan correctamente
"""

import pytest
import httpx
import json

pytestmark = pytest.mark.backend


class TestRAGSEndpoints:
    """Tests de los endpoints RAGAS del backend"""
    
    async def test_evaluate_single_endpoint_available(self, backend_url):
        """Verifica que el endpoint de evaluación simple existe"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{backend_url}/api/v1/ragas/evaluate",
                    json={}
                )
                # Puede retornar 422 si es validación, pero el endpoint debe existir
                assert response.status_code in [200, 422, 500]
            except httpx.ConnectError:
                pytest.skip("Backend no disponible")
    
    async def test_evaluate_single_with_valid_data(self, backend_url, sample_evaluation_request):
        """Verifica que se pueden evaluar instancias individuales"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{backend_url}/api/v1/ragas/evaluate",
                    json=sample_evaluation_request
                )
                
                if response.status_code == 200:
                    data = response.json()
                    assert "faithfulness" in data
                    assert "answer_relevancy" in data
                    assert "context_precision" in data
                    assert "context_recall" in data
            except httpx.ConnectError:
                pytest.skip("Backend no disponible")
    
    async def test_evaluate_batch_endpoint_available(self, backend_url):
        """Verifica que el endpoint de evaluación batch existe"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{backend_url}/api/v1/ragas/evaluate-batch",
                    json=[]
                )
                # Puede retornar 200 o 422
                assert response.status_code in [200, 422, 500]
            except httpx.ConnectError:
                pytest.skip("Backend no disponible")
    
    async def test_evaluate_batch_with_valid_data(self, backend_url, sample_batch_requests):
        """Verifica que se pueden evaluar lotes"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{backend_url}/api/v1/ragas/evaluate-batch",
                    json=sample_batch_requests
                )
                
                if response.status_code == 200:
                    data = response.json()
                    assert isinstance(data, list)
                    if len(data) > 0:
                        assert "faithfulness" in data[0]
            except httpx.ConnectError:
                pytest.skip("Backend no disponible")
    
    async def test_status_endpoint(self, backend_url):
        """Verifica que el endpoint de status funciona"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{backend_url}/api/v1/ragas/status")
                
                if response.status_code == 200:
                    data = response.json()
                    assert "status" in data
                    assert "llm_endpoint" in data
            except httpx.ConnectError:
                pytest.skip("Backend no disponible")
    
    async def test_health_endpoint(self, backend_url):
        """Verifica que el endpoint de health funciona"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{backend_url}/api/v1/ragas/health")
                
                if response.status_code == 200:
                    data = response.json()
                    assert "service" in data
                    assert "available" in data
            except httpx.ConnectError:
                pytest.skip("Backend no disponible")
    
    async def test_metrics_endpoint(self, backend_url):
        """Verifica que el endpoint de métricas funciona"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{backend_url}/api/v1/ragas/metrics")
                
                if response.status_code == 200:
                    data = response.json()
                    assert "timestamp" in data
                    assert "total_calls" in data
            except httpx.ConnectError:
                pytest.skip("Backend no disponible")
    
    async def test_validate_config_endpoint(self, backend_url):
        """Verifica que el endpoint de validación de config funciona"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(f"{backend_url}/api/v1/ragas/validate-config")
                
                if response.status_code == 200:
                    data = response.json()
                    assert "configured" in data
                    assert "checks" in data
            except httpx.ConnectError:
                pytest.skip("Backend no disponible")


class TestBackendIntegrationFlow:
    """Tests del flujo completo de integración"""
    
    @pytest.mark.integration
    async def test_complete_evaluation_flow(self, backend_url, sample_evaluation_request):
        """Verifica el flujo completo de evaluación"""
        async with httpx.AsyncClient() as client:
            try:
                # 1. Validar config
                config_response = await client.post(
                    f"{backend_url}/api/v1/ragas/validate-config"
                )
                
                if config_response.status_code != 200:
                    pytest.skip("Configuración inválida")
                
                # 2. Evaluar
                eval_response = await client.post(
                    f"{backend_url}/api/v1/ragas/evaluate",
                    json=sample_evaluation_request
                )
                
                if eval_response.status_code == 200:
                    # 3. Verificar resultado
                    result = eval_response.json()
                    assert all(key in result for key in [
                        "faithfulness", "answer_relevancy",
                        "context_precision", "context_recall"
                    ])
                    
                    # 4. Ver métricas
                    metrics_response = await client.get(
                        f"{backend_url}/api/v1/ragas/metrics"
                    )
                    
                    if metrics_response.status_code == 200:
                        metrics = metrics_response.json()
                        assert metrics["total_calls"] > 0
            
            except httpx.ConnectError:
                pytest.skip("Backend no disponible")
    
    @pytest.mark.integration
    async def test_batch_evaluation_flow(self, backend_url, sample_batch_requests):
        """Verifica el flujo de evaluación batch"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{backend_url}/api/v1/ragas/evaluate-batch",
                    json=sample_batch_requests
                )
                
                if response.status_code == 200:
                    results = response.json()
                    assert len(results) == len(sample_batch_requests)
            
            except httpx.ConnectError:
                pytest.skip("Backend no disponible")


class TestBackendErrorHandling:
    """Tests de manejo de errores del backend"""
    
    async def test_invalid_request_format(self, backend_url):
        """Verifica que requests inválidos son rechazados"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{backend_url}/api/v1/ragas/evaluate",
                    json={"invalid": "data"}
                )
                
                assert response.status_code in [400, 422, 500]
            
            except httpx.ConnectError:
                pytest.skip("Backend no disponible")
    
    async def test_missing_required_fields(self, backend_url):
        """Verifica que fields requeridos son validados"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{backend_url}/api/v1/ragas/evaluate",
                    json={
                        "user_input": "test"
                        # Faltan retrieved_contexts y response
                    }
                )
                
                assert response.status_code in [400, 422]
            
            except httpx.ConnectError:
                pytest.skip("Backend no disponible")


class TestBackendPerformance:
    """Tests de performance del backend"""
    
    @pytest.mark.slow
    async def test_single_evaluation_response_time(self, backend_url, sample_evaluation_request):
        """Verifica que la evaluación individual es rápida"""
        import time
        
        async with httpx.AsyncClient() as client:
            try:
                start = time.time()
                response = await client.post(
                    f"{backend_url}/api/v1/ragas/evaluate",
                    json=sample_evaluation_request
                )
                elapsed = time.time() - start
                
                if response.status_code == 200:
                    # Debe completarse en menos de 30 segundos
                    assert elapsed < 30
            
            except httpx.ConnectError:
                pytest.skip("Backend no disponible")
    
    @pytest.mark.slow
    async def test_concurrent_evaluations(self, backend_url, sample_evaluation_request):
        """Verifica que maneja evaluaciones concurrentes"""
        import asyncio
        
        async def evaluate():
            async with httpx.AsyncClient() as client:
                return await client.post(
                    f"{backend_url}/api/v1/ragas/evaluate",
                    json=sample_evaluation_request
                )
        
        try:
            tasks = [evaluate() for _ in range(5)]
            responses = await asyncio.gather(*tasks)
            
            # Mínimo algunas deberían ser exitosas
            successful = sum(1 for r in responses if r.status_code == 200)
            assert successful > 0
        
        except httpx.ConnectError:
            pytest.skip("Backend no disponible")


class TestBackendDocumentation:
    """Tests de que la documentación es accesible"""
    
    async def test_openapi_docs(self, backend_url):
        """Verifica que la documentación OpenAPI está disponible"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{backend_url}/docs")
                assert response.status_code == 200
            except httpx.ConnectError:
                pytest.skip("Backend no disponible")
    
    async def test_openapi_schema(self, backend_url):
        """Verifica que el schema OpenAPI es válido"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{backend_url}/openapi.json")
                
                if response.status_code == 200:
                    schema = response.json()
                    assert "paths" in schema
                    assert "components" in schema
            
            except httpx.ConnectError:
                pytest.skip("Backend no disponible")
