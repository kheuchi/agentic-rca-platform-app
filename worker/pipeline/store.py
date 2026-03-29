"""Firestore upsert step — store embedded chunks in vector collection."""

import logging

from google.cloud.firestore import Client as FirestoreClient
from google.cloud.firestore_v1.vector import Vector
from llama_index.core.schema import TextNode

from config import settings

logger = logging.getLogger(__name__)

UPLOAD_BATCH_SIZE = 500  # Firestore batch limit


def get_firestore_client() -> FirestoreClient:
    """Create a Firestore client (uses WIF / ADC credentials)."""
    return FirestoreClient(
        project=settings.gcp_project_id,
        database=settings.firestore_database,
    )


def _node_to_document(node: TextNode) -> dict:
    """Convert a LlamaIndex TextNode to a Firestore document."""
    return {
        "content": node.get_content(),
        "embedding": Vector(node.embedding),
        "file_path": node.metadata.get("file_path", ""),
        "service_name": node.metadata.get("service_name", ""),
        "language": node.metadata.get("language", ""),
        "chunk_index": node.metadata.get("chunk_index", 0),
        "repo_url": node.metadata.get("repo_url", ""),
        "commit_sha": node.metadata.get("commit_sha", ""),
    }


def store_chunks(nodes: list[TextNode]) -> int:
    """Upsert embedded chunks into Firestore.

    Args:
        nodes: TextNode list with embeddings from embed_chunks().

    Returns:
        Number of documents successfully upserted.
    """
    if not nodes:
        return 0

    db = get_firestore_client()
    collection = db.collection(settings.firestore_collection)
    total_uploaded = 0

    for i in range(0, len(nodes), UPLOAD_BATCH_SIZE):
        batch_nodes = nodes[i : i + UPLOAD_BATCH_SIZE]
        batch = db.batch()

        for node in batch_nodes:
            doc_id = node.id_.replace(":", "-")
            doc_ref = collection.document(doc_id)
            batch.set(doc_ref, _node_to_document(node), merge=True)

        batch.commit()
        succeeded = len(batch_nodes)
        total_uploaded += succeeded

        logger.info(
            "Upserted batch %d-%d: %d succeeded",
            i, min(i + UPLOAD_BATCH_SIZE, len(nodes)),
            succeeded,
        )

    logger.info(
        "Stored %d/%d chunks in Firestore collection '%s'",
        total_uploaded, len(nodes), settings.firestore_collection,
    )
    return total_uploaded
