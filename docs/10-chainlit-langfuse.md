# Phase 5 — Chainlit + Langfuse

Version anglaise : [10-chainlit-langfuse.en.md](./10-chainlit-langfuse.en.md)

## Objectif

Cette etape ajoute une UI conversationnelle Chainlit pour piloter l'agent RCA existant, tout en enrichissant les traces Langfuse avec un contexte de session utile.

## Ce qui est implemente dans ce repo

- une app Chainlit dans `chainlit_ui/app.py`
- reutilisation directe de l'agent LangGraph existant
- reprise des settings utilisateur par session :
  - `service`
  - `time_range`
  - affichage ou non des etapes intermediaires
  - affichage ou non du resume de preuves final
- propagation des metadonnees Langfuse dans les appels LLM :
  - `langfuse_session_id`
  - `langfuse_user_id`
  - `langfuse_tags`
  - metadonnees de run (`question`, `service`, `time_range`, `stage`, `iteration`)

## Variables d'environnement Langfuse

Le backend supporte maintenant :

- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_BASE_URL`

Compatibilite legacy conservee :

- `LANGFUSE_HOST` reste accepte comme alias de `LANGFUSE_BASE_URL`

## Lancement local

Installer les dependances :

```bash
pip install -r chainlit_ui/requirements.txt
```

Lancer Chainlit :

```bash
chainlit run chainlit_ui/app.py
```

## Notes d'architecture

- la UI Chainlit n'appelle pas une API HTTP separee : elle importe le backend applicatif pour reutiliser directement `rca_agent`
- cela permet de garder la logique RCA dans un seul endroit
- `rag-dev` reste sur Azure : l'UI ne change pas la strategie provider et n'active pas Vertex

## Perimetre non couvert ici

- deploiement Kubernetes de Chainlit
- authentification Chainlit
- persistence Chainlit via data layer PostgreSQL
- rollout Kubecost
