# RAG Platform App — Inventory

> Ce fichier liste les composants importants de ce repo et leur raison d'être.
> Maintenu par Claude. Ne pas éditer manuellement.
> Dernière mise à jour : 2026-04-02

---

## Architecture applicative

| Composant | Rôle |
|-----------|------|
| **rag-backend** (FastAPI) | API REST : reçoit les requêtes d'ingestion et de query, orchestre via NATS et LangGraph |
| **rag-worker** | Consumer NATS : exécute le pipeline d'ingestion (clone → parse → chunk → embed → store) |
| **NATS JetStream** | Bus de messages entre backend et worker — découple l'API du traitement lourd |
| **Redis** | Cache de suivi des jobs d'ingestion (status, progress, chunks_indexed) |
| **GCP Firestore** | Vector store principal — stocke les chunks de code avec leurs embeddings |
| **Azure OpenAI** | Embedding (text-embedding-3-small) + LLM chat (gpt-4o) |
| **Vertex AI (GCP)** | Fallback LLM (gemini-1.5-pro) si Azure OpenAI indisponible |

---

## Backend — Endpoints clés

| Endpoint | Rôle |
|----------|------|
| `POST /ingest/repo` | Déclenche l'ingestion asynchrone d'un repo Git entier |
| `GET /ingest/status/{job_id}` | Poll le statut du job via Redis |
| `POST /query` | Recherche vectorielle simple dans Firestore |
| `POST /query/rca` | Agent LangGraph RCA — boucle multi-tours avec 4 outils d'observabilité |

---

## Agent RCA (LangGraph)

Boucle agentique pour Root Cause Analysis dans un environnement microservices :

| Nœud | Rôle |
|------|------|
| `plan_search` | LLM choisit quels outils appeler selon la question |
| `execute_tools` | Exécution async des outils, accumulation des résultats |
| `correlate_findings` | LLM synthétise des hypothèses à partir des preuves |
| `synthesize_root_cause` | Rapport final : root_cause, confidence, evidence_summary |

**Outils disponibles pour l'agent :**

| Outil | Source | Pourquoi |
|-------|--------|----------|
| `search_code_vectors` | Firestore | Cherche dans le code indexé (hot path RCA) |
| `query_loki_logs` | Loki (OTel Demo) | Analyse des logs applicatifs |
| `query_prometheus_metrics` | Prometheus (OTel Demo) | Analyse des métriques |
| `query_tempo_traces` | Tempo (OTel Demo) | Analyse des traces distribuées |

---

## Pipeline Worker

| Étape | Lib principale | Pourquoi |
|-------|---------------|----------|
| `clone_repo` | gitpython | Shallow clone (depth=1) pour performance |
| `parse_files` | stdlib | Détection langage par extension, mapping service OTel Demo |
| `chunk_documents` | llama-index CodeSplitter (tree-sitter) | Découpe sémantique du code, fallback SentenceSplitter |
| `embed_chunks` | llama-index + Azure OpenAI | Batch de 16, modèle text-embedding-3-small |
| `store_chunks` | google-cloud-firestore | Upsert Firestore par batch de 500, ID chunk déterministe (sha256) |

---

## Dépendances clés

| Lib | Pourquoi |
|-----|----------|
| **FastAPI + uvicorn** | API async, OpenAPI auto-généré |
| **pydantic / pydantic-settings** | Validation config et env vars |
| **nats-py** | Client NATS JetStream (async) |
| **redis[hiredis]** | Cache rapide, hiredis pour perf |
| **langchain-core / langchain-openai** | Abstraction LLM + Azure OpenAI |
| **langgraph** | DAG de l'agent RCA (boucle conditionnelle) |
| **langchain-google-vertexai** | Fallback LLM Vertex AI |
| **llama-index-core** | Chunking + embedding pipeline |
| **llama-index-embeddings-azure-openai** | Embedding Azure OpenAI dans llama-index |
| **google-cloud-firestore** | Vector store GCP |
| **docling** | Parsing de documents (worker) |
| **gitpython** | Clone Git dans le worker |
| **sse-starlette** | Streaming SSE pour /query/rca |
| **httpx** | Clients HTTP async (Loki, Prometheus, Tempo) |

---

## CI/CD

| Workflow | Déclencheur | Ce qu'il fait |
|----------|-------------|---------------|
| `ci.yml` | Push main / PR → main | CodeQL + Ruff lint + Docker build + Trivy scan (CRITICAL/HIGH) |
| `release.yml` | Merge sur main | semantic-release → bump version → Docker build/push → Trivy → Cosign sign → SBOM |

**Choix importants :**
- **Trivy** : scan local dans CI (pas de service externe) — préférence explicite
- **semantic-release** via `cycjimmy/semantic-release-action@v4` — automatise versions + changelog
- **Cosign** (keyless Sigstore) : signature des images Docker pour la supply chain
- **SBOM** SPDX JSON : attestation attachée à chaque image pushée sur GHCR
- **Pas de Dependabot/Renovate** — choix délibéré

---

## Scripts

| Script | Rôle |
|--------|------|
| `scripts/smoke-test.sh` | Test e2e : health → ingest repo OTel Demo → poll status → query vectorielle |
