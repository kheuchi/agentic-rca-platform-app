# Step 1 - Request entry (FastAPI backend)

English version. Version francaise: [01-request-entry.md](./01-request-entry.md)

> Full flow: **[Step 1]** -> [Step 2](./02-nats-publish.en.md) -> [Step 3](./03-worker-pipeline.en.md) -> [Step 4](./04-query-vector.en.md) -> [Step 5](./05-rca-agent.en.md)

---

## Overview

Everything starts in `backend/main.py`, the single entry point of the API.

The backend exposes:
- `POST /ingest/repo`
- `POST /ingest`
- `GET /ingest/status/{job_id}`
- `POST /query`
- `POST /query/rca`
- `GET /health`

## Pydantic in this project

Pydantic is used for:
- validating incoming HTTP payloads in FastAPI routers
- loading typed settings from environment variables

Examples:

```python
class RepoIngestRequest(BaseModel):
    repo_url: str
    branch: str = "main"
    services: list[str] = []
```

```python
class Settings(BaseSettings):
    nats_url: str = "nats://localhost:4222"
    redis_port: int = 6380
```

## Startup lifecycle

The FastAPI lifespan hook opens shared connections at startup:
- NATS JetStream
- Redis

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.nc = await nats.connect(settings.nats_url)
    js = app.state.nc.jetstream()
    await js.add_stream(name="RAG", subjects=["rag.>"], max_msgs=10_000)
    app.state.redis_client = redis.Redis(...)
    yield
```

Important detail:
- NATS and Redis are best-effort dependencies
- `/health` can stay `200` even when one dependency is unavailable
- routes that need those services can still return `503`

## Configuration

`backend/config.py` loads settings from environment variables:
- NATS
- Redis
- Azure OpenAI
- Firestore / GCP
- OpenSearch, Prometheus, Jaeger URLs

In AKS, those values come from deployment env vars and Kubernetes secrets.

## Routing

`backend/main.py` mounts two routers:

```python
app.include_router(ingest_router)
app.include_router(query_router)
```

They live in:
- `backend/routers/ingest.py`
- `backend/routers/query.py`

## Validation

Incoming request bodies are validated with Pydantic models such as:
- `RepoIngestRequest`
- `QueryRequest`
- `RCAQueryRequest`

If validation fails, FastAPI returns `422` automatically.

## Accessing shared clients

Handlers read shared clients from `request.app.state`:

```python
nc = request.app.state.nc
redis_client = request.app.state.redis_client
```

LLM and Firestore helpers are instantiated on demand inside the relevant modules.

## Summary

| Component | Role | File |
|---|---|---|
| lifespan | startup and shutdown connections | `backend/main.py` |
| settings | typed env config | `backend/config.py` |
| ingest router | `/ingest*` routes | `backend/routers/ingest.py` |
| query router | `/query*` routes | `backend/routers/query.py` |
| Pydantic models | request validation | router modules |

---

Next: [Step 2 - Publish to NATS JetStream](./02-nats-publish.en.md)
