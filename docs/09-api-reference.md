# Reference API

Version anglaise : [09-api-reference.en.md](./09-api-reference.en.md)

## OpenAPI

Disponible quand le backend est joignable :
- `/openapi.json` — spec OpenAPI lisible par machine
- `/docs` — Swagger UI
- `/redoc` — ReDoc

## Endpoints disponibles

### `GET /health`

But :
- health check simple du backend

Reponse :
```json
{"status":"ok"}
```

### `POST /ingest`

But :
- mettre en file un job d'ingestion d'un document unique dans NATS JetStream

Body :
```json
{
  "document_id": "doc-123",
  "content": "example content",
  "metadata": {
    "source": "manual"
  }
}
```

Reponse :
- `status`
- `document_id`
- `seq`

### `POST /ingest/repo`

But :
- mettre en file un job d'ingestion de repository

Body :
```json
{
  "repo_url": "https://github.com/open-telemetry/opentelemetry-demo",
  "branch": "main",
  "services": ["frontendproxy"],
  "file_patterns": ["src/frontend-proxy/**/*.yaml"]
}
```

Reponse :
- `status`
- `job_id`
- `seq`

### `GET /ingest/status/{job_id}`

But :
- lire la progression d'ingestion depuis Redis

Notes :
- retourne `503` si Redis n'est pas disponible
- retourne `404` si le job n'existe pas

Reponse :
```json
{
  "job_id": "uuid",
  "status": "running",
  "progress": 42.0,
  "chunks_indexed": 16,
  "error": null
}
```

### `POST /query`

But :
- lancer une recherche vectorielle dans Firestore

Body :
```json
{
  "query": "How does frontendproxy route requests?",
  "top_k": 3,
  "service_filter": "frontendproxy"
}
```

Reponse :
- `results`
- `count`

### `POST /query/rca`

But :
- lancer l'agent RCA LangGraph

Body :
```json
{
  "question": "Why is frontendproxy failing to route requests?",
  "service": "frontendproxy",
  "time_range": "1h",
  "stream": false
}
```

Comportement :
- `stream: false` retourne un JSON final
- `stream: true` retourne un flux SSE (`text/event-stream`)

Champs de reponse :
- `root_cause`
- `confidence`
- `evidence`
- `iterations`
- `hypotheses`
