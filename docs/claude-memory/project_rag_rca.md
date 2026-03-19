---
name: RAG RCA Architecture Decisions
description: Phase 4 architecture for RAG-based Root Cause Analysis tool — cold path (code) + hot path (observability), Bits AI-like tool
type: project
---

Phase 4 goal: build an AI-powered RCA tool similar to Datadog Bits AI.

**Cold path**: Ingest public code repo (OpenTelemetry Demo) → Docling → LlamaIndex → Azure OpenAI embeddings → Azure AI Search (primary) / Vertex AI Search (GCP fallback)

**Hot path**: LangGraph agent queries live Loki (logs), Prometheus (metrics), Tempo (traces) in real-time — too voluminous to embed.

**Critical constraint**: the repo and the observability data MUST be from the same application — the code and logs/metrics/traces must correlate for RCA to work.

**Vector store decision**: Azure AI Search (NOT Redis RediSearch). Redis is for caching/agent state only. User explicitly corrected this — cloud-native search services, not self-managed.

**Tool stack**: Docling (parsing), LlamaIndex (RAG indexing), LangChain (LLM orchestration), LangGraph (multi-step RCA agent)

**Multi-cloud**: Azure OpenAI + AI Search primary, GCP Vertex AI + Vertex AI Search secondary

**Why:** Recreate Datadog Bits AI — correlate code changes with observability signals to automate root cause analysis.
**How to apply:** All Phase 4 decisions should ensure code ↔ observability correlation is maintained. Architecture doc: docs/phase4-architecture.md. 6 sub-phases: 4.1 (foundation) through 4.6 (multi-cloud validation).
