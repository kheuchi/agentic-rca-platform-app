"""Prometheus metrics query tool — queries metrics via PromQL HTTP API."""

import logging
from datetime import datetime, timedelta, timezone

import httpx
from langchain_core.tools import tool

from config import settings

logger = logging.getLogger(__name__)


@tool
async def query_prometheus_metrics(
    promql_query: str,
    lookback_minutes: int = 60,
    step: str = "1m",
) -> list[dict]:
    """Query metrics from Prometheus using PromQL.

    Use this tool to check service health metrics like error rates, latency,
    request counts, CPU/memory usage, etc.

    Args:
        promql_query: A PromQL query string.
            Examples:
            - 'rate(http_server_request_duration_seconds_count{service_name="checkoutservice",http_status_code="500"}[5m])'
            - 'histogram_quantile(0.99, rate(http_server_request_duration_seconds_bucket{service_name="paymentservice"}[5m]))'
            - 'up{job=~".*checkoutservice.*"}'
            - 'increase(http_server_request_duration_seconds_count{http_status_code=~"5.."}[15m])'
        lookback_minutes: How far back to query (default 60 minutes).
        step: Resolution step for range queries (default "1m").
    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=lookback_minutes)

    params = {
        "query": promql_query,
        "start": start.isoformat(),
        "end": now.isoformat(),
        "step": step,
    }

    url = f"{settings.prometheus_url}/api/v1/query_range"
    instant_url = f"{settings.prometheus_url}/api/v1/query"
    results = []

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            logger.warning("Prometheus query failed: %s", data.get("error", "unknown"))
            return [{"error": data.get("error", "query failed")}]

        for series in data.get("data", {}).get("result", []):
            metric_labels = series.get("metric", {})
            values = [
                {
                    "timestamp": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
                    "value": float(val),
                }
                for ts, val in series.get("values", [])
            ]
            results.append({
                "metric": metric_labels,
                "values": values,
                "latest_value": float(values[-1]["value"]) if values else None,
            })

        # Some OTel demo metrics are easier to retrieve via instant query than via query_range,
        # especially shortly after sparse traffic bursts. Fall back so RCA still gets evidence.
        if not results:
            instant_resp = await client.get(
                instant_url,
                params={"query": promql_query, "time": now.isoformat()},
                timeout=30,
            )
            instant_resp.raise_for_status()
            instant_data = instant_resp.json()

            if instant_data.get("status") == "success":
                for series in instant_data.get("data", {}).get("result", []):
                    metric_labels = series.get("metric", {})
                    value = series.get("value")
                    latest_value = None
                    timestamp = None
                    if isinstance(value, list) and len(value) == 2:
                        timestamp = datetime.fromtimestamp(
                            float(value[0]), tz=timezone.utc
                        ).isoformat()
                        latest_value = float(value[1])
                    results.append({
                        "metric": metric_labels,
                        "values": (
                            [{"timestamp": timestamp, "value": latest_value}]
                            if timestamp is not None and latest_value is not None
                            else []
                        ),
                        "latest_value": latest_value,
                    })

    logger.info(
        "Prometheus query: %d series for '%s' (last %d min)",
        len(results), promql_query[:60], lookback_minutes,
    )
    return results
