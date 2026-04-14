# RCA Metrics Follow-up

English version. Version francaise: [08-metrics-follow-up.md](./08-metrics-follow-up.md)

## Purpose

This document tracks the remaining `metrics` work for the RCA agent.

## State as of 2026-04-14

- the RCA MVP is validated on `code + logs + traces`
- the live backend is aligned on `OpenSearch + Prometheus + Jaeger`
- `query_opensearch_logs` and `query_jaeger_traces` now return live evidence
- `query_prometheus_metrics` is still not stable enough on the chosen demo scenario

## What is already confirmed

- Prometheus responds correctly from `rag-backend`
- useful `frontendproxy` series do exist in Prometheus
- a `query_range -> query` fallback was added in application code

## What remains to verify

1. Identify which metric names are the most stable RCA targets in `otel-demo`.
2. Verify whether short lookback windows make `rate(...)` too fragile for the small traffic burst used in the mini test.
3. Decide whether the RCA planner should prefer more robust queries such as:
   - `calls_total`
   - `duration_milliseconds_bucket`
   - `up`
4. Confirm whether `frontendproxy` or `frontend` is the better RCA metrics reference service.

## Expected outcome

- a stable mini scenario where `query_prometheus_metrics` returns actionable RCA evidence
- updated docs that define the reference service and PromQL queries for RCA metrics tests
