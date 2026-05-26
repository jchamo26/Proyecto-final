from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./agent.db"
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    FHIR_SERVER_URL: str = "http://127.0.0.1:8080/hapi-fhir-jpaserver"
    ML_SERVICE_URL: str = "http://127.0.0.1:8100"
    DL_SERVICE_URL: str = "http://127.0.0.1:8200"
    AGENT_API_KEY: str = ""
    RAG_DEFAULT_STRATEGY: str = "hybrid"
    RAG_HYBRID_ALPHA: float = 0.6
    RAG_TOP_K: int = 4

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
