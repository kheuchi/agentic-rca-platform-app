"""Embedding model setup — Azure OpenAI text-embedding-3-small."""

import logging

from config import settings

logger = logging.getLogger(__name__)


def get_embedding_model():
    """Return an Azure OpenAI embedding model for vector operations."""
    from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding

    return AzureOpenAIEmbedding(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        azure_deployment=settings.azure_openai_embedding_deployment,
        api_version="2024-08-01-preview",
    )
