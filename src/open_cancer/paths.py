"""Cross-platform path helpers for persisted experiment metadata."""

from __future__ import annotations

from pathlib import Path


def relative_posix(path: str | Path, root: str | Path) -> str:
    """Return a repository-relative path with stable POSIX separators."""
    resolved_path = Path(path).resolve()
    resolved_root = Path(root).resolve()
    return resolved_path.relative_to(resolved_root).as_posix()
