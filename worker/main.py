"""RAG Worker — NATS JetStream consumer that processes document ingestion."""

import os
import json
import signal
import asyncio
import logging

import nats

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
NATS_SUBJECT = os.getenv("NATS_SUBJECT", "rag.ingest")

shutdown_event = asyncio.Event()


def handle_signal():
    shutdown_event.set()


async def process_message(msg):
    """Process an ingested document.

    Phase 4 will add:
    - Chunking with langchain or tiktoken
    - Embedding via Azure OpenAI / Vertex AI
    - Upsert into Azure AI Search / GCP vector store
    """
    try:
        data = json.loads(msg.data.decode())
        document_id = data.get("document_id", "unknown")
        content = data.get("content", "")

        logger.info(
            "Processing document %s (%d chars)",
            document_id,
            len(content),
        )

        # TODO Phase 4: chunk → embed → upsert to vector store
        await asyncio.sleep(0.1)  # simulate processing

        await msg.ack()
        logger.info("Document %s processed successfully", document_id)
    except Exception:
        logger.exception("Failed to process message")
        await msg.nak(delay=5)


async def main():
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal)

    nc = await nats.connect(NATS_URL)
    js = nc.jetstream()

    logger.info("Connected to NATS at %s", NATS_URL)
    logger.info("Subscribing to %s", NATS_SUBJECT)

    sub = await js.subscribe(
        NATS_SUBJECT,
        durable="rag-worker",
        manual_ack=True,
    )

    logger.info("Worker ready — waiting for messages")

    while not shutdown_event.is_set():
        try:
            msg = await asyncio.wait_for(sub.next_msg(timeout=5), timeout=10)
            await process_message(msg)
        except asyncio.TimeoutError:
            continue
        except nats.errors.TimeoutError:
            continue

    logger.info("Shutting down...")
    await sub.unsubscribe()
    await nc.close()


if __name__ == "__main__":
    asyncio.run(main())
