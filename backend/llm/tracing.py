"""Langfuse LLM tracing helpers for LangChain/LangGraph."""

import logging
import sys
import types
from collections.abc import Sequence

from config import settings

logger = logging.getLogger(__name__)

_handler = None


def _ensure_langchain_module():
    """Provide a tiny shim for langfuse>=4 when only langchain-core is installed.

    Langfuse's LangChain callback imports ``langchain`` first to choose the v0/v1
    compatibility path. This repo intentionally depends on ``langchain-core`` and
    modern provider packages, not the legacy ``langchain`` meta-package.
    """
    if "langchain" in sys.modules:
        return

    try:
        import langchain_core  # noqa: F401
    except Exception:
        return

    shim = types.ModuleType("langchain")
    shim.__version__ = "1.0.0"
    sys.modules["langchain"] = shim


def get_langfuse_handler():
    """Return a Langfuse callback handler (singleton), or None if not configured."""
    global _handler

    if _handler is not None:
        return _handler

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        logger.info("Langfuse not configured (missing keys), LLM tracing disabled")
        return None

    try:
        _ensure_langchain_module()
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler

        Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            base_url=settings.langfuse_base_url,
        )
        _handler = CallbackHandler()
        logger.info("Langfuse tracing enabled at %s", settings.langfuse_base_url)
        return _handler
    except Exception as exc:
        try:
            from langfuse.callback import CallbackHandler

            _handler = CallbackHandler(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_base_url,
            )
            logger.info("Langfuse tracing enabled at %s", settings.langfuse_base_url)
            return _handler
        except Exception:
            logger.warning("Failed to initialize Langfuse: %s", exc)
            return None


def build_langchain_config(
    *,
    session_id: str | None = None,
    user_id: str | None = None,
    tags: Sequence[str] | None = None,
    metadata: dict | None = None,
) -> dict:
    """Build LangChain invoke config with Langfuse callbacks and trace metadata."""
    handler = get_langfuse_handler()
    if not handler:
        return {}

    invoke_config: dict = {"callbacks": [handler]}
    trace_metadata = dict(metadata or {})

    if user_id:
        trace_metadata["langfuse_user_id"] = user_id
    if session_id:
        trace_metadata["langfuse_session_id"] = session_id
    if tags:
        trace_metadata["langfuse_tags"] = list(tags)

    if trace_metadata:
        invoke_config["metadata"] = trace_metadata

    return invoke_config
