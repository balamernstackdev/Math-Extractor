"""
LatexValidator.
Responsible for validation and structural integrity checks of LaTeX.
"""
from __future__ import annotations
import re
from core.logger import logger

class LatexValidator:
    """Validates LaTeX for potential issues before conversion."""
    
    @staticmethod
    def validate(latex: str) -> tuple[bool, str]:
        """
        Validate LaTeX string for structural correctness.
        Returns: (is_valid, error_message)
        """
        if not latex or not latex.strip():
            return False, "Empty or whitespace-only content"
            
        from .validation import validate_latex_syntax
        is_ok, violations = validate_latex_syntax(latex)
        
        if not is_ok:
            return False, "; ".join(violations) if violations else "Invalid LaTeX syntax"
            
        return True, ""

    @staticmethod
    def is_multiline(latex: str) -> bool:
        """Detect if LaTeX is a multiline equation."""
        if r"\\" in latex:
             return True
        multiline_envs = [
            'align', 'aligned', 'gather', 'gathered', 'eqnarray',
            'split', 'multline', 'cases', 'array', 'matrix', 'pmatrix'
        ]
        return any(f"\\begin{{{env}}}" in latex for env in multiline_envs)
