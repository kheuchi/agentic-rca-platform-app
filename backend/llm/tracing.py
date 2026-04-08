"""Langfuse LLM tracing — callback handler for LangChain/LangGraph."""

import logging

from config import settings

logger = logging.getLogger(__name__)

_handler = None


def get_langfuse_handler():
    """Return a Langfuse callback handler (singleton), or None if not configured."""
    global _handler

    if _handler is not None:
        return _handler

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        logger.info("Langfuse not configured (missing keys), LLM tracing disabled")
        return None

    try:
        from langfuse.callback import CallbackHandler

        _handler = CallbackHandler(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        logger.info("Langfuse tracing enabled at %s", settings.langfuse_host)
        return _handler
    except Exception as e:
        logger.warning("Failed to initialize Langfuse: %s", e)
        return None
