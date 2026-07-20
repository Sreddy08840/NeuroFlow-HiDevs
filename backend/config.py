from pydantic_settings import BaseSettings
from typing import Optional, Dict


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
    otel_exporter_otlp_endpoint: Optional[str] = None

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # LLM API Keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # Plugin Secrets
    plugin_secrets_key: str

    # Telemetry
    sentry_dsn: Optional[str] = None

    # App
    environment: str = "development"
    log_level: str = "INFO"

    # Clients (demo)
    # In production, store these securely (e.g., in a database with hashed secrets)
    jwt_clients: Dict[str, Dict[str, str]] = {
        "demo-client": {
            "client_secret": "demo-secret",
            "scopes": ["query", "ingest"]
        },
        "admin-client": {
            "client_secret": "admin-secret",
            "scopes": ["query", "ingest", "admin"]
        }
    }

    class Config:
        env_file = "../.env"
        env_file_encoding = "utf-8"


settings = Settings()
