"""Query routes — vector search and RCA agent."""

import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.graph import rca_agent
from agent.rca import build_initial_state, build_rca_response, build_stream_payload
from agent.tools.code_search import search_code_vectors

logger = logging.getLogger(__name__)

router = APIRouter(tags=["query"])


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    service_filter: str | None = None


class RCAQueryRequest(BaseModel):
    question: str
    service: str | None = None
    time_range: str = "1h"
    stream: bool = False


@router.post("/query")
async def query(req: QueryRequest):
    """Simple vector search against Firestore."""
    results = await search_code_vectors.ainvoke({
        "query": req.query,
        "service_filter": req.service_filter,
        "top_k": req.top_k,
    })
    return {"results": results, "count": len(results)}


@router.post("/query/rca")
async def query_rca(req: RCAQueryRequest):
    """Run the LangGraph RCA agent. Supports sync or SSE streaming."""
    initial_state = build_initial_state(
        question=req.question,
        service=req.service,
        time_range=req.time_range,
        trace_tags=["fastapi", "rca"],
    )

    if req.stream:
        return StreamingResponse(
            _stream_rca(initial_state),
            media_type="text/event-stream",
        )

    result = await rca_agent.ainvoke(initial_state)

    return build_rca_response(result)


async def _stream_rca(initial_state: dict):
    """Stream RCA agent steps as Server-Sent Events."""
    async for event in rca_agent.astream(initial_state, stream_mode="updates"):
        for node_name, update in event.items():
            payload = build_stream_payload(node_name, update)
            yield f"data: {json.dumps(payload)}\n\n"

    yield "data: [DONE]\n\n"
