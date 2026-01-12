from __future__ import annotations

import shutil
import sys
from pathlib import Path

from core.config import settings
from core.logger import logger


def run_system_check() -> dict:
    """
    Validate critical runtime dependencies.
    Returns a dict that can be shown in UI or logs.
    """
    results = {
        "python_version": sys.version.split()[0],
        "frozen": getattr(sys, "frozen", False),
        "poppler": False,
        "tesseract": False,
        "qt_webengine": False,
        "pix2tex": False,
    }

    # --------------------------------------------------
    # POPPLER
    # --------------------------------------------------
    if settings.poppler_path and (settings.poppler_path / "pdftoppm.exe").exists():
        results["poppler"] = True
    else:
        logger.error("❌ Poppler NOT found")

    # --------------------------------------------------
    # TESSERACT
    # --------------------------------------------------
    if settings.tesseract_cmd and Path(settings.tesseract_cmd).exists():
        results["tesseract"] = True
    else:
        logger.error("❌ Tesseract NOT found")

    # --------------------------------------------------
    # QT WEBENGINE
    # --------------------------------------------------
    try:
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        results["qt_webengine"] = True
    except Exception as exc:
        logger.error("❌ QtWebEngine failed: %s", exc)

    # --------------------------------------------------
    # PIX2TEX
    # --------------------------------------------------
    try:
        import pix2tex
        results["pix2tex"] = True
    except Exception as exc:
        logger.error("❌ pix2tex failed: %s", exc)

    return results
