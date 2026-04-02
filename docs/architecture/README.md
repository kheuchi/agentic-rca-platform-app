# Architecture - Explications des schemas

Ce dossier contient trois schemas `draw.io` qui presentent la cible d'architecture du projet a trois niveaux de lecture:

- une vue cible complete pour le cas d'usage RAG + agents applique au Root Cause Analysis
- une vue simplifiee "agents only" pour expliquer un demarrage rapide
- une vue focalisee sur la facade API LLM et son backend Vertex AI

L'objectif de cette note est de fournir une explication synthetique mais suffisamment complete pour un manager, en citant explicitement les outils utilises.

## Vue d'ensemble

- `01-rag-agents-rca.drawio` montre l'architecture cible la plus complete
- `02-only-agents.drawio` montre une version minimale pour lancer rapidement l'approche agentique
- `03-api-llm-vertex.drawio` montre la brique transverse qui industrialise l'acces aux modeles LLM

## 1. Schema `01-rag-agents-rca.drawio`

### Ce que montre le schema

- Ce schema decrit une architecture complete de `Root Cause Analysis` assistee par IA.
- Un utilisateur pose une question via une interface conversationnelle.
- La requete est prise en charge par une API, puis par un orchestrateur agentique qui decide quels outils utiliser.
- L'agent combine des donnees temps reel d'observabilite avec une base de connaissances issue du code et de l'ingestion documentaire.

### Objectif metier

- Reduire le temps d'investigation lors d'un incident.
- Aider a identifier plus vite une cause racine probable.
- Fournir une synthese exploitable au lieu de laisser l'utilisateur consulter chaque outil separement.

### Outils et composants utilises

- `Chainlit`
  - interface de chat pour les echanges avec l'utilisateur
- `FastAPI`
  - backend HTTP expose pour les routes `/query/rca`, `/query`, `/ingest`
  - point d'entree unique de l'application
- `LangGraph`
  - orchestrateur agentique
  - pilote les etapes `plan_search`, `execute_tools`, `correlate_findings`, `synthesize_root_cause`
- `LangChain`
  - couche d'outillage pour appeler les backends externes
- `Loki`
  - source de logs via `LogQL`
- `Prometheus`
  - source de metriques via `PromQL`
- `Tempo`
  - source de traces distribuees
- `Firestore`
  - stockage des "code vectors" ou de la connaissance indexee
- `NATS JetStream`
  - bus d'ingestion asynchrone sur le cold path
- `Worker`
  - pipeline `parse`, `chunk`, `embed`
- `Redis`
  - suivi de jobs, et potentiellement cache ou etat technique
- `KEDA`
  - autoscaling des workers
- `Vertex AI`
  - acces aux modeles LLM sur GCP
  - usage de `Gemini` en natif
  - acces a `Claude Sonnet` via `Model Garden`
- `ADC / Workload Identity`
  - mecanisme d'authentification cote serveur vers GCP
- `Langfuse`
  - observabilite LLM: traces, tokens, couts

### Logique de fonctionnement

- Etape 1: l'utilisateur pose une question dans `Chainlit`.
- Etape 2: `FastAPI` recoit la requete et l'envoie a l'orchestrateur `LangGraph`.
- Etape 3: `LangGraph` decide quels outils appeler selon la question.
- Etape 4: les outils `LangChain` interrogent en parallele `Loki`, `Prometheus`, `Tempo` et la base de connaissance vectorielle.
- Etape 5: l'agent recoupe les signaux, formule des hypotheses, puis boucle si besoin pour chercher plus de preuves.
- Etape 6: l'agent produit un rapport RCA final synthese.
- Etape 7: `Langfuse` capture les traces d'execution LLM pour pilotage, debugging et suivi des couts.

### Ce qu'il faut retenir

- C'est le schema cible le plus ambitieux et le plus complet.
- Il combine un `hot path` temps reel et un `cold path` asynchrone.
- Il permet de passer d'une logique "outils isoles" a une logique "assistant d'investigation".

### Benefices

- Vision unifiee des signaux d'observabilite.
- Meilleure vitesse de diagnostic.
- Architecture extensible a d'autres outils ou d'autres modeles.
- Bon niveau d'industrialisation grace a l'ingestion, l'observabilite LLM et l'autoscaling.

### Points d'attention

- C'est aussi le schema le plus complexe a operer.
- Il necessite une bonne qualite d'instrumentation et de donnees.
- La pertinence des reponses depend du parametrage des outils et de la qualite de la couche RAG.

### Pitch manager en 30 secondes

- "Ce premier schema represente la cible complete: une plateforme qui combine observabilite, base de connaissance et orchestration agentique pour accelerer l'analyse de cause racine. L'utilisateur pose une question, l'agent va chercher les bons signaux dans les logs, metriques, traces et la base documentaire, puis renvoie une synthese directement exploitable."

## 2. Schema `02-only-agents.drawio`

### Ce que montre le schema

- Ce schema presente une version simplifiee de l'architecture.
- On garde l'interface, l'API et l'orchestrateur agentique.
- On retire la plus grande partie de la complexite d'ingestion RAG pour se concentrer sur l'appel d'outils d'observabilite.

### Objectif metier

- Lancer rapidement un premier cas d'usage agentique.
- Valider la valeur du parcours utilisateur avant d'investir dans la couche complete RAG.
- Disposer d'un socle minimal demonstrable.

### Outils et composants utilises

- `Chainlit`
  - interface conversationnelle
- `FastAPI`
  - facade API backend
- `LangGraph`
  - orchestrateur de l'agent
- `LangChain Tools`
  - execution des appels vers les outils externes
- `Loki`
  - logs
- `Prometheus`
  - metriques
- `Tempo`
  - traces
- `Vertex AI`
  - backend LLM principal
- `Gemini 1.5 Pro`
  - modele principal illustre dans ce schema
- `Claude Sonnet`
  - modele alternatif accessible via `Model Garden`
- `Auth / API Key`
  - securisation de l'API cote application

### Logique de fonctionnement

- Etape 1: l'utilisateur interagit via `Chainlit`.
- Etape 2: `FastAPI` transmet la demande a `LangGraph`.
- Etape 3: `LangGraph` planifie quels outils appeler.
- Etape 4: l'agent appelle `Loki`, `Prometheus` et `Tempo` selon le besoin.
- Etape 5: le modele LLM sur `Vertex AI` aide a interpreter les resultats et a rediger la reponse.

### Ce qu'il faut retenir

- C'est la version la plus simple pour demarrer.
- Elle prouve l'interet du raisonnement multi-outils sans construire toute la chaine RAG.
- Elle est adaptee a un MVP, une demo ou une phase d'apprentissage.

### Benefices

- Mise en oeuvre plus rapide.
- Architecture plus lisible pour des non-specialistes.
- Moins de briques a deployer et a maintenir.
- Bonne option pour tester la valeur avant d'industrialiser.

### Limites

- Moins de memoire structuree qu'une architecture avec RAG.
- Capacites plus faibles sur les questions qui exigent du contexte code ou documentaire.
- Moins de profondeur sur les analyses qui demandent de croiser historique, documentation et telemetrie.

### Pitch manager en 30 secondes

- "Ce deuxieme schema montre le mode demarrage rapide: un agent, quelques outils d'observabilite et un backend LLM. C'est l'option la plus simple pour prouver la valeur du concept, avec moins de cout et moins de complexite que la cible complete."

## 3. Schema `03-api-llm-vertex.drawio`

### Ce que montre le schema

- Ce schema isole la couche de facade LLM.
- Il montre comment plusieurs clients peuvent appeler une API unique, sans connaitre les details des modeles ou du fournisseur.
- Le backend gere le routage vers `Vertex AI`, l'authentification et la selection du bon modele.

### Objectif metier

- Standardiser l'acces aux modeles IA pour les equipes.
- Eviter que chaque application implemente sa propre integration LLM.
- Centraliser securite, gouvernance, observabilite et choix des modeles.

### Outils et composants utilises

- `FastAPI`
  - API Gateway / facade unifiee
  - routes exposees pour messages, modeles et healthcheck
- `Auth Middleware`
  - gestion de `Bearer API Key` et rate limiting
- `Model Router`
  - logique de routage vers le bon provider selon le `model_id`
- `Swagger UI`
  - documentation auto-generee
- `Vertex AI`
  - plateforme d'execution LLM cote GCP
- `ADC`
  - `Application Default Credentials`
- `Workload Identity`
  - mecanisme d'identite pour les deploiements Kubernetes
- `Gemini 1.5 Pro`
  - modele Google expose via Vertex
- `Gemini 2.0 Flash`
  - modele optimise pour d'autres profils de latence ou cout
- `Claude Sonnet 4`
  - modele accessible via `Model Garden`
- `Claude Haiku 4.5`
  - autre modele accessible via `Model Garden`
- Clients consommateurs
  - `curl` / CLI
  - applications Python / JS
  - UI de chat interne
  - agents `LangGraph`
  - autres equipes via API key

### Logique de fonctionnement

- Etape 1: un client appelle la facade `FastAPI`.
- Etape 2: l'API verifie l'authentification et applique les regles de base.
- Etape 3: le `Model Router` choisit le bon modele selon le besoin fonctionnel.
- Etape 4: le backend appelle `Vertex AI` via SDK ou REST.
- Etape 5: le client recoit une reponse uniforme, sans dependre du provider reel.

### Ce qu'il faut retenir

- Ce schema ne parle pas d'usage RCA directement.
- Il montre la brique d'industrialisation commune a plusieurs cas d'usage IA.
- C'est la couche qui apporte standardisation, controle et mutualisation.

### Benefices

- Une seule integration pour plusieurs clients.
- Changement de modele plus simple sans impact cote consommateurs.
- Meilleure gouvernance sur les acces et les couts.
- Facilite l'evolution future vers d'autres modeles ou providers.

### Points d'attention

- Cette couche devient un composant critique et doit etre fiable.
- Il faut bien gouverner les modeles exposes et les quotas.
- La qualite d'experience depend du bon routage entre latence, cout et performance.

### Pitch manager en 30 secondes

- "Ce troisieme schema montre la facade d'entreprise pour les LLM. Au lieu de laisser chaque equipe integrer directement un modele, on centralise l'acces via une API unique. Cela simplifie les usages, renforce la gouvernance et permet de changer de modele sans casser les clients."

## Comment presenter les trois schemas ensemble

- `Schema 1`
  - la cible complete orientee RCA, avec RAG, observabilite et agents
- `Schema 2`
  - la version simplifiee pour demarrer vite et valider la valeur
- `Schema 3`
  - la brique transverse de mutualisation de l'acces aux modeles

## Message de synthese pour un manager

- La demarche proposee n'est pas "tout ou rien".
- On peut commencer par une architecture legere `agents only`.
- On peut ensuite monter vers une architecture complete `RAG + agents`.
- En parallele, la facade `API LLM` permet d'industrialiser l'acces aux modeles pour plusieurs equipes et plusieurs cas d'usage.
