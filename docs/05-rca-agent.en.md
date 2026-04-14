# Step 5 - LangGraph RCA agent (`/query/rca`)

English version. Version francaise: [05-rca-agent.md](./05-rca-agent.md)

> Full flow: [Step 1](./01-request-entry.en.md) -> [Step 2](./02-nats-publish.en.md) -> [Step 3](./03-worker-pipeline.en.md) -> [Step 4](./04-query-vector.en.md) -> **[Step 5]** -> [Phase 6 - MCP](./06-mcp-future.en.md)

---

## Overview

`POST /query/rca` runs a LangGraph agent instead of a single search.

The loop is:
1. plan which tools to call
2. execute tools
3. correlate evidence
4. decide whether to continue
5. synthesize the RCA report

The graph can iterate up to `8` times.

## Sync vs SSE

`backend/routers/query.py` supports:
- `stream: false` -> full JSON response
- `stream: true` -> SSE updates for each completed node

## Shared state

`backend/agent/state.py` holds:
- input fields such as `question`, `service`, `time_range`
- accumulated evidence lists
- hypotheses and iteration counters
- final report fields such as `root_cause`, `confidence`, and `evidence_summary`

Evidence lists accumulate across iterations.

## Graph structure

`backend/agent/graph.py` defines:

```text
plan_search
  -> execute_tools
  -> correlate_findings
  -> should_continue
      -> continue -> plan_search
      -> synthesize -> synthesize_root_cause
```

## Node 1 - `plan_search`

The LLM sees:
- the user question
- target service
- time range
- all evidence gathered so far

It returns a JSON plan of tool calls.

## Node 2 - `execute_tools`

Current tool map:
- `search_code_vectors` -> Firestore
- `query_opensearch_logs` -> OpenSearch HTTP API
- `query_prometheus_metrics` -> Prometheus HTTP API
- `query_jaeger_traces` -> Jaeger HTTP API

Important clarification:
- the agent does not read logs, metrics, or traces from buckets, PVCs, or raw databases
- it calls OpenSearch, Prometheus, and Jaeger through their service APIs inside the cluster

Physical storage, as verified on 2026-04-13:
- Prometheus stores data in `/data` on an `EmptyDir` volume inside `otel-demo-prometheus-server`
- no PVC-backed observability storage was visible in `otel-demo`
- the repos now target OpenSearch and Jaeger for logs and traces, but the live cluster still needs to converge to that desired state before the RCA path can use them reliably

## Node 3 - `correlate_findings`

The LLM analyzes all accumulated evidence and produces:
- hypotheses
- `needs_more_data`
- optional next focus

## Routing - `should_continue`

The graph synthesizes when:
- `iteration >= max_iterations`
- the plan says `ready`
- correlation says no more data is needed

## Node 4 - `synthesize_root_cause`

The final LLM call produces:
- `root_cause`
- `confidence`
- `evidence_summary`

## LLM provider strategy

`backend/llm/providers.py` returns:
- `fallback`: Azure OpenAI `gpt-4o` as primary, Vertex AI on error
- `switch`: force Azure or Vertex explicitly with environment variables

## Summary

| Node | Role | LLM |
|---|---|---|
| `plan_search` | decide tool calls | yes |
| `execute_tools` | run Firestore, OpenSearch, Prometheus, and Jaeger tools | no |
| `correlate_findings` | analyze evidence | yes |
| `synthesize_root_cause` | write final RCA | yes |
| `should_continue` | route loop vs finish | no |

---

Next: [Phase 6 - MCP future](./06-mcp-future.en.md)

---

## Live Validation Status

MVP validation was achieved on 2026-04-14:

- `search_code_vectors` is validated on `frontendproxy`
- `query_opensearch_logs` is validated on `productcatalogservice`
- `query_jaeger_traces` is validated on `frontendproxy`
- `/query/rca` is now stable and no longer restarts `rag-backend`

Known limits:

- `query_prometheus_metrics` remains a separate follow-up
- the slim `otel-demo` deployment still does not expose one single service with clean `code + logs + metrics + traces` coverage for a full RCA test on one target
