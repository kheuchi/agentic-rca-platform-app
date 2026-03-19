"""Ingest routes — document and repo ingestion via NATS JetStream."""

import json
import uuid
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingest"])


class IngestRequest(BaseModel):
    document_id: str
    content: str
    metadata: dict = {}


class RepoIngestRequest(BaseModel):
    repo_url: str
    branch: str = "main"
    services: list[str] = []
    file_patterns: list[str] = ["**/*.py", "**/*.go", "**/*.java", "**/*.ts"]


@router.post("/ingest")
async def ingest(req: IngestRequest, request: Request):
    nc = request.app.state.nc
    if not nc or nc.is_closed:
        raise HTTPException(503, "NATS not connected")

    payload = json.dumps({
        "document_id": req.document_id,
        "content": req.content,
        "metadata": req.metadata,
    }).encode()

    js = nc.jetstream()
    ack = await js.publish("rag.ingest", payload)
    logger.info("Published document %s (seq=%d)", req.document_id, ack.seq)

    return {"status": "queued", "document_id": req.document_id, "seq": ack.seq}


@router.post("/ingest/repo")
async def ingest_repo(req: RepoIngestRequest, request: Request):
    nc = request.app.state.nc
    if not nc or nc.is_closed:
        raise HTTPException(503, "NATS not connected")

    job_id = str(uuid.uuid4())
    payload = json.dumps({
        "job_id": job_id,
        "repo_url": req.repo_url,
        "branch": req.branch,
        "services": req.services,
        "file_patterns": req.file_patterns,
    }).encode()

    js = nc.jetstream()
    ack = await js.publish("rag.ingest.repo", payload)
    logger.info("Queued repo ingest %s (job=%s, seq=%d)", req.repo_url, job_id, ack.seq)

    return {"status": "queued", "job_id": job_id, "seq": ack.seq}


@router.get("/ingest/status/{job_id}")
async def ingest_status(job_id: str, request: Request):
    redis_client = request.app.state.redis_client
    if not redis_client:
        raise HTTPException(503, "Redis not available")

    status = await redis_client.hgetall(f"ingest:job:{job_id}")
    if not status:
        raise HTTPException(404, f"Job {job_id} not found")

    return {
        "job_id": job_id,
        "status": status.get("status", "unknown"),
        "progress": float(status.get("progress", 0)),
        "chunks_indexed": int(status.get("chunks_indexed", 0)),
        "error": status.get("error"),
    }
