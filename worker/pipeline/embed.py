"""Azure OpenAI embedding step — batch embed chunks."""

import logging

from llama_index.core.schema import TextNode
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding

from config import settings

logger = logging.getLogger(__name__)

BATCH_SIZE = 16  # Azure OpenAI batch limit


def get_embedding_model() -> AzureOpenAIEmbedding:
    """Create an Azure OpenAI embedding model instance."""
    return AzureOpenAIEmbedding(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        azure_deployment=settings.azure_openai_embedding_deployment,
        api_version="2024-08-01-preview",
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
