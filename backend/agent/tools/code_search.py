"""Code vector search tool — vector search against GCP Firestore."""

import asyncio
import logging

from google.cloud.firestore import Client as FirestoreClient
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector
from langchain_core.tools import tool

from config import settings

logger = logging.getLogger(__name__)


def _get_firestore_client() -> FirestoreClient:
    return FirestoreClient(
        project=settings.gcp_project_id,
        database=settings.firestore_database,
    )


def _run_vector_search(
    query_embedding: list[float],
    service_filter: str | None,
    top_k: int,
) -> list[dict]:
    """Run the blocking Firestore vector search off the asyncio event loop."""
    db = _get_firestore_client()
    collection = db.collection(settings.firestore_collection)

    query_ref = collection
    if service_filter:
        query_ref = query_ref.where("service_name", "==", service_filter)

    vector_query = query_ref.find_nearest(
        vector_field="embedding",
        query_vector=Vector(query_embedding),
        distance_measure=DistanceMeasure.COSINE,
        limit=top_k,
    )

    results = []
    for doc in vector_query.get():
        data = doc.to_dict()
        results.append({
            "file_path": data.get("file_path", ""),
            "service_name": data.get("service_name", ""),
            "language": data.get("language", ""),
            "content": data.get("content", ""),
            "score": data.get("distance", 0),
        })
    return results


@tool
async def search_code_vectors(
    query: str,
    service_filter: str | None = None,
    top_k: int = 5,
) -> list[dict]:
    """Search the code vector store for relevant source code chunks.

    Use this tool to find source code related to a service, function, or concept.
    The results include file paths, code content, and the service name.

    Args:
        query: Natural language description of what you're looking for.
        service_filter: Optional service name to restrict results (e.g. "checkoutservice").
        top_k: Number of results to return (default 5).
    """
    from llm.embeddings import get_embedding_model

    # Embed the query (Azure OpenAI primary, Vertex AI fallback)
    embed_model = get_embedding_model()
    query_embedding = await embed_model.aget_text_embedding(query)

    results = await asyncio.to_thread(
        _run_vector_search,
        query_embedding,
        service_filter,
        top_k,
    )

    logger.info("Code search: %d results for query='%s' service=%s", len(results), query[:50], service_filter)
    return results
