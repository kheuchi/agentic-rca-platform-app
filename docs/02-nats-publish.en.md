# Step 2 - Publish to NATS JetStream

English version. Version francaise: [02-nats-publish.md](./02-nats-publish.md)

> Full flow: [Step 1](./01-request-entry.en.md) -> **[Step 2]** -> [Step 3](./03-worker-pipeline.en.md) -> [Step 4](./04-query-vector.en.md) -> [Step 5](./05-rca-agent.en.md)

---

## Overview

After validation, the backend publishes an ingest job to NATS JetStream and immediately returns a `job_id`.

The heavy work happens later in the worker:
- clone
- parse
- chunk
- embed
- store

## Why JetStream

JetStream gives the platform:
- persistence
- retries
- replay
- decoupling between API and worker
- safer restarts
- KEDA-friendly queue semantics

## Stream configuration

At startup the backend ensures the `RAG` stream exists:

```python
await js.add_stream(name="RAG", subjects=["rag.>"], max_msgs=10_000)
```

Current subjects:
- `rag.ingest`
- `rag.ingest.repo`

## `/ingest/repo`

The backend:
1. generates a `job_id`
2. serializes the payload as JSON bytes
3. publishes to `rag.ingest.repo`

```python
job_id = str(uuid.uuid4())
payload = json.dumps({...}).encode()
ack = await js.publish("rag.ingest.repo", payload)
```

The response includes:
- `status`
- `job_id`
- `seq`

## Status tracking

The client can poll:

```text
GET /ingest/status/{job_id}
```

That route reads Redis entries written by the worker during processing:
- `cloning`
- `parsing`
- `chunking`
- `embedding`
- `storing`
- `completed`
- `failed`

Redis is optional, so the status route can return `503`.

## What the worker receives

The worker rebuilds the original payload with:

```python
data = json.loads(msg.data.decode())
```

It depends on the message contract, not on an in-process backend call.

## Summary

| Action | Where | Detail |
|---|---|---|
| generate `job_id` | `backend/routers/ingest.py` | `uuid.uuid4()` |
| serialize payload | `backend/routers/ingest.py` | `json.dumps(...).encode()` |
| publish to JetStream | `backend/routers/ingest.py` | `js.publish("rag.ingest.repo", payload)` |
| persist job | NATS JetStream | stored until ack |
| track status | Redis | `ingest:job:{job_id}` |

---

Next: [Step 3 - Worker pipeline](./03-worker-pipeline.en.md)
