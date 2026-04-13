# Step 3 - Worker pipeline (clone -> parse -> chunk -> embed -> store)

English version. Version francaise: [03-worker-pipeline.md](./03-worker-pipeline.md)

> Full flow: [Step 1](./01-request-entry.en.md) -> [Step 2](./02-nats-publish.en.md) -> **[Step 3]** -> [Step 4](./04-query-vector.en.md) -> [Step 5](./05-rca-agent.en.md)

---

## Overview

The worker is a standalone Python process, not part of the FastAPI backend.

It runs in its own pod and consumes `rag.ingest.repo` messages from NATS JetStream.

Pipeline:
1. clone
2. parse
3. chunk
4. embed
5. store

## Worker loop

`worker/main.py`:
- connects to NATS
- opens durable subscriptions
- consumes messages
- dispatches repo-ingest messages to `process_repo_ingest`

Durable consumer names preserve read position across restarts.

## Step 1 - Clone

`worker/pipeline/clone.py` performs a shallow clone:
- `depth=1`
- `single_branch=True`
- temp directory cleanup after processing

## Step 2 - Parse

`worker/pipeline/parse.py`:
- walks matching files
- skips large or irrelevant directories
- detects service name from the OpenTelemetry Demo directory layout
- detects language from file extension
- returns `ParsedFile` objects

If a targeted service ingest is requested, files outside that service are excluded.

## Step 3 - Chunk

`worker/pipeline/chunk.py` converts parsed files into `TextNode` chunks.

It uses:
- `CodeSplitter` for supported programming languages
- `SentenceSplitter` for text-like files or fallbacks

Chunk IDs are deterministic, which makes reindexing idempotent.

## Step 4 - Embed

`worker/pipeline/embed.py` generates embeddings with:
- Azure OpenAI first
- Vertex AI fallback

Embeddings are produced in batches of `16`.

## Step 5 - Store

`worker/pipeline/store.py` writes chunks into Firestore collection `code-chunks`.

Stored fields include:
- `content`
- `embedding`
- `file_path`
- `service_name`
- `language`
- `chunk_index`
- `repo_url`
- `commit_sha`

Writes use Firestore batch upserts with `merge=True`.

## Error handling

If processing succeeds:
- `msg.ack()`

If processing fails:
- status is updated as failed
- `msg.nak(delay=30)` asks JetStream to redeliver later

Temp clone directories are cleaned in `finally`.

## Summary

| Step | File | Input | Output |
|---|---|---|---|
| clone | `pipeline/clone.py` | repo URL + branch | local repo path |
| parse | `pipeline/parse.py` | repo path + filters | `ParsedFile` list |
| chunk | `pipeline/chunk.py` | parsed files | `TextNode` list |
| embed | `pipeline/embed.py` | chunks | chunks with embeddings |
| store | `pipeline/store.py` | embedded chunks | Firestore upserts |

---

Next: [Step 4 - Direct vector query](./04-query-vector.en.md)
