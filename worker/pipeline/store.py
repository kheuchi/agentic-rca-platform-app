"""Azure AI Search upsert step — store embedded chunks in vector index."""

import logging

from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from llama_index.core.schema import TextNode

from config import settings

logger = logging.getLogger(__name__)

UPLOAD_BATCH_SIZE = 100


def get_search_client() -> SearchClient:
    """Create an Azure AI Search client."""
    return SearchClient(
        endpoint=settings.azure_search_endpoint,
        index_name=settings.azure_search_index,
        credential=AzureKeyCredential(settings.azure_search_api_key),
    )


def _node_to_document(node: TextNode) -> dict:
    """Convert a LlamaIndex TextNode to an Azure AI Search document."""
    return {
        "id": node.id_.replace(":", "-"),  # Azure AI Search keys can't contain ':'
        "content": node.get_content(),
        "embedding": node.embedding,
        "file_path": node.metadata.get("file_path", ""),
        "service_name": node.metadata.get("service_name", ""),
        "language": node.metadata.get("language", ""),
        "chunk_index": node.metadata.get("chunk_index", 0),
        "repo_url": node.metadata.get("repo_url", ""),
        "commit_sha": node.metadata.get("commit_sha", ""),
    }


def store_chunks(nodes: list[TextNode]) -> int:
    """Upsert embedded chunks into Azure AI Search.

    Args:
        nodes: TextNode list with embeddings from embed_chunks().

    Returns:
        Number of documents successfully upserted.
    """
    if not nodes:
        return 0

    client = get_search_client()
    total_uploaded = 0

    for i in range(0, len(nodes), UPLOAD_BATCH_SIZE):
        batch = nodes[i : i + UPLOAD_BATCH_SIZE]
        documents = [_node_to_document(node) for node in batch]

        result = client.merge_or_upload_documents(documents)

        succeeded = sum(1 for r in result if r.succeeded)
        total_uploaded += succeeded

        logger.info(
            "Upserted batch %d-%d: %d/%d succeeded",
            i, min(i + UPLOAD_BATCH_SIZE, len(nodes)),
            succeeded, len(batch),
        )

    logger.info(
        "Stored %d/%d chunks in Azure AI Search index '%s'",
        total_uploaded, len(nodes), settings.azure_search_index,
    )
    return total_uploaded
