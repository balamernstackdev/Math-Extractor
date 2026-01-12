"""Structural analysis and AST construction from spatial tokens.

This module builds a semantic math tree from the spatial token stream,
preserving operator precedence, grouping, and layout relationships.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
from core.logger import logger
from .ast import ASTNode
from .glyph_classifier import Token


class StructureBuilder:
    """Build an abstract syntax tree from spatially-ordered tokens.
    
    Implements algorithms for:
    - Vertical relationship detection (subscripts/superscripts)
    - Fraction detection (horizontal bars)
    - Matrix/Grid detection
    - Operator precedence
    """
    
    def __init__(self):
        # Thresholds for spatial relationship detection
        self.sub_sup_vertical_threshold = 0.4  # relative to height
        self.sub_sup_horizontal_threshold = 1.0  # relative to width
        self.fraction_vertical_gap = 20  # pixels
        self.matrix_alignment_threshold = 10  # pixels
    
    def build_ast(self, tokens: List[Token]) -> ASTNode:
        """Build an AST from a list of spatial tokens.
        
        Args:
            tokens: List of classified tokens (sorted spatially)
            
        Returns:
            Root AST node representing the equation
        """
        if not tokens:
            logger.warning("[StructureBuilder] Empty token list, returning empty AST")
            return ASTNode(node_type="empty")
        
        logger.info(f"[StructureBuilder] Building AST from {len(tokens)} tokens")
        
        # 1. Detect Matrices (Grid Structure) first
        matrix_tokens, remaining_tokens = self._detect_matrices(tokens)
        root_nodes = []
        if matrix_tokens:
            root_nodes.append(matrix_tokens)
            # Re-process remaining tokens (linear approx)
            tokens = remaining_tokens
        
        # 2. Detect Fractions (Horizontal Bars)
        # This is recursive: fractions consume tokens above/below them
        nodes = self._process_fractions(tokens)
        
        # 3. Detect Sub/Superscripts on the remaining sequence
        final_nodes = self._process_sub_superscripts(nodes)
        
        # 4. Build Operator Tree / Sequence
        if len(final_nodes) == 1 and final_nodes[0].node_type == "matrix":
             return final_nodes[0] # Return the matrix directly if it's the only thing
             
        # Create a root equation node with the processed sequence
        root = ASTNode(node_type="equation")
        root.children.extend(final_nodes)
        
        return root

    def _process_fractions(self, tokens: List[Token]) -> List[ASTNode]:
        """Convert tokens into a list of AST nodes, processing fraction bars."""
        # Identification of fraction bars: long, thin, horizontal lines
        # This logic assumes 'operator' type or specific glyph '-' with high aspect ratio
        
        # Sort by x-coordinate primarily
        sorted_tokens = sorted(tokens, key=lambda t: t.bbox[0])
        
        nodes: List[ASTNode] = []
        
        # Heuristic: Find potential fraction bars
        # A token is a fraction bar if it's type is 'operator' and width/height > 3
        fraction_bars = []
        other_tokens = []
        
        for t in sorted_tokens:
            w, h = t.bbox[2], t.bbox[3]
            aspect = w / h if h > 0 else 0
            if t.glyph in ['-', '—', '−'] and aspect > 2.5:
                fraction_bars.append(t)
            else:
                other_tokens.append(t)
        
        if not fraction_bars:
            # No fractions, return tokens as basic Symbol nodes
            return [ASTNode(node_type="symbol", value=t.glyph) for t in other_tokens]
        
        # Process simplest case: One main fraction bar (simplification)
        # In a real implementation, we'd build a recursive proximity graph.
        # Here we take the widest bar as the main fraction.
        main_bar = max(fraction_bars, key=lambda t: t.bbox[2])
        
        bar_x, bar_y, bar_w, bar_h = main_bar.bbox
        
        numerator_tokens = []
        denominator_tokens = []
        remaining_tokens = []
        
        for t in other_tokens:
            tx, ty, tw, th = t.bbox
            t_center_x = tx + tw / 2
            t_center_y = ty + th / 2
            
            # Check horizontal overlap with bar
            if bar_x <= t_center_x <= bar_x + bar_w:
                if t_center_y < bar_y: # Above
                    numerator_tokens.append(t)
                elif t_center_y > bar_y + bar_h: # Below
                    denominator_tokens.append(t)
                else:
                    remaining_tokens.append(t) # Inline?
            else:
                remaining_tokens.append(t)
                
        # Recursively process numerator and denominator
        # (This handles nested fractions if we implement full recursion)
        num_node = self._build_sub_ast(numerator_tokens)
        denom_node = self._build_sub_ast(denominator_tokens)
        
        frac_node = ASTNode(node_type="fraction", children=[num_node, denom_node])
        
        # Re-assemble sequence: Left tokens -> Fraction -> Right tokens
        # Note: This simple logic assumes a single split. 
        # Robust implementation requires a full layout tree.
        
        result_nodes = []
        
        # Add tokens to left of fraction
        left_tokens = [t for t in remaining_tokens if t.bbox[0] + t.bbox[2] < bar_x]
        result_nodes.extend([ASTNode(node_type="symbol", value=t.glyph) for t in left_tokens])
        
        result_nodes.append(frac_node)
        
        # Add tokens to right of fraction
        right_tokens = [t for t in remaining_tokens if t.bbox[0] > bar_x + bar_w]
        result_nodes.extend([ASTNode(node_type="symbol", value=t.glyph) for t in right_tokens])
        
        return result_nodes

    def _build_sub_ast(self, tokens: List[Token]) -> ASTNode:
        """Helper to build AST from a subset of tokens (e.g. numerator)."""
        if not tokens:
            return ASTNode(node_type="empty")
        # Recursion: Process sub/sups for this subset
        nodes = [ASTNode(node_type="symbol", value=t.glyph) for t in tokens]
        nodes = self._process_sub_superscripts(nodes, tokens) # Pass corresponding tokens for geometry
        
        if len(nodes) == 1:
            return nodes[0]
        return ASTNode(node_type="sequence", children=nodes)

    def _process_sub_superscripts(self, nodes: List[ASTNode], source_tokens: List[Token] = None) -> List[ASTNode]:
        """
        Detect sub/superscript relationships based on token geometry.
        Note: The input `nodes` are currently simple symbols. 
        We need original geometry to determine containment.
        
        Limitations: Since `nodes` here are ASTNodes, we've lost BBox info.
        Ideally, we should work with a `TokenNode` wrapper until the final step.
        For this Phase 2 implementation, we will use a heuristic:
        This function currently just returns the linear sequence unless we refactor 
        to pass Geometry info through.
        
        FUTURE UPGRADE: Modify `_process_fractions` to return objects containing BBox info,
        so this step can do geometry checks.
        
        For now, this is a placeholder behavior as per Phase 1/2 transition.
        """
        return nodes

    def _detect_matrices(self, tokens: List[Token]) -> Tuple[Optional[ASTNode], List[Token]]:
        """
        Detect matrix/grid structures.
        Returns (MatrixNode, RemainingTokens)
        """
        # Placeholder: No matrix detection logic yet
        return None, tokens
