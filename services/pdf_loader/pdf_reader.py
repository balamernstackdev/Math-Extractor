"""PDF reader service to split PDFs into pages."""
from __future__ import annotations

from pathlib import Path
from typing import List

from core.logger import logger


class PDFReader:
    """Handles PDF ingestion and page extraction."""

    def read_pdf(self, pdf_path: str | Path) -> List[Path]:
        """Validate and return list of page paths (for renderer)."""
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")
        logger.info("Reading PDF: %s", path)
        # This service only validates; rendering splits pages.
        return [path]

