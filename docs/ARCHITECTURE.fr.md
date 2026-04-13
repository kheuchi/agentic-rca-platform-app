# Architecture

Version francaise. English version: [ARCHITECTURE.md](./ARCHITECTURE.md)

Cette page documente l'architecture d'execution de `rag-platform-app` avec des diagrammes Mermaid.

Une source draw.io editable est aussi disponible dans [architecture-diagram.drawio](./architecture-diagram.drawio).

## Vue end-to-end

```mermaid
flowchart LR
    user[Utilisateur / UI / client API]
    backend[rag-backend\nFastAPI]
    nats[NATS JetStream\nsubjects: rag.ingest, rag.ingest.repo]
    worker[rag-worker\nclone -> parse -> chunk -> embed -> store]
    aoai_embed[Azure OpenAI\ntext-embedding-3-small]
    aoai_llm[Azure OpenAI\ngpt-4o]
    vertex[Vertex AI\nfallback]
    firestore[Firestore\ncollection: code-chunks]
    redis[Azure Redis\ncache de statut]
    loki[Loki]
    prom[Prometheus]
    tempo[Tempo]
    agent[Agent RCA LangGraph]

    user -->|POST /ingest/repo| backend
    user -->|POST /query| backend
    user -->|POST /query/rca| backend

    backend -->|publie un job d'ingestion| nats
    nats -->|consommation| worker

    worker -->|requete embeddings| aoai_embed
    worker -->|fallback embeddings| vertex
    worker -->|stocke vecteurs + metadata| firestore
    worker -->|mise a jour best-effort du statut| redis

    backend -->|lecture du statut| redis
    backend -->|recherche vectorielle| firestore

    backend --> agent
    agent -->|raisonnement LLM| aoai_llm
    agent -->|fallback LLM| vertex
    agent -->|recherche de code| firestore
    agent -->|requete logs| loki
    agent -->|requete metriques| prom
    agent -->|requete traces| tempo
```

## Sources observabilite

L'agent RCA ne lit pas les logs, metriques ou traces depuis des buckets, des PVC ou des bases de donnees brutes.

Il interroge directement les API HTTP de :
- Loki pour les logs
- Prometheus pour les metriques
- Tempo pour les traces

Ces appels sont implementes dans :
- [backend/agent/tools/loki.py](../backend/agent/tools/loki.py)
- [backend/agent/tools/prometheus.py](../backend/agent/tools/prometheus.py)
- [backend/agent/tools/tempo.py](../backend/agent/tools/tempo.py)
