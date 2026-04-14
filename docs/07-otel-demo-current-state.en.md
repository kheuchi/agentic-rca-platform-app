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

That initially created a mismatch with the visible `otel-demo` stack:

- metrics align with Prometheus
- the desired log backend is now OpenSearch, which matches the collector config
- the desired trace backend is now Jaeger, which matches the collector config
- the remaining work was deployment convergence, because those live services were still absent or broken during the last cluster verification

Live state confirmed on 2026-04-14:

- `Prometheus` responds correctly from `rag-backend`
- `Jaeger` responds correctly through `otel-demo-jaeger-query:16686/jaeger/ui/api/...`
- `OpenSearch` responds correctly on `:9200`
- the collector now runs as a `DaemonSet`
- the `logsCollection` preset is now active with a `filelog` receiver that reads `/var/log/pods/*/*/*.log`
- the `otel` log index now exists in OpenSearch

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

Resolution confirmed later on 2026-04-14:

- GitOps PR `#12` switched the collector to `DaemonSet` mode
- `presets.logsCollection.enabled: true` enabled pod stdout log collection through `filelog`
- collector logs now show regular `LogsExporter` activity on the `debug` exporter
- OpenSearch now exposes an `otel` index
- `GET /otel/_count` returned `598` documents at verification time

Practical conclusion:

- application logs from the mini cluster are now being indexed in OpenSearch
- the RCA agent can now query a real log backend aligned with the live stack
- the remaining question is no longer "are there logs?" but "is the RCA scenario representative enough?"

Additional live validation on 2026-04-14:

- the `query_opensearch_logs` tool now returns live logs for `productcatalogservice`
- the `query_jaeger_traces` tool now returns live traces for `frontendproxy`
- `query_prometheus_metrics` remains a separate follow-up: the Prometheus backend does contain useful series, but the current RCA scenario is not yet stable enough to call metrics fully validated end to end

MVP conclusion:

- the platform now validates an RCA MVP on `code + logs + traces`
- `metrics` remain an explicit follow-up item

## Can we run a real mini corpus test right now?

Yes, as long as the test targets a service that is still alive in `otel-demo`.

Current blockers:

1. `checkoutservice` is not running in `otel-demo`, so the old checkout-focused scenario is not representative.
2. The question should target a live service such as `frontendproxy`, `frontend`, `cartservice`, or `productcatalogservice`.
3. The RCA question should be scoped to a controlled traffic window so the evidence stays readable.

## Recommended path for a real mini observability test

Pick one live service such as:

- `frontendproxy`
- `frontend`
- `cartservice`
- `productcatalogservice`

### Option A: use the now-converged stack

The live stack is now coherent enough for a mini test:

1. `OpenSearch` is available and contains application logs.
2. `Jaeger` is available for traces.
3. `Prometheus` is available for metrics.
4. The collector now also gathers pod stdout logs through `filelog`.

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

The next meaningful mini test can now aim for a real `code + logs + metrics + traces` correlation once the metrics follow-up is closed.
