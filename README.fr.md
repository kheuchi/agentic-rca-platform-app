# rag-platform-app

Version francaise. English version: [README.md](./README.md)

Code applicatif de la plateforme RAG multi-cloud.

Ce depot contient :
- `rag-backend` : API FastAPI pour l'ingestion, la recherche et le RCA
- `rag-worker` : consommateur NATS JetStream pour l'ingestion asynchrone

L'infrastructure et les manifests Kubernetes vivent dans des depots separes :
- `rag-platform-infra`
- `rag-platform-gitops`

## Documentation

La documentation technique est disponible dans les deux langues.

| Sujet | English | Francais |
|---|---|---|
| Architecture | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | [docs/ARCHITECTURE.fr.md](docs/ARCHITECTURE.fr.md) |
| Etape 1 - entree de requete | [docs/01-request-entry.en.md](docs/01-request-entry.en.md) | [docs/01-request-entry.md](docs/01-request-entry.md) |
| Etape 2 - publication NATS | [docs/02-nats-publish.en.md](docs/02-nats-publish.en.md) | [docs/02-nats-publish.md](docs/02-nats-publish.md) |
| Etape 3 - pipeline worker | [docs/03-worker-pipeline.en.md](docs/03-worker-pipeline.en.md) | [docs/03-worker-pipeline.md](docs/03-worker-pipeline.md) |
| Etape 4 - requete vectorielle | [docs/04-query-vector.en.md](docs/04-query-vector.en.md) | [docs/04-query-vector.md](docs/04-query-vector.md) |
| Etape 5 - agent RCA | [docs/05-rca-agent.en.md](docs/05-rca-agent.en.md) | [docs/05-rca-agent.md](docs/05-rca-agent.md) |
| Phase 6 - futur MCP | [docs/06-mcp-future.en.md](docs/06-mcp-future.en.md) | [docs/06-mcp-future.md](docs/06-mcp-future.md) |
| Etat actuel de `otel-demo` | [docs/07-otel-demo-current-state.en.md](docs/07-otel-demo-current-state.en.md) | [docs/07-otel-demo-current-state.md](docs/07-otel-demo-current-state.md) |
| Follow-up metriques | [docs/08-metrics-follow-up.en.md](docs/08-metrics-follow-up.en.md) | [docs/08-metrics-follow-up.md](docs/08-metrics-follow-up.md) |
| Reference API | [docs/09-api-reference.en.md](docs/09-api-reference.en.md) | [docs/09-api-reference.md](docs/09-api-reference.md) |
| ADR - Retrieval RAG production | [docs/10-adr-production-rag-retrieval.md](docs/10-adr-production-rag-retrieval.md) | [docs/10-adr-production-rag-retrieval.md](docs/10-adr-production-rag-retrieval.md) |

## Ou l'agent RCA cherche logs, metriques et traces

L'agent RCA ne lit pas les logs, metriques ou traces directement dans des buckets, des PVC ou des bases de donnees.

Il interroge les backends d'observabilite via leurs API HTTP :
- logs : API HTTP OpenSearch, via `backend/agent/tools/opensearch.py`
- metriques : API HTTP Prometheus avec PromQL, via `backend/agent/tools/prometheus.py`
- traces : API HTTP Jaeger, via `backend/agent/tools/jaeger.py`

Dans le deploiement AKS actuel, ces services tournent dans le namespace `otel-demo`. L'agent parle aux systemes d'observabilite, pas a leur couche de stockage sous-jacente.

### Stockage physique dans le cluster actuel

La question du stockage physique est distincte de l'API appelee par l'agent.

La verification cluster du 2026-04-13 a montre que :
- les metriques Prometheus sont stockees dans le pod `otel-demo-prometheus-server` via `--storage.tsdb.path=/data`
- ce repertoire `/data` est monte sur un volume `EmptyDir`, pas sur un PVC
- il n'y a ni PVC ni StatefulSet dans le namespace `otel-demo` pour les workloads d'observabilite actuellement visibles

Donc, dans l'environnement actuel, les metriques Prometheus sont physiquement stockees sur un stockage ephemere local au pod et sont perdues si le pod est recree.

Pour OpenSearch et Jaeger :
- la stack OpenTelemetry demo est configuree pour router les logs vers OpenSearch et les traces vers Jaeger
- ces backends etaient absents ou desalignes dans le namespace live lors du controle du 2026-04-14
- les repos applicatif et GitOps sont maintenant alignes sur `OpenSearch + Prometheus + Jaeger`, mais un redeploiement reste necessaire pour que le cluster converge vers cet etat voulu

## Architecture d'execution

Un schema plus detaille est disponible dans [docs/ARCHITECTURE.fr.md](docs/ARCHITECTURE.fr.md).

## Pourquoi ce design

- Ingestion event-driven : le backend publie dans NATS et repond tout de suite.
- Traitement decouple : le worker execute clone -> parse -> chunk -> embed -> store de facon asynchrone.
- Multi-cloud : Azure OpenAI pour LLM/embeddings, Firestore pour la recherche vectorielle, Vertex AI en fallback.
- Controle de provider : le backend et le worker supportent maintenant `fallback` et `switch` explicite entre Azure OpenAI et Vertex AI.
- RCA : l'agent LangGraph combine recherche de code et observabilite live.
- Separation claire : le code applicatif est ici, les manifests restent dans `rag-platform-gitops`.

## Structure du depot

```text
rag-platform-app/
|-- backend/
|-- worker/
|-- docs/
|-- scripts/
|-- catalog.yaml
|-- CONTEXT.md
|-- .github/workflows/
|-- package.json
`-- CHANGELOG.md
```

## CI/CD

```text
Pull request -> ci.yml
  -> lint
  -> docker build (sans push)
  -> Trivy
  -> CodeQL

Push sur main -> release.yml
  -> semantic-release
  -> build et push ghcr.io/kheuchi/rag-backend
  -> build et push ghcr.io/kheuchi/rag-worker
  -> signature des images + SBOM
```

## Developpement local

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

cd worker
pip install -r requirements.txt
python main.py

docker run -p 4222:4222 nats:latest -js
```

## Documentation API

FastAPI genere automatiquement la spec API a partir des routes backend.

Quand le backend est joignable, utilise :
- `/openapi.json` pour la spec OpenAPI
- `/docs` pour Swagger UI
- `/redoc` pour ReDoc

Reference des endpoints :
- [docs/09-api-reference.en.md](docs/09-api-reference.en.md)
- [docs/09-api-reference.md](docs/09-api-reference.md)

## Etat actuel

- Phase 4.5d : terminee, avec un MVP RCA valide sur `code + logs + traces`
- Les metriques restent un follow-up dedie
- Phase 4.6 : le mode `switch` est implemente et teste localement ; la validation live du fallback reste a faire

## Strategie de provider

Le runtime supporte maintenant deux strategies :
- `fallback` : Azure OpenAI d'abord, Vertex AI seulement en cas d'erreur
- `switch` : forcer explicitement le provider sans attendre une erreur

Variables d'environnement :
- `LLM_PROVIDER_STRATEGY=fallback|switch`
- `LLM_SWITCH_PROVIDER=azure|vertex`
- `EMBEDDING_PROVIDER_STRATEGY=fallback|switch`
- `EMBEDDING_SWITCH_PROVIDER=azure|vertex`

Exemple pour forcer Azure dans `rag-dev` :

```env
LLM_PROVIDER_STRATEGY=switch
LLM_SWITCH_PROVIDER=azure
EMBEDDING_PROVIDER_STRATEGY=switch
EMBEDDING_SWITCH_PROVIDER=azure
```

Etat de validation au 2026-04-14 :
- la selection `switch` est couverte par des tests unitaires
- le routage live `switch=vertex` est valide en cluster : backend et worker selectionnent bien Vertex
- l'API Vertex AI est maintenant activee sur `mon-rag-perso-2026`
- le compte de service des pods a maintenant `roles/aiplatform.user`
- les embeddings Vertex repondent maintenant correctement
- `/query` echoue encore car l'index vectoriel Firestore actuel attend 1536 dimensions alors que le chemin Vertex teste produit 768
- `/query/rca` echoue encore car le modele chat Vertex configure `gemini-1.5-pro` n'est pas disponible ou accessible sur ce projet
- `rag-dev` est repasse sur Azure pour garder une plateforme stable tant que ces blockers existent
- le fallback runtime sur erreur n'a pas encore ete valide
- Phase 5 : en attente
- Phase 6 : planifiee
