from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Union, Dict


@dataclass
class ASTNode:
    """A minimal abstract syntax tree node for mathematical expressions.
    This is a placeholder that will later be populated by a proper structural
    analysis stage. For now we store the raw LaTeX string so the rest of the
    pipeline can continue to function.
    """
    node_type: str
    value: Optional[str] = None
    children: List["ASTNode"] = field(default_factory=list)
    attributes: Dict[str, str] = field(default_factory=dict)
    
    # Semantic Flags (IMR Specification)
    is_operator: bool = False
    is_structural: bool = False  # True for tables, rows

    def __repr__(self) -> str:
        flags = ""
        if self.is_operator: flags += " [OP]"
        if self.is_structural: flags += " [STRUCT]"
        return f"ASTNode(type={self.node_type!r}, value={self.value!r}, children={len(self.children)}{flags})"
