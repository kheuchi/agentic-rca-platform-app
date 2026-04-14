"""OpenSearch log query tool - queries logs via the OpenSearch HTTP API."""

import json
import logging
from datetime import datetime, timedelta, timezone

import httpx
from httpx import HTTPStatusError
from langchain_core.tools import tool

from config import settings

logger = logging.getLogger(__name__)


def _normalize_k8s_workload_name(value: str) -> str:
    if not value:
        return ""
    normalized = value
    if normalized.startswith("otel-demo-"):
        normalized = normalized[len("otel-demo-") :]

    parts = normalized.split("-")
    if len(parts) >= 3:
        # Pod names often end with deployment hash + pod suffix.
        normalized = "-".join(parts[:-2])

    return normalized


def _extract_log_message(source: dict) -> str:
    """Best-effort extraction across common OpenTelemetry/OpenSearch log shapes."""
    for key in ("body", "message", "log", "msg"):
        value = source.get(key)
        if isinstance(value, str) and value:
            return value

    attributes = source.get("attributes", {})
    if isinstance(attributes, dict):
        for key in ("message", "body", "event.message"):
            value = attributes.get(key)
            if isinstance(value, str) and value:
                return value

    return json.dumps(source, ensure_ascii=True)[:500]


def _extract_service_name(source: dict) -> str:
    for key in ("service.name", "serviceName"):
        value = source.get(key)
        if isinstance(value, str) and value:
            return value

    resource = source.get("resource", {})
    if isinstance(resource, dict):
        for key in ("service.name", "serviceName"):
            value = resource.get(key)
            if isinstance(value, str) and value:
                return value

    attributes = source.get("attributes", {})
    if isinstance(attributes, dict):
        value = attributes.get("service.name")
        if isinstance(value, str) and value:
            return value

    resource = source.get("resource", {})
    if isinstance(resource, dict):
        for key in (
            "k8s.deployment.name",
            "k8s.statefulset.name",
            "k8s.daemonset.name",
            "k8s.container.name",
            "k8s.pod.name",
        ):
            value = resource.get(key)
            if isinstance(value, str) and value:
                normalized = _normalize_k8s_workload_name(value)
                if normalized:
                    return normalized

    return "unknown"


def _service_filter_clauses(service_name: str) -> list[dict]:
    prefixed = f"otel-demo-{service_name}"
    return [
        {"term": {"resource.service.name.keyword": service_name}},
        {"term": {"service.name.keyword": service_name}},
        {"term": {"serviceName.keyword": service_name}},
        {"term": {"attributes.service.name.keyword": service_name}},
        {"term": {"resource.k8s.deployment.name.keyword": prefixed}},
        {"term": {"resource.k8s.statefulset.name.keyword": prefixed}},
        {"term": {"resource.k8s.daemonset.name.keyword": prefixed}},
        {"term": {"resource.k8s.container.name.keyword": service_name}},
        {"wildcard": {"resource.k8s.pod.name.keyword": f"*{service_name}*"}},
        {"wildcard": {"attributes.log.file.path.keyword": f"*{service_name}*"}},
    ]


@tool
async def query_opensearch_logs(
    query_string: str,
    service_name: str | None = None,
    lookback_minutes: int = 60,
    limit: int = 100,
) -> list[dict]:
    """Query application logs from OpenSearch.

    Use this tool to search logs indexed by the OpenTelemetry demo stack.

    Args:
        query_string: Query text or Lucene-like expression to match in log bodies.
        service_name: Optional service name filter such as "frontendproxy" or "cartservice".
        lookback_minutes: How far back to search (default 60 minutes).
        limit: Maximum number of log entries to return (default 100).
    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=lookback_minutes)

    must: list[dict] = []
    filters: list[dict] = [
        {
            "range": {
                "@timestamp": {
                    "gte": start.isoformat(),
                    "lte": now.isoformat(),
                }
            }
        }
    ]

    if query_string.strip():
        must.append(
            {
                "simple_query_string": {
                    "query": query_string,
                    "fields": [
                        "body",
                        "message",
                        "log",
                        "attributes.*",
                        "resource.*",
                    ],
                    "default_operator": "and",
                }
            }
        )

    if service_name:
        filters.append(
            {
                "bool": {
                    "should": _service_filter_clauses(service_name),
                    "minimum_should_match": 1,
                }
            }
        )

    body = {
        "size": limit,
        "sort": [{"@timestamp": {"order": "desc"}}],
        "query": {
            "bool": {
                "must": must if must else [{"match_all": {}}],
                "filter": filters,
            }
        },
    }

    base_url = settings.opensearch_url.rstrip("/")
    # Support both the custom otel* pattern and the default SS4O data stream pattern.
    url = f"{base_url}/otel*,ss4o_logs*/_search"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=body, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.info(
                    "OpenSearch log index patterns otel* and ss4o_logs* not found; returning no log results"
                )
                return []
            raise

    results = []
    for hit in data.get("hits", {}).get("hits", []):
        source = hit.get("_source", {})
        results.append(
            {
                "timestamp": source.get("@timestamp", ""),
                "service_name": _extract_service_name(source),
                "line": _extract_log_message(source),
                "labels": {
                    "index": hit.get("_index", ""),
                    "trace_id": source.get("trace_id", ""),
                    "severity_text": source.get("severity_text", ""),
                },
            }
        )

    logger.info(
        "OpenSearch query: %d results for service=%s query='%s' (last %d min)",
        len(results),
        service_name or "*",
        query_string[:60],
        lookback_minutes,
    )
    return results
