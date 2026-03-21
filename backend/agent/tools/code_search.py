"""Code vector search tool — hybrid search against Azure AI Search."""

import logging

import httpx
from langchain_core.tools import tool

from config import settings

logger = logging.getLogger(__name__)


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
    from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding

    # Embed the query
    embed_model = AzureOpenAIEmbedding(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        azure_deployment=settings.azure_openai_embedding_deployment,
        api_version="2024-08-01-preview",
    )
    query_embedding = await embed_model.aget_text_embedding(query)

    # Build Azure AI Search request (hybrid: vector + keyword)
    search_body: dict = {
        "search": query,
        "vectorQueries": [
            {
                "kind": "vector",
                "vector": query_embedding,
                "fields": "embedding",
                "k": top_k,
            }
        ],
        "top": top_k,
        "select": "id,content,file_path,service_name,language,chunk_index,repo_url",
    }

    if service_filter:
        search_body["filter"] = f"service_name eq '{service_filter}'"

    url = f"{settings.azure_search_endpoint}/indexes/{settings.azure_search_index}/docs/search?api-version=2024-07-01"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            json=search_body,
            headers={
                "Content-Type": "application/json",
                "api-key": settings.azure_search_api_key,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for doc in data.get("value", []):
        results.append({
            "file_path": doc.get("file_path", ""),
            "service_name": doc.get("service_name", ""),
            "language": doc.get("language", ""),
            "content": doc.get("content", ""),
            "score": doc.get("@search.score", 0),
        })

    logger.info("Code search: %d results for query='%s' service=%s", len(results), query[:50], service_filter)
    return results
