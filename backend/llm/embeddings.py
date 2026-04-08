"""Embedding model setup — Azure OpenAI (primary) + Vertex AI (fallback)."""

import logging

from config import settings

logger = logging.getLogger(__name__)


def get_embedding_model():
    """Return an Azure OpenAI embedding model for vector operations.

    Falls back to Vertex AI textembedding-gecko if Azure is not configured.
    """
    if settings.azure_openai_endpoint and settings.azure_openai_api_key:
        from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding

        logger.info("Embeddings: Azure OpenAI %s", settings.azure_openai_embedding_deployment)
        return AzureOpenAIEmbedding(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            azure_deployment=settings.azure_openai_embedding_deployment,
            api_version="2024-08-01-preview",
        )

    # Fallback: Vertex AI embeddings
    logger.info("Azure OpenAI not configured, falling back to Vertex AI embeddings")
    from langchain_google_vertexai import VertexAIEmbeddings

    return VertexAIEmbeddings(
        model_name="text-embedding-004",
        project=settings.gcp_project_id,
        location=settings.gcp_location,
    )
