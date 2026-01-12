"""
LatexNormalizer.
Responsible for cleaning and preparing raw LaTeX before conversion.
"""
from __future__ import annotations
import re
from core.logger import logger
from services.ocr.pipeline_components.regex_patterns import SPACING_COMMANDS, UNSUPPORTED_COMMANDS

class LatexNormalizer:
    """Handles LaTeX string normalization and cleanup."""

    @staticmethod
    def normalize(latex: str) -> str:
        """Main normalization entry point."""
        if not latex:
            return ""
            
        from services.ocr.pipeline_components.normalization import strip_ai_artifacts
        normalized = strip_ai_artifacts(latex)
        
        normalized = LatexNormalizer.strip_delimiters(normalized)
        normalized = LatexNormalizer.remove_noise(normalized)
        normalized = LatexNormalizer._apply_semantic_corrections(normalized)
        normalized = LatexNormalizer.replace_unsupported(normalized)
        normalized = LatexNormalizer.fix_spacing(normalized)
        
        return normalized

    @staticmethod
    def strip_delimiters(latex: str) -> str:
        """Remove $...$ and $$...$$ wrappers."""
        latex = latex.strip()
        if latex.startswith("$$") and latex.endswith("$$"):
            return latex[2:-2].strip()
        if latex.startswith("$") and latex.endswith("$"):
            return latex[1:-1].strip()
        return latex

    @staticmethod
    def remove_noise(latex: str) -> str:
        """Remove common invisible OCR noise and redundant commands."""
        # Fix escaped spaces
        latex = latex.replace(r'\ ', ' ')
        # Normalize whitespace
        latex = re.sub(r'\s+', ' ', latex)
        # Remove redundant \displaystyle checks
        latex = latex.replace(r'\displaystyle', '') 
        
        # OCR Corrections (moved from latex_to_mathml)
        # 1. Fix missing space after operators - DISABLED (Too aggressive, breaks \inf, \left, \leqq)
        # latex = re.sub(r'\\(le|ge|leq|geq|in|to|neq|sim|approx)(?=[A-Za-z0-9])', r'\\\1 ', latex)
        latex = re.sub(r'\\equiv(?=[^a-zA-Z])', r'\\equiv ', latex)

        # 2. Fix \le and \ge appearing as text
        latex = re.sub(r'\\le(?=[^a-zA-Z])', r'\\leq', latex) # \leX -> \leqX
        latex = re.sub(r'\\le\s+', r'\\leq ', latex)           # \le X -> \leq X
        latex = re.sub(r'\\ge(?=[^a-zA-Z])', r'\\geq', latex)
        latex = re.sub(r'\\ge\s+', r'\\geq ', latex)
        
        return latex.strip()

    @staticmethod
    def _apply_semantic_corrections(latex: str) -> str:
        """Apply semantic fixes for common OCR misinterpretations."""
        # 1. Fix \mathbb{Z}(...) which is usually \mathcal{I}(...) (Information/Index set)
        latex = re.sub(r'\\mathbb\s*\{?Z\}?\s*\(', r'\\mathcal{I}(', latex)
        
        return latex

    @staticmethod
    def replace_unsupported(latex: str) -> str:
        """Replace unsupported LaTeX commands with supported equivalents."""
        for cmd, replacement in UNSUPPORTED_COMMANDS.items():
            # Use negative lookbehind to ensure we don't replace inside other commands if needed
            # Simple replace for now, but regex allows future expansion
            latex = re.sub(cmd, replacement, latex)
        return latex

    @staticmethod
    def fix_spacing(latex: str) -> str:
        """Normalize or remove layout-specific spacing."""
        for cmd in SPACING_COMMANDS:
             latex = latex.replace(cmd, ' ')
        return re.sub(r'\s+', ' ', latex).strip()
