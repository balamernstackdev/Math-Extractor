"""Tests for PDF pipeline."""
from __future__ import annotations

from pathlib import Path

import pytest

from services.pdf_loader.pdf_reader import PDFReader


def test_pdf_reader_missing(tmp_path: Path) -> None:
    reader = PDFReader()
    with pytest.raises(FileNotFoundError):
        reader.read_pdf(tmp_path / "missing.pdf")

