# """PDF renderer converts pages to images."""
# from __future__ import annotations

# from pathlib import Path
# from typing import List

# from pdf2image import convert_from_path
# from pdf2image.exceptions import PDFInfoNotInstalledError

# from core.config import settings
# from core.logger import logger


# class PDFRenderer:
#     """Render PDF pages to PNG files."""

#     def render_pages(self, pages: List[Path]) -> List[Path]:
#         """Render PDF pages to image files."""
#         output_images: List[Path] = []
#         poppler_path_str = str(settings.poppler_path) if settings.poppler_path else None
#         if poppler_path_str:
#             logger.info("Using Poppler path: %s", poppler_path_str)
#         for pdf_path in pages:
#             logger.info("Rendering PDF: %s", pdf_path)
#             try:
#                 images = convert_from_path(
#                     pdf_path,
#                     poppler_path=poppler_path_str,
#                 )
#             except PDFInfoNotInstalledError as exc:
#                 logger.error(
#                     "Render failed for %s: %s. Install Poppler and set POPPLER_PATH.",
#                     pdf_path,
#                     exc,
#                 )
#                 raise
#             except Exception as exc:  # noqa: BLE001
#                 logger.exception(
#                     "Render failed for %s: %s", pdf_path, exc, exc_info=True
#                 )
#                 raise
#             for idx, image in enumerate(images):
#                 out_path = (
#                     settings.uploads_dir
#                     / f"{pdf_path.stem}_page_{idx + 1}.png"
#                 )
#                 out_path.parent.mkdir(parents=True, exist_ok=True)
#                 image.save(out_path, "PNG")
#                 output_images.append(out_path)
#                 logger.debug("Saved page image: %s", out_path)
#         return output_images


"""
PDF renderer converts pages to images.
Production-safe for PyInstaller EXE.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List

from core.config import settings
from core.logger import logger


class PDFRenderer:
    """Render PDF pages to PNG files."""

    def _get_poppler_path(self) -> str | None:
        """Resolve Poppler path (supports PyInstaller EXE)."""
        if getattr(sys, "frozen", False):
            poppler = Path(sys._MEIPASS) / "poppler" / "bin"
            if poppler.exists():
                return str(poppler)
        if settings.poppler_path:
            return str(settings.poppler_path)
        return None

    def render_pages(self, pages: List[Path]) -> List[Path]:
        output_images: List[Path] = []

        for pdf_path in pages:
            logger.info("Rendering PDF: %s", pdf_path)

            images = []

            # --------------------------------------------------
            # TRY 1: PyMuPDF (NO EXTERNAL DEPENDENCY)
            # --------------------------------------------------
            try:
                import fitz  # PyMuPDF

                doc = fitz.open(pdf_path)
                if doc.page_count == 0:
                    raise RuntimeError("PDF has zero pages")

                for i in range(doc.page_count):
                    page = doc.load_page(i)
                    pix = page.get_pixmap(dpi=200)
                    images.append(pix)

                logger.info(
                    "[PDF] Rendered %d pages using PyMuPDF", len(images)
                )

            except Exception as exc:
                logger.warning(
                    "[PDF] PyMuPDF failed for %s: %s", pdf_path, exc
                )

            # --------------------------------------------------
            # TRY 2: pdf2image + Poppler (FALLBACK)
            # --------------------------------------------------
            if not images:
                try:
                    from pdf2image import convert_from_path

                    poppler_path = self._get_poppler_path()
                    logger.info("Using Poppler path: %s", poppler_path)

                    images = convert_from_path(
                        pdf_path,
                        dpi=200,
                        poppler_path=poppler_path,
                    )

                    if not images:
                        raise RuntimeError("Poppler returned zero images")

                    logger.info(
                        "[PDF] Rendered %d pages using Poppler", len(images)
                    )

                except Exception as exc:
                    logger.exception(
                        "[PDF] Poppler failed for %s: %s",
                        pdf_path,
                        exc,
                        exc_info=True,
                    )
                    raise RuntimeError(
                        "PDF rendering failed.\n\n"
                        "Possible reasons:\n"
                        "• Missing PDF renderer\n"
                        "• Encrypted or corrupted PDF\n"
                        "• Windows system restrictions"
                    )

            # --------------------------------------------------
            # SAVE IMAGES
            # --------------------------------------------------
            for idx, image in enumerate(images):
                out_path = (
                    settings.uploads_dir
                    / f"{pdf_path.stem}_page_{idx + 1}.png"
                )
                out_path.parent.mkdir(parents=True, exist_ok=True)

                # PyMuPDF pixmap vs PIL image
                if hasattr(image, "save"):
                    image.save(out_path, "PNG")
                else:
                    image.save(out_path)

                output_images.append(out_path)
                logger.debug("Saved page image: %s", out_path)

        if not output_images:
            raise RuntimeError("No images rendered from PDF")

        return output_images
