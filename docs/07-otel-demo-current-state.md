# Etat actuel de `otel-demo`

Version francaise. English version: [07-otel-demo-current-state.en.md](./07-otel-demo-current-state.en.md)

Cette note capture ce qui tournait reellement dans le namespace `otel-demo` lors de la verification du 2026-04-14.

## Services en cours d'execution

Les services applicatifs ou d'observabilite suivants etaient visibles via `kubectl get all -n otel-demo` :

| Service | Kind | Notes |
|---|---|---|
| `otel-demo-cartservice` | Deployment + Service | Service metier |
| `otel-demo-flagd` | Deployment + Service | Feature flags |
| `otel-demo-frontend` | Deployment + Service | Frontend de demo |
| `otel-demo-frontendproxy` | Deployment + Service | Point d'entree / proxy |
| `otel-demo-grafana` | Deployment + Service | Dashboards |
| `otel-demo-otelcol` | Deployment + Service | OpenTelemetry Collector |
| `otel-demo-productcatalogservice` | Deployment + Service | Service metier |
| `otel-demo-prometheus-server` | Deployment + Service | Backend metriques |
| `otel-demo-valkey` | Deployment + Service | Cache / compatible Redis |

Absents du namespace live au moment du premier controle :

- `checkoutservice`
- `paymentservice`
- `shippingservice`
- `recommendationservice`
- `otel-demo-loki`
- `otel-demo-tempo`
- `otel-demo-jaeger-query`
- `otel-demo-jaeger-collector`
- `otel-demo-opensearch`

Mise a jour du 2026-04-14 apres realignement et sync :

- `otel-demo-jaeger` tourne maintenant bien dans le namespace
- `otel-demo-opensearch` tourne maintenant bien dans le namespace
- le service `otel-demo-jaeger-query:16686` expose son API JSON sous `/jaeger/ui/api/...` car le pod est lance avec `--query.base-path=/jaeger/ui`

## Forme du stockage

Ce qui a ete confirme dans le cluster :

- aucun `StatefulSet` dans `otel-demo`
- aucun `PersistentVolumeClaim` dans `otel-demo`
- `otel-demo-prometheus-server` stocke sa TSDB sous `/data`
- ce repertoire `/data` est monte sur un volume `EmptyDir`, donc le stockage Prometheus est ephemere

Cela veut dire que les workloads `otel-demo` actuellement visibles n'utilisent pas de stockage persistant via PVC.

## Ou les logs, metriques et traces sont censes aller

La configuration active de l'OpenTelemetry Collector montre ce routage :

| Signal | Backend configure | Preuve |
|---|---|---|
| Logs | OpenSearch | exporter `opensearch` vers `http://otel-demo-opensearch:9200` |
| Metriques | Prometheus | exporter `otlphttp` vers `http://otel-demo-prometheus-server:9090/api/v1/otlp` |
| Traces | Jaeger | exporter `otlp` vers `otel-demo-jaeger-collector:4317` |

Grafana etait aussi configure avec des datasources pour :

- Prometheus
- Jaeger
- OpenSearch

Donc le design d'observabilite live ressemble davantage a `Prometheus + Jaeger + OpenSearch` qu'a `Prometheus + Tempo + Loki`.

## Etat d'alignement avec l'agent RCA

La stack RCA etait initialement branchee sur :

- logs via Loki
- metriques via Prometheus
- traces via Tempo

Les repos ont maintenant ete mis a jour pour viser :

- logs via OpenSearch
- metriques via Prometheus
- traces via Jaeger

Cela creait initialement un decalage avec la stack `otel-demo` :

- les metriques sont alignees avec Prometheus
- la cible logs voulue est maintenant OpenSearch, ce qui correspond a la config du collector
- la cible traces voulue est maintenant Jaeger, ce qui correspond a la config du collector
- le travail restant etait la convergence du cluster, car ces services live etaient encore absents ou casses lors du dernier controle

Etat live confirme le 2026-04-14 :

- `Prometheus` repond bien aux requetes depuis `rag-backend`
- `Jaeger` repond bien via `otel-demo-jaeger-query:16686/jaeger/ui/api/...`
- `OpenSearch` repond bien sur `:9200`
- le collector tourne maintenant en `DaemonSet`
- le preset `logsCollection` est maintenant actif avec un receiver `filelog` qui lit `/var/log/pods/*/*/*.log`
- l'index de logs `otel` existe maintenant bien dans OpenSearch

Mesures directes prises sur les metriques internes du collector :

- `otelcol_receiver_accepted_log_records{receiver="otlp"}` = `6`
- `otelcol_exporter_sent_log_records{exporter="debug"}` = `6`
- `otelcol_exporter_sent_log_records{exporter="opensearch"}` = `0`
- `otelcol_exporter_send_failed_log_records{exporter="opensearch"}` = `6`

Interpretation :

- les services envoient bien quelques log records au collector
- le collector les accepte bien
- l'exporter `opensearch` echoue ensuite a tous les ecrire dans OpenSearch
- le probleme n'est donc pas "aucun log n'est emis", mais "les logs recus ne sont pas indexes avec succes"

Resolution confirmee plus tard le 2026-04-14 :

- la PR GitOps `#12` a force le collector en `DaemonSet`
- `presets.logsCollection.enabled: true` a active la collecte stdout des pods via `filelog`
- les logs du collector montrent maintenant des `LogsExporter` reguliers sur le exporter `debug`
- OpenSearch expose maintenant un index `otel`
- `GET /otel/_count` retourne `598` documents au moment de la verification

Conclusion pratique :

- les logs applicatifs du mini cluster sont maintenant bien indexes dans OpenSearch
- l'agent RCA peut desormais interroger un backend de logs reel aligne avec la stack live
- le point restant n'est plus l'absence de logs, mais la qualite et la representativite du scenario RCA teste

Validation live complementaire du 2026-04-14 :

- le tool `query_opensearch_logs` retourne maintenant bien des logs live pour `productcatalogservice`
- le tool `query_jaeger_traces` retourne maintenant bien des traces live pour `frontendproxy`
- le tool `query_prometheus_metrics` reste un follow-up separe : le backend Prometheus contient des series utiles, mais le scenario RCA n'est pas encore suffisamment stable pour appeler cela une validation metriques bout en bout

Conclusion MVP :

- la plateforme valide maintenant un RCA MVP sur `code + logs + traces`
- la partie `metrics` reste explicitement suivie a part

## Peut-on faire un vrai mini test maintenant ?

Oui, a condition de choisir un service encore vivant dans `otel-demo`.

Bloquants actuels :

1. `checkoutservice` ne tourne pas dans `otel-demo`, donc l'ancien scenario centre sur checkout n'est plus representatif.
2. Il faut viser un service live comme `frontendproxy`, `frontend`, `cartservice` ou `productcatalogservice`.
3. Il faut cadrer la question RCA sur une fenetre de trafic controlee pour que les preuves restent lisibles.

## Chemin recommande pour un vrai mini test observabilite

Choisir un service vivant, par exemple :

- `frontendproxy`
- `frontend`
- `cartservice`
- `productcatalogservice`

### Option A : utiliser la stack maintenant convergee

La stack live est maintenant coherente pour un mini test :

1. `OpenSearch` est disponible et contient les logs applicatifs.
2. `Jaeger` est disponible pour les traces.
3. `Prometheus` est disponible pour les metriques.
4. Le collector collecte maintenant aussi les logs stdout des pods via `filelog`.

## Petit plan de test realiste

Pour un vrai mini corpus :

1. Ingest uniquement quelques fichiers source d'un service vivant, par exemple le chemin de code `frontendproxy` ou `cartservice`.
2. Envoyer des requetes controlees qui exercent ce service de facon repetee.
3. Verifier :
   - que les chunks de code sont presents dans Firestore avec le bon `service_name`
   - que les metriques sont visibles dans Prometheus
   - que les logs sont visibles dans le backend de logs choisi
   - que les traces sont visibles dans le backend de traces choisi
4. Lancer `/query/rca` avec une question liee a ce service et a cette fenetre de trafic precise.

Le prochain mini test pertinent peut maintenant viser une vraie correlation `code + logs + metriques + traces` une fois le follow-up metrics ferme.
