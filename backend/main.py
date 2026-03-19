"""RAG Backend — FastAPI service for document ingestion and RCA queries."""

import logging
from contextlib import asynccontextmanager

import nats
import redis.asyncio as redis
from fastapi import FastAPI

from config import Settings
from routers.ingest import router as ingest_router
from routers.query import router as query_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        app.state.nc = await nats.connect(settings.nats_url)
        js = app.state.nc.jetstream()
        await js.add_stream(name="RAG", subjects=["rag.>"], max_msgs=10_000)
        logger.info("Connected to NATS at %s", settings.nats_url)
    except Exception as e:
        logger.warning("NATS not available: %s", e)
        app.state.nc = None

    try:
        app.state.redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_key or None,
            ssl=settings.redis_port == 6380,
            decode_responses=True,
        )
        await app.state.redis_client.ping()
        logger.info("Connected to Redis at %s", settings.redis_host)
    except Exception as e:
        logger.warning("Redis not available: %s", e)
        app.state.redis_client = None

    yield

    # Shutdown
    if app.state.nc:
        await app.state.nc.close()
    if app.state.redis_client:
        await app.state.redis_client.close()


app = FastAPI(title="RAG Backend", version="0.2.0", lifespan=lifespan)
app.include_router(ingest_router)
app.include_router(query_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
