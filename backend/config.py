from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Dict, Any


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # PostgreSQL
    postgres_user: str = "neuroflow"
    postgres_password: str = "neuroflow_secret_password"
    postgres_db: str = "neuroflow"
    database_url: str = "postgresql://neuroflow:neuroflow_secret_password@localhost:5432/neuroflow"

    # Redis
    redis_password: str = "redis_secret_password"
    redis_url: str = "redis://:redis_secret_password@localhost:6379/0"

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
    jwt_secret_key: str = "dev_secret_jwt_key_32_bytes_long_1234567890"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # Plugin Secrets
    plugin_secrets_key: str = "dev_plugin_secrets_key_32_bytes_long"

    # Telemetry
    sentry_dsn: Optional[str] = None

    # App
    environment: str = "development"
    log_level: str = "INFO"

    # Clients (demo)
    # In production, store these securely (e.g., in a database with hashed secrets)
    jwt_clients: Dict[str, Dict[str, Any]] = {
        "demo-client": {
            "client_secret": "demo-secret",
            "scopes": ["query", "ingest"]
        },
        "admin-client": {
            "client_secret": "admin-secret",
            "scopes": ["query", "ingest", "admin"]
        }
    }


settings = Settings()

