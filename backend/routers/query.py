"""Query routes — vector search and RCA agent."""

import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.graph import rca_agent
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
    initial_state = {
        "question": req.question,
        "service": req.service,
        "time_range": req.time_range,
        "code_context": [],
        "log_findings": [],
        "metric_findings": [],
        "trace_findings": [],
        "hypotheses": [],
        "current_step": "start",
        "iteration": 0,
        "max_iterations": 8,
        "root_cause": "",
        "confidence": 0.0,
        "evidence_summary": {},
        "messages": [],
    }

    if req.stream:
        return StreamingResponse(
            _stream_rca(initial_state),
            media_type="text/event-stream",
        )

    result = await rca_agent.ainvoke(initial_state)

    return {
        "root_cause": result.get("root_cause", ""),
        "confidence": result.get("confidence", 0.0),
        "evidence": result.get("evidence_summary", {}),
        "iterations": result.get("iteration", 0),
        "hypotheses": result.get("hypotheses", []),
    }


async def _stream_rca(initial_state: dict):
    """Stream RCA agent steps as Server-Sent Events."""
    async for event in rca_agent.astream(initial_state, stream_mode="updates"):
        for node_name, update in event.items():
            payload = {
                "node": node_name,
                "step": update.get("current_step", node_name),
                "iteration": update.get("iteration"),
            }

            if node_name == "synthesize_root_cause":
                payload["root_cause"] = update.get("root_cause", "")
                payload["confidence"] = update.get("confidence", 0.0)
                payload["evidence"] = update.get("evidence_summary", {})

            yield f"data: {json.dumps(payload)}\n\n"

    yield "data: [DONE]\n\n"
