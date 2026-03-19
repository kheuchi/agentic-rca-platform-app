"""Query routes — vector search and RCA agent."""

import logging

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["query"])


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5


class RCAQueryRequest(BaseModel):
    question: str
    service: str | None = None
    time_range: str = "1h"
    stream: bool = False


@router.post("/query")
async def query(req: QueryRequest):
    # Phase 4.2: will call Azure AI Search for vector similarity search
    return {
        "status": "not_implemented",
        "message": "Vector search will be available after Phase 4.2",
    }


@router.post("/query/rca")
async def query_rca(req: RCAQueryRequest):
    # Phase 4.4: LangGraph RCA agent
    return {
        "status": "not_implemented",
        "message": "RCA agent will be available after Phase 4.4",
    }
