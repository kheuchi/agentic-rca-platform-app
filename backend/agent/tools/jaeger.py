"""Jaeger trace query tool - queries distributed traces via the Jaeger HTTP API."""

import json
import logging
from datetime import datetime, timedelta, timezone

import httpx
from langchain_core.tools import tool

from config import settings

logger = logging.getLogger(__name__)


def _duration_to_microseconds(duration: str) -> int | None:
    value = duration.strip().lower()
    if not value:
        return None
    try:
        if value.endswith("ms"):
            return int(float(value[:-2]) * 1000)
        if value.endswith("s"):
            return int(float(value[:-1]) * 1_000_000)
        if value.endswith("us"):
            return int(float(value[:-2]))
    except ValueError:
        return None
    return None


def _lookback_to_jaeger(lookback_minutes: int) -> str:
    if lookback_minutes % 1440 == 0:
        return f"{lookback_minutes // 1440}d"
    if lookback_minutes % 60 == 0:
        return f"{lookback_minutes // 60}h"
    return f"{lookback_minutes}m"


def _span_has_error(span: dict) -> bool:
    for tag in span.get("tags", []):
        if tag.get("key") == "error":
            return str(tag.get("value", "")).lower() in {"true", "1", "yes"}
        if tag.get("key") == "otel.status_code":
            return str(tag.get("value", "")).upper() == "ERROR"
    return False


def _span_duration_ms(span: dict) -> float:
    return float(span.get("duration", 0)) / 1000.0


def _build_trace_summary(trace: dict) -> dict:
    spans = trace.get("spans", [])
    processes = trace.get("processes", {})

    process_service = {
        pid: proc.get("serviceName", "unknown")
        for pid, proc in processes.items()
    }

    ordered_spans = sorted(spans, key=lambda span: span.get("startTime", 0))
    top_spans = sorted(spans, key=_span_duration_ms, reverse=True)[:10]

    root_span = ordered_spans[0] if ordered_spans else {}
    trace_id = root_span.get("traceID", "")
    root_service = process_service.get(root_span.get("processID", ""), "unknown")
    root_endpoint = root_span.get("operationName", "")

    start_time = ""
    if root_span.get("startTime"):
        start_time = datetime.fromtimestamp(
            int(root_span["startTime"]) / 1_000_000,
            tz=timezone.utc,
        ).isoformat()

    return {
        "trace_id": trace_id,
        "root_service": root_service,
        "root_endpoint": root_endpoint,
        "duration_ms": sum(_span_duration_ms(span) for span in spans),
        "start_time": start_time,
        "span_count": len(spans),
        "has_error": any(_span_has_error(span) for span in spans),
        "spans": [
            {
                "service": process_service.get(span.get("processID", ""), "unknown"),
                "operation": span.get("operationName", ""),
                "kind": next(
                    (
                        tag.get("value", "")
                        for tag in span.get("tags", [])
                        if tag.get("key") == "span.kind"
                    ),
                    "",
                ),
                "status": "ERROR" if _span_has_error(span) else "OK",
                "duration_ms": _span_duration_ms(span),
            }
            for span in top_spans
        ],
    }


@tool
async def query_jaeger_traces(
    service_name: str,
    lookback_minutes: int = 60,
    min_duration: str | None = None,
    errors_only: bool = True,
    limit: int = 20,
) -> list[dict]:
    """Search for distributed traces in Jaeger.

    Args:
        service_name: The service to search traces for (for example "frontendproxy").
        lookback_minutes: How far back to search (default 60 minutes).
        min_duration: Optional minimum duration, such as "500ms" or "1s".
        errors_only: When true, only request traces tagged as errors.
        limit: Maximum number of traces to return (default 20).
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=lookback_minutes)

    params: dict[str, str] = {
        "service": service_name,
        "limit": str(limit),
        "lookback": _lookback_to_jaeger(lookback_minutes),
        "start": str(int(start.timestamp() * 1_000_000)),
        "end": str(int(end.timestamp() * 1_000_000)),
    }

    min_duration_us = _duration_to_microseconds(min_duration or "")
    if min_duration_us is not None:
        params["minDuration"] = str(min_duration_us)
    if errors_only:
        params["tags"] = json.dumps({"error": "true"})

    base_url = settings.jaeger_url.rstrip("/")
    url = f"{base_url}/jaeger/ui/api/traces"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        # Jaeger in this demo stack responds reliably to the simpler lookback-based query,
        # while explicit start/end bounds can occasionally over-constrain recent traces.
        if not data.get("data"):
            fallback_params = {
                "service": service_name,
                "limit": str(limit),
                "lookback": _lookback_to_jaeger(lookback_minutes),
            }
            if min_duration_us is not None:
                fallback_params["minDuration"] = str(min_duration_us)
            if errors_only:
                fallback_params["tags"] = json.dumps({"error": "true"})

            fallback_resp = await client.get(url, params=fallback_params, timeout=30)
            fallback_resp.raise_for_status()
            data = fallback_resp.json()

    results = [_build_trace_summary(trace) for trace in data.get("data", [])]
    logger.info(
        "Jaeger search: %d traces for service=%s (last %d min, errors_only=%s)",
        len(results),
        service_name,
        lookback_minutes,
        errors_only,
    )
    return results
