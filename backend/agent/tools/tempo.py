"""Tempo trace query tool — queries distributed traces via HTTP API."""

import logging
from datetime import datetime, timedelta, timezone

import httpx
from langchain_core.tools import tool

from config import settings

logger = logging.getLogger(__name__)


@tool
async def query_tempo_traces(
    service_name: str,
    lookback_minutes: int = 60,
    min_duration: str | None = None,
    status_code: str | None = "error",
    limit: int = 20,
) -> list[dict]:
    """Search for distributed traces in Tempo.

    Use this tool to find traces from a specific service, especially error traces
    or slow requests. Returns trace summaries with span details.

    Args:
        service_name: The service to search traces for (e.g. "checkoutservice").
        lookback_minutes: How far back to search (default 60 minutes).
        min_duration: Minimum trace duration filter (e.g. "500ms", "1s"). None = no filter.
        status_code: Filter by status ("error", "ok", or None for all). Default "error".
        limit: Maximum number of traces to return (default 20).
    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=lookback_minutes)

    # Tempo search API
    params: dict = {
        "q": f'{{resource.service.name="{service_name}"}}',
        "start": str(int(start.timestamp())),
        "end": str(int(now.timestamp())),
        "limit": str(limit),
    }

    if min_duration:
        params["minDuration"] = min_duration
    if status_code == "error":
        params["q"] = f'{{resource.service.name="{service_name}" && status=error}}'

    url = f"{settings.tempo_url}/api/search"

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for trace in data.get("traces", []):
        trace_id = trace.get("traceID", "")

        # Fetch full trace detail for span breakdown
        spans = await _fetch_trace_spans(trace_id)

        results.append({
            "trace_id": trace_id,
            "root_service": trace.get("rootServiceName", ""),
            "root_endpoint": trace.get("rootTraceName", ""),
            "duration_ms": trace.get("durationMs", 0),
            "start_time": datetime.fromtimestamp(
                trace.get("startTimeUnixNano", 0) / 1e9, tz=timezone.utc
            ).isoformat(),
            "span_count": trace.get("spanSets", [{}])[0].get("matched", 0) if trace.get("spanSets") else 0,
            "spans": spans[:10],  # top 10 spans to keep response manageable
        })

    logger.info(
        "Tempo search: %d traces for service=%s (last %d min, status=%s)",
        len(results), service_name, lookback_minutes, status_code,
    )
    return results


async def _fetch_trace_spans(trace_id: str) -> list[dict]:
    """Fetch span details for a single trace."""
    url = f"{settings.tempo_url}/api/traces/{trace_id}"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()

        spans = []
        for batch in data.get("batches", []):
            resource_attrs = {}
            for attr in batch.get("resource", {}).get("attributes", []):
                resource_attrs[attr.get("key", "")] = attr.get("value", {}).get("stringValue", "")

            for scope_span in batch.get("scopeSpans", []):
                for span in scope_span.get("spans", []):
                    spans.append({
                        "service": resource_attrs.get("service.name", "unknown"),
                        "operation": span.get("name", ""),
                        "kind": span.get("kind", ""),
                        "status": span.get("status", {}).get("code", "UNSET"),
                        "duration_ms": (
                            int(span.get("endTimeUnixNano", 0)) - int(span.get("startTimeUnixNano", 0))
                        ) / 1e6,
                    })

        # Sort by duration descending (slowest first)
        spans.sort(key=lambda s: s["duration_ms"], reverse=True)
        return spans

    except Exception:
        logger.debug("Could not fetch spans for trace %s", trace_id)
        return []
