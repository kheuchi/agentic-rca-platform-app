# Current `otel-demo` State

English version. Version francaise: [07-otel-demo-current-state.md](./07-otel-demo-current-state.md)

This note captures what was actually running in the `otel-demo` namespace when checked on 2026-04-14.

## Running services

The following application or observability services were visible from `kubectl get all -n otel-demo`:

| Service | Kind | Notes |
|---|---|---|
| `otel-demo-cartservice` | Deployment + Service | Business service |
| `otel-demo-flagd` | Deployment + Service | Feature flags |
| `otel-demo-frontend` | Deployment + Service | Demo frontend |
| `otel-demo-frontendproxy` | Deployment + Service | Front door / proxy |
| `otel-demo-grafana` | Deployment + Service | Dashboards |
| `otel-demo-otelcol` | Deployment + Service | OpenTelemetry Collector |
| `otel-demo-productcatalogservice` | Deployment + Service | Business service |
| `otel-demo-prometheus-server` | Deployment + Service | Metrics backend |
| `otel-demo-valkey` | Deployment + Service | Cache / Redis-compatible |

Notably absent from the live namespace during the first check:

- `checkoutservice`
- `paymentservice`
- `shippingservice`
- `recommendationservice`
- `otel-demo-loki`
- `otel-demo-tempo`
- `otel-demo-jaeger-query`
- `otel-demo-jaeger-collector`
- `otel-demo-opensearch`

Update on 2026-04-14 after the alignment and sync work:

- `otel-demo-jaeger` is now running in the namespace
- `otel-demo-opensearch` is now running in the namespace
- the `otel-demo-jaeger-query:16686` service exposes its JSON API under `/jaeger/ui/api/...` because the pod is started with `--query.base-path=/jaeger/ui`

## Storage shape

What was confirmed in the cluster:

- there were no `StatefulSet` resources in `otel-demo`
- there were no `PersistentVolumeClaim` resources in `otel-demo`
- `otel-demo-prometheus-server` stores its TSDB under `/data`
- that `/data` path is backed by `EmptyDir`, so Prometheus storage is ephemeral

This means the currently visible `otel-demo` workloads are not using PVC-backed persistent storage.

## Where logs, metrics, and traces are supposed to go

The active OpenTelemetry Collector config shows this routing:

| Signal | Configured backend | Evidence |
|---|---|---|
| Logs | OpenSearch | `opensearch` exporter to `http://otel-demo-opensearch:9200` |
| Metrics | Prometheus | `otlphttp` exporter to `http://otel-demo-prometheus-server:9090/api/v1/otlp` |
| Traces | Jaeger | `otlp` exporter to `otel-demo-jaeger-collector:4317` |

Grafana was also configured with datasources for:

- Prometheus
- Jaeger
- OpenSearch

So the live observability design is closer to `Prometheus + Jaeger + OpenSearch` than to `Prometheus + Tempo + Loki`.

## Alignment status with the RCA agent

The RCA stack was originally wired to:

- logs via Loki
- metrics via Prometheus
- traces via Tempo

The repositories have now been updated to target:

- logs via OpenSearch
- metrics via Prometheus
- traces via Jaeger

That creates a mismatch with the currently visible `otel-demo` stack:

- metrics align with Prometheus
- the desired log backend is now OpenSearch, which matches the collector config
- the desired trace backend is now Jaeger, which matches the collector config
- the remaining work is deployment convergence, because those live services were still absent or broken during the last cluster verification

Live state confirmed on 2026-04-14:

- `Prometheus` responds correctly from `rag-backend`
- `Jaeger` responds correctly through `otel-demo-jaeger-query:16686/jaeger/ui/api/...`
- `OpenSearch` responds correctly on `:9200`
- however, the expected log index `otel` still did not exist at check time, so application logs were not yet queryable by the RCA agent

Direct measurements from the collector's internal metrics:

- `otelcol_receiver_accepted_log_records{receiver="otlp"}` = `6`
- `otelcol_exporter_sent_log_records{exporter="debug"}` = `6`
- `otelcol_exporter_sent_log_records{exporter="opensearch"}` = `0`
- `otelcol_exporter_send_failed_log_records{exporter="opensearch"}` = `6`

Interpretation:

- services are sending at least a few log records to the collector
- the collector is accepting them
- the `opensearch` exporter is then failing to write all of them into OpenSearch
- so the problem is not "no logs are emitted", but "accepted logs are not successfully indexed"

Working hypothesis:

- the collector's OpenSearch exporter is still `alpha`
- the live config uses a custom `logs_index: otel`
- according to the upstream exporter documentation, the default log pattern is `ss4o_logs-{dataset}-{namespace}`
- so it is plausible that we are hitting either an exporter compatibility issue or a problem related to the chosen indexing mode

## Can we run a real mini corpus test right now?

Not yet for a fully grounded `code + logs + metrics + traces` RCA scenario.

Current blockers:

1. `checkoutservice` is not running in `otel-demo`, so the old checkout-focused scenario is not representative.
2. Traces and metrics are now verifiable, but logs are still missing from the expected OpenSearch `otel` index.
3. Until the `otel` index exists, the agent can produce an RCA mostly from code, metrics, and traces, but not from a fully grounded log correlation.

## Recommended path for a real mini observability test

Pick one live service such as:

- `frontendproxy`
- `frontend`
- `cartservice`
- `productcatalogservice`

Then use one of these two paths.

### Option A: converge the cluster to the now-aligned RCA agent

Best if we want to keep the updated app and GitOps configuration.

1. Deploy or restore live `OpenSearch` and `Jaeger` services in `otel-demo`.
2. Ensure the collector exports logs to OpenSearch and traces to Jaeger.
3. Keep Prometheus as the metrics backend.
4. Generate controlled traffic against one live service.
5. Confirm data exists in all three observability backends before running `/query/rca`.

## Small, realistic test plan

For a true mini corpus test:

1. Ingest only a few source files from one live service, for example the `frontendproxy` or `cartservice` code path.
2. Send controlled requests that exercise that service repeatedly.
3. Verify:
   - code chunks are present in Firestore with the right `service_name`
   - metrics are visible in Prometheus
   - logs are visible in the chosen log backend
   - traces are visible in the chosen trace backend
4. Run `/query/rca` with a question tied to that exact service and traffic window.

Until the backend/tooling mismatch is fixed, the current smoke test proves code ingestion and RCA runtime stability, but not a fully grounded RCA correlation across all three observability signal types.
