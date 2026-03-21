"""Git clone step — shallow clone of target repo."""

import logging
import tempfile
from pathlib import Path

from git import Repo

logger = logging.getLogger(__name__)


def clone_repo(repo_url: str, branch: str = "main", dest_dir: str | None = None) -> Path:
    """Shallow clone a repo and return the local path.

    Args:
        repo_url: HTTPS URL of the public repo.
        branch: Branch to clone.
        dest_dir: Optional destination. If None, uses a temp directory.

    Returns:
        Path to the cloned repo root.
    """
    if dest_dir is None:
        dest_dir = tempfile.mkdtemp(prefix="rag-clone-")

    dest = Path(dest_dir)
    logger.info("Cloning %s (branch=%s) into %s", repo_url, branch, dest)

    Repo.clone_from(
        repo_url,
        str(dest),
        branch=branch,
        depth=1,
        single_branch=True,
    )

    logger.info("Clone complete: %s", dest)
    return dest
