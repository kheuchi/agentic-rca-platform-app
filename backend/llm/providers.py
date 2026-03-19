"""LLM provider setup — Azure OpenAI (primary) + Vertex AI (fallback)."""

import logging

from config import settings

logger = logging.getLogger(__name__)


def get_chat_llm():
    """Return a chat LLM with Azure OpenAI primary and Vertex AI fallback."""
    from langchain_openai import AzureChatOpenAI

    primary = AzureChatOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        azure_deployment=settings.azure_openai_chat_deployment,
        api_version="2024-08-01-preview",
    )

    try:
        from langchain_google_vertexai import ChatVertexAI

        fallback = ChatVertexAI(
            model_name="gemini-1.5-pro",
            project=settings.gcp_project_id,
            location=settings.gcp_location,
        )
        logger.info("LLM: Azure OpenAI (primary) + Vertex AI (fallback)")
        return primary.with_fallbacks([fallback])
    except Exception:
        logger.info("LLM: Azure OpenAI only (Vertex AI fallback not configured)")
        return primary
