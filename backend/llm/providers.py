"""LLM provider setup — Azure OpenAI (primary) + Vertex AI (fallback)."""

import logging

from config import settings
from llm.tracing import get_langfuse_handler

logger = logging.getLogger(__name__)


def _get_callbacks() -> list:
    """Return LangChain callbacks (Langfuse if configured)."""
    handler = get_langfuse_handler()
    return [handler] if handler else []


def get_chat_llm():
    """Return a chat LLM with Azure OpenAI primary and Vertex AI fallback."""
    callbacks = _get_callbacks()
    azure_ready = bool(settings.azure_openai_endpoint and settings.azure_openai_api_key)
    vertex_ready = bool(settings.gcp_project_id)

    primary = None
    fallback = None

    if azure_ready:
        from langchain_openai import AzureChatOpenAI

        primary = AzureChatOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            azure_deployment=settings.azure_openai_chat_deployment,
            api_version="2024-08-01-preview",
            callbacks=callbacks,
        )

    try:
        if vertex_ready:
            from langchain_google_vertexai import ChatVertexAI

            fallback = ChatVertexAI(
                model_name="gemini-1.5-pro",
                project=settings.gcp_project_id,
                location=settings.gcp_location,
                callbacks=callbacks,
            )
    except Exception:
        fallback = None

    if primary and fallback:
        logger.info("LLM: Azure OpenAI (primary) + Vertex AI (fallback)")
        return primary.with_fallbacks([fallback])

    if primary:
        logger.info("LLM: Azure OpenAI only")
        return primary

    if fallback:
        logger.info("LLM: Vertex AI only")
        return fallback

    raise RuntimeError("No chat LLM configured. Set Azure OpenAI or Vertex AI settings.")
