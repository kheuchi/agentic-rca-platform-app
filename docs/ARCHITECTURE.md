# Architecture

This page documents the runtime architecture of `rag-platform-app` with Mermaid diagrams.

GitHub renders Mermaid directly in Markdown, which makes it a good fit for versioned architecture docs.

An editable draw.io source is also available in [architecture-diagram.drawio](/C:/Users/cheik/OneDrive/Old%20OneDrive/Documents/code/mon-rag-multicloud/rag-platform-app/docs/architecture-diagram.drawio).

## End-to-End View

```mermaid
flowchart LR
    user[User / UI / API client]
    backend[rag-backend\nFastAPI]
    nats[NATS JetStream\nsubjects: rag.ingest, rag.ingest.repo]
    worker[rag-worker\nclone -> parse -> chunk -> embed -> store]
    aoai_embed[Azure OpenAI\ntext-embedding-3-small]
    aoai_llm[Azure OpenAI\ngpt-4o]
    vertex[Vertex AI\nfallback]
    firestore[Firestore\ncollection: code-chunks]
    redis[Azure Redis\njob status cache]
    loki[Loki]
    prom[Prometheus]
    tempo[Tempo]
    agent[LangGraph RCA Agent]

    user -->|POST /ingest/repo| backend
    user -->|POST /query| backend
    user -->|POST /query/rca| backend

    backend -->|publish ingest job| nats
    nats -->|consume| worker

    worker -->|embedding requests| aoai_embed
    worker -->|fallback embeddings| vertex
    worker -->|store vectors + metadata| firestore
    worker -->|best-effort status updates| redis

    backend -->|status lookup| redis
    backend -->|vector search| firestore

    backend --> agent
    agent -->|LLM reasoning| aoai_llm
    agent -->|LLM fallback| vertex
    agent -->|search code vectors| firestore
    agent -->|query logs| loki
    agent -->|query metrics| prom
    agent -->|query traces| tempo
```

## Ingestion Flow

```mermaid
flowchart TD
    ingest[POST /ingest/repo]
    publish[Publish job to NATS]
    consume[Worker consumes job]
    clone[Clone repo]
    parse[Parse matching files]
    chunk[Chunk source code]
    embed[Generate embeddings]
    store[Store chunks in Firestore]
    query_ready[Chunks available for /query]

    ingest --> publish --> consume --> clone --> parse --> chunk --> embed --> store --> query_ready

    embed --> aoai[Azure OpenAI\ntext-embedding-3-small]
    embed --> vertex[Vertex AI fallback]
    store --> firestore[Firestore\ncode-chunks]
```

## Query and RCA Flow

```mermaid
flowchart TD
    query[POST /query]
    rca[POST /query/rca]

    query --> q_embed[Embed user query]
    q_embed --> q_model[Azure OpenAI embeddings\nor Vertex fallback]
    q_model --> q_search[Vector search in Firestore]
    q_search --> q_resp[Relevant code chunks]

    rca --> plan[Plan search strategy]
    plan --> code[Search code vectors]
    plan --> logs[Query Loki]
    plan --> metrics[Query Prometheus]
    plan --> traces[Query Tempo]
    code --> correlate[Correlate evidence]
    logs --> correlate
    metrics --> correlate
    traces --> correlate
    correlate --> synth[Synthesize RCA]
    synth --> llm[Azure OpenAI gpt-4o\nor Vertex fallback]
    llm --> rca_resp[RCA response]
```

## What Lives Where

- Azure OpenAI computes embeddings and chat completions.
- Firestore stores embedded code chunks and serves vector search.
- The backend orchestrates query and RCA requests.
- The worker handles asynchronous ingestion.
- Loki, Prometheus, and Tempo provide runtime observability evidence to the RCA agent.
- Redis is optional and only used for ingest job status tracking.

## Protocol Notes

- `backend -> NATS JetStream`: NATS client protocol over TCP via the NATS server.
- `worker -> Azure OpenAI` for embeddings: HTTPS requests to the Azure OpenAI REST API.
- `backend/agent -> Azure OpenAI` for chat: HTTPS requests to the Azure OpenAI REST API.
- `worker -> Firestore` for vector storage: Google Cloud Firestore client calls, implemented over Google APIs/gRPC by the SDK.
- `backend -> Firestore` for vector search: same Firestore client path, via the Google SDK.
- `agent -> Loki / Prometheus / Tempo`: HTTP API calls (`LogQL`, `PromQL`, `TraceQL` queries, depending on the backend).
- `backend/worker -> Redis`: Redis protocol via the async Redis client, when Redis is available.
