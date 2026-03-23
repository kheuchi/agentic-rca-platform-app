---
name: Project Progress & Current State
description: What has been implemented so far and where to resume — tracks completed phases, current versions, deployed state
type: project
---

## Repo state as of 2026-03-23

### Infrastructure (unchanged)
- Cluster: aks-rag-dev (East US, 2 nodes Standard_DC2as_v5)
- NATS JetStream: namespace nats, service nats-helm (port 4222)
- KEDA 2.16.1: namespace keda (ScaledObject — stream name mismatch rag-ingest vs RAG still needs fix in gitops)
- Redis Azure: via Crossplane (Basic tier — cache only, not vector store)
- ArgoCD: https://13.92.13.5

### CI/CD & Supply Chain (completed earlier)
- semantic-release (cycjimmy/semantic-release-action@v4), auto CHANGELOG
- CodeQL SAST, Trivy vulnerability gate, Cosign keyless signing, SPDX SBOM

### Phase 4 Progress

**✅ Phase 4.1: Foundation (commit 8f55f0f)**
- Backend restructured: main.py → config.py + routers/ + agent/ + llm/
- Worker restructured: config.py + pipeline/ modules
- pydantic-settings for all env vars
- LLM providers: Azure OpenAI (primary) + Vertex AI (fallback)
- Dockerfiles updated (Docling system deps)

**✅ Phase 4.2: Cold Path — Ingestion Pipeline (commit 8051c3a)**
- clone.py, parse.py, chunk.py, embed.py, store.py — full pipeline
- Dual NATS subscription (rag.ingest + rag.ingest.repo)
- Job status tracking via Redis
- Azure AI Search as vector store (not Redis)

**✅ Phase 4.3: Hot Path — Observability Tools (commit 392da25)**
- code_search.py: hybrid search Azure AI Search
- loki.py: LogQL, prometheus.py: PromQL, tempo.py: TraceQL
- All async, httpx, @langchain_core.tools.tool decorated

**🔜 Phase 4.4: LangGraph RCA Agent (NEXT)**
- agent/graph.py, agent/nodes.py — build the StateGraph
- POST /query/rca endpoint with SSE streaming
- POST /query → simple vector search

**Pending:**
- Phase 4.5: Deploy OTel Demo on AKS, end-to-end test
- Phase 4.6: Multi-cloud validation
- Keycloak auth, Chainlit UI (future phases)
- Azure AI Search + Azure OpenAI provisioning (infra repo)

**Why:** Track what's done vs what's next so future sessions can resume without re-exploring.
**How to apply:** Read this at start of new conversation. Check git log for changes since 2026-03-23.
