# Step 4 - Direct vector query (`/query`)

English version. Version francaise: [04-query-vector.md](./04-query-vector.md)

> Full flow: [Step 1](./01-request-entry.en.md) -> [Step 2](./02-nats-publish.en.md) -> [Step 3](./03-worker-pipeline.en.md) -> **[Step 4]** -> [Step 5](./05-rca-agent.en.md) -> [Phase 6 - MCP](./06-mcp-future.en.md)

---

## Overview

`POST /query` is the shortest retrieval path:
- no NATS
- no LangGraph
- no streaming

The backend:
1. embeds the natural-language query
2. searches Firestore vectors
3. returns the closest code chunks

## HTTP handler

`backend/routers/query.py`:

```python
@router.post("/query")
async def query(req: QueryRequest):
    results = await search_code_vectors.ainvoke({
        "query": req.query,
        "service_filter": req.service_filter,
        "top_k": req.top_k,
    })
    return {"results": results, "count": len(results)}
```

## Query embedding

`backend/llm/embeddings.py` embeds the query with:
- Azure OpenAI first
- Vertex AI fallback

The query and the indexed chunks must share the same embedding space.

## Firestore vector search

`backend/agent/tools/code_search.py`:
- embeds the query
- optionally filters on `service_name`
- calls Firestore `find_nearest(...)`
- returns normalized results

Current implementation detail:
- the blocking Firestore search is moved off the asyncio event loop with `asyncio.to_thread(...)`
- this prevents probe starvation during RCA calls that reuse the same tool

## Optional service filter

When `service_filter` is present, the query is narrowed to one service:

```python
query_ref = query_ref.where("service_name", "==", service_filter)
```

## Response shape

Each result contains:
- `file_path`
- `service_name`
- `language`
- `content`
- `score`

Lower `score` means a closer cosine distance.

## Required Firestore indexes

The search relies on:
- a vector index on `embedding`
- a composite index for filtered vector search with `service_name`

## Summary

| Operation | File | Detail |
|---|---|---|
| receive request | `backend/routers/query.py` | `QueryRequest` |
| embed query | `backend/llm/embeddings.py` | Azure OpenAI or Vertex fallback |
| vector search | `backend/agent/tools/code_search.py` | Firestore `find_nearest` |
| filter by service | `backend/agent/tools/code_search.py` | optional service filter |
| return results | `backend/routers/query.py` | JSON payload |

---

Next: [Step 5 - LangGraph RCA agent](./05-rca-agent.en.md)
