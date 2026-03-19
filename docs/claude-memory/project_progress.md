---
name: Project Progress & Current State
description: What has been implemented so far and where to resume — tracks completed phases, current versions, deployed state
type: project
---

## Repo state as of 2026-03-19

### Completed
- **Scaffold**: FastAPI backend (/health, /ingest, /query stub) + NATS JetStream worker (durable consumer, no-op processing)
- **Docker**: Both services containerized (python:3.12-slim), images on ghcr.io/kheuchi/rag-backend and rag-worker
- **CI/CD**: semantic-release (cycjimmy/semantic-release-action@v4), auto CHANGELOG, Docker push via matrix strategy
- **Supply chain security**: CodeQL SAST (Python), Trivy vulnerability gate (HIGH/CRITICAL), Cosign keyless signing, SPDX SBOM with Cosign attestation
- **Dependency fixes**: redis bumped to 7.3.0 (PyJWT now optional), dropped explicit PyJWT pin, fixed starlette CVE-2025-62727 via FastAPI bump
- **Bug fixes**: Cosign digest issue (was using empty $DIGEST from metadata-action, fixed to use build-push-action output), Trivy action bumped from 0.28.0 to 0.35.0

### Current versions
- Latest release: ~v1.1.4 (check git tags for exact)
- FastAPI 0.135.1, redis 7.3.0, nats-py 2.10.0, pydantic 2.11.1

### Deployed on AKS
- Cluster: aks-rag-dev (East US, 2 nodes Standard_DC2as_v5)
- NATS JetStream: namespace nats, service nats-helm (port 4222)
- KEDA 2.16.1: namespace keda (ScaledObject on rag-worker — NOTE: stream name mismatch rag-ingest vs RAG, needs fix in Phase 4.1)
- Redis Azure: via Crossplane (Basic tier — NOT suitable for RediSearch, but OK since we use Azure AI Search now)
- ArgoCD: https://13.92.13.5

### NOT yet implemented (Phase 4)
- Code ingestion pipeline (cold path)
- LangGraph RCA agent (hot path)
- Keycloak authentication
- Chainlit UI
- OpenTelemetry Demo deployment
- Azure AI Search / Azure OpenAI provisioning
- Architecture plan written: docs/phase4-architecture.md

### Known issues to fix in Phase 4.1
- KEDA ScaledObject stream name: `rag-ingest` should be `RAG` (in rag-platform-gitops)
- CodeQL needs `push` trigger on main in ci.yml (currently only on PR, never ran because user pushes directly to main)
- Backend /query returns hardcoded stub `{"status": "not_implemented"}`
- Worker process_message is a no-op (log + sleep 100ms + ack)

**Why:** Track what's done vs what's next so future sessions can resume without re-exploring the codebase.
**How to apply:** Read this memory at the start of any new conversation to know the current state. Check git log for any changes since 2026-03-19.
