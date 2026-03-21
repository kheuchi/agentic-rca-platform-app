"""LlamaIndex chunking step — split parsed files into indexed chunks."""

import hashlib
import logging

from llama_index.core.node_parser import CodeSplitter, SentenceSplitter
from llama_index.core.schema import Document, TextNode

from pipeline.parse import ParsedFile

logger = logging.getLogger(__name__)

# Languages supported by CodeSplitter (via tree-sitter)
CODE_LANGUAGES = {
    "python", "go", "java", "typescript", "javascript",
    "rust", "csharp", "ruby",
}

CHUNK_SIZE = 512
CHUNK_OVERLAP = 50


def _make_chunk_id(repo_url: str, file_path: str, chunk_index: int) -> str:
    """Deterministic chunk ID for deduplication."""
    repo_hash = hashlib.sha256(repo_url.encode()).hexdigest()[:12]
    file_hash = hashlib.sha256(file_path.encode()).hexdigest()[:12]
    return f"{repo_hash}:{file_hash}:{chunk_index}"


def chunk_documents(
    parsed_files: list[ParsedFile],
    repo_url: str,
    commit_sha: str = "",
) -> list[TextNode]:
    """Split parsed files into chunks with metadata.

    Args:
        parsed_files: Output from parse_files().
        repo_url: Source repo URL (for metadata).
        commit_sha: Current commit SHA (for metadata).

    Returns:
        List of LlamaIndex TextNode objects ready for embedding.
    """
    all_nodes: list[TextNode] = []

    for pf in parsed_files:
        # Choose splitter based on language
        if pf.language in CODE_LANGUAGES:
            try:
                splitter = CodeSplitter(
                    language=pf.language,
                    chunk_lines=40,
                    chunk_lines_overlap=5,
                    max_chars=CHUNK_SIZE * 4,  # approximate chars from tokens
                )
            except Exception:
                # Fallback if tree-sitter grammar not available
                logger.debug("CodeSplitter unavailable for %s, using SentenceSplitter", pf.language)
                splitter = SentenceSplitter(
                    chunk_size=CHUNK_SIZE,
                    chunk_overlap=CHUNK_OVERLAP,
                )
        else:
            splitter = SentenceSplitter(
                chunk_size=CHUNK_SIZE,
                chunk_overlap=CHUNK_OVERLAP,
            )

        doc = Document(
            text=pf.content,
            metadata={
                "file_path": pf.file_path,
                "service_name": pf.service_name,
                "language": pf.language,
                "repo_url": repo_url,
                "commit_sha": commit_sha,
            },
        )

        nodes = splitter.get_nodes_from_documents([doc])

        for i, node in enumerate(nodes):
            node.id_ = _make_chunk_id(repo_url, pf.file_path, i)
            node.metadata["chunk_index"] = i
            all_nodes.append(node)

    logger.info(
        "Chunked %d files into %d nodes (repo=%s)",
        len(parsed_files), len(all_nodes), repo_url,
    )
    return all_nodes
