"""
Optimización de Componentes - Caching, Connection Pooling, Performance
Mejora de performance del sistema completo
"""

import os
from typing import Any, Callable, Optional, Dict, List
from functools import wraps, lru_cache
from datetime import datetime, timedelta
import json
import hashlib
import asyncio
from pathlib import Path
import httpx

class CacheManager:
    """Gestor centralizado de cache"""
    
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.memory_cache: Dict[str, Any] = {}
        self.cache_timestamps: Dict[str, datetime] = {}
    
    def _hash_key(self, key: str) -> str:
        """Genera hash para la clave de cache"""
        return hashlib.sha256(key.encode()).hexdigest()
    
    def get(self, key: str, ttl_seconds: int = 3600) -> Optional[Any]:
        """Obtiene valor del cache"""
        # Primero buscar en memory cache
        if key in self.memory_cache:
            timestamp = self.cache_timestamps.get(key)
            if timestamp and (datetime.now() - timestamp).total_seconds() < ttl_seconds:
                return self.memory_cache[key]
            else:
                del self.memory_cache[key]
                del self.cache_timestamps[key]
        
        # Luego en disco
        cache_file = self.cache_dir / f"{self._hash_key(key)}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    data = json.load(f)
                    timestamp = datetime.fromisoformat(data["timestamp"])
                    if (datetime.now() - timestamp).total_seconds() < ttl_seconds:
                        return data["value"]
                    else:
                        cache_file.unlink()
            except Exception:
                pass
        
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Guarda valor en cache"""
        # Memory cache
        self.memory_cache[key] = value
        self.cache_timestamps[key] = datetime.now()
        
        # Disk cache
        cache_file = self.cache_dir / f"{self._hash_key(key)}.json"
        try:
            with open(cache_file, "w") as f:
                json.dump({
                    "value": value,
                    "timestamp": datetime.now().isoformat()
                }, f)
        except Exception:
            pass
    
    def clear(self, key: Optional[str] = None) -> None:
        """Limpia cache"""
        if key:
            if key in self.memory_cache:
                del self.memory_cache[key]
            cache_file = self.cache_dir / f"{self._hash_key(key)}.json"
            if cache_file.exists():
                cache_file.unlink()
        else:
            self.memory_cache.clear()
            self.cache_timestamps.clear()
            for f in self.cache_dir.glob("*.json"):
                f.unlink()
    
    def clear_expired(self, ttl_seconds: int = 3600) -> int:
        """Limpia entries expirados"""
        expired = 0
        now = datetime.now()
        
        # Memory cache
        for key, timestamp in list(self.cache_timestamps.items()):
            if (now - timestamp).total_seconds() > ttl_seconds:
                del self.memory_cache[key]
                del self.cache_timestamps[key]
                expired += 1
        
        return expired


class ConnectionPool:
    """Pool de conexiones HTTP reutilizables"""
    
    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self.client: Optional[httpx.AsyncClient] = None
        self.semaphore = asyncio.Semaphore(max_connections)
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(limits=httpx.Limits(max_connections=self.max_connections))
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def get(self, url: str, **kwargs) -> httpx.Response:
        """GET request con límite de conexiones"""
        async with self.semaphore:
            if not self.client:
                raise RuntimeError("ConnectionPool no inicializado")
            return await self.client.get(url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> httpx.Response:
        """POST request con límite de conexiones"""
        async with self.semaphore:
            if not self.client:
                raise RuntimeError("ConnectionPool no inicializado")
            return await self.client.post(url, **kwargs)


class EmbeddingCache:
    """Cache especializado para embeddings"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
    
    def get_embedding(self, text: str) -> Optional[List[float]]:
        """Obtiene embedding del cache"""
        key = f"embedding:{hashlib.sha256(text.encode()).hexdigest()}"
        return self.cache.get(key, ttl_seconds=86400)  # 24h TTL para embeddings
    
    def cache_embedding(self, text: str, embedding: List[float]) -> None:
        """Cachea un embedding"""
        key = f"embedding:{hashlib.sha256(text.encode()).hexdigest()}"
        self.cache.set(key, embedding)
    
    def batch_cache(self, texts: List[str], embeddings: List[List[float]]) -> None:
        """Cachea múltiples embeddings"""
        for text, embedding in zip(texts, embeddings):
            self.cache_embedding(text, embedding)


class PerformanceOptimizer:
    """Optimizador de performance para evaluaciones RAGAS"""
    
    def __init__(self):
        self.cache = CacheManager()
        self.embedding_cache = EmbeddingCache(self.cache)
        self.stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "total_requests": 0,
            "avg_response_time": 0.0
        }
    
    async def optimize_embeddings(
        self,
        texts: List[str],
        embedding_fn: Callable,
        use_cache: bool = True
    ) -> List[List[float]]:
        """Optimiza obtención de embeddings con cache"""
        
        embeddings = []
        uncached_texts = []
        uncached_indices = []
        
        # Buscar en cache
        for i, text in enumerate(texts):
            if use_cache:
                cached = self.embedding_cache.get_embedding(text)
                if cached is not None:
                    embeddings.append(cached)
                    self.stats["cache_hits"] += 1
                    continue
            
            embeddings.append(None)
            uncached_texts.append(text)
            uncached_indices.append(i)
            self.stats["cache_misses"] += 1
        
        # Obtener embeddings no cacheados
        if uncached_texts:
            new_embeddings = await embedding_fn(uncached_texts)
            
            # Guardar en cache
            if use_cache:
                self.embedding_cache.batch_cache(uncached_texts, new_embeddings)
            
            # Incorporar al resultado
            for idx, embedding in zip(uncached_indices, new_embeddings):
                embeddings[idx] = embedding
        
        self.stats["total_requests"] += 1
        return embeddings
    
    async def optimize_llm_calls(
        self,
        prompts: List[str],
        llm_fn: Callable,
        use_cache: bool = True,
        ttl_seconds: int = 3600
    ) -> List[str]:
        """Optimiza llamadas a LLM con cache"""
        
        results = []
        uncached_prompts = []
        uncached_indices = []
        
        # Buscar en cache
        for i, prompt in enumerate(prompts):
            cache_key = f"llm:{hashlib.sha256(prompt.encode()).hexdigest()}"
            
            if use_cache:
                cached = self.cache.get(cache_key, ttl_seconds=ttl_seconds)
                if cached is not None:
                    results.append(cached)
                    self.stats["cache_hits"] += 1
                    continue
            
            results.append(None)
            uncached_prompts.append(prompt)
            uncached_indices.append(i)
            self.stats["cache_misses"] += 1
        
        # Obtener respuestas no cacheadas
        if uncached_prompts:
            new_results = await llm_fn(uncached_prompts)
            
            # Guardar en cache
            for prompt, result in zip(uncached_prompts, new_results):
                cache_key = f"llm:{hashlib.sha256(prompt.encode()).hexdigest()}"
                self.cache.set(cache_key, result)
            
            # Incorporar al resultado
            for idx, result in zip(uncached_indices, new_results):
                results[idx] = result
        
        self.stats["total_requests"] += 1
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de optimización"""
        total = self.stats["cache_hits"] + self.stats["cache_misses"]
        hit_rate = (self.stats["cache_hits"] / total * 100) if total > 0 else 0
        
        return {
            "cache_hits": self.stats["cache_hits"],
            "cache_misses": self.stats["cache_misses"],
            "hit_rate": f"{hit_rate:.2f}%",
            "total_requests": self.stats["total_requests"]
        }


def cached(ttl_seconds: int = 3600):
    """Decorator para cachear resultados de función"""
    cache_manager = CacheManager()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Crear clave única basada en función, args y kwargs
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            cache_key = hashlib.sha256(key.encode()).hexdigest()
            
            # Buscar en cache
            result = cache_manager.get(cache_key, ttl_seconds=ttl_seconds)
            if result is not None:
                return result
            
            # Ejecutar función
            result = func(*args, **kwargs)
            
            # Guardar en cache
            cache_manager.set(cache_key, result)
            
            return result
        
        return wrapper
    
    return decorator


class BatchProcessor:
    """Procesador de batch optimizado"""
    
    def __init__(self, batch_size: int = 10, max_concurrent: int = 5):
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_batch(
        self,
        items: List[Any],
        process_fn: Callable,
        show_progress: bool = True
    ) -> List[Any]:
        """Procesa items en batches concurrentes"""
        
        results = []
        
        for i in range(0, len(items), self.batch_size):
            batch = items[i:i + self.batch_size]
            
            tasks = [
                self._process_item(item, process_fn)
                for item in batch
            ]
            
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
            
            if show_progress:
                print(f"Procesado {min(i + self.batch_size, len(items))}/{len(items)}")
        
        return results
    
    async def _process_item(self, item: Any, process_fn: Callable) -> Any:
        """Procesa un item individual"""
        async with self.semaphore:
            return await process_fn(item) if asyncio.iscoroutinefunction(process_fn) else process_fn(item)


class ResponseCompression:
    """Compresión de respuestas para optimizar bandwidth"""
    
    @staticmethod
    def compress_response(data: Dict[str, Any]) -> str:
        """Comprime respuesta JSON"""
        import gzip
        import base64
        
        json_str = json.dumps(data, separators=(',', ':'))
        compressed = gzip.compress(json_str.encode())
        return base64.b64encode(compressed).decode()
    
    @staticmethod
    def decompress_response(compressed: str) -> Dict[str, Any]:
        """Descomprime respuesta JSON"""
        import gzip
        import base64
        
        compressed_bytes = base64.b64decode(compressed)
        json_str = gzip.decompress(compressed_bytes).decode()
        return json.loads(json_str)


# Instancia global del optimizador
_optimizer: Optional[PerformanceOptimizer] = None

def get_optimizer() -> PerformanceOptimizer:
    """Obtiene instancia global del optimizador"""
    global _optimizer
    if _optimizer is None:
        _optimizer = PerformanceOptimizer()
    return _optimizer


def clear_cache():
    """Limpia cache global"""
    optimizer = get_optimizer()
    optimizer.cache.clear()


def get_cache_stats() -> Dict[str, Any]:
    """Obtiene estadísticas de cache"""
    optimizer = get_optimizer()
    return optimizer.get_stats()
