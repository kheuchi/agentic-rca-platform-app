# rag-platform-app

Version francaise. English version: [README.md](./README.md)

Code applicatif de la plateforme RAG multi-cloud.

Ce depot contient :
- `rag-backend` : API FastAPI pour l'ingestion, la recherche et le RCA
- `rag-worker` : consommateur NATS JetStream pour l'ingestion asynchrone

L'infrastructure et les manifests Kubernetes vivent dans des depots separes :
- `rag-platform-infra`
- `rag-platform-gitops`

## Documentation

La documentation technique est disponible dans les deux langues.

| Sujet | English | Francais |
|---|---|---|
| Architecture | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | [docs/ARCHITECTURE.fr.md](docs/ARCHITECTURE.fr.md) |
| Etape 1 - entree de requete | [docs/01-request-entry.en.md](docs/01-request-entry.en.md) | [docs/01-request-entry.md](docs/01-request-entry.md) |
| Etape 2 - publication NATS | [docs/02-nats-publish.en.md](docs/02-nats-publish.en.md) | [docs/02-nats-publish.md](docs/02-nats-publish.md) |
| Etape 3 - pipeline worker | [docs/03-worker-pipeline.en.md](docs/03-worker-pipeline.en.md) | [docs/03-worker-pipeline.md](docs/03-worker-pipeline.md) |
| Etape 4 - requete vectorielle | [docs/04-query-vector.en.md](docs/04-query-vector.en.md) | [docs/04-query-vector.md](docs/04-query-vector.md) |
| Etape 5 - agent RCA | [docs/05-rca-agent.en.md](docs/05-rca-agent.en.md) | [docs/05-rca-agent.md](docs/05-rca-agent.md) |
| Phase 6 - futur MCP | [docs/06-mcp-future.en.md](docs/06-mcp-future.en.md) | [docs/06-mcp-future.md](docs/06-mcp-future.md) |
| Etat actuel de `otel-demo` | [docs/07-otel-demo-current-state.en.md](docs/07-otel-demo-current-state.en.md) | [docs/07-otel-demo-current-state.md](docs/07-otel-demo-current-state.md) |
| Follow-up metriques | [docs/08-metrics-follow-up.en.md](docs/08-metrics-follow-up.en.md) | [docs/08-metrics-follow-up.md](docs/08-metrics-follow-up.md) |
| Reference API | [docs/09-api-reference.en.md](docs/09-api-reference.en.md) | [docs/09-api-reference.md](docs/09-api-reference.md) |
| Phase 5 - Chainlit + Langfuse | [docs/10-chainlit-langfuse.en.md](docs/10-chainlit-langfuse.en.md) | [docs/10-chainlit-langfuse.md](docs/10-chainlit-langfuse.md) |

## Ou l'agent RCA cherche logs, metriques et traces

L'agent RCA ne lit pas les logs, metriques ou traces directement dans des buckets, des PVC ou des bases de donnees.

Il interroge les backends d'observabilite via leurs API HTTP :
- logs : API HTTP OpenSearch, via `backend/agent/tools/opensearch.py`
- metriques : API HTTP Prometheus avec PromQL, via `backend/agent/tools/prometheus.py`
- traces : API HTTP Jaeger, via `backend/agent/tools/jaeger.py`

Dans le deploiement AKS actuel, ces services tournent dans le namespace `otel-demo`. L'agent parle aux systemes d'observabilite, pas a leur couche de stockage sous-jacente.

### Stockage physique dans le cluster actuel

La question du stockage physique est distincte de l'API appelee par l'agent.

La verification cluster du 2026-04-13 a montre que :
- les metriques Prometheus sont stockees dans le pod `otel-demo-prometheus-server` via `--storage.tsdb.path=/data`
- ce repertoire `/data` est monte sur un volume `EmptyDir`, pas sur un PVC
- il n'y a ni PVC ni StatefulSet dans le namespace `otel-demo` pour les workloads d'observabilite actuellement visibles

Donc, dans l'environnement actuel, les metriques Prometheus sont physiquement stockees sur un stockage ephemere local au pod et sont perdues si le pod est recree.

Pour OpenSearch et Jaeger :
- la stack OpenTelemetry demo est configuree pour router les logs vers OpenSearch et les traces vers Jaeger
- ces backends etaient absents ou desalignes dans le namespace live lors du controle du 2026-04-14
- les repos applicatif et GitOps sont maintenant alignes sur `OpenSearch + Prometheus + Jaeger`, mais un redeploiement reste necessaire pour que le cluster converge vers cet etat voulu

## Architecture d'execution

Un schema plus detaille est disponible dans [docs/ARCHITECTURE.fr.md](docs/ARCHITECTURE.fr.md).

## Pourquoi ce design

- Ingestion event-driven : le backend publie dans NATS et repond tout de suite.
- Traitement decouple : le worker execute clone -> parse -> chunk -> embed -> store de facon asynchrone.
- Multi-cloud : Azure OpenAI pour LLM/embeddings, Firestore pour la recherche vectorielle, Vertex AI en fallback.
- Controle de provider : le backend et le worker supportent maintenant `fallback` et `switch` explicite entre Azure OpenAI et Vertex AI.
- RCA : l'agent LangGraph combine recherche de code et observabilite live.
- Separation claire : le code applicatif est ici, les manifests restent dans `rag-platform-gitops`.

## Stack RAG conventionnelle — positionnement du projet

Un pipeline RAG de production standard couvre six couches. Cette section met en regard les choix mainstream et les decisions prises dans ce projet.

### 1. Ingestion et parsing

Transformer des PDF, HTML, pages Confluence, fichiers de code en texte propre.

- Mainstream : **Unstructured.io**, **LlamaParse**, **Docling** (IBM), **Apache Tika**
- Pour le code source specifiquement : **tree-sitter** (chunking au niveau AST — utilise par Cursor, Sourcegraph, GitHub Copilot)

### 2. Chunking

Decouper le texte en fenetres de ~200-1000 tokens avec overlap.

- Mainstream : **LangChain `RecursiveCharacterTextSplitter`**, **LlamaIndex `SemanticSplitter`** (detection de changement de sujet par embeddings), **Chonkie**
- Pattern enterprise : *parent-child chunking* — indexer de petits chunks, retourner le chunk parent plus large au LLM

### 3. Embeddings

- SaaS mainstream : **OpenAI `text-embedding-3-small` / `-3-large`**, **Cohere Embed v3**, **Voyage AI**
- Open-source self-hosted : **BGE-M3**, **E5-mistral-7b**, **nomic-embed-text** (servis via HuggingFace TGI ou Infinity)
- Ce projet : **Azure OpenAI `text-embedding-3-small`** (1536 dims) — meme famille de modeles qu'OpenAI, avec residentialite Azure

### 4. Vector store

Trois familles en pratique :

**Bases vectorielles dediees** (le plus courant sur les projets greenfield)

| DB | Notes |
|---|---|
| Pinecone | Leader SaaS historique, serverless depuis 2024, cher a l'echelle |
| Qdrant | Rust, rapide, open-source, monte fort |
| Weaviate | Hybrid search natif (BM25 + vector) |
| Milvus / Zilliz | Scale massif |
| Chroma | Prototypage uniquement |

**Extensions de DB existantes** (prefere quand la DB est deja en place)

| DB | Notes |
|---|---|
| pgvector (PostgreSQL) | Choix par defaut si l'equipe a deja du Postgres |
| Elasticsearch / OpenSearch | Hybrid BM25 + kNN solide, largement adopte |
| MongoDB Atlas Vector Search | Pour les stacks MongoDB |

**Ce projet : Firestore** — utilise le type `VECTOR` + l'operateur `FIND_NEAREST` ajoutes fin 2024. Non conventionnel, mais elimine un systeme supplementaire a operer. Compromis : pas de hybrid search BM25 natif.

### 5. Retrieval et reranking

- La **recherche hybride** (BM25 + vector + fusion RRF) est quasi-obligatoire en production — la recherche purement vectorielle rate les correspondances exactes sur les mots-cles
- **Reranking** apres le premier retrieval : **Cohere Rerank v3** (SaaS), **BGE-reranker** / **Jina Reranker** (open-source), **ColBERT** (late-interaction, haute precision)
- **Transformation de requete** : HyDE, multi-query expansion, decomposition de requete — LangChain et LlamaIndex ont des primitives pour tout ca

### 6. Orchestration

- **LangChain** — le standard historique, tres utilise, critique pour sa complexite
- **LangGraph** (sous-projet LangChain) — modele state machine pour RAG agentique et raisonnement multi-etapes ; la reference actuelle pour les workflows RAG complexes — c'est ce qu'utilise l'agent RCA
- **LlamaIndex** — plus fort sur l'indexation et les query engines
- **Haystack** (deepset) — courant dans l'enterprise europeen
- **DSPy** (Stanford) — adoption croissante, traite les prompts comme des programmes a optimiser

### Pourquoi pas Airflow ou un ETL avance ?

Apache Airflow est un **orchestrateur de workflows batch** base sur des DAGs (Directed Acyclic Graph — graphe sans cycle, ou chaque etape s'execute dans un ordre fixe de dependances sans boucle possible). Il est concu pour des pipelines schedules orientes analytique (DataOps, entrainement ML).

L'ingestion RAG a des besoins differents :

| Besoin | Airflow | Pattern event-driven |
|---|---|---|
| Ingerer un fichier des son arrivee | Poll toutes les N minutes | Immediat (trigger queue/webhook) |
| Retry granulaire par chunk | Lourd a configurer | Natif dans NATS / Kafka |
| Scale horizontal des workers | Pas natif | KEDA + Kubernetes |
| Faible latence (indexer en secondes) | Overhead DAG eleve | Natif |
| Simplicite operationnelle | Postgres + Redis + webserver + scheduler | Un seul broker de queue |

Airflow apparait quand meme dans des projets RAG en grande entreprise, mais pour des cas specifiques : re-indexation batch complete apres une mise a jour du modele d'embedding, pipeline data engineering en amont depuis un data warehouse (Snowflake, BigQuery), ou sync batch depuis Confluence ou Jira. Alternatives modernes : **Prefect**, **Dagster**, **Temporal**.

Ce projet utilise **NATS JetStream + KEDA** — le pattern d'ingestion event-driven correspond mieux a la charge que tout orchestrateur batch.

### Observabilite et evaluation (souvent oubliees dans les POCs)

Cette couche separe un prototype d'un RAG de production.

- **Langfuse** — traces, eval, gestion des prompts (open-source) — cible Phase 5 dans ce repo
- **LangSmith** — equivalent SaaS de LangChain
- **Arize Phoenix** — eval + observabilite, open-source
- **Ragas** — framework d'eval : faithfulness, context precision, answer relevancy
- **TruLens** — eval avec feedback functions

### Positionnement resume

| Couche | Defaut mainstream | Ce projet | Notes |
|---|---|---|---|
| Parsing code | tree-sitter | tree-sitter | Aligne |
| Embeddings | OpenAI | Azure OpenAI | Meme famille de modeles |
| Vector store | Pinecone / Qdrant / pgvector | **Firestore** | Pas de hybrid search natif |
| Orchestration | LangGraph | LangGraph | Standard actuel pour RAG agentique |
| LLM | GPT-4o | GPT-4o + Vertex Gemini fallback | Bonus multi-cloud |
| Observabilite | Langfuse | Langfuse (Phase 5) | Etat de l'art |
| Trigger ingestion | Kafka / SQS / Airflow | **NATS JetStream + KEDA** | Event-driven, scale a zero |
| Infrastructure | K8s manage | AKS + Crossplane + ArgoCD + KEDA | Au-dessus de la moyenne pour un projet portfolio |

**Ce qui ameliorerait la qualite du retrieval au-dela du setup actuel :**
- Hybrid search : ajouter un passage BM25 (OpenSearch tourne deja dans le cluster via `otel-demo`)
- Reranker : Cohere Rerank ou BGE-reranker sur top-20 → top-5 avant d'envoyer au LLM
- Evaluation : Ragas ou LangSmith sur un dataset golden pour mesurer faithfulness et context precision
- Transformation de requete : au minimum HyDE pour ameliorer le recall sur les requetes courtes ou ambigues

La Phase 6 (hybride RAG + MCP) s'aligne sur les patterns emergents chez Anthropic et Cursor — decouverte semantique via RAG, navigation directe via MCP.

## Redis — usage actuel et usages futurs potentiels

### Usage actuel

Redis est actuellement utilise uniquement pour le **suivi du statut des jobs** : le worker ecrit la progression de l'ingestion (`cloning`, `parsing`, `embedding`, `done`) dans un hash Redis avec un TTL de 24h, et le backend le lit quand le client poll `/ingest/status/{job_id}`. C'est du best-effort — si Redis est indisponible, le worker continue quand meme.

Note : Redis ne fonctionne pas encore dans le cluster (variables d'env non injectees dans le deployment worker). C'est un blocker connu documente dans context.md.

### TODO — usages futurs potentiels

- [ ] **Cache des reponses LLM** — mettre en cache la reponse finale de `/query` sur `hash(query)`. Meilleur ROI etant donne le rate limit S0 d'Azure OpenAI (erreurs 429). LangChain propose `RedisSemanticCache` qui cache sur la similarite, pas seulement sur la correspondance exacte.
- [ ] **Deduplication d'ingestion** — ecrire une cle `indexed:{repo_url}:{commit_sha}` apres une ingestion reussie. Evite les chunks en double dans Firestore si `/ingest/repo` est appele deux fois sur le meme commit.
- [ ] **Rate limiting** — compteur a fenetre glissante par utilisateur/IP pour proteger le quota Azure OpenAI. Un middleware FastAPI ecrivant `ratelimit:{ip}:{minute}` avec `INCR` + `EXPIRE` couvre ca en ~10 lignes.
- [ ] **Historique de session conversationnel** — stocker les N derniers messages par session Chainlit. LangGraph gere ses propres checkpoints, mais Redis est adapte pour l'etat de session ephemere entre les redemarrages.
- [ ] **Pub/Sub pour les evenements de fin d'ingestion** — publier un evenement `ingest.done` quand le worker termine, s'abonner dans le backend pour envoyer une notification WebSocket a Chainlit. NATS couvre deja ca dans l'archi actuelle, donc redondant sauf si NATS est retire.

## Structure du depot

```text
rag-platform-app/
|-- backend/
|-- worker/
|-- docs/
|-- scripts/
|-- catalog.yaml
|-- CONTEXT.md
|-- .github/workflows/
|-- package.json
`-- CHANGELOG.md
```

## CI/CD

```text
Pull request -> ci.yml
  -> lint
  -> docker build (sans push)
  -> Trivy
  -> CodeQL

Push sur main -> release.yml
  -> semantic-release
  -> build et push ghcr.io/kheuchi/rag-backend
  -> build et push ghcr.io/kheuchi/rag-worker
  -> signature des images + SBOM
```

## Developpement local

Depuis un terminal Windows, preferer l'execution des commandes projet via `wsl`.

```bash
wsl bash -lc "cd backend && pip install -r requirements.txt && uvicorn main:app --reload"

wsl bash -lc "cd worker && pip install -r requirements.txt && python main.py"

wsl bash -lc "pip install -r chainlit_ui/requirements.txt && chainlit run chainlit_ui/app.py"

wsl bash -lc "docker run -p 4222:4222 nats:latest -js"
```

## Documentation API

FastAPI genere automatiquement la spec API a partir des routes backend.

Quand le backend est joignable, utilise :
- `/openapi.json` pour la spec OpenAPI
- `/docs` pour Swagger UI
- `/redoc` pour ReDoc

Reference des endpoints :
- [docs/09-api-reference.en.md](docs/09-api-reference.en.md)
- [docs/09-api-reference.md](docs/09-api-reference.md)

## Etat actuel

- Phase 4.5d : terminee, avec un MVP RCA valide sur `code + logs + traces`
- Les metriques restent un follow-up dedie
- Phase 4.6 : le mode `switch` est implemente et teste en live, mais la piste Vertex est maintenant en pause
- `rag-dev` doit rester sur Azure (`switch=azure`) tant que les blockers Vertex documentes ne sont pas leves
- La phase 5 est le chantier actif
- Chainlit est maintenant containerise dans ce repo et deploye dans `rag-dev` via GitOps sous la forme `rag-chainlit`
- Langfuse est maintenant declare dans GitOps comme application ArgoCD Helm avec PostgreSQL, Redis, ClickHouse et stockage compatible S3 embarques
- Etat live au 2026-04-15 : le nodepool AKS `systempool` a ete scale de 1 a 2 noeuds
- `rag-chainlit`, `rag-backend`, `langfuse-clickhouse` et `langfuse-redis` tournent apres ce scale
- Langfuse reste toutefois bloque parce que les deux noeuds passent en `DiskPressure`, ce qui empeche `langfuse-postgresql` de se scheduler proprement et laisse `langfuse-web` en attente de la base
- Le flux live complet `Chainlit -> backend/agent -> Langfuse` reste donc en attente tant que la capacite cluster n'est pas augmentee ou liberee
- Chainlit doit rester en mode simple pour l'instant : `ClusterIP` interne, pas d'auth, pas d'ingress
- L'acces interne reste possible via `kubectl port-forward -n rag-dev svc/rag-chainlit 8000:8000`

## Strategie de provider

Le runtime supporte deux strategies :
- `fallback` : Azure OpenAI d'abord, Vertex AI seulement en cas d'erreur
- `switch` : forcer explicitement le provider sans attendre une erreur

Variables d'environnement :
- `LLM_PROVIDER_STRATEGY=fallback|switch`
- `LLM_SWITCH_PROVIDER=azure|vertex`
- `EMBEDDING_PROVIDER_STRATEGY=fallback|switch`
- `EMBEDDING_SWITCH_PROVIDER=azure|vertex`

Exemple pour forcer Azure dans `rag-dev` :

```env
LLM_PROVIDER_STRATEGY=switch
LLM_SWITCH_PROVIDER=azure
EMBEDDING_PROVIDER_STRATEGY=switch
EMBEDDING_SWITCH_PROVIDER=azure
```

Decision courante et etat de validation au 2026-04-14 :
- la selection `switch` est couverte par des tests unitaires
- le routage live `switch=vertex` est valide en cluster : backend et worker selectionnent bien Vertex
- l'API Vertex AI est maintenant activee sur `mon-rag-perso-2026`
- le compte de service des pods a maintenant `roles/aiplatform.user`
- les embeddings Vertex repondent maintenant correctement
- `/query` echoue encore car l'index vectoriel Firestore actuel attend 1536 dimensions alors que le chemin Vertex teste produit 768
- `/query/rca` echoue encore car le modele chat Vertex configure `gemini-1.5-pro` n'est pas disponible ou accessible sur ce projet
- `rag-dev` est repasse sur Azure pour garder une plateforme stable tant que ces blockers existent
- le fallback runtime sur erreur reste volontairement non valide tant que la piste Vertex est en pause
- les settings par defaut de ce repo gardent maintenant Azure selectionne via `switch`
- Phase 5 : reprise cote app pour le tracing Langfuse
- Phase 6 : planifiee

## Focus phase 5 dans ce repo

La phase 5 couvre plusieurs depots. Dans `rag-platform-app`, le focus est l'observabilite LLM via Langfuse pour le backend et l'agent RCA.

Variables d'environnement utiles :
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_BASE_URL`

Notes d'implementation :
- Langfuse est optionnel : si les cles sont absentes, le backend continue sans tracing
- les callbacks Langfuse sont attaches aux invocations des modeles avec des metadonnees de session
- une UI Chainlit locale est disponible dans `chainlit_ui/app.py`
- le deploiement Kubernetes reference aussi `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` et `LANGFUSE_BASE_URL`
- le secret Kubernetes `langfuse-secrets` n'est volontairement pas committe et depend encore du premier bootstrap Langfuse pour creer les cles API projet
- pendant le rollout live du 2026-04-15, le secret de bootstrap PostgreSQL a aussi du contenir la cle `postgres-password` en plus de `password`
- Kubecost releve surtout du travail d'infrastructure et de deploiement GitOps, pas de ce repo applicatif
