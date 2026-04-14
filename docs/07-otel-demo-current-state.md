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

Cela cree un decalage avec la stack `otel-demo` actuellement visible :

- les metriques sont alignees avec Prometheus
- la cible logs voulue est maintenant OpenSearch, ce qui correspond a la config du collector
- la cible traces voulue est maintenant Jaeger, ce qui correspond a la config du collector
- le travail restant est la convergence du cluster, car ces services live etaient encore absents ou casses lors du dernier controle

Etat live confirme le 2026-04-14 :

- `Prometheus` repond bien aux requetes depuis `rag-backend`
- `Jaeger` repond bien via `otel-demo-jaeger-query:16686/jaeger/ui/api/...`
- `OpenSearch` repond bien sur `:9200`
- en revanche, l'index de logs attendu `otel` n'existait toujours pas au moment du controle, donc les logs applicatifs n'etaient pas encore interrogeables par l'agent RCA

## Peut-on faire un vrai mini test maintenant ?

Pas encore pour un scenario RCA complet `code + logs + metriques + traces` pleinement ancre sur des donnees live.

Bloquants actuels :

1. `checkoutservice` ne tourne pas dans `otel-demo`, donc l'ancien scenario centre sur checkout n'est plus representatif.
2. Les traces et metriques sont maintenant verifiables, mais les logs ne sont pas encore presents dans l'index OpenSearch attendu `otel`.
3. Tant que l'index `otel` n'existe pas, l'agent peut produire un RCA surtout a partir du code, des metriques et des traces, mais pas d'une vraie correlation complete avec les logs.

## Chemin recommande pour un vrai mini test observabilite

Choisir un service vivant, par exemple :

- `frontendproxy`
- `frontend`
- `cartservice`
- `productcatalogservice`

Puis suivre l'une de ces deux voies.

### Option A : faire converger le cluster vers l'agent RCA maintenant aligne

La meilleure option si on veut garder le code applicatif et GitOps mis a jour.

1. Deployer ou restaurer de vrais services `OpenSearch` et `Jaeger` dans `otel-demo`.
2. Verifier que le collector exporte les logs vers OpenSearch et les traces vers Jaeger.
3. Garder Prometheus pour les metriques.
4. Generer du trafic controle contre un service vivant.
5. Confirmer que les donnees existent dans les trois backends avant de lancer `/query/rca`.

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

Tant que le mismatch backend/tools n'est pas corrige, le smoke test actuel prouve surtout l'ingestion de code et la stabilite runtime de `/query/rca`, mais pas une correlation RCA pleinement ancree sur les trois types de signaux d'observabilite.
