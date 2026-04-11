# RAG Platform — Project Context

> Ce fichier est la source de vérité du projet. Mis à jour à chaque fin de phase.
> Il est dupliqué sur les 3 repos. Quand tu ouvres une nouvelle session Claude, dis-lui de lire ce fichier.

## Dernière mise à jour : 2026-04-11

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
| **4.5d — e2e smoke test** | **app** | **⏳ En cours** |
| 4.6 — Multi-cloud validation (Vertex AI fallback) | app | ⬜ Pending |
| 5 — Langfuse + Kubecost | tous | ⬜ Pending |
| 6 — RAG + MCP hybride (navigation code live) | app | ⬜ Planned |

## Phase 4.5d — Smoke test progress (2026-04-11)

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

6. **⏳ Azure OpenAI rate limiting (429)** — le tier S0 rate-limit les embeddings. Pattern observé : 2 à 4 batches de 16 chunks passent, puis 429 avec retry 11-60s. Pour 264 chunks → indexation très lente. Non bloquant fonctionnellement, mais gênant pour le smoke test e2e.

7. **⏳ Worker JetStream restart bug** — le worker peut redémarrer puis échouer avec :
   - `nats: JetStream.Error consumer is already bound to a subscription`
   - Cause probable : durable consumers `rag-worker` et `rag-worker-repo` encore liés à une ancienne subscription au moment du restart
   - Correctif préparé dans `worker/main.py` (retry sur bind + shutdown plus propre), **mais pas encore validé en cluster**

8. **⏳ Corpus smoke test trop large pour S0** — le smoke test actuel sur `checkoutservice` + `**/*.go` produit encore ~10 fichiers / 264 chunks, trop coûteux pour un run rapide. Décision prise : passer à un **mini corpus ciblé** pour valider RAG + RCA avant d'élargir.

### État actuel du pipeline

- Backend **Running** : `/health` OK, Firestore accessible, `/query` et `/query/rca` répondent
- `/query` ne retourne encore souvent **0 résultat** car l'ingestion n'atteint pas toujours `store complete`
- `/query/rca` répond, mais sans contexte code fiable tant que le corpus n'est pas réellement stocké dans Firestore
- Pipeline confirmé partiellement fonctionnel : clone → parse → chunk → embed OK ; **stabilité insuffisante** sur la fin de pipeline à cause des 429 + restart worker

### Tests manuels réalisés

- Vérification cluster WSL : contexte `aks-rag-dev` OK, `rag-backend` et `rag-worker` accessibles
- Firestore project confirmé : `mon-rag-perso-2026`
- Firestore indexes créés et vérifiés `READY`
- Test manuel `/query` : **HTTP 200**, mais `{"results":[],"count":0}`
- Test manuel `/query/rca` : **HTTP 200**, réponse générée par l'agent, mais peu fiable tant que `search_code_vectors` retourne 0 résultat

### Décisions prises

- **Pas de MCP maintenant** : MCP sera introduit après stabilisation de la plateforme (jusqu'à Chainlit + Langfuse), pas pendant le debug du smoke test
- **Mini corpus d'abord** : objectif court terme = prouver RAG + agent RCA sur un corpus checkout minimal, pas sur tout le service
- **Langfuse plus tard** : Azure Foundry monitoring suffit pour voir quotas/tokens/429 ; Langfuse restera utile en Phase 5 pour tracing LLM/agent

### Prochaine étape

1. Déployer/tester le correctif worker `worker/main.py` pour stabiliser les subscriptions JetStream au restart
2. Réduire le smoke test à un **mini corpus checkout** (quelques fichiers critiques, quelques dizaines de chunks max)
3. Obtenir enfin un `store complete` visible dans les logs worker
4. Retester manuellement `/query` jusqu'à obtenir des résultats Firestore non vides
5. Retester `/query/rca` avec vrai contexte code
6. Si OK → Phase 4.5d Done, puis Phase 4.6 (validation Vertex fallback)

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
