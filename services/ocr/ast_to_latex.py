"""AST to LaTeX pretty-printer.

This module generates LaTeX from an abstract syntax tree for export purposes.
LaTeX is NOT the source of truth - it's merely a pretty-printed view of the AST.
"""
from __future__ import annotations

from core.logger import logger
from .ast import ASTNode


class ASTToLaTeXPrettyPrinter:
    """Convert an AST to LaTeX string for export/display.
    
    This is Phase 4 - LaTeX export is optional and read-only.
    The LaTeX output is never fed back into the pipeline.
    """
    
    def __init__(self):
        pass
    
    def export(self, ast: ASTNode) -> str:
        """Convert an AST to LaTeX string.
        
        Args:
            ast: Root AST node
            
        Returns:
            LaTeX string representation
        """
        if not ast or ast.node_type == "empty":
            return ""
        
        logger.info(f"[ASTToLaTeX] Exporting AST to LaTeX (type={ast.node_type})")
        
        # Generate LaTeX from AST
        latex = self._export_node(ast)
        
        return latex.strip()
    
    def _export_node(self, node: ASTNode) -> str:
        """Recursively export an AST node to LaTeX.
        
        Args:
            node: AST node to export
            
        Returns:
            LaTeX string fragment
        """
        node_type = node.node_type
        
        # Handle different node types
        if node_type == "empty":
            return ""
        
        elif node_type == "equation" or node_type == "sequence":
            # Concatenate children with spaces
            return " ".join(self._export_node(child) for child in node.children if child)
        
        elif node_type == "symbol":
            # Return the symbol value directly
            return self._export_symbol(node.value)
        
        elif node_type == "subscript":
            # base_{sub}
            if len(node.children) >= 2:
                base = self._export_node(node.children[0])
                sub = self._export_node(node.children[1])
                return f"{base}_{{{sub}}}"
            return ""
        
        elif node_type == "superscript":
            # base^{sup}
            if len(node.children) >= 2:
                base = self._export_node(node.children[0])
                sup = self._export_node(node.children[1])
                return f"{base}^{{{sup}}}"
            return ""
        
        elif node_type == "subsup":
            # base_{sub}^{sup}
            if len(node.children) >= 3:
                base = self._export_node(node.children[0])
                sub = self._export_node(node.children[1])
                sup = self._export_node(node.children[2])
                return f"{base}_{{{sub}}}^{{{sup}}}"
            return ""
        
        elif node_type == "fraction":
            # \frac{num}{denom}
            if len(node.children) >= 2:
                num = self._export_node(node.children[0])
                denom = self._export_node(node.children[1])
                return f"\\frac{{{num}}}{{{denom}}}"
            return ""
        
        elif node_type == "sqrt":
            # \sqrt{content}
            if node.children:
                content = self._export_node(node.children[0])
                return f"\\sqrt{{{content}}}"
            return ""
        
        elif node_type == "root":
            # \sqrt[index]{content}
            if len(node.children) >= 2:
                content = self._export_node(node.children[0])
                index = self._export_node(node.children[1])
                return f"\\sqrt[{index}]{{{content}}}"
            return ""
        
        elif node_type == "matrix":
            # \begin{pmatrix} ... \end{pmatrix}
            return self._export_matrix(node)
        
        else:
            # Unknown node type - concatenate children
            logger.warning(f"[ASTToLaTeX] Unknown node type: {node_type}")
            return " ".join(self._export_node(child) for child in node.children if child)
    
    def _export_symbol(self, symbol: str | None) -> str:
        """Export a symbol to LaTeX.
        
        Args:
            symbol: The symbol string
            
        Returns:
            LaTeX representation
        """
        if not symbol:
            return ""
        
        # Map special symbols to LaTeX commands
        symbol_map = {
            '∑': r'\sum',
            '∏': r'\prod',
            '∫': r'\int',
            '√': r'\sqrt',
            '∈': r'\in',
            '∉': r'\notin',
            '⊆': r'\subseteq',
            '⊇': r'\supseteq',
            '∪': r'\cup',
            '∩': r'\cap',
            '×': r'\times',
            '÷': r'\div',
            '≤': r'\leq',
            '≥': r'\geq',
            '≠': r'\neq',
            '≈': r'\approx',
            '∞': r'\infty',
            '∂': r'\partial',
            '∇': r'\nabla',
            # Greek letters
            'α': r'\alpha',
            'β': r'\beta',
            'γ': r'\gamma',
            'δ': r'\delta',
            'ε': r'\epsilon',
            'ζ': r'\zeta',
            'η': r'\eta',
            'θ': r'\theta',
            'ι': r'\iota',
            'κ': r'\kappa',
            'λ': r'\lambda',
            'μ': r'\mu',
            'ν': r'\nu',
            'ξ': r'\xi',
            'π': r'\pi',
            'ρ': r'\rho',
            'σ': r'\sigma',
            'τ': r'\tau',
            'υ': r'\upsilon',
            'φ': r'\phi',
            'χ': r'\chi',
            'ψ': r'\psi',
            'ω': r'\omega',
        }
        
        # Return mapped symbol or original
        return symbol_map.get(symbol, symbol)
    
    def _export_matrix(self, node: ASTNode) -> str:
        """Export a matrix node to LaTeX.
        
        Args:
            node: Matrix AST node
            
        Returns:
            LaTeX pmatrix environment
        """
        # Build matrix rows
        rows = []
        for row_node in node.children:
            cells = [self._export_node(cell) for cell in row_node.children]
            rows.append(" & ".join(cells))
        
        matrix_content = " \\\\\n".join(rows)
        return f"\\begin{{pmatrix}}\n{matrix_content}\n\\end{{pmatrix}}"
