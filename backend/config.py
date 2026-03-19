"""Centralized configuration via pydantic-settings (reads env vars + .env)."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # NATS
    nats_url: str = "nats://localhost:4222"

    # Redis (cache only — not used as vector store)
    redis_host: str = "localhost"
    redis_port: int = 6380
    redis_key: str = ""

    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_chat_deployment: str = "gpt-4o"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"

    # Azure AI Search (vector store)
    azure_search_endpoint: str = ""
    azure_search_api_key: str = ""
    azure_search_index: str = "code-chunks"

    # GCP (fallback)
    gcp_project_id: str = ""
    gcp_location: str = "us-central1"

    # Observability backends (hot path)
    loki_url: str = "http://loki:3100"
    prometheus_url: str = "http://prometheus:9090"
    tempo_url: str = "http://tempo:3200"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
