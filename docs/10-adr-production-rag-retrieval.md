# ADR 010 - Retrieval cible pour un RAG + agent de production

Statut : propose

Date : 2026-04-21

## Contexte

Le projet actuel utilise Firestore comme vector store pour une demonstration RAG :

```text
chunk -> embedding -> Firestore vector search -> chunks -> agent/LLM
```

Ce choix est suffisant pour un MVP pedagogique : il montre clairement les briques de base
du RAG, reste simple a operer, et s'inscrit bien dans une architecture multi-cloud.

Pour une plateforme de production, le besoin change. Un agent fiable doit retrouver des
preuves exactes et semantiques dans du code, des documents, des runbooks, des tickets ou
des signaux techniques. La recherche vectorielle seule est rarement le meilleur compromis.

## Decision

Pour un RAG + agent de production, la cible recommandee est une couche de retrieval
abstraite exposee a l'agent sous forme d'un outil stable, par exemple :

```text
retrieve_context(query, filters, top_k)
```

Cette couche cache les details du moteur de recherche et execute, selon le backend choisi :

```text
retrieval =
  query understanding / query rewrite
  metadata filtering
  BM25 keyword search
  vector search
  hybrid fusion
  reranking
  deduplication
  context packing
```

Le pattern de production recommande est :

```text
BM25 / keyword search
+ vector search
+ rank fusion, souvent RRF
+ semantic reranking
+ context packing avec citations
```

Firestore reste acceptable pour un MVP vector-only. Pour une cible production, privilegier
un moteur ou service qui supporte nativement la recherche hybride et le reranking, ou qui
s'integre proprement avec un reranker.

## Options et positionnement

### Firestore vector search

Role : vector store simple et serverless.

Bon choix pour :

- MVP et demonstrations.
- Stockage document simple avec metadata.
- Faible charge operationnelle.
- Comprendre les briques RAG bas niveau.

Limites :

- Principalement vector search dans ce projet.
- Pas le choix ideal pour BM25 + vector + reranking integres.
- Moins adapte a une recherche technique tres precise sur code, logs ou identifiants.

Decision : conserver pour la demo actuelle, ne pas en faire la cible par defaut d'un RAG
agentique production.

### Azure AI Search

Role : moteur de recherche manage, configurable, tres adapte au RAG de production.

Capacites cles :

- Full-text/BM25.
- Vector search.
- Hybrid search dans une requete unique.
- Fusion des resultats avec RRF.
- Semantic ranker pour reranking.
- Filtres metadata, facettes, scoring profiles.
- Integration naturelle avec Azure OpenAI.

Bon choix pour :

- RAG production avec peu d'operations.
- Documents, code, runbooks, tickets, knowledge bases.
- Besoin de hybrid search + reranking sans operer un cluster search complet.

Decision : choix recommande par defaut si la plateforme est Azure ou si l'on veut un
retrieval manage mais encore controlable.

References :

- https://learn.microsoft.com/azure/search/hybrid-search-overview
- https://learn.microsoft.com/azure/search/semantic-ranking

### OpenSearch

Role : moteur de recherche flexible, open source / cloud-agnostic, plus bas niveau.

Capacites cles :

- BM25 natif.
- kNN / neural search / vector search.
- Hybrid search via search pipelines.
- Normalization processors ou rank fusion.
- Rerank processor avec cross-encoder ou modele externe.
- Controle fin des mappings, analyzers, pipelines et scoring.

Bon choix pour :

- Besoin de controle fin.
- Cloud-agnostic ou self-managed.
- Unification possible de code, docs, logs ou traces textuelles dans un meme moteur.
- Equipes capables d'operer et tuner OpenSearch.

Limites :

- Plus d'ops : sizing, shards, heap, snapshots, securite, upgrades.
- Plus de configuration pour obtenir une experience RAG propre.

Decision : alternative recommandee quand le controle, l'ouverture ou l'unification des
sources prime sur la simplicite operationnelle.

References :

- https://docs.opensearch.org/docs/3.0/vector-search/ai-search/hybrid-search/
- https://docs.opensearch.org/latest/search-plugins/search-pipelines/rerank-processor/

### Vertex AI Search

Role : service Google de search enterprise et generative search.

Capacites cles :

- Recherche semantique et comprehension de requetes.
- Ranking manage.
- Filtres, boosts, controls.
- Generative answers / conversational search selon les cas.
- Connecteurs et ingestion managee pour documents, sites ou donnees structurees.

Bon choix pour :

- Application de recherche enterprise ou knowledge base Google-native.
- Besoin d'une experience search packagee.
- Donnees documentaires, sites web, bases de connaissance.

Decision : choix recommande pour une experience de recherche managee cote Google,
particulierement quand l'objectif est une search app plus qu'un pipeline RAG custom.

Reference :

- https://cloud.google.com/generative-ai-app-builder/docs/introduction

### Vertex AI RAG Engine

Role : abstraction RAG managee dans Vertex AI.

Capacites cles :

- Ingestion de donnees dans un corpus RAG.
- Transformation / chunking.
- Embedding.
- Indexing / corpus.
- Retrieval.
- Integration avec Gemini via retrieval tools.
- Reranking via Vertex AI Ranking API ou LLM reranker.
- Peut utiliser Vertex AI Search ou Vertex AI Vector Search comme backend selon les cas.

Bon choix pour :

- Architecture full Google avec Gemini.
- Besoin d'un RAG manage sans construire toute la plomberie.
- Applications ou l'on accepte de s'appuyer sur les abstractions Vertex.

Decision : choix recommande par defaut pour un RAG + agent full Google, lorsque l'on veut
une abstraction RAG plus directe que Vertex AI Search.

References :

- https://cloud.google.com/vertex-ai/generative-ai/docs/rag-engine/rag-overview
- https://cloud.google.com/vertex-ai/generative-ai/docs/rag-engine/retrieval-and-ranking

### BigQuery vector search

Role : moteur analytique avec capacites vector search.

Capacites cles :

- Stockage et requetes SQL a grande echelle.
- Vector search avec indexes vectoriels.
- Jointures SQL, filtres analytiques, donnees historisees.
- Integration naturelle avec donnees deja presentes dans BigQuery.

Bon choix pour :

- Donnees deja dans BigQuery.
- Retrieval sur datasets analytiques, logs historises, events, tables metier.
- Besoin de combiner SQL, filtres, aggregations et similarite vectorielle.
- Scenarios batch, exploration, evaluation ou retrieval analytique.

Limites :

- Ce n'est pas une abstraction RAG complete.
- Le context packing, le reranking, l'orchestration agent et une partie du retrieval
  applicatif restent a construire autour.
- Pas le choix le plus simple pour une API RAG temps reel generaliste si les donnees ne
  vivent pas deja dans BigQuery.

Decision : utiliser BigQuery comme backend retrieval lorsque la source de verite est
analytique/tabulaire ou deja dans BigQuery. Ne pas le confondre avec Vertex AI RAG Engine.

Reference :

- https://cloud.google.com/bigquery/docs/vector-search-intro

## Recommandations par contexte

### Projet actuel

Conserver Firestore :

- la plateforme est une demo ;
- le vector-only retrieval suffit pour valider le cold path ;
- le but est de comprendre les briques RAG ;
- changer maintenant ajouterait de la complexite sans benefice immediat.

### Cible production Azure

Utiliser :

```text
Azure OpenAI embeddings + Azure AI Search hybrid search + semantic ranker + agent
```

Azure AI Search devient le retrieval backend principal.

### Cible production Google

Choix recommande selon l'objectif :

```text
Agent RAG full Google generaliste :
  Vertex AI RAG Engine + Vertex AI Ranking API + Gemini

Search app enterprise :
  Vertex AI Search + Gemini

Donnees analytiques deja dans BigQuery :
  BigQuery vector search + SQL filters + Vertex AI Ranking API + Gemini

Retrieval vectoriel bas niveau custom :
  Vertex AI Vector Search + custom retrieval service + Ranking API + Gemini
```

### Cible cloud-agnostic ou controle fin

Utiliser :

```text
OpenSearch hybrid search + rerank processor/model externe + agent
```

OpenSearch devient le moteur central de retrieval, avec plus de responsabilite
operationnelle.

## Regles pratiques

### Embeddings et vector store

L'embedding provider ne doit pas obligatoirement etre dans le meme cloud que le vector
store.

Ce qui est obligatoire :

```text
Meme modele d'embedding
Meme dimension
Meme espace vectoriel
```

Les documents et les requetes doivent etre embeddes avec un modele compatible. Melanger
des embeddings Azure 1536 dimensions avec des embeddings Vertex 768 dimensions dans le
meme index casse la recherche ou degrade fortement la pertinence.

### Retrieval

La phase retrieval ne se limite pas au vector search. En production, elle inclut aussi :

- comprehension / rewriting de requete ;
- filtres metadata et ACL ;
- recherche keyword/BM25 ;
- recherche vectorielle ;
- fusion hybride ;
- reranking ;
- deduplication ;
- context packing.

### Agent

L'agent ne doit pas connaitre les details du moteur de retrieval.

Il doit appeler un outil stable :

```text
retrieve_context(query, filters, top_k)
```

L'implementation peut ensuite changer de Firestore vers Azure AI Search, OpenSearch,
Vertex AI RAG Engine ou BigQuery sans changer le raisonnement agentique.

## Consequences

Positives :

- clarifie pourquoi Firestore est suffisant pour la demo ;
- donne une cible production plus robuste ;
- separe les responsabilites entre agent, retrieval service et backend search ;
- rend possible une migration future sans reecrire l'agent.

Negatives :

- une vraie couche retrieval production ajoute de la complexite ;
- hybrid search et reranking doivent etre evalues, pas seulement configures ;
- chaque backend a ses compromis de cout, latence, lock-in et operations.

## Decision finale resumee

```text
Demo actuelle :
  Firestore vector search

Production par defaut Azure :
  Azure AI Search

Production par defaut Google RAG :
  Vertex AI RAG Engine

Production Google search app :
  Vertex AI Search

Production Google analytique :
  BigQuery vector search + Ranking API autour

Production controle fin / cloud-agnostic :
  OpenSearch
```
