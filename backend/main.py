"""RAG Backend — FastAPI service that receives documents and queries."""

import os
import json
import logging

import nats
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RAG Backend", version="0.1.0")

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6380"))
REDIS_KEY = os.getenv("REDIS_KEY", "")

nc = None
redis_client = None


class IngestRequest(BaseModel):
    document_id: str
    content: str
    metadata: dict = {}


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5


@app.on_event("startup")
async def startup():
    global nc, redis_client
    try:
        nc = await nats.connect(NATS_URL)
        js = nc.jetstream()
        await js.add_stream(name="RAG", subjects=["rag.>"], max_msgs=10_000)
        logger.info("Connected to NATS at %s", NATS_URL)
    except Exception as e:
        logger.warning("NATS not available: %s", e)

    try:
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_KEY or None,
            ssl=REDIS_PORT == 6380,
            decode_responses=True,
        )
        await redis_client.ping()
        logger.info("Connected to Redis at %s", REDIS_HOST)
    except Exception as e:
        logger.warning("Redis not available: %s", e)
        redis_client = None


@app.on_event("shutdown")
async def shutdown():
    if nc:
        await nc.close()
    if redis_client:
        await redis_client.close()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/ingest")
async def ingest(req: IngestRequest):
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


@app.post("/query")
async def query(req: QueryRequest):
    # Phase 4: will call Azure AI Search / Vertex AI for vector search
    return {
        "status": "not_implemented",
        "message": "Vector search will be available after Phase 4 (AI Search + OpenAI embeddings)",
    }
