# Phase 5 — Chainlit + Langfuse

French version: [10-chainlit-langfuse.md](./10-chainlit-langfuse.md)

## Goal

This phase adds a Chainlit conversational UI on top of the existing RCA agent and enriches Langfuse traces with useful session context.

## What is implemented in this repo

- a Chainlit app in `chainlit_ui/app.py`
- direct reuse of the existing LangGraph RCA agent
- per-session user settings:
  - `service`
  - `time_range`
  - whether to show intermediate steps
  - whether to show the final evidence summary
- Langfuse metadata propagated into LLM calls:
  - `langfuse_session_id`
  - `langfuse_user_id`
  - `langfuse_tags`
  - run metadata (`question`, `service`, `time_range`, `stage`, `iteration`)

## Langfuse environment variables

The backend now supports:

- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_BASE_URL`

Legacy compatibility remains:

- `LANGFUSE_HOST` is still accepted as an alias for `LANGFUSE_BASE_URL`

## Local run

Install dependencies:

```bash
pip install -r chainlit_ui/requirements.txt
```

Run Chainlit:

```bash
chainlit run chainlit_ui/app.py
```

## Architecture notes

- the Chainlit UI does not call a separate HTTP API: it imports the application backend to reuse `rca_agent` directly
- this keeps the RCA logic in one place
- `rag-dev` stays on Azure: the UI does not change provider strategy and does not enable Vertex

## Not covered here

- Kubernetes deployment for Chainlit
- Chainlit authentication
- Chainlit persistence through a PostgreSQL data layer
- Kubecost rollout
