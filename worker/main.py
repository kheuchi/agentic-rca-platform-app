"""RAG Worker — NATS JetStream consumer for document and repo ingestion."""

import json
import shutil
import signal
import asyncio
import logging
from contextlib import suppress

import nats
import redis.asyncio as redis

from config import settings
from pipeline.clone import clone_repo
from pipeline.parse import parse_files
from pipeline.chunk import chunk_documents
from pipeline.embed import embed_chunks
from pipeline.store import store_chunks

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

shutdown_event = asyncio.Event()
SUBSCRIBE_RETRY_DELAY_SECONDS = 5


def handle_signal():
    shutdown_event.set()


async def get_redis_client():
    """Create a Redis client for job status tracking."""
    try:
        client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_key or None,
            ssl=settings.redis_port == 6380,
            decode_responses=True,
        )
        await client.ping()
        return client
    except Exception as e:
        logger.warning("Redis not available for status tracking: %s", e)
        return None


async def update_job_status(redis_client, job_id: str, **fields):
    """Update job status in Redis (best-effort)."""
    if not redis_client:
        return
    try:
        key = f"ingest:job:{job_id}"
        await redis_client.hset(key, mapping={k: str(v) for k, v in fields.items()})
        await redis_client.expire(key, 86400)  # TTL 24h
    except Exception:
        logger.debug("Failed to update job status for %s", job_id)


async def process_message(msg):
    """Process a single document ingestion (backward compat)."""
    try:
        data = json.loads(msg.data.decode())
        document_id = data.get("document_id", "unknown")
        content = data.get("content", "")

        logger.info("Processing document %s (%d chars)", document_id, len(content))

        # TODO Phase 4.2+: chunk → embed → upsert single documents
        await asyncio.sleep(0.1)

        await msg.ack()
        logger.info("Document %s processed successfully", document_id)
    except Exception:
        logger.exception("Failed to process message")
        await msg.nak(delay=5)


async def process_repo_ingest(msg, redis_client):
    """Process a full repo ingestion (cold path pipeline)."""
    repo_dir = None
    data = {}
    try:
        data = json.loads(msg.data.decode())
        job_id = data.get("job_id", "unknown")
        repo_url = data.get("repo_url", "")
        branch = data.get("branch", "main")
        services = data.get("services", [])
        file_patterns = data.get("file_patterns", ["**/*.py", "**/*.go", "**/*.java", "**/*.ts"])

        logger.info("Starting repo ingest job=%s repo=%s", job_id, repo_url)
        await update_job_status(redis_client, job_id, status="cloning", progress=0)

        # Step 1: Clone
        repo_dir = clone_repo(repo_url, branch)
        await update_job_status(redis_client, job_id, status="parsing", progress=0.1)

        # Step 2: Parse
        parsed_files = parse_files(repo_dir, file_patterns, services or None)
        await update_job_status(redis_client, job_id, status="chunking", progress=0.3)

        # Step 3: Chunk
        nodes = chunk_documents(parsed_files, repo_url)
        await update_job_status(redis_client, job_id, status="embedding", progress=0.5)

        # Step 4: Embed
        nodes = await embed_chunks(nodes)
        await update_job_status(redis_client, job_id, status="storing", progress=0.8)

        # Step 5: Store in Firestore
        chunks_indexed = store_chunks(nodes)
        await update_job_status(
            redis_client, job_id,
            status="completed", progress=1.0, chunks_indexed=chunks_indexed,
        )

        await msg.ack()
        logger.info("Repo ingest job=%s completed: %d chunks indexed", job_id, chunks_indexed)

    except Exception as e:
        logger.exception("Failed to process repo ingest")
        await update_job_status(
            redis_client, data.get("job_id", "unknown"),
            status="failed", error=str(e),
        )
        await msg.nak(delay=30)

    finally:
        # Cleanup cloned repo
        if repo_dir and repo_dir.exists():
            shutil.rmtree(repo_dir, ignore_errors=True)


async def subscribe_with_retry(js, subject: str, durable: str):
    """Retry JetStream durable binding until the old subscription is released."""
    while not shutdown_event.is_set():
        try:
            sub = await js.subscribe(
                subject,
                durable=durable,
                manual_ack=True,
            )
            logger.info("Subscribed to %s (durable=%s)", subject, durable)
            return sub
        except nats.js.errors.Error as e:
            if "already bound to a subscription" not in str(e):
                raise

            logger.warning(
                "Consumer durable=%s is still bound to a previous subscription, retrying in %ss",
                durable,
                SUBSCRIBE_RETRY_DELAY_SECONDS,
            )
            await asyncio.sleep(SUBSCRIBE_RETRY_DELAY_SECONDS)

    raise asyncio.CancelledError(f"Shutdown requested before subscribing to {subject}")


async def main():
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal)

    nc = await nats.connect(settings.nats_url)
    js = nc.jetstream()
    redis_client = await get_redis_client()

    logger.info("Connected to NATS at %s", settings.nats_url)

    # Subscription 1: single document ingestion (backward compat)
    sub_doc = await subscribe_with_retry(
        js,
        settings.nats_subject,
        durable="rag-worker",
    )

    # Subscription 2: repo ingestion (cold path)
    sub_repo = await subscribe_with_retry(
        js,
        settings.nats_subject_repo,
        durable="rag-worker-repo",
    )

    logger.info("Worker ready — waiting for messages")

    while not shutdown_event.is_set():
        try:
            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(sub_doc.next_msg(timeout=5)),
                    asyncio.create_task(sub_repo.next_msg(timeout=5)),
                ],
                timeout=10,
                return_when=asyncio.FIRST_COMPLETED,
            )
            # Cancel pending tasks to avoid leaks
            for task in pending:
                task.cancel()

            for task in done:
                try:
                    msg = task.result()
                    if msg.subject == settings.nats_subject_repo:
                        await process_repo_ingest(msg, redis_client)
                    else:
                        await process_message(msg)
                except (asyncio.TimeoutError, nats.errors.TimeoutError):
                    continue
        except (asyncio.TimeoutError, nats.errors.TimeoutError):
            continue

    logger.info("Shutting down...")
    with suppress(Exception):
        await sub_doc.unsubscribe()
    with suppress(Exception):
        await sub_repo.unsubscribe()
    if redis_client:
        await redis_client.close()
    await nc.drain()


if __name__ == "__main__":
    asyncio.run(main())
