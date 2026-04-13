# RAG Platform — Project Context

> Ce fichier est la source de vérité du projet. Mis à jour à chaque fin de phase.
> Il est dupliqué sur les 3 repos. Quand tu ouvres une nouvelle session Claude, dis-lui de lire ce fichier.

## Dernière mise à jour : 2026-04-13

## Architecture globale

```
rag-platform-infra   → Terraform : AKS, VNet, Azure OpenAI, GCP Firestore, WIF
rag-platform-gitops  → ArgoCD : NATS, KEDA, Crossplane, OTel Demo, deployments rag-dev
rag-platform-app     → Code : FastAPI backend + NATS worker (Python)
```

## Cluster AKS — État actuel

| Composant | Namespace | État |
|-----------|-----------|------|
| ArgoCD | argocd | Running — https://13.92.13.5 |
| NATS JetStream | nats | Running — service `nats-helm`, stream `RAG` |
| KEDA | keda-system | Running |
| Crossplane | crossplane-system | Running |
| rag-backend | rag-dev | Running — 1/1 |
| rag-worker | rag-dev | Running, mais instable au restart (JetStream durable binding) |
| OTel Demo | otel-demo | Running — Grafana + Prometheus + OTel Collector |
| Redis | Azure (Crossplane) | Basic C0 |

## Services cloud

| Service | Cloud | Détails |
|---------|-------|---------|
| AKS aks-rag-dev | Azure East US | D2s_v3 system + D4s_v3 spot x0-2 |
| Azure OpenAI oai-rag-dev | Azure East US | gpt-4o + text-embedding-3-small, S0 |
| GCP Firestore | GCP us-central1 | Native mode, collection `code-chunks`, 1536 dims |
| Vertex AI | GCP | gemini-1.5-pro (LLM fallback, non encore testé) |

## Env vars dans le cluster (rag-dev)

```
NATS_URL=nats://nats-helm.nats.svc.cluster.local:4222
AZURE_OPENAI_ENDPOINT=https://eastus.api.cognitive.microsoft.com/  (secret rag-ai-secrets)
AZURE_OPENAI_API_KEY=<secret rag-ai-secrets>
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
GCP_PROJECT_ID=mon-rag-perso-2026
FIRESTORE_DATABASE=(default)
FIRESTORE_COLLECTION=code-chunks
GCP_LOCATION=us-central1
LOKI_URL=http://otel-demo-loki.otel-demo.svc.cluster.local:3100
PROMETHEUS_URL=http://otel-demo-prometheus-server.otel-demo.svc.cluster.local:9090
TEMPO_URL=http://otel-demo-tempo.otel-demo.svc.cluster.local:3200
```

## Phases

| Phase | Repo | État |
|-------|------|------|
| 0 — Structure repos | tous | ✅ Done |
| 1 — Networking Azure + GCP + WIF | infra | ✅ Done |
| 2 — AKS provisionné | infra | ✅ Done |
| 3 — ArgoCD + NATS + KEDA + Crossplane | gitops | ✅ Done |
| 4.1-4.4 — FastAPI backend + worker + LangGraph RCA | app | ✅ Done |
| 4.5a — Azure OpenAI + Firestore + AKS spot (Terraform) | infra | ✅ Done 2026-03-29 |
| 4.5b — GitOps : env vars + OTel Demo + KEDA fix | gitops | ✅ Done 2026-03-29 |
| 4.5c — Swap Azure AI Search → Firestore dans le code | app | ✅ Done 2026-03-29 |
| **4.5d — e2e smoke test** | **app** | **✅ Done 2026-04-13** |
| 4.6 — Multi-cloud validation (Vertex AI fallback) | app | ⏳ Ready to start |
| 5 — Langfuse + Kubecost | tous | ⬜ Pending |
| 6 — RAG + MCP hybride (navigation code live) | app | ⬜ Planned |

## Phase 4.5d — Smoke test progress (2026-04-13)

### Run final du 2026-04-13 — Steps 0-4 validés bout en bout ✅

Pipeline cold path **fonctionnel de bout en bout** sur le mini corpus, après merge des PRs app et gitops puis redéploiement des pods :

- **Step 0** ✅ Health check backend
- **Step 1** ✅ `/ingest/repo` queued
- **Step 2** ⚠️ Endpoint `/ingest/status/{id}` renvoie toujours 503 (Redis non dispo). Script reste en fallback sur polling `/query`.
- **Step 3** ✅ `/query` retourne **3 résultats** sur `src/checkout/main.go` avec `service_filter=checkoutservice`
- **Step 4** ✅ `/query/rca` retourne un rapport RCA HTTP 200 avec `confidence=0.78`, sans restart backend

Validation complémentaire post-run :

- `/query` avec `service_filter=checkoutservice` retourne **3 résultats**
- les résultats Firestore exposent maintenant `service_name=checkoutservice` (plus `unknown`)
- le pod `rag-backend` redéployé charge le fix `asyncio.to_thread(...)` dans [backend/agent/tools/code_search.py](backend/agent/tools/code_search.py)
- le pod `rag-worker` redéployé charge la nouvelle map OTel Demo dans [worker/pipeline/parse.py](worker/pipeline/parse.py)

### Découvertes et fixes finalisés le 2026-04-13

9. **OTel Demo a renommé ses services** — `src/checkoutservice/` → `src/checkout/`, idem pour cart/payment/shipping/etc. Cela cassait `parse.py/OTEL_DEMO_SERVICE_MAP`. **Fix appliqué et maintenant déployé** : map augmentée avec nouveaux + anciens paths, canonical service name conservé `checkoutservice`.

10. **`service_filter` restauré dans le smoke test** — après rebuild/redeploy worker validé, [scripts/smoke-test.sh](scripts/smoke-test.sh) Step 3 filtre à nouveau sur `checkoutservice`.

11. **Blocker mémoire / réactivité RCA résolu** — le bump gitops `rag-backend` à **1Gi** était nécessaire mais pas suffisant. Le backend bloquait encore les probes pendant la recherche Firestore synchrone. **Fix appliqué et déployé** dans [backend/agent/tools/code_search.py](backend/agent/tools/code_search.py) : recherche Firestore déplacée hors event loop via `asyncio.to_thread(...)`.

12. **Release pipeline images débloqué** — la release `v1.6.2` a d'abord échoué sur Trivy (`CVE-2026-28390` dans OpenSSL du base image). **Fix appliqué** dans `backend/Dockerfile` et `worker/Dockerfile` via `apt-get upgrade`, puis nouvelle release `v1.6.3` publiée avec images backend/worker poussées sur GHCR.

### Blockers résolus

1. **✅ KEDA ScaledObject** — fixé : `minReplicaCount: 0 → 1` + `service.ports.monitor.enabled: true` dans nats-app.yaml (syntaxe native chart NATS v1.2.6 au lieu de `service.merge`). Le port 8222 est maintenant exposé sur le service `nats-helm`.

2. **✅ Worker scheduling** — le noeud system (D2s_v3, 2 vCPU) était saturé (50 pods, 105% CPU, disk pressure). Résolu par :
   - Retrait de la toleration spot du worker (le spot pool autoscaler refusait de provisionner)
   - Réduction resources worker (50m/256Mi au lieu de 100m/512Mi)
   - Langfuse mis à replicas=0 (Phase 5, CrashLoopBackOff car nécessite PostgreSQL)
   - 8 services OTel Demo non essentiels désactivés (adService, emailService, etc.) → CPU passé de 105% à 49%

3. **✅ GCP credentials** — le backend et le worker n'avaient pas de credentials GCP pour Firestore. Résolu temporairement par :
   - Création SA GCP `rag-app@mon-rag-perso-2026.iam.gserviceaccount.com` avec rôle `datastore.user`
   - Secret K8s `gcp-credentials` avec clé JSON, monté en volume dans les deux deployments
   - `GOOGLE_APPLICATION_CREDENTIALS=/var/secrets/gcp/key.json`
   - **TODO Phase future** : remplacer par Workload Identity Federation complète (Azure AD → AKS pod identity → GCP)

4. **✅ Firestore vector indexes** — le backend échouait sur `/query` avec `Missing vector index configuration`. Résolu par création des index Firestore sur `code-chunks` :
   - index vectoriel `embedding` (1536 dims)
   - index composite `service_name + __name__ + embedding`
   - État vérifié via API Firestore Admin : **READY**

### Blockers restants

5. **⏳ Redis** — non-critique. Le secret `redis-rag-dev-conn` dépend de Crossplane Azure Redis (Basic C0). Le worker fonctionne sans Redis (status tracking dégradé, `optional: true`).

6. **⏳ Azure OpenAI rate limiting (429)** — le tier S0 rate-limit les embeddings. Pattern observé : 2 à 4 batches de 16 chunks passent, puis 429 avec retry 11-60s. Pour 264 chunks → indexation très lente. Non bloquant pour le mini corpus, mais gênant pour des corpus plus larges.

7. **✅ Worker JetStream restart bug** — résolu + validé en cluster 2026-04-13. Le correctif `subscribe_with_retry` dans [worker/main.py](worker/main.py) boucle sur `JetStream.Error "already bound"` avec un backoff 5s jusqu'à libération du durable. Testé via `kubectl delete pod` + purge NATS : le nouveau pod rebind proprement les deux durables `rag-worker` / `rag-worker-repo`.

8. **✅ Corpus smoke test trop large pour S0** — résolu 2026-04-13. Le défaut de `scripts/smoke-test.sh` reste le mini corpus `src/checkout/main.go` (1 fichier, ~quelques chunks). Override possible via env vars `SERVICES` et `FILE_PATTERNS` pour repasser sur `**/*.go` une fois le pipeline stable.

### État actuel du pipeline (2026-04-13 après run)

- Backend **Running** : `/health` OK, Firestore accessible, `/query` ✅ retourne résultats réels
- **Cold path complet VALIDÉ** : clone → parse → chunk → embed (sans 429 sur mini corpus) → **store 16/16 Firestore** ✅
- `/query` : `Code search: 3 results` côté backend, réponse HTTP 200 avec count=3
- `/query/rca` : ✅ retourne un rapport RCA avec confiance `0.78` sur le mini corpus
- Service name stocké : ✅ `checkoutservice` sur `src/checkout/main.go`

### Tests manuels réalisés (cumulé)

- Vérification cluster WSL : contexte `aks-rag-dev` OK
- Firestore project `mon-rag-perso-2026`, collection `code-chunks`, index vectoriel `READY`
- Run 2026-04-13 : `smoke-test.sh` mini corpus `src/checkout/main.go` → Steps 0-3 verts, Step 4 OOM
- NATS stream `RAG` purgée 2x pour dégager jobs stale 264-chunks hérités des runs précédents
- Worker restart (delete pod) : `subscribe_with_retry` rebinde proprement les deux durables

### Décisions prises

- **Pas de MCP maintenant** : MCP sera introduit après stabilisation de la plateforme (jusqu'à Chainlit + Langfuse), pas pendant le debug du smoke test
- **Mini corpus d'abord** : objectif court terme = prouver RAG + agent RCA sur un corpus checkout minimal, pas sur tout le service
- **Langfuse plus tard** : Azure Foundry monitoring suffit pour voir quotas/tokens/429 ; Langfuse restera utile en Phase 5 pour tracing LLM/agent

### Prochaine étape

1. ✅ `subscribe_with_retry` validé en cluster 2026-04-13 (bind clean au restart worker)
2. ✅ Mini corpus appliqué + défaut mis à jour après rename OTel demo : `src/checkout/main.go`
3. ✅ `store complete` obtenu sur le mini corpus
4. ✅ `/query` retourne 3 résultats avec `service_filter=checkoutservice`
5. ✅ `/query/rca` retourne un rapport RCA sans restart backend
6. ⏭️ **Phase 4.6 — validation Vertex AI fallback** : provoquer/émuler le fallback Azure OpenAI → Vertex AI et vérifier la continuité des réponses LLM/embeddings

## Décisions d'architecture

### Pourquoi RAG plutôt que MCP seul

Le choix du RAG (et non MCP pur) repose sur :

- **Recherche sémantique cross-repo** : avec N repos, un agent MCP ne peut pas ouvrir chaque fichier — le RAG pré-indexe et retrouve par intention ("gestion d'erreur checkout") en ~100ms.
- **Confluence / docs non structurées** : un index vectoriel est nécessaire pour 1000+ pages. MCP lit page par page, trop lent.
- **Coût token maîtrisé** : le RAG retourne 5-10 chunks, pas 50 fichiers entiers.
- **Portfolio** : démontre un pipeline data complet (ingestion async, event-driven, autoscaling, multi-cloud).

**Phase 6 prévue : hybride RAG + MCP** — RAG pour la découverte sémantique, MCP pour la navigation directe (lecture fichiers, arborescence, git blame, doc Confluence). L'agent RCA utilisera les deux.

## Comptes

- Azure : Free Trial, subscription `9cee7c54-1645-4fd0-b027-18f4d49cae57`
- GCP : projet `mon-rag-perso-2026`, billing `0178A4-931D60-35809B` (Open)
- GitHub : `kheuchi`

## Conventions

- Conventional commits (`feat:`, `fix:`, `chore:`) → semantic-release auto sur main
- Feature branches + PRs, jamais directement sur main
- `wsl` prefix pour toutes les commandes CLI (az, gcloud, kubectl, terraform)
- Secrets K8s via `kubectl create secret` — jamais dans git
- Platform Helm apps (`argocd/apps/*.yaml`) : `kubectl apply` manuel, pas via ArgoCD gitops
