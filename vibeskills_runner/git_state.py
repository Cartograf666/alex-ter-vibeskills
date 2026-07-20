import subprocess
import hashlib
from pathlib import Path
from .errors import GitStateError


def is_git_repo(repository: Path) -> bool:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=repository,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return res.returncode == 0 and res.stdout.strip() == "true"
    except Exception:
        return False


def get_repo_root(repository: Path) -> Path:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=repository,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return Path(res.stdout.strip()).resolve()
    except subprocess.SubprocessError as e:
        raise GitStateError(f"Failed to find git repository root: {e}")


def get_git_head(repository: Path) -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except subprocess.SubprocessError as e:
        raise GitStateError(f"Failed to get git HEAD commit: {e}")


def get_committed_tree_sha256(repository: Path, revision: str) -> str:
    try:
        res = subprocess.run(
            ["git", "ls-tree", "-r", "--full-tree", revision],
            cwd=repository,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        return hashlib.sha256(res.stdout).hexdigest()
    except subprocess.SubprocessError as e:
        raise GitStateError(f"Failed to get committed tree SHA-256: {e}")
