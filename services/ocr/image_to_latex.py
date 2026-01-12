"""Minimal stub to diagnose SyntaxError."""
from __future__ import annotations
from pathlib import Path
from typing import Optional, Union

class ImageToLatex:
    def __init__(self):
        self.has_math_ocr = False
    
    def set_api_key(self, api_key: str):
        pass

    def has_vision_fallback_configured(self) -> bool:
        return True

    def image_to_latex(self, image_path: Union[str, Path], handwriting_mode: bool = False, table_mode: bool = False) -> str:
        return "Stubbed OCR Result: System is diagnosing a crash."

    def _is_corrupted_ocr_output(self, text: str) -> bool:
        return False
