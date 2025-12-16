"""PDF renderer converts pages to images."""
from __future__ import annotations

from pathlib import Path
from typing import List

from pdf2image import convert_from_path
from pdf2image.exceptions import PDFInfoNotInstalledError

from core.config import settings
from core.logger import logger


class PDFRenderer:
    """Render PDF pages to PNG files."""

    def render_pages(self, pages: List[Path]) -> List[Path]:
        """Render PDF pages to image files."""
        output_images: List[Path] = []
        poppler_path_str = str(settings.poppler_path) if settings.poppler_path else None
        if poppler_path_str:
            logger.info("Using Poppler path: %s", poppler_path_str)
        for pdf_path in pages:
            logger.info("Rendering PDF: %s", pdf_path)
            try:
                images = convert_from_path(
                    pdf_path,
                    poppler_path=poppler_path_str,
                )
            except PDFInfoNotInstalledError as exc:
                logger.error(
                    "Render failed for %s: %s. Install Poppler and set POPPLER_PATH.",
                    pdf_path,
                    exc,
                )
                raise
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "Render failed for %s: %s", pdf_path, exc, exc_info=True
                )
                raise
            for idx, image in enumerate(images):
                out_path = (
                    settings.uploads_dir
                    / f"{pdf_path.stem}_page_{idx + 1}.png"
                )
                out_path.parent.mkdir(parents=True, exist_ok=True)
                image.save(out_path, "PNG")
                output_images.append(out_path)
                logger.debug("Saved page image: %s", out_path)
        return output_images

