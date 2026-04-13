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

## Ou l'agent RCA cherche logs, metriques et traces

L'agent RCA ne lit pas les logs, metriques ou traces directement dans des buckets, des PVC ou des bases de donnees.

Il interroge les backends d'observabilite via leurs API HTTP :
- logs : API HTTP Loki avec LogQL, via `backend/agent/tools/loki.py`
- metriques : API HTTP Prometheus avec PromQL, via `backend/agent/tools/prometheus.py`
- traces : API HTTP Tempo, via `backend/agent/tools/tempo.py`

Dans le deploiement AKS actuel, ces services tournent dans le namespace `otel-demo`. L'agent parle aux systemes d'observabilite, pas a leur couche de stockage sous-jacente.

## Architecture d'execution

Un schema plus detaille est disponible dans [docs/ARCHITECTURE.fr.md](docs/ARCHITECTURE.fr.md).

## Pourquoi ce design

- Ingestion event-driven : le backend publie dans NATS et repond tout de suite.
- Traitement decouple : le worker execute clone -> parse -> chunk -> embed -> store de facon asynchrone.
- Multi-cloud : Azure OpenAI pour LLM/embeddings, Firestore pour la recherche vectorielle, Vertex AI en fallback.
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

## Etat actuel

- Phase 4.5d : terminee
- Phase 4.6 : prochaine etape, valider le fallback Vertex AI
- Phase 5 : en attente
- Phase 6 : planifiee
