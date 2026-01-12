"""LaTeX to AST parser.

This module parses LaTeX strings into an Abstract Syntax Tree (AST)
using a Recursive Descent approach, enabling robust handling of nested structures.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple, Dict, Any
from core.logger import logger
from .ast import ASTNode


class LaTeXParser:
    """Recursive Descent Parser for LaTeX."""
    
    def __init__(self):
        # Semantic sets
        self.large_operators = {'∑', '∏', '∫', '∬', '∭', '∮', '⋃', '⋂', '⋁', '⋀', 'lim', 'max', 'min', 'sup', 'inf'}
        
        self.accent_commands = {
            r'\vec': '→', r'\hat': '^', r'\bar': '⎯', r'\dot': '˙', 
            r'\tilde': '~', r'\check': 'ˇ', r'\overline': '⎯',
            r'\widetilde': '~', r'\widehat': '^'
        }

        # Greek letters and operators map
        self.symbol_map = {
            r'\alpha': 'α', r'\beta': 'β', r'\gamma': 'γ', r'\delta': 'δ',
            r'\epsilon': 'ε', r'\zeta': 'ζ', r'\eta': 'η', r'\theta': 'θ',
            r'\iota': 'ι', r'\kappa': 'κ', r'\lambda': 'λ', r'\mu': 'μ',
            r'\nu': 'ν', r'\xi': 'ξ', r'\pi': 'π', r'\rho': 'ρ',
            r'\sigma': 'σ', r'\tau': 'τ', r'\upsilon': 'υ', r'\phi': 'φ',
            r'\chi': 'χ', r'\psi': 'ψ', r'\omega': 'ω',
            r'\Delta': 'Δ', r'\Gamma': 'Γ', r'\Theta': 'Θ', r'\Lambda': 'Λ',
            r'\Xi': 'Ξ', r'\Pi': 'Π', r'\Sigma': 'Σ', r'\Phi': 'Φ', r'\Psi': 'Ψ', r'\Omega': 'Ω',
                
            r'\sum': '∑', r'\prod': '∏', r'\int': '∫', r'\iint': '∬', r'\iiint': '∭', r'\oint': '∮', r'\infty': '∞',
            r'\in': '∈', r'\notin': '∉', r'\subset': '⊂', r'\supset': '⊃',
            r'\cup': '∪', r'\cap': '∩', r'\times': '×', r'\div': '÷',
            r'\leq': '≤', r'\geq': '≥', r'\neq': '≠', r'\approx': '≈',
            r'\leqq': '≦', r'\geqq': '≧', r'\leqslant': '⩽', r'\geqslant': '⩾',
            r'\partial': '∂', r'\nabla': '∇', r'\pm': '±', r'\mp': '∓',
            r'\cdot': '·', r'\ldots': '…',
            r'\equiv': '=', r'\rightarrow': '→', r'\leftarrow': '←', r'\leftrightarrow': '↔',
            r'\Rightarrow': '⇒', r'\Leftarrow': '⇐', r'\Leftrightarrow': '⇔',
            r'\iff': '⇔', r'\implies': '⇒', r'\longrightarrow': '⟶',
            r'\mapsto': '↦', r'\to': '→', r'\gets': '←',
            r'\forall': '∀', r'\exists': '∃', r'\nexists': '∄',
            r'\emptyset': '∅', r'\varnothing': '∅',
            r'\setminus': '∖', r'\land': '∧', r'\lor': '∨', r'\neg': '¬',
            r'\therefore': '∴', r'\because': '∵',
            r'\angle': '∠', r'\perp': '⊥', r'\parallel': '∥',
            r'\triangle': '△', r'\ast': '∗', r'\star': '⋆', r'\circ': '∘', r'\bullet': '∙',
            r'\sim': '∼', r'\simeq': '≃', r'\cong': '≅',
            r'\triangleq': '≜',
            r'\ell': 'ℓ', r'\Re': 'ℜ', r'\Im': 'ℑ', r'\hbar': 'ℏ',
            r'\{': '{', r'\}': '}',
            # Spacing
            r'\quad': '\u2003', r'\qquad': '\u2003\u2003', r'\,': '\u2009', r'\;': '\u2004',
            # Relations
            r'\subseteq': '⊆', r'\supseteq': '⊇',
        }

    def parse(self, latex: str) -> ASTNode:
        """Parse LaTeX string into AST."""
        if not latex or not latex.strip():
            return ASTNode(node_type="empty")

        # 1. Preprocess
        clean_latex = self._preprocess(latex)
        
        # 2. Tokenize (Atomic)
        tokens = self._tokenize_atomic(clean_latex)
        
        # 3. Parse with State
        self.tokens = tokens
        self.pos = 0
        
        try:
            # Parse as if we are in a flexible environment allowing \\ and &
            rows = []
            current_row_cells = []
            
            while self.pos < len(self.tokens):
                # Parse sequence until & or \\ or EOF
                # _parse_sequence automatically stops at these tokens (implicitly returning None in _parse_item)
                # It returns a 'row' node containing the sequence found.
                cell_node = self._parse_sequence(stop_tokens=[])
                
                # Wrap content in mtd (cell)
                # cell_node is an 'row' (mrow) wrapper around the items
                current_row_cells.append(ASTNode(node_type="mtd", children=[cell_node], is_structural=True))
                
                token = self._peek()
                
                if token == '&':
                    self._consume()
                    continue
                elif token == r'\\' or token == r'\cr':
                    self._consume()
                    # Finish row
                    rows.append(ASTNode(node_type="mtr", children=current_row_cells, is_structural=True))
                    current_row_cells = []
                    continue
                else:
                    # EOF or stopped for other reason (like '}' which shouldn't happen at top level but might)
                    break
            
            # Flush last pending row
            if current_row_cells:
                rows.append(ASTNode(node_type="mtr", children=current_row_cells, is_structural=True))
                
            # Decision: Single line vs Multiline
            if len(rows) == 0:
                return ASTNode(node_type="empty")
                
            if len(rows) == 1:
                # If single row
                single_row = rows[0]
                
                # Check for empty row (e.g. only ignored commands)
                if not single_row.children:
                    return ASTNode(node_type="empty")
                    
                # If single cell in that row
                if len(single_row.children) == 1:
                    # Return the content of that cell (unwrap to standard AST)
                    # mtr -> mtd -> row -> content
                    # We want 'row' (or its children if needed, but 'row' is safe)
                    return single_row.children[0].children[0]
                else:
                    # Single row but multiple columns (a & b)
                    # Treat as matrix/table
                    return ASTNode(node_type="mtable", children=rows, attributes={"columnalign": "center"}, is_structural=True)
            else:
                # Multiple rows -> Multiline equation
                # Default to left alignment for multiline equations
                return ASTNode(node_type="mtable", children=rows, attributes={"columnalign": "left", "rowspacing": "0.5ex"}, is_structural=True)

        except Exception as e:
            logger.error(f"[LaTeXParser] Recursive parse failed: {e}")
            # Fallback
            return ASTNode(node_type="equation", children=[
                ASTNode(node_type="symbol", value=latex)
            ], is_structural=True)

    def _preprocess(self, latex: str) -> str:
        """Clean latex string."""
        latex = latex.strip()
        # Remove delimiters
        if latex.startswith('$$') and latex.endswith('$$'): latex = latex[2:-2]
        elif latex.startswith('$') and latex.endswith('$'): latex = latex[1:-1]
        elif latex.startswith(r'\(') and latex.endswith(r'\)'): latex = latex[2:-2]
        elif latex.startswith(r'\[') and latex.endswith(r'\]'): latex = latex[2:-2]
        
        # Common replacements

        
        return latex.strip()

    def _tokenize_atomic(self, latex: str) -> List[str]:
        """Break LaTeX into atomic tokens."""
        tokens = []
        i = 0
        n = len(latex)
        
        while i < n:
            char = latex[i]
            
            # Whitespace
            if char.isspace():
                i += 1
                continue
                
            # Command
            if char == '\\':
                # Check for escaped braces \{ and \}
                if i + 1 < n and latex[i+1] in ['{', '}']:
                    tokens.append('\\' + latex[i+1])
                    i += 2
                    continue
                
                # Check for escaped char like \{ or \%
                if i + 1 < n and not latex[i+1].isalpha():
                    tokens.append(latex[i:i+2])
                    i += 2
                    continue
                    
                # Read command name
                j = i + 1
                while j < n and latex[j].isalpha():
                    j += 1
                tokens.append(latex[i:j])
                i = j
                continue
                
            # Braces and Special Chars
            if char in '{}()[]^_-&':
                tokens.append(char)
                i += 1
                continue
                
            # Digits (group them?)
            # For simplicity, keeping digits separate or grouped doesn't matter much 
            # if we parse atomic. But grouping numbers is nicer.
            if char.isdigit():
                j = i + 1
                while j < n and (latex[j].isdigit() or latex[j] == '.'):
                    j += 1
                tokens.append(latex[i:j])
                i = j
                continue
            
            # Normal char
            tokens.append(char)
            i += 1
            
        return tokens

    # -------------------------------------------------------------------------
    # Recursive Descent Methods
    # -------------------------------------------------------------------------

    def _peek(self) -> Optional[str]:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def _consume(self) -> Optional[str]:
        if self.pos < len(self.tokens):
            t = self.tokens[self.pos]
            self.pos += 1
            return t
        return None

    def _expect(self, token: str) -> bool:
        """Consume if matches, else false."""
        if self._peek() == token:
            self._consume()
            return True
        return False

    def _parse_sequence(self, stop_tokens: List[str] = None) -> ASTNode:
        """Parse a sequence of expressions until a stop token or EOF."""
        children = []
        stop_tokens = stop_tokens or []
        
        while self._peek() is not None:
            if self._peek() in stop_tokens:
                break
                
            # Special handling for & and \\ in matrices
            # If we are NOT in a matrix environment, how do we handle them?
            # Usually they delimit rows/cells.
            # Ideally _parse_sequence stops at them if they are delimiters.
            if self._peek() in ['&', r'\\']:
                 if 'matrix_context' not in stop_tokens: 
                     # If we are just reading a row, these acts as implicit stoppers 
                     # if we treat top-level as potential matrix.
                     pass 
                 else:
                     break
            
            node = self._parse_item()
            if node:
                # Handle Post-fix operators (subscript/superscript)
                while self._peek() in ['_', '^']:
                    node = self._parse_script(node)
                
                children.append(node)
            else:
                # Node is None. This could mean:
                # 1. We hit a stop token (handled by _parse_item check usually)
                # 2. We hit an ignored command (like \displaystyle)
                # 3. We hit EOF (loop condition handles this)
                
                # Check if we should actually stop
                next_tok = self._peek()
                if next_tok is None or next_tok in stop_tokens or next_tok in ['}', '&', r'\\', r'\end']:
                    break
                
                # Otherwise, it was just an ignored command/token -> Continue parsing
                continue
        
        # If single child? usually return row anyway for consistency
        return ASTNode(node_type="row", children=children, is_structural=True)

    def _parse_item(self) -> Optional[ASTNode]:
        """Parse a single item (command, group, or symbol)."""
        token = self._peek()
        if token is None: return None
        
        # Group { ... }
        if token == '{':
            self._consume()
            # Recurse
            node = self._parse_sequence(stop_tokens=['}'])
            self._expect('}')
            return node
            
        # Command
        if token.startswith('\\'):
            return self._parse_command()
            
        # Stopping tokens
        if token in ['}', '&', r'\\', r'\end']:
            return None
            
        # Symbols / Text
        self._consume()
        return self._create_symbol_node(token)

    def _parse_command(self) -> ASTNode:
        cmd = self._consume()
        
        # 1. Fraction
        if cmd == r'\frac':
            num = self._parse_argument()
            denom = self._parse_argument()
            return ASTNode(node_type="fraction", children=[num, denom])

        # 2. Sqrt/Root
        if cmd == r'\sqrt':
            # Check for optional index [n]
            if self._peek() == '[':
                self._consume() # [
                index = self._parse_sequence(stop_tokens=[']'])
                self._expect(']')
                content = self._parse_argument()
                return ASTNode(node_type="root", children=[content, index])
            else:
                content = self._parse_argument()
                return ASTNode(node_type="sqrt", children=[content])

        # 3. Scripts / Limits
        if cmd == r'\limits':
            # This should modify the previous node in a real parser, but here we ignore 
            # or it's handled by _parse_script logic logic usually.
            # For strict AST, we can treat it as a flag or ignore.
            return None # Ignore for now

        # 4. Environment
        if cmd == r'\begin':
            return self._parse_environment()
            
        # 5. Text / Styles
        # 8. Font Styles (mathbb, etc.)
        style_map = {
            r'\mathbb': 'double-struck',
            r'\mathbf': 'bold', r'\bf': 'bold',
            r'\mathit': 'italic', r'\it': 'italic',
            r'\mathrm': 'normal', r'\rm': 'normal',
            r'\mathcal': 'script', r'\cal': 'script',
            r'\text': 'normal',
            r'\textit': 'italic',
            r'\textbf': 'bold',
            r'\texttt': 'monospace', r'\tt': 'monospace',
            r'\mathsf': 'sans-serif', r'\sf': 'sans-serif',
            r'\mathscr': 'script',
        }
        
        if cmd in style_map:
            content = self._parse_argument()
            
            # Special handling for \text - Produce text node
            if cmd == r'\text':
                try:
                    text_val = self._extract_text_from_node(content)
                except Exception:
                    text_val = ""
                return ASTNode(node_type="text", value=text_val, attributes={"variant": "normal"})
                
            # Standard styles - Produce style node
            variant = style_map[cmd]
            return ASTNode(node_type="style", children=[content], 
                         attributes={"mathvariant": variant})

        # 8. Accents (\tilde, \vec, etc.)
        if cmd in self.accent_commands:
            content = self._parse_argument()
            accent_char = self.accent_commands[cmd]
            
            # Create symbol node for the accent
            accent_node = ASTNode(node_type="symbol", value=accent_char, is_operator=True)
            
            # Return overscript with accent=true
            return ASTNode(node_type="overscript", children=[content, accent_node], 
                         attributes={"accent": "true"})

        # 8a. Underscripts (\underline, etc.)
        if cmd == r'\underline':
            content = self._parse_argument()
            # U+005F or appropriate underline char. Standard MathML uses <munder> with bar.
            # We can use a special symbol or just let MathML serializer handle 'underline' if we had a specific node.
            # But here we want to map to an underscript node with a line operator.
            line_node = ASTNode(node_type="symbol", value="_", is_operator=True)
            return ASTNode(node_type="underscript", children=[content, line_node])

        # 7. Underover / Limits
        if cmd == r'\munderover':
            base = self._parse_argument()
            under = self._parse_argument()
            over = self._parse_argument()
            return ASTNode(node_type="underover", children=[base, under, over])

        if cmd == r'\underset':
            under = self._parse_argument()
            base = self._parse_argument()
            return ASTNode(node_type="underscript", children=[base, under])

        if cmd == r'\overset':
            over = self._parse_argument()
            base = self._parse_argument()
            return ASTNode(node_type="overscript", children=[base, over])

        # 6. Fences (\left ... \right)
        if cmd == r'\left':
            # Consume open delimiter
            open_delim = self._consume() # e.g. ( or [ or \{
            
            # Parse content until \right
            # This is tricky because we need to match the specific \right
            # but usually recursive parsing works fine if we just stop at \right
            
            # Use _parse_sequence with stop token \right?
            # Issue: _parse_sequence splits by token. \right is a token.
            content = self._parse_sequence(stop_tokens=[r'\right'])
            
            self._expect(r'\right')
            close_delim = self._consume() # e.g. ) or ]
            
            return ASTNode(node_type="fence", children=[content], 
                         attributes={"open": open_delim, "close": close_delim})

        # 9. Ignored Style Commands/Declarations (Prevent artifacts)
        # We silently consume them to prevent them appearing as text
        if cmd in [r'\displaystyle', r'\textstyle', r'\scriptstyle', r'\scriptscriptstyle']:
            # These are declarations. For now, strictly ignore them to fix artifacts.
            # Ideally they should affect the current group mode.
            return None

        # Default: Symbol
        return self._create_symbol_node(cmd)

    def _parse_argument(self) -> ASTNode:
        """Parse a mandatory argument for a command."""
        node = None
        # Argument can be a group { ... } or widely a single token
        if self._peek() == '{':
            node = self._parse_item() # This handles the group parsing
        else:
            # Single token argument
            node = self._parse_item()
            
        # Unwrap single-child row if needed (for cleaner AST)
        if node and node.node_type == "row" and len(node.children) == 1:
            return node.children[0]
            
        return node

    def _parse_script(self, base: ASTNode) -> ASTNode:
        """Attach subscript or superscript to base."""
        op = self._consume() # _ or ^
        script = self._parse_argument()
        
        # Check for large operator context (limits vs scripts)
        is_large_op = self._is_large_operator(base)
        
        if op == '_':
            if is_large_op:
                return ASTNode(node_type="underscript", children=[base, script])
            
            # Check if base is already superscript -> subsup
            if base.node_type == "superscript":
                real_base = base.children[0]
                sup = base.children[1]
                return ASTNode(node_type="subsup", children=[real_base, script, sup])
            
            # Check if base is already overscript -> underover
            if base.node_type == "overscript":
                real_base = base.children[0]
                over = base.children[1]
                return ASTNode(node_type="underover", children=[real_base, script, over])
                
            return ASTNode(node_type="subscript", children=[base, script])
            
        elif op == '^':
            if is_large_op:
                return ASTNode(node_type="overscript", children=[base, script])
                
            # Check if base is already subscript -> subsup
            if base.node_type == "subscript":
                real_base = base.children[0]
                sub = base.children[1]
                return ASTNode(node_type="subsup", children=[real_base, sub, script])

            # Check if base is underscript -> underover
            if base.node_type == "underscript":
                real_base = base.children[0]
                under = base.children[1]
                return ASTNode(node_type="underover", children=[real_base, under, script])
                
            return ASTNode(node_type="superscript", children=[base, script])
            
        return base

    def _parse_environment(self) -> ASTNode:
        """Parse \\begin{env} ... \\end{env}."""
        # 1. Get Environment Name
        if self._peek() != '{':
            return ASTNode(node_type="error", value="missing env name")
        
        self._consume() # {
        env_node = self._parse_sequence(stop_tokens=['}']) 
        env_name = self._extract_text_from_node(env_node)
        self._expect('}')
        
        # 2. Environment Configuration
        # Different environments have different logical structures
        env_config = self._get_environment_config(env_name)
        
        # 2b. Check for Environment Arguments (e.g. \begin{array}{lcl})
        if env_name in ["array", "tabular"]:
            if self._peek() == '{':
                self._consume() # {
                arg_node = self._parse_sequence(stop_tokens=['}'])
                arg_text = self._extract_text_from_node(arg_node)
                self._expect('}')
                
                # Parse alignment chars (l, c, r)
                # Ignore | for now (could translate to columnlines)
                aligns = []
                for char in arg_text:
                    if char == 'l': aligns.append('left')
                    elif char == 'c': aligns.append('center')
                    elif char == 'r': aligns.append('right')
                
                if aligns:
                    env_config["attributes"]["columnalign"] = " ".join(aligns)
        
        # 3. Parse Content (Rows and Cells)
        rows = []
        current_row = []
        current_cell_nodes = []
        
        # We parse until \\end{env_name}
        while self.pos < len(self.tokens):
            token = self._peek()
            
            # Check for end of environment
            if token == r'\end':
                # Lookahead to check if it's OUR end
                save_pos = self.pos
                self._consume() # \end
                if self._peek() == '{':
                    self._consume()
                    end_name_node = self._parse_sequence(stop_tokens=['}'])
                    end_name_text = self._extract_text_from_node(end_name_node)
                    self._expect('}')
                    
                    if end_name_text == env_name:
                        break # Successfully found matching end
                    else:
                        # Mismatched end - backtrack and treat as content (maybe nested error)
                        # or just break if we assume it closes the outer one too?
                        # For robustness: backtrack.
                        self.pos = save_pos
                else:
                     self.pos = save_pos
            
            # Handle Cell Delimiter (&)
            if token == '&':
                self._consume()
                # Finish current cell
                # Wrap content in mtd -> row
                cell_row = ASTNode(node_type="row", children=current_cell_nodes, is_structural=True)
                current_row.append(ASTNode(node_type="mtd", children=[cell_row], is_structural=True))
                current_cell_nodes = []
                continue
                
            # Handle Row Delimiter (\\ or \cr)
            if token == r'\\' or token == r'\cr':
                self._consume()
                # Finish current cell
                cell_row = ASTNode(node_type="row", children=current_cell_nodes, is_structural=True)
                current_row.append(ASTNode(node_type="mtd", children=[cell_row], is_structural=True))
                current_cell_nodes = []
                # Finish row
                rows.append(ASTNode(node_type="mtr", children=current_row, is_structural=True))
                current_row = []
                continue
            
            # Parse Item
            item = self._parse_item()
            if item:
                # Check for scripts
                while self._peek() in ['_', '^']:
                    item = self._parse_script(item)
                current_cell_nodes.append(item)
            else:
                # Item is None. This happens if we hit a stop token that _parse_item recognizes (like } or &)
                # If we hit '&', the loop above should have caught it.
                # If we hit '}', it might be a stray brace.
                # Avoid infinite loop: consume one token if we're stuck
                if self.pos < len(self.tokens):
                    # Consuming unknown token as symbol to proceed
                    unknown = self._consume()
                    current_cell_nodes.append(ASTNode(node_type="symbol", value=unknown))
                else:
                    break
                
        # Flush pending cell/row
        if current_cell_nodes:
            cell_row = ASTNode(node_type="row", children=current_cell_nodes, is_structural=True)
            current_row.append(ASTNode(node_type="mtd", children=[cell_row], is_structural=True))
        if current_row:
             rows.append(ASTNode(node_type="mtr", children=current_row, is_structural=True))
             
        # 4. Construct Result Node
        attributes = env_config.get("attributes", {}).copy()
        
        # If it's a matrix/table type, return mtable
        if env_config.get("is_table", True):
            node = ASTNode(node_type="mtable", children=rows, attributes=attributes, is_structural=True)
            
            # Wrap in fence if needed
            if "fence" in env_config:
                open_f, close_f = env_config["fence"]
                return ASTNode(node_type="fence", children=[node], 
                             attributes={"open": open_f, "close": close_f})
            return node
            
        return ASTNode(node_type="row", children=rows, is_structural=True)

    def _get_environment_config(self, env_name: str) -> Dict[str, Any]:
        """Get semantic configuration for an environment."""
        # Defaults
        config = {
            "is_table": True, 
            "attributes": {"columnspacing": "1em", "rowspacing": "0.5ex"}
        }
        
        # 1. Matrices (Simple)
        if env_name == "matrix":
            pass # Default
        elif env_name == "pmatrix":
            config["fence"] = ("(", ")")
        elif env_name == "bmatrix":
            config["fence"] = ("[", "]")
        elif env_name == "vmatrix":
            config["fence"] = ("|", "|")
        elif env_name == "Vmatrix":
            config["fence"] = ("‖", "‖")
        elif env_name == "Bmatrix":
            config["fence"] = ("{", "}")
            
        # 2. Cases
        elif env_name == "cases":
            config["fence"] = ("{", "")
            config["attributes"]["columnalign"] = "left"
            config["attributes"]["rowspacing"] = "0.2ex" # Tighter for cases
            
        # 3. Align / Aligned (Alternating right/left)
        elif env_name in ["align", "align*", "aligned"]:
            # Standard align is usually RLRL...
            # We can approximate with "right left" repeating or just "right left"
            config["attributes"]["columnalign"] = "right left"
            config["attributes"]["displaystyle"] = "true"
            
        # 4. Gather (Centered)
        elif env_name in ["gather", "gather*", "gathered"]:
            config["attributes"]["columnalign"] = "center"
            
        # 5. Split (used inside align)
        elif env_name == "split":
            config["attributes"]["columnalign"] = "right left"
            
        # 6. Array (User defined columns - complex)
        elif env_name == "array":
            # Parsing array args ({ccl}) is complex; defaulting to center for now
            config["attributes"]["columnalign"] = "center"
            
        return config

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _create_symbol_node(self, token: str) -> ASTNode:
        if token in self.symbol_map:
            val = self.symbol_map[token]
            # Check if operator (heuristic: not alphanumeric or is in large_operators)
            is_op = not val.isalnum() or val in self.large_operators
            return ASTNode(node_type="symbol", value=val, is_operator=is_op)
            
        # Check if text command (should have been caught) or just chars
        is_op = not token.isalnum()
        return ASTNode(node_type="symbol", value=token, is_operator=is_op)

    def _is_large_operator(self, node: ASTNode) -> bool:
        if node.node_type == "symbol":
            return node.value in self.large_operators
        # Check text value for commands like \sum that mapped to unicode
        return False

    def _extract_text_from_node(self, node: ASTNode) -> str:
        """Recursively get text from node."""
        if node.value: return node.value
        return "".join(self._extract_text_from_node(c) for c in node.children)