from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # PostgreSQL
    postgres_user: str = "neuroflow"
    postgres_password: str
    postgres_db: str = "neuroflow"
    database_url: str

    # Redis
    redis_password: str
    redis_url: str

    # MLflow
    mlflow_tracking_uri: str = "http://localhost:5000"

    # OpenTelemetry
    otel_service_name: str = "neuroflow-api"
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # LLM API Keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    class Config:
        env_file = "../.env"
        env_file_encoding = "utf-8"


settings = Settings()
