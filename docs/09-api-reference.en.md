# API Reference

French version: [09-api-reference.md](./09-api-reference.md)

## OpenAPI

Available when the backend is reachable:
- `/openapi.json` — machine-readable OpenAPI spec
- `/docs` — Swagger UI
- `/redoc` — ReDoc

## Available Endpoints

### `GET /health`

Purpose:
- simple backend health check

Response:
```json
{"status":"ok"}
```

### `POST /ingest`

Purpose:
- queue a single document ingestion job into NATS JetStream

Body:
```json
{
  "document_id": "doc-123",
  "content": "example content",
  "metadata": {
    "source": "manual"
  }
}
```

Response:
- `status`
- `document_id`
- `seq`

### `POST /ingest/repo`

Purpose:
- queue a repository ingestion job

Body:
```json
{
  "repo_url": "https://github.com/open-telemetry/opentelemetry-demo",
  "branch": "main",
  "services": ["frontendproxy"],
  "file_patterns": ["src/frontend-proxy/**/*.yaml"]
}
```

Response:
- `status`
- `job_id`
- `seq`

### `GET /ingest/status/{job_id}`

Purpose:
- read ingestion progress from Redis

Notes:
- returns `503` when Redis is not available
- returns `404` if the job is unknown

Response:
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

Purpose:
- run vector search against Firestore

Body:
```json
{
  "query": "How does frontendproxy route requests?",
  "top_k": 3,
  "service_filter": "frontendproxy"
}
```

Response:
- `results`
- `count`

### `POST /query/rca`

Purpose:
- run the LangGraph RCA agent

Body:
```json
{
  "question": "Why is frontendproxy failing to route requests?",
  "service": "frontendproxy",
  "time_range": "1h",
  "stream": false
}
```

Behavior:
- `stream: false` returns one final JSON object
- `stream: true` returns an SSE stream (`text/event-stream`)

Response fields:
- `root_cause`
- `confidence`
- `evidence`
- `iterations`
- `hypotheses`
