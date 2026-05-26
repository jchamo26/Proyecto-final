from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./agent.db"
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    FHIR_SERVER_URL: str = "http://127.0.0.1:8080/hapi-fhir-jpaserver"
    ML_SERVICE_URL: str = "http://127.0.0.1:8100"
    DL_SERVICE_URL: str = "http://127.0.0.1:8200"
    LLM_ENDPOINT: str = "http://127.0.0.1:8501"
    LLM_MODEL: str = "qwen/qwen3-32b"
    LLM_API_KEY: str = ""
    AGENT_API_KEY: str = ""
    AGENT_REQUIRE_HTTPS: bool = False
    RAG_DEFAULT_STRATEGY: str = "hybrid"
    RAG_HYBRID_ALPHA: float = 0.6
    RAG_TOP_K: int = 4
    RAG_INDEX_PATH: str = "/data/faiss"
    RAG_DOCS_PATH: str = "/app/knowledge_base/documentos"
    AGENT_MAX_ITERATIONS: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
