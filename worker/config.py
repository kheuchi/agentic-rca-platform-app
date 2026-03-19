"""Worker configuration via pydantic-settings (reads env vars + .env)."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # NATS
    nats_url: str = "nats://localhost:4222"
    nats_subject: str = "rag.ingest"
    nats_subject_repo: str = "rag.ingest.repo"

    # Azure OpenAI (embeddings)
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_embedding_deployment: str = "text-embedding-3-small"

    # Azure AI Search (vector store)
    azure_search_endpoint: str = ""
    azure_search_api_key: str = ""
    azure_search_index: str = "code-chunks"

    # Redis (job status tracking)
    redis_host: str = "localhost"
    redis_port: int = 6380
    redis_key: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
