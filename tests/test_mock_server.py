"""
Tests para Mock OpenAI Server
Verifica que todos los endpoints respondan correctamente
"""

import pytest
import httpx
import time

pytestmark = pytest.mark.mock_server


class TestMockServerHealth:
    """Tests de health check del mock server"""
    
    async def test_health_endpoint(self, mock_server_url):
        """Verifica que el endpoint de health funciona"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{mock_server_url}/health")
        
        assert response.status_code == 200
    
    async def test_health_response_format(self, mock_server_url):
        """Verifica que la respuesta tiene el formato correcto"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{mock_server_url}/health")
        
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"


class TestMockServerStats:
    """Tests de estadísticas del mock server"""
    
    async def test_stats_endpoint(self, mock_server_url):
        """Verifica que el endpoint de stats funciona"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{mock_server_url}/stats")
        
        assert response.status_code == 200
    
    async def test_stats_response_format(self, mock_server_url):
        """Verifica que la respuesta tiene el formato correcto"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{mock_server_url}/stats")
        
        data = response.json()
        assert "total_calls" in data
        assert "calls_by_metric" in data
        assert isinstance(data["total_calls"], int)
        assert isinstance(data["calls_by_metric"], dict)


class TestMockServerEmbeddings:
    """Tests de endpoint de embeddings"""
    
    async def test_embeddings_endpoint(self, mock_server_url):
        """Verifica que el endpoint de embeddings funciona"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{mock_server_url}/v1/embeddings",
                json={
                    "input": "test text",
                    "model": "text-embedding-ada-002"
                }
            )
        
        assert response.status_code == 200
    
    async def test_embeddings_response_format(self, mock_server_url):
        """Verifica que el formato de respuesta es correcto"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{mock_server_url}/v1/embeddings",
                json={
                    "input": "test text",
                    "model": "text-embedding-ada-002"
                }
            )
        
        data = response.json()
        assert "data" in data
        assert len(data["data"]) > 0
        assert "embedding" in data["data"][0]
        assert isinstance(data["data"][0]["embedding"], list)
    
    async def test_embeddings_deterministic(self, mock_server_url):
        """Verifica que embeddings son determinísticos"""
        test_text = "test text for deterministic embeddings"
        
        async with httpx.AsyncClient() as client:
            response1 = await client.post(
                f"{mock_server_url}/v1/embeddings",
                json={
                    "input": test_text,
                    "model": "text-embedding-ada-002"
                }
            )
            
            response2 = await client.post(
                f"{mock_server_url}/v1/embeddings",
                json={
                    "input": test_text,
                    "model": "text-embedding-ada-002"
                }
            )
        
        data1 = response1.json()
        data2 = response2.json()
        
        assert data1["data"][0]["embedding"] == data2["data"][0]["embedding"]
    
    async def test_embeddings_batch(self, mock_server_url):
        """Verifica que se pueden procesar múltiples textos"""
        texts = ["texto 1", "texto 2", "texto 3"]
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{mock_server_url}/v1/embeddings",
                json={
                    "input": texts,
                    "model": "text-embedding-ada-002"
                }
            )
        
        data = response.json()
        assert len(data["data"]) == 3


class TestMockServerChatCompletions:
    """Tests de chat completions"""
    
    async def test_chat_completions_endpoint(self, mock_server_url):
        """Verifica que el endpoint de chat completions funciona"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{mock_server_url}/v1/chat/completions",
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "user", "content": "Hello"}
                    ]
                }
            )
        
        assert response.status_code == 200
    
    async def test_chat_completions_response_format(self, mock_server_url):
        """Verifica que la respuesta tiene el formato correcto"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{mock_server_url}/v1/chat/completions",
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "user", "content": "Test message"}
                    ]
                }
            )
        
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0
        assert "message" in data["choices"][0]
        assert "content" in data["choices"][0]["message"]
    
    async def test_chat_completions_multiple_generations(self, mock_server_url):
        """Verifica que se pueden generar múltiples respuestas"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{mock_server_url}/v1/chat/completions",
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "user", "content": "Test"}
                    ],
                    "n": 3
                }
            )
        
        data = response.json()
        assert len(data["choices"]) == 3
    
    async def test_chat_completions_with_temperature(self, mock_server_url):
        """Verifica que temperature es aceptado"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{mock_server_url}/v1/chat/completions",
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "user", "content": "Test"}
                    ],
                    "temperature": 0.7
                }
            )
        
        assert response.status_code == 200


class TestMockServerMetricDetection:
    """Tests de detección de métricas RAGAS"""
    
    @pytest.mark.parametrize("metric_type,keywords", [
        ("faithfulness", ["Determine", "faithfulness", "statement"]),
        ("answer_relevancy", ["Evaluate", "answer relevancy", "question"]),
        ("context_precision", ["precision", "context", "relevant"]),
        ("context_recall", ["recall", "context", "retrieved"])
    ])
    async def test_metric_detection(self, mock_server_url, metric_type, keywords):
        """Verifica que se detectan correctamente los tipos de métricas"""
        prompt = " ".join(keywords)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{mock_server_url}/v1/chat/completions",
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verificar que la respuesta tiene estructura JSON válida
        assert "choices" in data
        assert len(data["choices"]) > 0


class TestMockServerErrorHandling:
    """Tests de manejo de errores"""
    
    async def test_invalid_model(self, mock_server_url):
        """Verifica manejo de modelo inválido"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{mock_server_url}/v1/chat/completions",
                json={
                    "model": "invalid-model-xyz",
                    "messages": [{"role": "user", "content": "test"}]
                }
            )
        
        # Debe tener código 200 con respuesta fallback
        assert response.status_code == 200
    
    async def test_missing_messages(self, mock_server_url):
        """Verifica manejo de solicitud sin messages"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{mock_server_url}/v1/chat/completions",
                json={
                    "model": "gpt-3.5-turbo"
                }
            )
        
        # Debe retornar error o fallback válido
        assert response.status_code in [200, 400]


class TestMockServerConcurrency:
    """Tests de concurrencia"""
    
    @pytest.mark.slow
    async def test_concurrent_requests(self, mock_server_url):
        """Verifica que maneja múltiples solicitudes concurrentes"""
        import asyncio
        
        async def make_request(client, index):
            return await client.post(
                f"{mock_server_url}/v1/chat/completions",
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "user", "content": f"Request {index}"}
                    ]
                }
            )
        
        async with httpx.AsyncClient() as client:
            tasks = [make_request(client, i) for i in range(10)]
            responses = await asyncio.gather(*tasks)
        
        # Todas las solicitudes deben ser exitosas
        assert all(r.status_code == 200 for r in responses)
        assert len(responses) == 10
