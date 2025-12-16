"""Tests for OCR pipeline."""
from __future__ import annotations

from pathlib import Path

import pytest

from services.ocr.latex_to_mathml import LatexToMathML


def test_latex_to_mathml_empty() -> None:
    converter = LatexToMathML()
    with pytest.raises(ValueError):
        converter.convert("")

