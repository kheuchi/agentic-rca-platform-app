"""Embedding step with fallback or explicit provider switching."""

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


class FallbackEmbeddingAdapter:
    """Try Azure embeddings first, then fall back to Vertex AI on runtime errors."""

    def __init__(self, primary, fallback):
        self._primary = primary
        self._fallback = fallback

    async def aget_text_embedding(self, text: str) -> list[float]:
        try:
            return await self._primary.aget_text_embedding(text)
        except Exception as exc:
            logger.warning("Azure embedding failed, falling back to Vertex AI: %s", exc)
            return await self._fallback.aget_text_embedding(text)

    async def aget_text_embedding_batch(self, texts: Sequence[str]) -> list[list[float]]:
        try:
            return await self._primary.aget_text_embedding_batch(texts)
        except Exception as exc:
            logger.warning("Azure embedding batch failed, falling back to Vertex AI: %s", exc)
            return await self._fallback.aget_text_embedding_batch(texts)


def _normalize_strategy(value: str) -> str:
    normalized = (value or "fallback").strip().lower()
    aliases = {
        "azure_only": "switch",
        "vertex_only": "switch",
        "primary_only": "switch",
    }
    return aliases.get(normalized, normalized)


def _normalize_provider(value: str) -> str:
    normalized = (value or "azure").strip().lower()
    if normalized in {"primary", "azure_only"}:
        return "azure"
    if normalized in {"fallback", "vertex_only"}:
        return "vertex"
    return normalized


def resolve_embedding_provider_mode(
    strategy: str,
    switch_provider: str,
    *,
    azure_ready: bool,
    vertex_ready: bool,
) -> str:
    """Resolve which provider mode to use for worker embeddings."""
    strategy = _normalize_strategy(strategy)
    switch_provider = _normalize_provider(switch_provider)

    if strategy == "switch":
        if switch_provider == "azure":
            if not azure_ready:
                raise RuntimeError("Embedding switch is set to Azure OpenAI, but Azure is not configured.")
            return "azure"
        if switch_provider == "vertex":
            if not vertex_ready:
                raise RuntimeError("Embedding switch is set to Vertex AI, but Vertex is not configured.")
            return "vertex"
        raise RuntimeError(f"Unsupported embedding_switch_provider: {switch_provider}")

    if strategy != "fallback":
        raise RuntimeError(f"Unsupported embedding_provider_strategy: {strategy}")

    if azure_ready and vertex_ready:
        return "fallback"
    if azure_ready:
        return "azure"
    if vertex_ready:
        return "vertex"

    raise RuntimeError("No embedding provider configured. Set Azure OpenAI or Vertex AI settings.")


def get_embedding_model():
    """Create an embedding model with fallback or explicit provider switching."""
    azure_ready = bool(settings.azure_openai_endpoint and settings.azure_openai_api_key)
    vertex_ready = bool(settings.gcp_project_id)
    mode = resolve_embedding_provider_mode(
        settings.embedding_provider_strategy,
        settings.embedding_switch_provider,
        azure_ready=azure_ready,
        vertex_ready=vertex_ready,
    )

    vertex_model = None
    if vertex_ready and mode in {"vertex", "fallback"}:
        from langchain_google_vertexai import VertexAIEmbeddings

        vertex_model = VertexEmbeddingAdapter(
            VertexAIEmbeddings(
                model_name="text-embedding-004",
                project=settings.gcp_project_id,
                location=settings.gcp_location,
            )
        )

    azure_model = None
    if azure_ready and mode in {"azure", "fallback"}:
        from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding

        azure_model = AzureOpenAIEmbedding(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            azure_deployment=settings.azure_openai_embedding_deployment,
            api_version="2024-08-01-preview",
        )

    if mode == "fallback" and azure_model and vertex_model:
        logger.info(
            "Embeddings: Azure OpenAI %s with Vertex AI fallback",
            settings.azure_openai_embedding_deployment,
        )
        return FallbackEmbeddingAdapter(azure_model, vertex_model)

    if mode == "azure" and azure_model:
        logger.info(
            "Embeddings: Azure OpenAI %s only (switch mode)",
            settings.azure_openai_embedding_deployment,
        )
        return azure_model

    if mode == "vertex" and vertex_model:
        logger.info("Embeddings: Vertex AI only (switch mode)")
        return vertex_model

    if mode == "fallback" and azure_model:
        logger.info("Embeddings: Azure OpenAI only")
        return azure_model

    if mode == "fallback" and vertex_model:
        logger.info("Embeddings: Vertex AI only")
        return vertex_model

    raise RuntimeError("Failed to initialize the configured embedding provider.")


async def embed_chunks(nodes: list[TextNode]) -> list[TextNode]:
    """Embed all chunks using the configured embedding provider."""
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
