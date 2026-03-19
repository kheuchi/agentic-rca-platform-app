"""RAG Worker — NATS JetStream consumer for document and repo ingestion."""

import json
import signal
import asyncio
import logging

import nats

from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

shutdown_event = asyncio.Event()


def handle_signal():
    shutdown_event.set()


async def process_message(msg):
    """Process a single document ingestion (backward compat)."""
    try:
        data = json.loads(msg.data.decode())
        document_id = data.get("document_id", "unknown")
        content = data.get("content", "")

        logger.info("Processing document %s (%d chars)", document_id, len(content))

        # TODO Phase 4.2: chunk → embed → upsert to Azure AI Search
        await asyncio.sleep(0.1)

        await msg.ack()
        logger.info("Document %s processed successfully", document_id)
    except Exception:
        logger.exception("Failed to process message")
        await msg.nak(delay=5)


async def process_repo_ingest(msg):
    """Process a full repo ingestion (cold path pipeline)."""
    try:
        data = json.loads(msg.data.decode())
        job_id = data.get("job_id", "unknown")
        repo_url = data.get("repo_url", "")

        logger.info("Starting repo ingest job=%s repo=%s", job_id, repo_url)

        # TODO Phase 4.2: implement full pipeline
        # 1. clone_repo(repo_url, branch, services)
        # 2. parse_files(repo_dir, file_patterns)
        # 3. chunk_documents(documents)
        # 4. embed_chunks(chunks)
        # 5. store_chunks(chunks)
        # 6. publish status to rag.ingest.status
        await asyncio.sleep(0.1)

        await msg.ack()
        logger.info("Repo ingest job=%s completed", job_id)
    except Exception:
        logger.exception("Failed to process repo ingest")
        await msg.nak(delay=30)


async def main():
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal)

    nc = await nats.connect(settings.nats_url)
    js = nc.jetstream()

    logger.info("Connected to NATS at %s", settings.nats_url)

    # Subscription 1: single document ingestion (backward compat)
    sub_doc = await js.subscribe(
        settings.nats_subject,
        durable="rag-worker",
        manual_ack=True,
    )
    logger.info("Subscribed to %s (durable=rag-worker)", settings.nats_subject)

    # Subscription 2: repo ingestion (cold path)
    sub_repo = await js.subscribe(
        settings.nats_subject_repo,
        durable="rag-worker-repo",
        manual_ack=True,
    )
    logger.info("Subscribed to %s (durable=rag-worker-repo)", settings.nats_subject_repo)

    logger.info("Worker ready — waiting for messages")

    while not shutdown_event.is_set():
        try:
            # Poll both subscriptions
            done, _ = await asyncio.wait(
                [
                    asyncio.create_task(sub_doc.next_msg(timeout=5)),
                    asyncio.create_task(sub_repo.next_msg(timeout=5)),
                ],
                timeout=10,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                try:
                    msg = task.result()
                    if msg.subject == settings.nats_subject_repo:
                        await process_repo_ingest(msg)
                    else:
                        await process_message(msg)
                except (asyncio.TimeoutError, nats.errors.TimeoutError):
                    continue
        except (asyncio.TimeoutError, nats.errors.TimeoutError):
            continue

    logger.info("Shutting down...")
    await sub_doc.unsubscribe()
    await sub_repo.unsubscribe()
    await nc.close()


if __name__ == "__main__":
    asyncio.run(main())
