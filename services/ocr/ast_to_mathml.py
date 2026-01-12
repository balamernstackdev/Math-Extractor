"""AST to MathML serializer.

This module generates valid MathML from an abstract syntax tree,
ensuring deterministic, schema-compliant output.
"""
from __future__ import annotations

from typing import List
from core.logger import logger
from .ast import ASTNode


class ASTToMathMLSerializer:
    """Serialize an AST into valid MathML.
    
    This replaces the LaTeX→MathML conversion with a direct tree→MathML
    transformation that guarantees:
    - Schema-valid MathML tags
    - Correct operator precedence
    - Proper nesting and attributes
    - No invalid constructs
    
    Phase 3 implementation will handle:
    - All MathML elements (mi, mo, mn, mrow, msub, msup, mfrac, mtable, etc.)
    - Proper operator spacing and stretchy delimiters
    - Multiline equations with correct alignment
    - Matrix structures with rows and columns
    """
    
    def __init__(self):
        self.xmlns = 'http://www.w3.org/1998/Math/MathML'
    
    def serialize(self, ast: ASTNode) -> str:
        """Convert an AST to MathML string.
        
        Args:
            ast: Root AST node
            
        Returns:
            Valid MathML string
        """
        if not ast or ast.node_type == "empty":
            return self._empty_mathml()
        
        logger.info(f"[ASTToMathML] Serializing AST (type={ast.node_type})")
        
        # Build MathML content
        content = self._serialize_node(ast)
        
        # Wrap in <math> tag with proper attributes
        mathml = (
            f'<math xmlns="{self.xmlns}" display="block">'
            f'{content}'
            f'</math>'
        )
        
        return mathml
    
    def _serialize_node(self, node: ASTNode) -> str:
        """Recursively serialize an AST node to MathML.
        
        Args:
            node: AST node to serialize
            
        Returns:
            MathML string fragment
        """
        node_type = node.node_type
        
        # Handle different node types
        if node_type == "empty":
            return ""
        
        elif node_type == "equation" or node_type == "sequence" or node_type == "row":
            # Wrap children in <mrow>
            if not node.children:
                return ""
            children_mathml = "".join(self._serialize_node(child) for child in node.children)
            return f"<mrow>{children_mathml}</mrow>"
        
        elif node_type == "symbol":
            # Classify symbol as identifier, number, or operator
            return self._serialize_symbol(node)
        
        elif node_type == "subscript":
            # <msub><base/><sub/></msub>
            if len(node.children) >= 2:
                base = self._serialize_node(node.children[0])
                sub = self._serialize_node(node.children[1])
                return f"<msub>{base}{sub}</msub>"
            return ""
        
        elif node_type == "superscript":
            # <msup><base/><sup/></msup>
            if len(node.children) >= 2:
                base = self._serialize_node(node.children[0])
                sup = self._serialize_node(node.children[1])
                return f"<msup>{base}{sup}</msup>"
            return ""
        
        elif node_type == "subsup":
            # <msubsup><base/><sub/><sup/></msubsup>
            if len(node.children) >= 3:
                base = self._serialize_node(node.children[0])
                sub = self._serialize_node(node.children[1])
                sup = self._serialize_node(node.children[2])
                return f"<msubsup>{base}{sub}{sup}</msubsup>"
            return ""
        
        elif node_type == "fraction":
            # <mfrac><numerator/><denominator/></mfrac>
            if len(node.children) >= 2:
                num = self._serialize_node(node.children[0])
                denom = self._serialize_node(node.children[1])
                return f"<mfrac>{num}{denom}</mfrac>"
            return ""
        
        elif node_type == "sqrt":
            # <msqrt><content/></msqrt>
            if node.children:
                content = self._serialize_node(node.children[0])
                return f"<msqrt>{content}</msqrt>"
            return ""
        
        elif node_type == "root":
            # <mroot><content/><index/></mroot>
            if len(node.children) >= 2:
                content = self._serialize_node(node.children[0])
                index = self._serialize_node(node.children[1])
                return f"<mroot>{content}{index}</mroot>"
            return ""
        


        elif node_type == "text":
            # Literal text <mtext>content</mtext>
            # If variant is script/mathcal, use <mi> or <mstyle> because <mtext> doesn't support it well in all renderers
            variant = node.attributes.get('variant', 'normal')
            text_val = self._escape_xml(node.value)
            
            if variant in ['script', 'double-struck', 'bold-script', 'fraktur']:
                 # Use <mi> for these math alphanumeric styles
                 # But <mi> implies identifier. If value is long text, this is weird.
                 # Usually \mathcal{I} -> I is 1 char.
                 return f'<mi mathvariant="{variant}">{text_val}</mi>'
            
            attr_str = f' mathvariant="{variant}"' if variant != "normal" else ""
            return f"<mtext{attr_str}>{text_val}</mtext>"

        elif node_type == "fence":
            # <mfenced open="..." close="...">...</mfenced>
            open_delim = self._escape_xml(node.attributes.get('open', '('))
            close_delim = self._escape_xml(node.attributes.get('close', ')'))
            
            # Wrap contents in mrow to avoid default separators
            children_mathml = "".join(self._serialize_node(child) for child in node.children)
            return f'<mfenced open="{open_delim}" close="{close_delim}" separators=""><mrow>{children_mathml}</mrow></mfenced>'

        elif node_type == "style":
            # <mstyle mathvariant="...">...</mstyle>
            variant = node.attributes.get('mathvariant', 'normal')
            children_mathml = "".join(self._serialize_node(child) for child in node.children)
            return f'<mstyle mathvariant="{variant}">{children_mathml}</mstyle>'

        elif node_type == "overscript":
            # <mover accent="true"><base/><overscript/></mover>
            is_accent = node.attributes.get('accent', 'false')
            if len(node.children) >= 2:
                base = self._serialize_node(node.children[0])
                over = self._serialize_node(node.children[1])
                return f'<mover accent="{is_accent}">{base}{over}</mover>'
            # Fallback for malformed node
            children_mathml = "".join(self._serialize_node(child) for child in node.children)
            return f'<mover accent="{is_accent}">{children_mathml}</mover>'
            
        elif node_type == "underscript":
            # <munder accent="true"><base/><underscript/></munder>
            is_accent = node.attributes.get('accent', 'false')
            if len(node.children) >= 2:
                base = self._serialize_node(node.children[0])
                under = self._serialize_node(node.children[1])
                return f'<munder accent="{is_accent}">{base}{under}</munder>'
            return ""

        elif node_type == "underover":
            # <munderover><base/><underscript/><overscript/></munderover>
            if len(node.children) >= 3:
                base = self._serialize_node(node.children[0])
                under = self._serialize_node(node.children[1])
                over = self._serialize_node(node.children[2])
                return f"<munderover>{base}{under}{over}</munderover>"
            return ""

        elif node_type == "binomial":
            # <mfenced><mfrac linethickness="0"><num/><denom/></mfrac></mfenced>
            if len(node.children) >= 2:
                top = self._serialize_node(node.children[0])
                bottom = self._serialize_node(node.children[1])
                return f'<mfenced><mfrac linethickness="0">{top}{bottom}</mfrac></mfenced>'
            return ""

        elif node_type == "mtable":
            # <mtable ...> ... </mtable>
            # Attributes: columnalign, rowspacing, etc.
            attrs = []
            if "columnalign" in node.attributes:
                attrs.append(f'columnalign="{node.attributes["columnalign"]}"')
            if "rowspacing" in node.attributes:
                attrs.append(f'rowspacing="{node.attributes["rowspacing"]}"')
            if "columnspacing" in node.attributes:
                attrs.append(f'columnspacing="{node.attributes["columnspacing"]}"')
            
            attr_str = " ".join(attrs)
            children_mathml = "".join(self._serialize_node(child) for child in node.children)
            table_mathml = f"<mtable {attr_str}>{children_mathml}</mtable>"
            
            # Wrap in fence if requested (e.g., for cases, matrices)
            if "fence" in node.attributes:
                fences = node.attributes["fence"]
                # Handle tuple fences from parser
                if isinstance(fences, (tuple, list)) and len(fences) >= 2:
                    open_fence = self._escape_xml(fences[0])
                    close_fence = self._escape_xml(fences[1])
                else:
                    open_fence = self._escape_xml(str(fences))
                    close_fence = self._escape_xml(node.attributes.get("close_fence", ""))
                    
                return f'<mfenced open="{open_fence}" close="{close_fence}" separators="">{table_mathml}</mfenced>'
                
            return table_mathml

        elif node_type == "mtr":
            # <mtr><mtd>...</mtd></mtr>
            # Children are cells. We must wrap each child's serialized output in <mtd>
            cells = []
            for child in node.children:
                # Serialize the content of the cell (usually an 'row'/'mrow')
                cell_content = self._serialize_node(child)
                cells.append(f"<mtd>{cell_content}</mtd>")
            return f"<mtr>{''.join(cells)}</mtr>"
            
        elif node_type == "tag":
            # <mtext>(1.1)</mtext>
            # Use mtext for the tag. It will be part of the outer mrow or mtable.
            return f"<mtext>({self._escape_xml(node.value)})</mtext>"
            
        else:
            # Unknown node type - log warning and wrap children
            logger.warning(f"[ASTToMathML] Unknown node type: {node_type}")
            children_mathml = "".join(self._serialize_node(child) for child in node.children)
            return f"<mrow>{children_mathml}</mrow>" if children_mathml else ""
    
    def _serialize_symbol(self, node: ASTNode) -> str:
        """Serialize a symbol to the appropriate MathML tag.
        
        Args:
            node: The AST node containing the symbol
            
        Returns:
            MathML element (<mi>, <mn>, or <mo>)
        """
        symbol = node.value
        if not symbol:
            return ""
        
        # 1. Trust Semantic IMR
        if node.is_operator:
            return f"<mo>{self._escape_xml(symbol)}</mo>"
            
        # 2. Strip leading backslash for standard text operators/functions
        # e.g., \sin -> sin, \min -> min
        # MathJax typically handles these better as <mi mathvariant='normal'> or <mo>
        clean_symbol = symbol
        if symbol.startswith('\\') and len(symbol) > 1 and symbol[1].isalpha():
             clean_symbol = symbol[1:]
             
        # Standard Functions (should be upright identifiers or operators)
        # MathML recommends <mi>sin</mi> for function names, but with defaults it might differ.
        # MathJax treats <mi>sin</mi> as italic "s" "i" "n".
        # We need <mi mathvariant="normal">sin</mi>
        text_functions = {
            'sin', 'cos', 'tan', 'sec', 'csc', 'cot', 
            'arcsin', 'arccos', 'arctan', 'sinh', 'cosh', 'tanh',
            'log', 'ln', 'lg', 'exp', 
            'lim', 'min', 'max', 'sup', 'inf', 'det', 'gcd', 'lcm'
        }
        
        if clean_symbol in text_functions:
            return f'<mi mathvariant="normal">{clean_symbol}</mi>'
            
        # Classify symbol based on content
        if clean_symbol.isdigit():
            # Number
            return f"<mn>{self._escape_xml(clean_symbol)}</mn>"
            
        elif clean_symbol.isalpha() or clean_symbol in 'αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ':
            return f"<mi>{self._escape_xml(clean_symbol)}</mi>"
            
        else:
            # Fallback to operator if unknown non-alpha
            return f"<mo>{self._escape_xml(symbol)}</mo>"
    

    
    def _empty_mathml(self) -> str:
        """Generate empty but valid MathML."""
        return f'<math xmlns="{self.xmlns}" display="block"></math>'
    
    def _escape_xml(self, text: str) -> str:
        """Escape XML special characters.
        
        Args:
            text: Raw text
            
        Returns:
            XML-escaped text
        """
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )
