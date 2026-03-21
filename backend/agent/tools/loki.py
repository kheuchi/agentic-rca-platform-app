"""Loki log query tool — queries logs via LogQL HTTP API."""

import logging
from datetime import datetime, timedelta, timezone

import httpx
from langchain_core.tools import tool

from config import settings

logger = logging.getLogger(__name__)


@tool
async def query_loki_logs(
    logql_query: str,
    lookback_minutes: int = 60,
    limit: int = 100,
) -> list[dict]:
    """Query application logs from Loki using LogQL.

    Use this tool to search for log entries matching a LogQL query.
    Useful for finding errors, warnings, or specific log patterns from services.

    Args:
        logql_query: A LogQL query string.
            Examples:
            - '{service_name="checkoutservice"} |= "error"'
            - '{service_name="paymentservice"} | json | level="ERROR"'
            - '{service_name="cartservice"} |~ "timeout|connection refused"'
        lookback_minutes: How far back to search (default 60 minutes).
        limit: Maximum number of log lines to return (default 100).
    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=lookback_minutes)

    params = {
        "query": logql_query,
        "start": str(int(start.timestamp() * 1e9)),  # nanoseconds
        "end": str(int(now.timestamp() * 1e9)),
        "limit": str(limit),
        "direction": "backward",
    }

    url = f"{settings.loki_url}/loki/api/v1/query_range"

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for stream in data.get("data", {}).get("result", []):
        labels = stream.get("stream", {})
        for ts, line in stream.get("values", []):
            results.append({
                "timestamp": datetime.fromtimestamp(
                    int(ts) / 1e9, tz=timezone.utc
                ).isoformat(),
                "labels": labels,
                "line": line,
            })

    # Sort by timestamp descending
    results.sort(key=lambda x: x["timestamp"], reverse=True)
    results = results[:limit]

    logger.info(
        "Loki query: %d results for '%s' (last %d min)",
        len(results), logql_query[:60], lookback_minutes,
    )
    return results
