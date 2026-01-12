"""
MatrixConverter.
Handles Matrix specific environments.
"""
from __future__ import annotations
import re
from latex2mathml.converter import convert as latex2mathml_convert
from core.logger import logger

class MatrixConverter:
    """Specialized converter for matrices."""

    def is_matrix_equation(self, latex: str) -> bool:
        """Check if equation is a matrix."""
        matrix_envs = ['matrix', 'pmatrix', 'bmatrix', 'vmatrix', 'Bmatrix', 'Vmatrix', 'smallmatrix']
        return any(f"\\begin{{{env}}}" in latex for env in matrix_envs)

    def convert_matrix(self, latex: str) -> str:
        """
        Convert matrix LaTeX to MathML.
        Currently wraps standard conversion but can handle special matrix rules if needed.
        """
        # Matrices are generally handled well by latex2mathml if clean
        # But we might need custom handling for complex nesting or spacing
        
        # Simple passthrough with error handling for now, matching original logic
        # which tried standard conversion then fell back to AI
        try:
             return latex2mathml_convert(latex)
        except Exception as e:
             logger.warning(f"Standard matrix conversion failed: {e}")
             raise e
