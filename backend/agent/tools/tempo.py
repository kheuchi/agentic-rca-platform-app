"""Tempo trace query tool — queries distributed traces via TraceQL HTTP API."""

# TODO Phase 4.3: Implement query_tempo_traces tool
# - Input: service_name, min_duration, status, limit (or trace_id)
# - HTTP GET to {TEMPO_URL}/api/traces (by ID) or /api/search (by filters)
# - Return trace spans with service, operation, duration, status
