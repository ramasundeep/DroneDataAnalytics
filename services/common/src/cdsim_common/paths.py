"""Locate the repository root when running from a checkout (not in Docker)."""

from __future__ import annotations

from pathlib import Path


def repo_root(start: Path | None = None) -> Path | None:
    """Walk up from ``start`` (default: this file) to the dir holding CLAUDE.md + schemas/."""
    here = (start or Path(__file__)).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "CLAUDE.md").is_file() and (candidate / "schemas").is_dir():
            return candidate
    return None
