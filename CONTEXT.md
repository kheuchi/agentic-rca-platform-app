# RAG Platform — Project Context

> Ce fichier est la source de vérité du projet. Mis à jour à chaque fin de phase.
> Il est dupliqué sur les 3 repos. Quand tu ouvres une nouvelle session Claude, dis-lui de lire ce fichier.

## Dernière mise à jour : 2026-03-29

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
| rag-worker | rag-dev | 0 replicas (scale via KEDA) |
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
| **4.5c — Swap Azure AI Search → Firestore dans le code** | **app** | **⏳ En cours** |
| 4.5d — e2e smoke test | app | ⬜ Pending |
| 4.6 — Multi-cloud validation (Vertex AI fallback) | app | ⬜ Pending |
| 5 — Langfuse + Kubecost | tous | ⬜ Pending |

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
