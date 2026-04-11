"""Embedding step — Azure OpenAI (primary) + Vertex AI (fallback)."""

import logging
from typing import Sequence

from llama_index.core.schema import TextNode

from config import settings

logger = logging.getLogger(__name__)

BATCH_SIZE = 16


class VertexEmbeddingAdapter:
    """Expose the async embedding methods used by the worker pipeline."""

    def __init__(self, model):
        self._model = model

    async def aget_text_embedding(self, text: str) -> list[float]:
        return await self._model.aembed_query(text)

    async def aget_text_embedding_batch(self, texts: Sequence[str]) -> list[list[float]]:
        return await self._model.aembed_documents(list(texts))


def get_embedding_model():
    """Create an embedding model — Azure OpenAI primary, Vertex AI fallback."""
    if settings.azure_openai_endpoint and settings.azure_openai_api_key:
        from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding

        logger.info("Embeddings: Azure OpenAI %s", settings.azure_openai_embedding_deployment)
        return AzureOpenAIEmbedding(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            azure_deployment=settings.azure_openai_embedding_deployment,
            api_version="2024-08-01-preview",
        )

    # Fallback: Vertex AI embeddings via LangChain adapter
    logger.info("Azure OpenAI not configured, falling back to Vertex AI embeddings")
    from langchain_google_vertexai import VertexAIEmbeddings

    return VertexEmbeddingAdapter(
        VertexAIEmbeddings(
            model_name="text-embedding-004",
            project=settings.gcp_project_id,
            location=settings.gcp_location,
        )
    )


async def embed_chunks(nodes: list[TextNode]) -> list[TextNode]:
    """Embed all chunks using Azure OpenAI text-embedding-3-small.

    Args:
        nodes: TextNode list from chunk_documents().

    Returns:
        Same nodes with embedding vectors populated.
    """
    if not nodes:
        return nodes

    embed_model = get_embedding_model()

    for i in range(0, len(nodes), BATCH_SIZE):
        batch = nodes[i : i + BATCH_SIZE]
        texts = [node.get_content() for node in batch]

        embeddings = await embed_model.aget_text_embedding_batch(texts)

        for node, embedding in zip(batch, embeddings):
            node.embedding = embedding

        logger.info(
            "Embedded batch %d-%d / %d",
            i, min(i + BATCH_SIZE, len(nodes)), len(nodes),
        )

    logger.info("Embedded %d chunks total", len(nodes))
    return nodes
