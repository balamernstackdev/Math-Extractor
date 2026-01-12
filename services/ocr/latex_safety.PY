# services/ocr/latex_safety.py
from __future__ import annotations
import re
from core.logger import logger


class LatexSafety:
    """Hard-fail LaTeX safety & normalization layer."""

    # -------------------------------
    # HARD FAIL DETECTOR
    # -------------------------------
    @staticmethod
    def detect_hard_truncation(latex: str) -> None:
        if not latex or not latex.strip():
            return

        s = latex.strip()

        # Environments
        if len(re.findall(r'\\begin\{[^}]+\}', s)) != len(re.findall(r'\\end\{[^}]+\}', s)):
            raise ValueError("Truncated LaTeX: begin/end mismatch")

        # Braces / brackets
        if s.count("{") != s.count("}"):
            raise ValueError("Truncated LaTeX: unbalanced braces")
        if s.count("(") != s.count(")"):
            raise ValueError("Truncated LaTeX: unbalanced parentheses")
        if s.count("[") != s.count("]"):
            raise ValueError("Truncated LaTeX: unbalanced brackets")

        # \left / \right
        if s.count("\\left") != s.count("\\right"):
            raise ValueError("Truncated LaTeX: unmatched \\left/\\right")

        # Dangling tokens
        if re.search(r'\\$', s):
            raise ValueError("Truncated LaTeX: dangling backslash")
        if re.search(r'[\^_]\s*$', s):
            raise ValueError("Truncated LaTeX: dangling ^ or _")

    # -------------------------------
    # NORMALIZATION
    # -------------------------------
    @staticmethod
    def normalize_pix2tex_noise(text: str) -> str:
        if not text:
            return text

        # collapse \displaystyle spam
        text = re.sub(r'(\\displaystyle\s*){2,}', r'\displaystyle ', text)

        # kill \left. / \right.
        text = re.sub(r'\\left\.', '', text)
        text = re.sub(r'\\right\.', '', text)

        return text.strip()

    @staticmethod
    def collapse_quads(text: str) -> str:
        return re.sub(r'(\\qquad\s*){2,}', ' ', text)
