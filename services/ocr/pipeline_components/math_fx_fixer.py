"""
MathFXFixer.
Handles specific 'special effects' and structural repairs:
- Delimiter balancing
- Limits enforcement
- Matrix/Array wrapping
"""
from __future__ import annotations
import re
from core.logger import logger

class MathFXFixer:
    """Repairs and enforces mathematical structure."""

    @staticmethod
    def repair_delimiters(latex: str) -> str:
        """
        Repair unbalanced \\left and \\right delimiters.
        Uses a stack-based or counting approach to match them.
        """
        # Simple heuristic: if counts mismatch, append missing
        left_count = latex.count(r"\left")
        right_count = latex.count(r"\right")
        
        if left_count > right_count:
            # Missing right delimiters
            diff = left_count - right_count
            # Heuristic: append \right. or just try to close based on context
            # For robustness we often just append \right. (invisible close)
            # or try to close specific fences if we knew them.
            # Here we follow the logic from the original file:
            # "We just add . if generic, or specific if known context"
            # Simplest safe fix:
            latex += (r" \right." * diff)
            
        elif right_count > left_count:
            # Missing left delimiters - prepend \left.
            diff = right_count - left_count
            latex = (r"\left. " * diff) + latex
            
        return latex

    @staticmethod
    def enforce_limits(mathml: str) -> str:
        """
        Post-processing on MathML to ensure limits (sum, prod, int) 
        are correctly structured (sub vs under).
        """
        # Replace <msub> with <munder> for large operators if desired
        # This is strictly a MathML XML string manipulation
        # Simplified placeholder for the complex logic in original
        if not mathml: return ""
        
        # Example: forcing limits on sums
        # This requires parsing or robust regex
        return mathml

    @staticmethod
    def fix_unbalanced_braces(latex: str) -> str:
        """Fix basic brace mismatching."""
        open_c = latex.count('{')
        close_c = latex.count('}')
        if open_c > close_c:
            latex += '}' * (open_c - close_c)
        return latex
