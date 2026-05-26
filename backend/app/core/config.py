import os
import secrets

from pydantic import Field

try:
    from pydantic_settings import BaseSettings
except Exception:
    from pydantic import BaseSettings

LOCAL_FERNET_KEY = "R2pUXBafZ5-Xtqw3RlIscgDSwIT9WsoBUKIYr0MBtRc="


def _env_or_fallback(name: str, fallback: str) -> str:
    value = os.getenv(name)
    if value:
        return value

    if os.getenv("APP_ENV", "development").lower() == "production":
        raise RuntimeError(f"{name} debe estar definido en producción")

    return fallback


class Settings(BaseSettings):
    SECRET_KEY: str = Field(default_factory=lambda: _env_or_fallback("SECRET_KEY", "dev-secret-please-change"))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"
    SUPERUSER_EMAIL: str = Field(default_factory=lambda: _env_or_fallback("SUPERUSER_EMAIL", "medico@pechychon.com"))
    SUPERUSER_PASSWORD: str = Field(default_factory=lambda: _env_or_fallback("SUPERUSER_PASSWORD", "SuperPass2026"))
    SUPERUSER_LICENSE: str = Field(default_factory=lambda: _env_or_fallback("SUPERUSER_LICENSE", "MED123456"))
    DATABASE_URL: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./clinica.db"))
    FERNET_KEY: str = Field(default_factory=lambda: _env_or_fallback("FERNET_KEY", LOCAL_FERNET_KEY))
    MINIO_ROOT_USER: str = Field(default_factory=lambda: _env_or_fallback("MINIO_ROOT_USER", "minioadmin"))
    MINIO_ROOT_PASSWORD: str = Field(default_factory=lambda: _env_or_fallback("MINIO_ROOT_PASSWORD", "minioadmin"))
    MINIO_BUCKET: str = "models"
    MLFLOW_TRACKING_URI: str = Field(default_factory=lambda: _env_or_fallback("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    REDIS_URL: str = Field(default_factory=lambda: _env_or_fallback("REDIS_URL", "redis://localhost:6379/0"))
    LLM_ENDPOINT: str = Field(default_factory=lambda: _env_or_fallback("LLM_ENDPOINT", "http://127.0.0.1:8501"))
    ML_SERVICE_URL: str = Field(default_factory=lambda: _env_or_fallback("ML_SERVICE_URL", "http://localhost:8100"))
    DL_SERVICE_URL: str = Field(default_factory=lambda: _env_or_fallback("DL_SERVICE_URL", "http://localhost:8200"))
    FHIR_SERVER_URL: str = Field(default_factory=lambda: _env_or_fallback("FHIR_SERVER_URL", "http://localhost:8080/hapi-fhir-jpaserver"))
    LLM_API_KEY: str = ""
    FRONTEND_HOST: str = Field(default_factory=lambda: _env_or_fallback("FRONTEND_HOST", "http://localhost"))
    ALLOWED_ORIGINS: str = Field(default_factory=lambda: os.getenv("ALLOWED_ORIGINS", ""))
    APP_ENV: str = Field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    REQUIRE_HTTPS: bool = Field(default_factory=lambda: os.getenv("REQUIRE_HTTPS", "false").lower() == "true")
    TLS_CERT_PATH: str = "/etc/nginx/certs/fullchain.pem"
    TLS_KEY_PATH: str = "/etc/nginx/certs/privkey.pem"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
