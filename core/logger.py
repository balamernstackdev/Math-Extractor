"""Logging utilities for Mathpix clone."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from core.config import settings

LOG_FILE = settings.base_dir / "mathpix_clone.log"


def init_logging() -> None:
    """Initialize logging with console and rotating file handler."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logger.setLevel(settings.log_level)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler = logging.StreamHandler()
    # Set encoding to UTF-8 to handle Unicode characters
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    console_handler.setFormatter(formatter)
    # File handler with UTF-8 encoding
    file_handler = RotatingFileHandler(
        LOG_FILE, 
        maxBytes=1_000_000, 
        backupCount=3,
        encoding='utf-8',
        errors='replace'
    )
    file_handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)


logger = logging.getLogger("mathpix_clone")

