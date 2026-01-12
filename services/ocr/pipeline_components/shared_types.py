"""
Shared definitions for OCR pipeline components.
"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class MultilineInfo:
    """
    Metadata about multi-line equation structure.
    """
    is_multiline: bool = False
    environment: Optional[str] = None
    alignment_spec: Optional[str] = None
    line_break_char: str = r'\\'
    has_alignment_markers: bool = False
    column_count: int = 1
    line_count: int = 1
    
    def __str__(self) -> str:
        if not self.is_multiline:
            return "Single-line equation"
        return (f"Multiline: {self.environment or 'manual'} "
                f"({self.line_count} lines, {self.column_count} cols, "
                f"align={self.alignment_spec})")

ALIGNMENT_SPECS = {
    'align': 'right left',
    'aligned': 'right left',
    'split': 'right left',
    'eqnarray': 'right center left',
    'gather': 'center',
    'gathered': 'center',
    'cases': 'left left',
    'multline': 'left',
    'array': None,
    'tabular': None
}
