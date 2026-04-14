# Follow-up metriques RCA

Version francaise. English version: [08-metrics-follow-up.en.md](./08-metrics-follow-up.en.md)

## Objet

Ce document suit le reste a faire sur le signal `metrics` pour l'agent RCA.

## Constat au 2026-04-14

- le MVP RCA est valide sur `code + logs + traces`
- le backend live est aligne sur `OpenSearch + Prometheus + Jaeger`
- les tools `query_opensearch_logs` et `query_jaeger_traces` retournent des preuves live
- `query_prometheus_metrics` reste instable sur le scenario de demo retenu

## Ce qui est deja confirme

- Prometheus repond bien depuis `rag-backend`
- des series utiles existent bien dans Prometheus pour `frontendproxy`
- un fallback `query_range -> query` a ete ajoute dans le code applicatif

## Ce qui reste a verifier

1. Verifier quels noms de metriques sont vraiment les plus stables pour le RCA dans `otel-demo`.
2. Verifier si les fenetres temporelles courtes rendent les `rate(...)` trop fragiles pour le mini trafic genere.
3. Decider si le prompt/planner RCA doit privilegier des requetes plus robustes :
   - `calls_total`
   - `duration_milliseconds_bucket`
   - `up`
4. Verifier si le bon service RCA pour les metriques est `frontendproxy` ou `frontend`.

## Sortie attendue

- un mini scenario stable ou `query_prometheus_metrics` retourne une preuve exploitable
- une doc mise a jour indiquant quel service et quelles requetes PromQL sont la reference pour les tests RCA
