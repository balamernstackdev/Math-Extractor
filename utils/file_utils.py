"""File utilities."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from core.config import settings
from core.logger import logger


def ensure_directories() -> None:
    """Create required directories."""
    for path in (
        settings.data_dir,
        settings.uploads_dir,
        settings.snips_dir,
        settings.notes_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
        logger.debug("Ensured directory: %s", path)


def save_bytes(content: bytes, path: Path) -> Path:
    """Save raw bytes to a path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    logger.debug("Saved file: %s", path)
    return path


def list_files(directory: Path, extensions: Iterable[str]) -> list[Path]:
    """List files in directory with given extensions."""
    if not directory.exists():
        return []
    return [p for p in directory.iterdir() if p.suffix.lower() in extensions]

