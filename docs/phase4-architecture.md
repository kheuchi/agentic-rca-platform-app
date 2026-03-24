# Phase 4 Architecture: RAG-based Root Cause Analysis (RCA)

## 1. Executive Summary

Phase 4 transforms the current scaffolded `rag-platform-app` into a functioning RCA tool that correlates source code knowledge with live observability data to perform automated root cause analysis, similar to Datadog's Bits AI. The system has two data paths: a **cold path** (code repo ingested into a vector store via NATS JetStream) and a **hot path** (real-time queries against Loki, Prometheus, and Tempo). A **LangGraph agent** orchestrates multi-step reasoning across both paths.

---

## 2. Demo Application: OpenTelemetry Astronomy Shop

**Choice: `open-telemetry/opentelemetry-demo`**

- 11+ microservices in Go, Python, Java, .NET, TypeScript, Rust
- Ships with fully instrumented observability: logs, metrics, distributed traces out of the box
- Built-in fault injection (`featureFlags` service) to create real failures for RCA demos
- Helm chart includes Grafana, Prometheus, Jaeger/Tempo, and OpenTelemetry Collector
- MIT-licensed, actively maintained

Alternative considered: Grafana TNS. Rejected — too simple (3 services) to demonstrate meaningful cross-service RCA.

---

## 3. Vector Store: Cloud-Native Search Services

### Primary: Azure AI Search
- Managed vector search with hybrid (keyword + vector) retrieval
- Native integration with Azure OpenAI embeddings
- Built-in semantic ranking, filters, and facets
- Provisioned via Terraform in `rag-platform-infra`
- LlamaIndex has first-class `AzureAISearchVectorStore` integration

### Secondary: Vertex AI Search (GCP)
- Managed vector search on GCP side
- Native integration with Vertex AI embeddings
- Provides multi-cloud parity and failover

### Redis (kept for caching only)
- Agent state and session cache
- Hot-path query result caching (TTL-based)
- NOT used as vector store — stays on Basic tier, no RediSearch needed

**Azure AI Search index schema**:
```json
{
  "name": "code-chunks",
  "fields": [
    { "name": "id",           "type": "Edm.String", "key": true },
    { "name": "content",      "type": "Edm.String", "searchable": true },
    { "name": "embedding",    "type": "Collection(Edm.Single)", "dimensions": 1536, "vectorSearchProfile": "default" },
    { "name": "file_path",    "type": "Edm.String", "filterable": true },
    { "name": "service_name", "type": "Edm.String", "filterable": true, "facetable": true },
    { "name": "language",     "type": "Edm.String", "filterable": true },
    { "name": "chunk_index",  "type": "Edm.Int32" },
    { "name": "repo_url",     "type": "Edm.String", "filterable": true },
    { "name": "commit_sha",   "type": "Edm.String", "filterable": true }
  ],
  "vectorSearch": {
    "algorithms": [{ "name": "hnsw", "kind": "hnsw" }],
    "profiles": [{ "name": "default", "algorithm": "hnsw" }]
  }
}
```

---

## 4. Observability Backends (Hot Path)

The hot path queries live observability data. Too voluminous to embed — the LangGraph agent queries them on-demand via tool calls.

| Signal | Backend | Query API | Protocol |
|--------|---------|-----------|----------|
| **Logs** | Grafana Loki | LogQL via `/loki/api/v1/query_range` | HTTP |
| **Metrics** | Prometheus | PromQL via `/api/v1/query_range` | HTTP |
| **Traces** | Grafana Tempo | TraceQL via `/api/traces` + `/api/search` | HTTP |

---

## 5. Embedding & LLM Models

### Embeddings
| Provider | Model | Dimensions | Usage |
|----------|-------|-----------|-------|
| **Azure OpenAI** (primary) | `text-embedding-3-small` | 1536 | Cold path code ingestion |
| **GCP Vertex AI** (secondary) | `text-embedding-004` | 768 | Multi-cloud fallback |

### LLM (RCA Agent)
| Provider | Model | Usage |
|----------|-------|-------|
| **Azure OpenAI** (primary) | `gpt-4o` | Agent reasoning + synthesis |
| **GCP Vertex AI** (fallback) | `gemini-1.5-pro` | Failover |

Multi-cloud routing via LangChain `with_fallbacks`:
```python
llm = AzureChatOpenAI(deployment="gpt-4o").with_fallbacks([ChatVertexAI(model="gemini-1.5-pro")])
```

---

## 6. System Architecture

```
                          rag-backend (FastAPI)
  ┌──────────────────────────────────────────────────────────────────┐
  │                                                                  │
  │  POST /ingest/repo                    POST /query/rca            │
  │    { repo_url, branch, services[] }     { question, service?,    │
  │    │                                       time_range? }         │
  │    │                                       │                     │
  │    ▼                                       ▼                     │
  │  Publish to NATS                    LangGraph RCA Agent          │
  │  rag.ingest.repo                    (sync or SSE streaming)      │
  └────────┬──────────────────────────────────┬──────────────────────┘
           │                                   │
           │ NATS JetStream                    │ Direct calls
           │                                   │
  ┌────────▼──────────┐          ┌─────────────▼──────────────────────┐
  │   rag-worker      │          │       LangGraph RCA Agent          │
  │                   │          │                                     │
  │  1. git clone     │          │  Tools:                             │
  │  2. Docling parse │          │    - search_code_vectors (Azure AI Search)    │
  │  3. LlamaIndex    │          │    - query_loki_logs (LogQL)        │
  │     chunk         │          │    - query_prometheus_metrics       │
  │  4. Embed (Azure  │          │    - query_tempo_traces (TraceQL)   │
  │     OpenAI)       │          │    - correlate_findings             │
  │  5. Upsert Azure  │
  │     AI Search     │          │                                     │
  └───────┬───────────┘          └──────────┬──────────────────────────┘
          │                                  │
          ▼                                  ▼
  ┌──────────────────┐          ┌──────────────────────────────┐
  │  Azure AI Search │◄─────────│   Observability Backends     │
  │  (vector index)  │  code    │   (in-cluster, OTel Demo)    │
  │                  │  search  │                              │
  │  code-chunks     │          │  Loki    ← logs              │
  │                  │          │  Prometheus ← metrics        │
  │  Redis (cache)   │          │  Tempo   ← traces            │
  └──────────────────┘          └──────────────────────────────┘
```

---

## 7. NATS JetStream Subject Design

Extend the existing `RAG` stream (`rag.>`) with new subjects:

| Subject | Publisher | Consumer | Payload |
|---------|-----------|----------|---------|
| `rag.ingest` | backend `/ingest` | rag-worker | Existing single document (backward compat) |
| `rag.ingest.repo` | backend `/ingest/repo` | rag-worker | `{ repo_url, branch, services[], commit_sha }` |
| `rag.ingest.status` | rag-worker | backend (SSE/polling) | `{ job_id, status, progress, error? }` |

**Known issue to fix**: KEDA ScaledObject references stream `rag-ingest` but backend creates stream `RAG`. Must align in gitops.

---

## 8. API Endpoints

### Existing (kept)
- `GET /health` — unchanged
- `POST /ingest` — single document ingestion (backward compat)

### New

**`POST /ingest/repo`** — Cold path trigger
```json
{
  "repo_url": "https://github.com/open-telemetry/opentelemetry-demo",
  "branch": "main",
  "services": ["checkoutservice", "paymentservice"],
  "file_patterns": ["**/*.py", "**/*.go", "**/*.java", "**/*.ts"]
}
// Response: { "status": "queued", "job_id": "...", "seq": 42 }
```

**`GET /ingest/status/{job_id}`** — Poll ingestion progress
```json
// Response: { "job_id": "...", "status": "processing", "progress": 0.75, "chunks_indexed": 1234 }
```

**`POST /query/rca`** — RCA query (hot + cold path)
```json
{
  "question": "Why is the checkout service returning 500 errors?",
  "service": "checkoutservice",
  "time_range": "1h",
  "stream": false
}
// Response:
// {
//   "root_cause": "The checkout service is failing because...",
//   "confidence": 0.85,
//   "evidence": { "code": [...], "logs": [...], "metrics": [...], "traces": [...] },
//   "steps": [{ "tool": "search_code_vectors", "input": ..., "output_summary": ... }]
// }
```

**`POST /query`** — Simple vector search (non-RCA)
```json
// Thin wrapper around Redis vector similarity search
// Returns top-k code chunks matching the query
```

---

## 9. LangGraph RCA Agent

### 9.1 State

```python
class RCAState(TypedDict):
    question: str
    service: str | None
    time_range: str

    # Accumulated evidence
    code_context: list[dict]
    log_findings: list[dict]
    metric_findings: list[dict]
    trace_findings: list[dict]

    # Reasoning
    hypotheses: list[str]
    current_step: str
    iteration: int
    max_iterations: int          # safety limit (default 8)

    # Output
    root_cause: str
    confidence: float
    evidence_summary: dict
    messages: list[BaseMessage]
```

### 9.2 Graph

```
              ┌───────────────┐
              │   START       │
              │  parse question│
              └───────┬───────┘
                      │
              ┌───────▼───────┐
              │  plan_search  │  LLM decides which tools to call
              │  (router)     │
              └───────┬───────┘
                      │
        ┌─────────────┼─────────────┐──────────────┐
        ▼             ▼             ▼              ▼
  ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐
  │search_code│ │query_logs│ │query_    │ │query_traces  │
  │(AI Search)│ │(Loki)    │ │metrics   │ │(Tempo)       │
  └─────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘
        └─────────────┴────────────┴───────────────┘
                      │
              ┌───────▼───────┐
              │  correlate    │  LLM analyzes all evidence
              │  findings     │  with code context
              └───────┬───────┘
                      │
              ┌───────▼───────┐
              │  should       │── Yes ── loop back to plan_search
              │  continue?    │   (iteration < max)
              └───────┬───────┘
                      │ No
              ┌───────▼───────┐
              │  synthesize   │  Final RCA report
              │  root_cause   │
              └───────┬───────┘
                      │
              ┌───────▼───────┐
              │     END       │
              └───────────────┘
```

### 9.3 Tools

| Tool | Input | Action | Source |
|------|-------|--------|--------|
| `search_code_vectors` | query, service_filter, top_k | Embed query → hybrid search Azure AI Search | Cold path (Azure AI Search) |
| `query_loki_logs` | logql_query, start, end, limit | HTTP GET Loki query_range | Hot path (Loki) |
| `query_prometheus_metrics` | promql_query, start, end, step | HTTP GET Prometheus query_range | Hot path (Prometheus) |
| `query_tempo_traces` | service_name, min_duration, status | HTTP GET Tempo search API | Hot path (Tempo) |
| `correlate_findings` | current state | LLM synthesizes hypotheses | Internal |

---

## 10. Cold Path: Ingestion Pipeline (Worker)

```
rag.ingest.repo message received
        │
        ▼
  1. git clone (shallow, specific branch)
        │
        ▼
  2. File discovery
     └── Filter by file_patterns and services[]
     └── Map directories to OTel Demo service names
        │
        ▼
  3. Docling parse (per file)
     └── Code, Markdown, config files (YAML, Dockerfiles)
     └── Fallback: raw text + CodeSplitter for .py/.go/.java
        │
        ▼
  4. LlamaIndex chunking
     └── CodeSplitter (language-aware)
     └── chunk_size=512 tokens, overlap=50
     └── Preserve file_path, service_name, language in metadata
        │
        ▼
  5. Embedding (Azure OpenAI text-embedding-3-small)
     └── Batch embed with rate limit handling
        │
        ▼
  6. Azure AI Search upsert
     └── Index: code-chunks, key: <repo_hash>:<file_hash>:<chunk_idx>
        │
        ▼
  7. Publish status to rag.ingest.status
```

---

## 11. Project Structure (Target)

```
rag-platform-app/
├── backend/
│   ├── main.py                      # FastAPI app, startup/shutdown
│   ├── config.py                    # Settings via pydantic-settings
│   ├── routers/
│   │   ├── ingest.py                # /ingest, /ingest/repo, /ingest/status
│   │   └── query.py                 # /query, /query/rca
│   ├── agent/
│   │   ├── graph.py                 # LangGraph graph definition
│   │   ├── state.py                 # RCAState TypedDict
│   │   ├── nodes.py                 # plan_search, correlate, synthesize
│   │   └── tools/
│   │       ├── code_search.py       # search_code_vectors
│   │       ├── loki.py              # query_loki_logs
│   │       ├── prometheus.py        # query_prometheus_metrics
│   │       └── tempo.py             # query_tempo_traces
│   ├── llm/
│   │   ├── providers.py             # Azure OpenAI + Vertex AI fallback
│   │   └── embeddings.py            # Embedding model setup
│   ├── requirements.txt
│   └── Dockerfile
├── worker/
│   ├── main.py                      # NATS consumer (updated)
│   ├── config.py                    # Worker settings
│   ├── pipeline/
│   │   ├── clone.py                 # git clone logic
│   │   ├── parse.py                 # Docling parsing
│   │   ├── chunk.py                 # LlamaIndex chunking
│   │   ├── embed.py                 # Azure OpenAI embeddings
│   │   └── store.py                 # Azure AI Search upsert
│   ├── requirements.txt
│   └── Dockerfile
├── tests/
│   ├── test_backend/
│   └── test_worker/
└── docs/
    └── phase4-architecture.md
```

---

## 12. Dependencies (New)

### backend/requirements.txt (additions)
```
pydantic-settings>=2.0
langchain-core>=0.3
langchain-openai>=0.2              # Azure OpenAI chat + embeddings
langchain-google-vertexai>=2.0     # Vertex AI fallback
langgraph>=0.2                     # Agent orchestration
llama-index-core>=0.11
llama-index-vector-stores-azureaisearch>=0.2
llama-index-embeddings-azure-openai>=0.2
azure-search-documents>=11.6       # Azure AI Search SDK
httpx>=0.27                        # Loki/Prometheus/Tempo HTTP calls
sse-starlette>=2.0                 # SSE streaming for agent steps
```

### worker/requirements.txt (additions)
```
pydantic>=2.11
pydantic-settings>=2.0
docling>=2.0                       # Document/code parsing
llama-index-core>=0.11
llama-index-vector-stores-azureaisearch>=0.2
llama-index-embeddings-azure-openai>=0.2
azure-search-documents>=11.6       # Azure AI Search SDK
gitpython>=3.1                     # git clone
langchain-openai>=0.2              # For embeddings
```

---

## 13. Infrastructure Changes

### rag-platform-gitops
1. **OTel Demo**: Add ArgoCD Application for `open-telemetry/opentelemetry-demo` Helm chart (includes Loki, Prometheus, Tempo, Grafana)
2. **New env vars** in backend + worker deployments:
   - `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`
   - `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`, `AZURE_OPENAI_CHAT_DEPLOYMENT`
   - `AZURE_SEARCH_ENDPOINT`, `AZURE_SEARCH_API_KEY`
   - `GCP_PROJECT_ID`, `GCP_LOCATION`
   - `LOKI_URL`, `PROMETHEUS_URL`, `TEMPO_URL`
3. **Worker resources**: Increase memory to 1Gi (Docling loads ML models)
4. **KEDA fix**: Change stream name from `rag-ingest` to `RAG`

### rag-platform-infra
1. **Azure AI Search**: Terraform resource for Search service (Standard tier) + index `code-chunks`
2. **Azure OpenAI**: Terraform resource for Cognitive Services account + `gpt-4o` + `text-embedding-3-small` deployments
3. **GCP Vertex AI**: Enable API in GCP project + Vertex AI Search datastore

---

## 14. Implementation Sub-phases

### Phase 4.1: Foundation ✅ (2026-03-21)
- ✅ Restructure backend into `routers/`, `agent/`, `llm/`, `config.py`
- ✅ Restructure worker into `pipeline/` modules
- ✅ Add pydantic-settings configuration
- ✅ Set up LLM provider abstraction with Azure OpenAI + Vertex AI fallback
- ✅ Update Dockerfiles (Docling system deps)
- Commit: `8f55f0f`

### Phase 4.2: Cold Path — Ingestion Pipeline ✅ (2026-03-21)
- ✅ Implement `worker/pipeline/` (clone, parse, chunk, embed, store)
- ✅ Update `worker/main.py` for dual NATS subscription (`rag.ingest` + `rag.ingest.repo`)
- ✅ Implement `POST /ingest/repo` and `GET /ingest/status/{job_id}`
- ✅ Job status tracking via Redis (progress, chunks_indexed, errors)
- ⏳ Test: ingest OTel Demo repo into Azure AI Search (requires infra)
- Commit: `8051c3a`

### Phase 4.3: Hot Path — Observability Tools ✅ (2026-03-21)
- ✅ Implement `agent/tools/code_search.py` — hybrid search (vector + keyword) via Azure AI Search REST API
- ✅ Implement `agent/tools/loki.py` — LogQL query_range HTTP client
- ✅ Implement `agent/tools/prometheus.py` — PromQL query_range HTTP client
- ✅ Implement `agent/tools/tempo.py` — TraceQL search + trace detail fetch
- ✅ All tools async, httpx-based, `@langchain_core.tools.tool` decorated
- ⏳ Test each tool against OTel Demo stack (requires Phase 4.5 deploy)
- Commit: `392da25`

### Phase 4.4: LangGraph RCA Agent ✅ (2026-03-24)
- ✅ `agent/state.py` — Annotated reducers for list accumulation (`operator.add`, `add_messages`)
- ✅ `agent/nodes.py` — `plan_search`, `execute_tools`, `correlate_findings`, `should_continue`, `synthesize_root_cause`
- ✅ `agent/graph.py` — StateGraph: plan → execute → correlate → continue/synthesize → END
- ✅ `routers/query.py` — `POST /query` (vector search) + `POST /query/rca` (sync + SSE streaming)

### Phase 4.5: Integration & Demo
- Deploy OTel Demo to AKS via ArgoCD
- Ingest OTel Demo source code
- Trigger fault injection → run RCA query → validate agent finds root cause

### Phase 4.6: Multi-cloud Validation
- Test Vertex AI fallback
- Verify embedding compatibility
- Document multi-cloud failover

---

## 15. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Docling not ideal for raw source code | Fallback: skip Docling for .py/.go/.java, use LlamaIndex CodeSplitter directly on raw text |
| Worker OOM with Docling ML models | Increase memory limits to 1Gi; use `--no-ocr` mode |
| LLM cost explosion in agent loops | Cap `max_iterations=8`; use `gpt-4o-mini` for tool calls, `gpt-4o` for synthesis only |
| Azure AI Search cost (Standard tier) | Use Free tier (50MB, 3 indexes) for dev; Standard for prod |
| Embedding dimension mismatch multi-cloud | Azure (1536) vs Vertex (768) — maintain separate indexes per cloud, or align on 1536 |
| KEDA stream name mismatch | Fix in Phase 4.1 (gitops: `rag-ingest` → `RAG`) |
