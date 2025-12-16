"""MathML writer utility."""
from __future__ import annotations

from pathlib import Path

from core.config import settings
from core.logger import logger


class MathMLWriter:
    """Persist MathML snippets to disk."""

    def __init__(self) -> None:
        self.output_dir = settings.data_dir / "mathml"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_mathml(self, mathml: str, name: str) -> Path:
        """Save MathML string to a file."""
        if not mathml:
            raise ValueError("MathML content is empty")
        path = self.output_dir / f"{name}.xml"
        logger.info("Saving MathML to %s", path)
        path.write_text(mathml, encoding="utf-8")
        return path

    def write_mathml(self, mathml: str) -> Path:
        """Write MathML to a file with auto-generated name."""
        from datetime import datetime
        if not mathml:
            raise ValueError("MathML content is empty")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.output_dir / f"mathml_{timestamp}.xml"
        logger.info("Writing MathML to %s", path)
        path.write_text(mathml, encoding="utf-8")
        return path

