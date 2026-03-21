"""File parsing step — discover and read source files from a cloned repo."""

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Map file extensions to language identifiers (used for chunking strategy)
EXTENSION_LANG_MAP = {
    ".py": "python",
    ".go": "go",
    ".java": "java",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".rs": "rust",
    ".cs": "csharp",
    ".rb": "ruby",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".md": "markdown",
    ".dockerfile": "dockerfile",
}

# OTel Demo service-to-directory mapping
OTEL_DEMO_SERVICE_MAP = {
    "src/accountingservice": "accountingservice",
    "src/adservice": "adservice",
    "src/cartservice": "cartservice",
    "src/checkoutservice": "checkoutservice",
    "src/currencyservice": "currencyservice",
    "src/emailservice": "emailservice",
    "src/frauddetectionservice": "frauddetectionservice",
    "src/frontend": "frontend",
    "src/frontendproxy": "frontendproxy",
    "src/loadgenerator": "loadgenerator",
    "src/paymentservice": "paymentservice",
    "src/productcatalogservice": "productcatalogservice",
    "src/quoteservice": "quoteservice",
    "src/recommendationservice": "recommendationservice",
    "src/shippingservice": "shippingservice",
}


@dataclass
class ParsedFile:
    """A source file with its content and metadata."""
    content: str
    file_path: str
    language: str
    service_name: str
    metadata: dict = field(default_factory=dict)


def detect_service(file_path: str) -> str:
    """Map a file path to an OTel Demo service name."""
    normalized = file_path.replace("\\", "/")
    for prefix, service in OTEL_DEMO_SERVICE_MAP.items():
        if normalized.startswith(prefix):
            return service
    return "unknown"


def detect_language(file_path: Path) -> str:
    """Detect language from file extension."""
    suffix = file_path.suffix.lower()
    # Handle Dockerfile (no extension, but name matches)
    if file_path.name.lower() in ("dockerfile", "dockerfile.dev"):
        return "dockerfile"
    return EXTENSION_LANG_MAP.get(suffix, "text")


def parse_files(
    repo_dir: Path,
    file_patterns: list[str],
    services: list[str] | None = None,
    max_file_size: int = 100_000,
) -> list[ParsedFile]:
    """Walk a cloned repo and parse matching files.

    Args:
        repo_dir: Path to the cloned repo root.
        file_patterns: Glob patterns to match (e.g. ["**/*.py", "**/*.go"]).
        services: Optional list of service names to filter. Empty = all.
        max_file_size: Skip files larger than this (bytes).

    Returns:
        List of ParsedFile objects ready for chunking.
    """
    parsed = []
    seen = set()

    for pattern in file_patterns:
        for file_path in repo_dir.glob(pattern):
            if not file_path.is_file():
                continue
            if file_path in seen:
                continue
            seen.add(file_path)

            # Skip large files (generated code, vendored deps, etc.)
            if file_path.stat().st_size > max_file_size:
                logger.debug("Skipping large file: %s", file_path)
                continue

            # Skip hidden dirs and common non-source dirs
            rel_path = str(file_path.relative_to(repo_dir))
            skip_dirs = {".git", "node_modules", "vendor", "__pycache__", ".venv", "dist", "build"}
            if any(part in skip_dirs for part in file_path.parts):
                continue

            service = detect_service(rel_path)

            # Filter by service if specified
            if services and service not in services and service != "unknown":
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                logger.warning("Could not read file: %s", file_path)
                continue

            if not content.strip():
                continue

            language = detect_language(file_path)

            parsed.append(ParsedFile(
                content=content,
                file_path=rel_path,
                language=language,
                service_name=service,
                metadata={
                    "file_size": file_path.stat().st_size,
                    "file_name": file_path.name,
                },
            ))

    logger.info(
        "Parsed %d files from %s (patterns=%s, services=%s)",
        len(parsed), repo_dir, file_patterns, services,
    )
    return parsed
