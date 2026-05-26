import os
try:
    from pydantic_settings import BaseSettings
except Exception:
    from pydantic import BaseSettings

class Settings(BaseSettings):
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"
    SUPERUSER_EMAIL: str
    SUPERUSER_PASSWORD: str
    SUPERUSER_LICENSE: str
    DATABASE_URL: str = "postgresql://clinica_user:ClinicaPass123!@postgres:5432/clinica"
    FERNET_KEY: str
    MINIO_ROOT_USER: str
    MINIO_ROOT_PASSWORD: str
    MINIO_BUCKET: str = "models"
    MLFLOW_TRACKING_URI: str
    REDIS_URL: str
    LLM_ENDPOINT: str
    ML_SERVICE_URL: str
    DL_SERVICE_URL: str
    FHIR_SERVER_URL: str
    LLM_API_KEY: str = ""
    FRONTEND_HOST: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
