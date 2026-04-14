"""LLM provider setup with fallback or explicit provider switching."""

import logging

from config import settings
from llm.tracing import get_langfuse_handler

logger = logging.getLogger(__name__)


def _get_callbacks() -> list:
    """Return LangChain callbacks (Langfuse if configured)."""
    handler = get_langfuse_handler()
    return [handler] if handler else []


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


def resolve_chat_provider_mode(
    strategy: str,
    switch_provider: str,
    *,
    azure_ready: bool,
    vertex_ready: bool,
) -> str:
    """Resolve which provider mode to use for chat."""
    strategy = _normalize_strategy(strategy)
    switch_provider = _normalize_provider(switch_provider)

    if strategy == "switch":
        if switch_provider == "azure":
            if not azure_ready:
                raise RuntimeError("Chat switch is set to Azure OpenAI, but Azure is not configured.")
            return "azure"
        if switch_provider == "vertex":
            if not vertex_ready:
                raise RuntimeError("Chat switch is set to Vertex AI, but Vertex is not configured.")
            return "vertex"
        raise RuntimeError(f"Unsupported llm_switch_provider: {switch_provider}")

    if strategy != "fallback":
        raise RuntimeError(f"Unsupported llm_provider_strategy: {strategy}")

    if azure_ready and vertex_ready:
        return "fallback"
    if azure_ready:
        return "azure"
    if vertex_ready:
        return "vertex"

    raise RuntimeError("No chat LLM configured. Set Azure OpenAI or Vertex AI settings.")


def get_chat_llm():
    """Return a chat LLM with fallback or explicit provider switching."""
    callbacks = _get_callbacks()
    azure_ready = bool(settings.azure_openai_endpoint and settings.azure_openai_api_key)
    vertex_ready = bool(settings.gcp_project_id)
    mode = resolve_chat_provider_mode(
        settings.llm_provider_strategy,
        settings.llm_switch_provider,
        azure_ready=azure_ready,
        vertex_ready=vertex_ready,
    )

    azure_llm = None
    if azure_ready and mode in {"azure", "fallback"}:
        from langchain_openai import AzureChatOpenAI

        azure_llm = AzureChatOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            azure_deployment=settings.azure_openai_chat_deployment,
            api_version="2024-08-01-preview",
            callbacks=callbacks,
        )

    vertex_llm = None
    try:
        if vertex_ready and mode in {"vertex", "fallback"}:
            from langchain_google_vertexai import ChatVertexAI

            vertex_llm = ChatVertexAI(
                model_name="gemini-1.5-pro",
                project=settings.gcp_project_id,
                location=settings.gcp_location,
                callbacks=callbacks,
            )
    except Exception:
        vertex_llm = None

    if mode == "fallback" and azure_llm and vertex_llm:
        logger.info("LLM: Azure OpenAI (primary) + Vertex AI (fallback)")
        return azure_llm.with_fallbacks([vertex_llm])

    if mode == "azure" and azure_llm:
        logger.info("LLM: Azure OpenAI only (switch mode)")
        return azure_llm

    if mode == "vertex" and vertex_llm:
        logger.info("LLM: Vertex AI only (switch mode)")
        return vertex_llm

    if mode == "fallback" and azure_llm:
        logger.info("LLM: Azure OpenAI only")
        return azure_llm

    if mode == "fallback" and vertex_llm:
        logger.info("LLM: Vertex AI only")
        return vertex_llm

    raise RuntimeError("Failed to initialize the configured chat provider.")
