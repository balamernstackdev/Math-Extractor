"""
Corrected Latex → MathML converter.

ENHANCED VERSION:
- Handles multi-line equations (2+ lines) with mtable structure
- Detects equation labels like (ii), (2.1), etc.
- Supports align, aligned, eqnarray environments
- Uses latex2mathml strictly for each line
- Provides clean fallback MathML on failure
"""

from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from latex2mathml.converter import convert as latex2mathml_convert

from core.logger import logger


ET.register_namespace("", "http://www.w3.org/1998/Math/MathML")


from services.ocr.pipeline_components.latex_normalizer import LatexNormalizer
from services.ocr.pipeline_components.latex_validator import LatexValidator
from services.ocr.pipeline_components.math_fx_fixer import MathFXFixer
from services.ocr.pipeline_components.shared_types import MultilineInfo, ALIGNMENT_SPECS
from services.ocr.pipeline_components.multiline_converter import MultilineConverter
from services.ocr.pipeline_components.matrix_converter import MatrixConverter
from services.ocr.pipeline_components.post_processor import PostProcessor

MULTILINE_ENVIRONMENTS = ['align', 'aligned', 'eqnarray', 'gather', 'gathered', 'cases', 'split', 'multline']

# Explicitly export for backward compatibility with tests
__all__ = ['LatexToMathML', 'MultilineInfo', 'ALIGNMENT_SPECS']


class LatexToMathML:
    """Convert clean LaTeX to MathML, with multi-line equation support."""
    
    def __init__(self):
        self.normalizer = LatexNormalizer()
        self.validator = LatexValidator()
        self.fixer = MathFXFixer()
        self.multiline_conv = MultilineConverter()
        self.matrix_conv = MatrixConverter()
        self.post_processor = PostProcessor()
        
        # DEBUG: Check dependencies explicitly
        try:
            import lxml.etree
            logger.info("[LatexToMathML] lxml.etree available")
        except ImportError as e:
            logger.error(f"[LatexToMathML] lxml.etree MISSING: {e}")
            
        try:
            import latex2mathml.converter
            logger.info("[LatexToMathML] latex2mathml available")
        except ImportError as e:
            logger.error(f"[LatexToMathML] latex2mathml MISSING: {e}")

    def _validate_latex(self, latex: str) -> tuple[bool, str]:
        """Shim for backward compatibility with tests."""
        return self.validator.validate(latex)

    def detect_multiline_equation(self, latex: str) -> Optional[MultilineInfo]:
        """Shim for backward compatibility with tests."""
        return self.multiline_conv.detect(latex)

    def _get_column_alignment(self, info: MultilineInfo) -> str:
        """Shim for backward compatibility with tests."""
        return self.multiline_conv.get_alignment(info)

    def _parse_aligned_line(self, line: str, environment: str) -> List[str]:
        """Shim for backward compatibility with tests."""
        return self.multiline_conv.parse_line(line, environment)

    def _repair_common_ocr_errors(self, latex: str) -> str:
        """Restore missing legacy method for tests."""
        return self.normalizer.normalize(latex)

    def detect_probability_of_error(self, latex: str) -> bool:
        """Restore missing legacy method for tests."""
        patterns = [r'P_r', r'P_e', r'P\{', r'P\(']
        return any(re.search(p, latex) for p in patterns)


    def _apply_mml_prefixes(self, mathml: str) -> str:
        """
        Add 'mml:' prefix to all MathML tags and ensure xmlns:mml declaration.
        This changes <math> to <mml:math>, <mi> to <mml:mi>, etc.
        """
        if not mathml:
            return mathml
            
        # 1. Add prefixes to opening tags
        # Match <tag where tag doesn't start with mml:, /, !, ?
        mathml = re.sub(r'<(?!(?:mml:|/|!|\?))([a-zA-Z0-9]+)', r'<mml:\1', mathml)
        
        # 2. Add prefixes to closing tags
        # Match </tag where tag doesn't start with mml:
        mathml = re.sub(r'</(?!(?:mml:))([a-zA-Z0-9]+)', r'</mml:\1', mathml)
        
        # 3. Add xmlns:mml declaration to root math tag if not present
        if 'xmlns:mml=' not in mathml and '<mml:math' in mathml:
            # We add it to the first <mml:math tag we find
            mathml = mathml.replace('<mml:math', '<mml:math xmlns:mml="http://www.w3.org/1998/Math/MathML"', 1)
            
        return mathml

    def convert(self, latex: str) -> str:
        """
        Convert LaTeX to MathML.
        """
        try:
            # Internal conversion (returns standard MathML)
            mathml = self._convert_internal(latex)
            
            # Fix unbalanced fences specifically for cases/array environments (e.g. missing closing fence)
            mathml = self._fix_unbalanced_cases(mathml)
            
            return mathml
        except Exception as e:
            logger.error(f"LatexToMathML.convert failure: {e}")
            return f'<math xmlns="http://www.w3.org/1998/Math/MathML" display="block" data-error="conversion-failure" data-details="{str(e)[:100]}"/>'

    def _convert_internal(self, latex: str) -> str:
        if not latex or not latex.strip():
            return '<math xmlns="http://www.w3.org/1998/Math/MathML" display="block"></math>'

        original = latex

        # 1. Pipeline: Normalization (Includes OCR fixes now)
        latex = self.normalizer.normalize(latex)

        # CRITICAL: Handle implicit newlines from OCR (which LaTeX treats as space)
        # If we have newlines but no '\\', convert them to '\\' to force multiline display
        if '\n' in latex and '\\\\' not in latex and '\\begin' not in latex:
             logger.info("Converting implicit newlines to backslashes for multiline display structure")
             latex = latex.replace('\n', ' \\\\ ')

        # 2. Pipeline: Validation
        is_valid, error = self.validator.validate(latex)
        if not is_valid:
            logger.warning(f"Validation Warning: {error}")
            if "Truncated" in error:
                raise ValueError(error)

        # 3. Extract labels (preserve them separate from AST)
        equation_label, latex = self._extract_label(latex)

        # 4. Convert using Semantic AST (Primary Path)
        try:
            from services.ocr.latex_parser import LaTeXParser
            from services.ocr.ast_to_mathml import ASTToMathMLSerializer
            
            parser = LaTeXParser()
            serializer = ASTToMathMLSerializer()
            
            # Parse
            ast = parser.parse(latex)
            
            # Check for trivial fallback logic in Parser
            # If the parser failed recursively, it might return equation -> [symbol(full_latex)]
            is_trivial_fallback = (
                ast.node_type == "equation" 
                and len(ast.children) == 1 
                and ast.children[0].node_type == "symbol"
                and len(ast.children[0].value or "") > 20 # Only if it's a long string (not just 'x')
            )
            
            if is_trivial_fallback:
                logger.warning("Parser returned trivial fallback - attempting legacy regex.")
                raise ValueError("Parser returned trivial fallback")

            # Serialize
            mathml = serializer.serialize(ast)
            
            if mathml and '<math' in mathml:
                # 5. Post-process (Standardize namespace/attributes)
                # Note: Serializer already adds namespace/display, but PostProcessor ensures it.
                mathml = self.post_processor.ensure_namespace(mathml)
                mathml = self.fixer.enforce_limits(mathml)
                
                # 6. Re-attach label
                if equation_label:
                    mathml = self._attach_label(mathml, equation_label)
                
                # 7. Final attributes
                mathml = self._ensure_block_display(mathml)
                return mathml

        except Exception as ast_exc:
            logger.warning(f"AST Conversion failed: {ast_exc}, falling back to regex extraction.")
            # Fallthrough to legacy
            pass
            
        # 5. Legacy Regex Conversion (Fallback)
        # Only reached if Parser crashes or gives trivial output
        mathml = latex2mathml_convert(latex)
        
        # Post-process legacy output
        mathml = self.post_processor.ensure_namespace(mathml)
        mathml = self._normalize_operator_tags(mathml) 
        mathml = self.post_processor.clean_invalid_mathml(mathml)
        mathml = self.fixer.enforce_limits(mathml)

        if equation_label:
            mathml = self._attach_label(mathml, equation_label)
        
        mathml = self._ensure_block_display(mathml)
        return mathml

    def _apply_critical_fixes(self, latex: str) -> str:
        """Apply critical regex-based fixes for common LaTeX issues."""
        try:
             # 1. Wrap text keywords in \text{} to prevent them being parsed as variables
             # Pattern: "} for {" or ") for =" or "∈ E for i"
             latex = re.sub(r'(?<=[)}\s∈=])\s+(for|and|where|if)\s+(?=[=(∈\\a-z])', 
                           r' \\quad \\text{\1} \\quad ', latex)

             # 2. Fix missing space after operators - REMOVED (Too aggressive, breaks \inf, \left, \leqq)
             # latex = re.sub(r'\\(le|ge|leq|geq|in|to|neq|sim|approx)(?=[A-Za-z0-9])', r'\\\1 ', latex)

             # Match \equiv not followed by space, replace with \equiv + space
             latex = re.sub(r'\\equiv(?=[^a-zA-Z])', r'\\equiv ', latex)

             # CRITICAL FIX for User Feedback "Paragraph style is confusion"
             # 1. Strip \left and \right commands to prevent them from appearing as literal text
             #    if the converter fails to parse them. Standard delimiters [ ] ( ) will render fine.
             latex = latex.replace(r'\left', '')
             latex = latex.replace(r'\right', '')

             # 2. Fix \le and \ge appearing as text
             latex = re.sub(r'\\le(?=[^a-zA-Z])', r'\\leq', latex) # \leX -> \leqX
             latex = re.sub(r'\\le\s+', r'\\leq ', latex)           # \le X -> \leq X
             latex = re.sub(r'\\ge(?=[^a-zA-Z])', r'\\geq', latex)
             latex = re.sub(r'\\ge\s+', r'\\geq ', latex)

             # 3. Force display style limits for clearer, non-inline summation/products
             #    Replace \sum_{...} with \sum\limits_{...}
             latex = re.sub(r'\\(sum|prod|lim|max|min|sup|inf|bigcap|bigcup)(?=\s*_)', r'\\\1\\limits', latex)
             
             # Also replace \sim with \sim (no change needed usually, but check context)
        except Exception:
            pass
            
        # EXTRA NORMALIZATION for "Listing" artifacts
        # If \mathit{...} contains LaTeX commands (starting with \), chances are it's an error or 
        # latex2mathml will treat it as verbatim text. Unwrap it.
        # Regex: \mathit{...\\[a-zA-Z]...}
        # We greedily replace \mathit{<code>} with <code> if <code> contains \
        # This is a heuristic.
        try:
            # 1. Specific fix for overlapping/hallucinated \mathit{\Big|} artifacts
            if r'\mathit{\Big' in latex:
                 latex = latex.replace(r'\mathit{\Big|}', r'\Big|')
                 latex = latex.replace(r'\mathit{\Big', r'\Big')

            # 2. General unwrap of \mathit if it contains '\'
            # Note: robust brace matching is hard with regex, focusing on simple cases
            latex = re.sub(r'\\mathit\{([^\}]*?\\[^\}]*?)\}', r'\1', latex)
        except Exception:
            pass

        return latex

    def _fallback_complex_equation(self, latex: str) -> str:
        """
        Fallback for very complex equations that fail latex2mathml.
        Try to convert in a more robust way by simplifying.
        """
        logger.info("[Fallback] Attempting simplified conversion for complex equation")
        
        # Try wrapping in displaymath environment
        try:
            simplified = r'\[' + latex + r'\]'
            mathml = latex2mathml_convert(simplified)
            if mathml and '<math' in mathml:
                return self._ensure_namespace(mathml)
        except Exception:
            pass
        
        # If that failed, try removing problematic constructs
        try:
            # Remove \limits commands (they might be causing issues)
            simplified = latex.replace(r'\limits', '')
            mathml = latex2mathml_convert(simplified)
            if mathml and '<math' in mathml:
                return self._ensure_namespace(mathml)
        except Exception:
            pass
        
        # Last resort: Return a placeholder MathML
        logger.error("[Fallback] All conversion attempts failed")
        raise ValueError("Complex equation conversion failed in fallback")


    def _clean_invalid_mathml(self, mathml: str) -> str:
        """
        Clean invalid MathML by removing literal LaTeX commands and fixing corrupted text.
        
        Fixes:
        - Removes literal LaTeX commands like \\stackrel, \\dag from MathML
        - Fixes corrupted text like "Iniln" → "min" (OCR errors)
        - Removes invalid elements containing LaTeX commands
        """
        if not mathml or '<math' not in mathml:
            return mathml
        
        try:
            root = ET.fromstring(mathml)
        except Exception:
            # If parsing fails, try regex-based cleaning
            return self._clean_invalid_mathml_regex(mathml)
        
        ns = "{http://www.w3.org/1998/Math/MathML}"
        changed = False
        
        # Pattern: Detect corrupted "min" as separate letters (Iniln, mln, etc.)
        # Common OCR errors: Iniln, mln, mln, etc. → min
        corrupted_min_patterns = [
            (r'^[Ii][Nn][Ii][Ll][Nn]$', 'min'),  # Iniln → min
            (r'^[Mm][Ll][Nn]$', 'min'),  # mln → min
            (r'^[Mm][Ii][Nn]$', 'min'),  # min (already correct but normalize)
        ]
        
        # Walk through all elements
        stack = [root]
        while stack:
            el = stack.pop()
            stack.extend(list(el))
            
            # Check <mi> elements for literal LaTeX commands or corrupted text
            if el.tag == f"{ns}mi" or el.tag == "mi":
                text = (el.text or "").strip()
                
                # Remove literal LaTeX commands
                if text.startswith('\\') and len(text) > 1:
                    # Contains LaTeX command - remove it
                    logger.warning("Found literal LaTeX command in MathML: %s - removing", text)
                    # Remove the element by clearing its parent's reference
                    # We'll handle this by replacing with empty or removing
                    el.text = ""
                    changed = True
                elif text in ['\\stackrel', 'stackrel', '\\dag', 'dag']:
                    # Common literal LaTeX commands
                    logger.warning("Found literal LaTeX command in MathML: %s - removing", text)
                    el.text = ""
                    changed = True
                else:
                    # Check for corrupted "min" patterns
                    for pattern, replacement in corrupted_min_patterns:
                        if re.match(pattern, text):
                            logger.info("Fixed corrupted 'min' pattern: %s → %s", text, replacement)
                            el.text = replacement
                            changed = True
                            break
            
            # Check <mtext> elements for LaTeX commands (should never have LaTeX)
            if el.tag == f"{ns}mtext" or el.tag == "mtext":
                text = (el.text or "").strip()
                if text.startswith('\\') and len(text) > 1:
                    logger.warning("Found LaTeX command in <mtext>: %s - removing", text)
                    el.text = ""
                    changed = True
        
        # Fix corrupted "min" that appears as multiple <mi> elements
        # Pattern: <mi>I</mi><mi>n</mi><mi>i</mi><mi>l</mi><mi>n</mi> → <mi>min</mi>
        def fix_corrupted_min_in_sequence(parent):
            """Fix sequences of <mi> elements that form corrupted 'min'."""
            children = list(parent)
            if len(children) < 3:
                return False
            
            # Look for sequences of <mi> elements that might be corrupted "min"
            i = 0
            fixed_any = False
            while i < len(children) - 2:
                # Check if we have a sequence of <mi> elements
                seq_length = 0
                while i + seq_length < len(children):
                    child = children[i + seq_length]
                    if child.tag == f"{ns}mi" or child.tag == "mi":
                        seq_length += 1
                    else:
                        break
                
                if seq_length >= 3:
                    # Collect text from sequence
                    seq_text = "".join((children[i+j].text or "").strip() for j in range(seq_length))
                    if len(seq_text) >= 3:
                        # Check if it matches corrupted min patterns
                        for pattern, replacement in corrupted_min_patterns:
                            if re.match(pattern, seq_text):
                                # Replace sequence with single <mi>min</mi>
                                logger.info("Fixed corrupted 'min' sequence: %s → %s", seq_text, replacement)
                                # Remove the sequence elements (in reverse to maintain indices)
                                for j in range(seq_length - 1, -1, -1):
                                    parent.remove(children[i + j])
                                # Insert new <mi>min</mi> at position i
                                new_mi = ET.Element(f"{ns}mi" if parent.tag.startswith(ns) else "mi")
                                new_mi.text = replacement
                                parent.insert(i, new_mi)
                                fixed_any = True
                                # Update children list and continue from next position
                                children = list(parent)
                                break
                i += 1
            return fixed_any
        
        # Try to fix corrupted min sequences (recursively on all elements)
        def fix_recursive(el):
            """Recursively fix corrupted min in all elements."""
            fixed = False
            if fix_corrupted_min_in_sequence(el):
                fixed = True
            for child in el:
                if fix_recursive(child):
                    fixed = True
            return fixed
        
        if fix_recursive(root):
            changed = True
        
        if not changed:
            return mathml
        
        try:
            ET.indent(root, space="  ")
        except AttributeError:
            pass
        
        return ET.tostring(root, encoding="unicode", method="xml")
    
    def _clean_invalid_mathml_regex(self, mathml: str) -> str:
        """Regex-based cleaning for when XML parsing fails."""
        fixed = mathml
        
        # Remove literal LaTeX commands in <mi> tags
        fixed = re.sub(r'<mi[^>]*>\\?stackrel</mi>', '<mi></mi>', fixed)
        fixed = re.sub(r'<mi[^>]*>\\?dag</mi>', '<mi></mi>', fixed)
        
        # Fix corrupted "min" patterns
        fixed = re.sub(r'<mi[^>]*>I</mi><mi[^>]*>n</mi><mi[^>]*>i</mi><mi[^>]*>l</mi><mi[^>]*>n</mi>', 
                      '<mi>min</mi>', fixed, flags=re.IGNORECASE)
        fixed = re.sub(r'<mi[^>]*>m</mi><mi[^>]*>l</mi><mi[^>]*>n</mi>', 
                      '<mi>min</mi>', fixed, flags=re.IGNORECASE)
        
        return fixed

    def _normalize_operator_tags(self, mathml: str) -> str:
        """Ensure operator characters use <mo> instead of <mi>."""
        try:
            root = ET.fromstring(mathml)
        except Exception:
            return mathml

        ns = "{http://www.w3.org/1998/Math/MathML}"
        operator_tokens = {
            "=", "+", "-", "*", "/", "<", ">", "|", "‖", ":", ";",  # Added semicolon
            "≤", "≥", "≠", "≈", "≡", "∝",
            "∈", "∉", "∪", "∩", "⊂", "⊆", "⊃", "⊇", "∅",
            "→", "⇒", "↔", "⇔", "±", "∓", "×", "÷",
            ",",  # Comma can be an operator in some contexts
        }

        changed = False
        stack = [root]
        while stack:
            el = stack.pop()
            stack.extend(list(el))

            if el.tag == f"{ns}mi" or el.tag == "mi":
                text = (el.text or "").strip()
                if text in operator_tokens:
                    el.tag = f"{ns}mo" if el.tag.startswith(ns) else "mo"
                    changed = True

        if not changed:
            return mathml

        try:
            ET.indent(root, space="  ")
        except AttributeError:
            pass

        return ET.tostring(root, encoding="unicode", method="xml")

    def _fix_unbalanced_cases(self, mathml: str) -> str:
        """
        Fix unbalanced fences specifically for cases blocks generated by latex2mathml.
        latex2mathml often outputs <mrow><mo>{...</mo><mtable>...</mtable></mrow> without a closing fence.
        This triggers strict validation errors.
        """
        if not mathml or ('<mtable' not in mathml):
            return mathml
        
        try:
            # Register namespace to avoid "ns0" prefixes in output
            ET.register_namespace("", "http://www.w3.org/1998/Math/MathML")
            
            # Simple check before parsing
            # Check for left brace characters (text or entity)
            if "{" not in mathml and "&#x0007B;" not in mathml and "&#123;" not in mathml and "&#x7B;" not in mathml:
                return mathml
                
            try:
                root = ET.fromstring(mathml)
            except ET.ParseError:
                return mathml

            changed = False
            
            # Determine namespace from root tag
            uri = ""
            if '}' in root.tag:
                uri = root.tag.split('}')[0] + "}"
            
            # Helper to check if node is { fence
            def is_left_brace(node):
                tag = node.tag
                # Strip namespace if present for tag check
                local_tag = tag.split('}')[-1] if '}' in tag else tag
                if local_tag != 'mo': return False
                
                text = (node.text or "").strip()
                return text in ["{", "&#x0007B;", "&#123;", "\\{", "&#x7B;"]
            
            # Iterate over all mrows (using detected namespace)
            for mrow in root.iter(f"{uri}mrow"):
                # We expect structure: <mo>{...</mo> <mtable>...
                # Check children
                children = list(mrow)
                if len(children) >= 2:
                    first = children[0]
                    first_text = (first.text or "").strip()
                    
                    second = children[1]
                    
                    # Check first element is left brace
                    if is_left_brace(first):
                        # Get local tag for second element check
                        second_tag = second.tag.split('}')[-1] if '}' in second.tag else second.tag
                                                
                        # Check second element is mtable (or mstyle wrapping mtable)
                        is_table_structure = second_tag == 'mtable'
                        
                        # Sometimes latex2mathml puts mstyle around mtable
                        if not is_table_structure and second_tag == 'mstyle' and len(second) > 0:
                             child_tag = second[0].tag.split('}')[-1] if '}' in second[0].tag else second[0].tag
                             if child_tag == 'mtable':
                                 is_table_structure = True

                        if is_table_structure:
                            # Check if last element is a closing fence
                            last = children[-1]
                            is_closed = False
                            
                            last_tag = last.tag.split('}')[-1] if '}' in last.tag else last.tag
                            
                            # Check if the last element is an operator that looks like a fence
                            if last_tag == 'mo':
                                # It's an operator, assume it's a fence if it explicitly says so
                                # OR if it is empty (invisible fence) 
                                if last.get('fence') == 'true' or not (last.text or "").strip() or last.text == ".":
                                    is_closed = True
                            
                            if not is_closed:
                                # Add closing invisible fence
                                close_fence = ET.Element(f"{uri}mo")
                                close_fence.set("stretchy", "true")
                                close_fence.set("fence", "true")
                                close_fence.set("form", "postfix")
                                # Empty text for invisible fence
                                close_fence.text = "" 
                                mrow.append(close_fence)
                                changed = True
            
            if changed:
                 return ET.tostring(root, encoding="unicode", method="xml")
                 
            return mathml
            
        except Exception as e:
            logger.warning(f"Error fixing cases fences: {e}")
            return mathml

    def _unwrap_simple_array(self, latex: str) -> str | None:
        """
        Detect a simple \\begin{array}{c} ... \\end{array} wrapper (single column)
        and return a multiline string of its rows. Returns None if not matched.
        """
        match = re.match(r'^\\begin\{array\}\{c+\}(.*)\\end\{array\}\s*$', latex, re.DOTALL)
        if not match:
            return None

        body = match.group(1)
        if not body:
            return None

        # CRITICAL: Check for truncated LaTeX in array body
        # If body ends with unmatched braces (e.g., {{), it's truncated
        if re.search(r'\{+\s*$', body):
            logger.warning("Truncated LaTeX in array body detected - rejecting unwrap")
            raise ValueError(f"Truncated LaTeX in array body: ends with unmatched opening braces")

        # Split rows on \\ while keeping content
        rows = re.split(r'\\\\', body)
        cleaned_rows = []
        for idx, row in enumerate(rows):
            # Strip outer braces that often wrap pix2tex rows: {{ ... }}
            r = row.strip()
            
            # CRITICAL: Check if row is truncated (ends with unmatched braces)
            if re.search(r'\{+\s*$', r):
                logger.warning("Truncated row %d in array detected - rejecting unwrap", idx + 1)
                raise ValueError(f"Truncated row {idx + 1} in array: ends with unmatched opening braces")
            
            if r.startswith("{{") and r.endswith("}}"):
                r = r[2:-2].strip()
            elif r.startswith("{") and r.endswith("}"):
                r = r[1:-1].strip()
            
            # CRITICAL: Preserve all non-empty rows (don't filter out empty lines that might be placeholders)
            # But skip truly empty rows (whitespace only)
            if r and r.strip():
                cleaned_rows.append(r)
            # Note: We skip empty rows ({{}} becomes empty after stripping) as they're likely OCR artifacts

        if not cleaned_rows:
            return None

        return " \\\\ ".join(cleaned_rows)

    def _split_latex_smart(self, latex: str) -> List[str]:
        """
        Split LaTeX string by '\\\\' or '\\cr' respecting nested environments and braces.
        Does NOT split inside { }, \\begin{...}...\\end{...}, or \\left...\\right.
        
        Enhanced to handle 3+ nested levels properly using environment stack.
        """
        if not latex:
            return []
        
        # Track environment stack (for \begin{...} \end{...})
        env_stack = []
        
        # Track delimiter stack (for \left \right)
        delimiter_depth = 0
        
        # Track brace depth (for { })
        brace_depth = 0
        
        # Result parts
        parts = []
        current_part = []
        
        i = 0
        while i < len(latex):
            # Check for \begin{...}
            if latex[i:i+7] == r'\begin{':
                # Extract environment name
                j = i + 7
                while j < len(latex) and latex[j] != '}':
                    j += 1
                if j < len(latex):
                    env_name = latex[i+7:j]
                    env_stack.append(env_name)
                    current_part.append(latex[i:j+1])
                    i = j + 1
                    continue
            
            # Check for \end{...}
            if latex[i:i+5] == r'\end{':
                # Extract environment name
                j = i + 5
                while j < len(latex) and latex[j] != '}':
                    j += 1
                if j < len(latex):
                    env_name = latex[i+5:j]
                    # Pop matching environment
                    if env_stack and env_stack[-1] == env_name:
                        env_stack.pop()
                    current_part.append(latex[i:j+1])
                    i = j + 1
                    continue
            
            # Check for \left
            if latex[i:i+5] == r'\left':
                delimiter_depth += 1
                # Include the delimiter character
                j = i + 5
                while j < len(latex) and latex[j] in ' \t':
                    j += 1
                if j < len(latex):
                    current_part.append(latex[i:j+1])
                    i = j + 1
                    continue
            
            # Check for \right
            if latex[i:i+6] == r'\right':
                delimiter_depth = max(0, delimiter_depth - 1)
                # Include the delimiter character
                j = i + 6
                while j < len(latex) and latex[j] in ' \t':
                    j += 1
                if j < len(latex):
                    current_part.append(latex[i:j+1])
                    i = j + 1
                    continue
            
            # Track braces
            if latex[i] == '{':
                brace_depth += 1
                current_part.append(latex[i])
                i += 1
                continue
            
            if latex[i] == '}':
                brace_depth = max(0, brace_depth - 1)
                current_part.append(latex[i])
                i += 1
                continue
            
            # Check for line break: \\ or \cr
            # Only split if we're at top level (no active environments, delimiters, or braces)
            if (latex[i:i+2] == r'\\' and i+2 < len(latex) and latex[i+2] not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'):
                # This is \\ (line break), not a command like \left
                if env_stack == [] and delimiter_depth == 0 and brace_depth == 0:
                    # Top level - split here
                    parts.append(''.join(current_part))
                    current_part = []
                    i += 2
                    # Skip optional spacing after \\
                    while i < len(latex) and latex[i] in ' \t\r\n':
                        i += 1
                    continue
                else:
                    # Inside environment/braces - don't split
                    current_part.append(latex[i:i+2])
                    i += 2
                    continue
            
            if latex[i:i+3] == r'\cr':
                # \cr line break
                if env_stack == [] and delimiter_depth == 0 and brace_depth == 0:
                    # Top level - split here
                    parts.append(''.join(current_part))
                    current_part = []
                    i += 3
                    # Skip optional spacing
                    while i < len(latex) and latex[i] in ' \t\r\n':
                        i += 1
                    continue
                else:
                    # Inside environment - don't split
                    current_part.append(latex[i:i+3])
                    i += 3
                    continue
            
            # Regular character
            current_part.append(latex[i])
            i += 1
        
        # Add remaining part
        if current_part:
            parts.append(''.join(current_part))
        
        # Return non-empty parts
        return [part.strip() for part in parts if part.strip()]

    def _split_latex_aggressive(self, latex: str) -> list[str]:
        """
        Aggressively split LaTeX by '\\' or '\\cr', ignoring all but environment depth.
        Useful for malformed inputs where braces/delimiters are unbalanced.
        """
        if not latex:
            return []
            
        env_stack = []
        parts = []
        current_part = []
        i = 0
        
        while i < len(latex):
            # Check for \\begin{...}
            if latex[i:i+7] == r'\begin{':
                j = i + 7
                while j < len(latex) and latex[j] != '}':
                    j += 1
                if j < len(latex):
                    env_name = latex[i+7:j]
                    env_stack.append(env_name)
                    current_part.append(latex[i:j+1])
                    i = j + 1
                    continue
            
            # Check for \\end{...}
            if latex[i:i+5] == r'\end{':
                j = i + 5
                while j < len(latex) and latex[j] != '}':
                    j += 1
                if j < len(latex):
                    env_name = latex[i+5:j]
                    if env_stack and env_stack[-1] == env_name:
                        env_stack.pop()
                    current_part.append(latex[i:j+1])
                    i = j + 1
                    continue
            
            # Check for line break: \\ or \\cr
            # Only split if we're at top level (no active environments)
            # IGNORE brace_depth and delimiter_depth
            if (latex[i:i+2] == r'\\' and i+2 < len(latex) and latex[i+2] not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'):
                if env_stack == []:
                    parts.append(''.join(current_part))
                    current_part = []
                    i += 2
                    while i < len(latex) and latex[i] in ' \t\r\n':
                        i += 1
                    continue
                else:
                    current_part.append(latex[i:i+2])
                    i += 2
                    continue
            
            if latex[i:i+3] == r'\cr':
                if env_stack == []:
                    parts.append(''.join(current_part))
                    current_part = []
                    i += 3
                    while i < len(latex) and latex[i] in ' \t\r\n':
                        i += 1
                    continue
                else:
                    current_part.append(latex[i:i+3])
                    i += 3
                    continue
            
            # Regular character
            current_part.append(latex[i])
            i += 1
        
        if current_part:
            parts.append(''.join(current_part))
        
        return [part.strip() for part in parts if part.strip()]


    def detect_multiline_equation(self, latex: str) -> MultilineInfo:
        """
        Detect if LaTeX is multiline and extract structural metadata.
        
        This is the ENHANCED detection that preserves mathematical structure.
        Returns comprehensive metadata to enable proper MathML generation.
        
        Args:
            latex: LaTeX string to analyze
            
        Returns:
            MultilineInfo with full structure analysis
        """
        info = MultilineInfo()
        
        # Tier 1: EXPLICIT ENVIRONMENT DETECTION (99% confidence)
        env_pattern = r'\\begin\{(' + '|'.join(MULTILINE_ENVIRONMENTS) + r')\}'
        env_match = re.search(env_pattern, latex)
        
        if env_match:
            env_name = env_match.group(1)
            info.is_multiline = True
            info.environment = env_name
            info.alignment_spec = ALIGNMENT_SPECS.get(env_name, 'left')
            
            logger.info(f"[Multiline] Detected environment: {env_name}")
            
            # Count lines within environment (count \\ or \cr)
            env_content = self._extract_environment_content(latex, env_name)
            if env_content:
                info.line_count = env_content.count(r'\\') + env_content.count(r'\cr') + 1
                
                # Count columns (based on & markers)
                lines = env_content.split(r'\\')
                if lines:
                    # Count & in first line to determine columns
                    first_line = lines[0]
                    ampersand_count = first_line.count('&')
                    info.column_count = ampersand_count + 1 if ampersand_count > 0 else 1
                    info.has_alignment_markers = ampersand_count > 0
            
            logger.info(f"[Multiline] Structure: {info}")
            return info
        
        # Tier 2: LINE BREAK DETECTION (95% confidence)
        # Check for \\ line breaks (not part of command like \\left)
        if re.search(r'\\\\(?![a-zA-Z])', latex):
            info.is_multiline = True
            info.environment = 'manual'
            info.line_break_char = r'\\'
            
            # Use smart splitting to count actual top-level lines
            parts = self._split_latex_smart(latex)
            
            # Fallback: If minimal split detected but LaTeX contains line breaks, try aggressive split
            # This handles cases where braces/delimiters are unbalanced or wrapping lines (common in truncated/OCR LaTeX)
            if len(parts) <= 1:
                aggressive_parts = self._split_latex_aggressive(latex)
                if len(aggressive_parts) > 1:
                    logger.info("[Multiline] detection: Smart split failed (likely unbalanced), used aggressive split")
                    parts = aggressive_parts

            non_empty_parts = [p for p in parts if p.strip()]
            info.line_count = len(non_empty_parts)
            
            # Check for alignment markers in first line
            if non_empty_parts:
                first_line = non_empty_parts[0]
                ampersand_count = first_line.count('&')
                if ampersand_count > 0:
                    info.has_alignment_markers = True
                    info.column_count = ampersand_count + 1
                    # Guess alignment based on column count
                    if ampersand_count == 1:
                        info.alignment_spec = 'right left'  # Probably x &= expr
                    elif ampersand_count == 2:
                        info.alignment_spec = 'right center left'  # Probably x &=& y
                    else:
                        info.alignment_spec = 'left'
                else:
                    # No alignment markers, left-align by default
                    info.alignment_spec = 'left'
                    info.column_count = 1
            
            logger.info(f"[Multiline] Manual line breaks detected: {info}")
            return info
        
        # Also check for \cr
        if r'\cr' in latex:
            info.is_multiline = True
            info.environment = 'manual'
            info.line_break_char = r'\cr'
            info.line_count = latex.count(r'\cr') + 1
            info.alignment_spec = 'left'
            logger.info(f"[Multiline] \\cr line breaks detected: {info}")
            return info
        
        # Tier 3: VISUAL/HEURISTIC DETECTION (70% confidence)
        # Check for literal newlines with math content
        lines = latex.split('\n')
        math_lines = [line for line in lines if line.strip() and any(c in line for c in ['=', '+', '-', '\\', '{', '}'])]
        
        if len(math_lines) >= 2:
            logger.info(f"[Multiline] Detected {len(math_lines)} lines with math content (literal newlines)")
            info.is_multiline = True
            info.environment = 'visual'
            info.line_break_char = '\n'
            info.line_count = len(math_lines)
            info.alignment_spec = 'left'
            return info
        
        # Not multiline
        logger.debug("[Multiline] Single-line equation")
        return info
    
    def _extract_environment_content(self, latex: str, env_name: str) -> Optional[str]:
        """Extract content between \\begin{env} and \\end{env}."""
        pattern = rf'\\begin\{{{env_name}\}}(.*?)\\end\{{{env_name}\}}'
        match = re.search(pattern, latex, re.DOTALL)
        return match.group(1).strip() if match else None
    
    def _is_multiline_equation(self, latex: str) -> bool:
        """
        DEPRECATED: Use detect_multiline_equation() instead.
        Kept for backward compatibility.
        """
        info = self.detect_multiline_equation(latex)
        return info.is_multiline

    
    # ==========================================================================
    # ALIGNMENT-AWARE LINE PARSING (Phase 2)
    # ==========================================================================
    
    def _parse_aligned_line(self, line: str, environment: str) -> List[str]:
        """
        Split a single line of aligned equation into column cells.
        
        This preserves mathematical structure by respecting & alignment markers.
        
        Args:
            line: Single line of LaTeX (e.g., "x &= a + b")
            environment: Environment type ('align', 'eqnarray', 'cases', etc.)
        
        Returns:
            List of cell contents for each <mtd>
            
        Examples:
            _parse_aligned_line("x &= a", "align") → ["x", "= a"]
            _parse_aligned_line("a &=& b", "eqnarray") → ["a", "=", "b"]
            _parse_aligned_line("x^2 & \\text{if } x > 0", "cases") → ["x^2", "\\text{if } x > 0"]
        """
        if environment in ['align', 'aligned', 'split']:
            # Split at &, create 2 columns (left & right)
            parts = line.split('&', maxsplit=1)
            if len(parts) == 1:
                # No & found, put everything in right column (left-aligned)
                return ['', parts[0].strip()]
            return [parts[0].strip(), parts[1].strip()]
        
        elif environment == 'eqnarray':
            # Split at &, create 3 columns (LHS & operator & RHS)
            parts = line.split('&')
            if len(parts) >= 3:
                return [parts[0].strip(), parts[1].strip(), parts[2].strip()]
            elif len(parts) == 2:
                # Only one &, treat as align-style
                return [parts[0].strip(), parts[1].strip(), '']
            else:
                # No &, center in middle column
                return ['', parts[0].strip(), '']
        
        elif environment in ['cases', 'matrix', 'pmatrix', 'bmatrix', 'vmatrix']:
            # cases: expression & condition
            # matrices: elements separated by &
            parts = line.split('&')
            return [part.strip() for part in parts]
        
        elif environment == 'array':
            # Custom alignment from preamble, split at all &
            parts = line.split('&')
            return [part.strip() for part in parts]
        
        else:
            # Unknown environment or 'manual', single column
            return [line.strip()]
    
    def _get_column_alignment(self, info: MultilineInfo) -> str:
        """
        Get the MathML columnalign attribute for an equation.
        
        Args:
            info: MultilineInfo from detection
            
        Returns:
            Column alignment string (e.g., "right left", "center")
        """
        if info.alignment_spec:
            return info.alignment_spec
        
        # Fallback based on environment
        if info.environment:
            return ALIGNMENT_SPECS.get(info.environment, 'left')
        
        # Default: left alignment
        return 'left'
    
    def _create_mtable_row(self, cells: List[str], row_idx: int) -> str:
        """
        Create a single <mtr> (table row) from cell contents.
        
        Args:
            cells: List of LaTeX strings for each cell
            row_idx: Row index (for debugging)
            
        Returns:
            MathML <mtr> element with <mtd> children
        """
        mtr_parts = ['  <mtr>']
        
        for cell_idx, cell_latex in enumerate(cells):
            if not cell_latex.strip():
                # Empty cell
                mtr_parts.append('    <mtd></mtd>')
            else:
                try:
                    # Convert cell LaTeX to MathML
                    cell_mathml = latex2mathml_convert(cell_latex)
                    
                    # Extract content (remove outer <math> tags)
                    cell_mathml = self._ensure_namespace(cell_mathml)
                    cell_mathml = self._normalize_operator_tags(cell_mathml)
                    
                    # Remove <math>...</math> wrapper to get just the content
                    content = re.sub(r'<math[^>]*>(.*?)</math>', r'\1', cell_mathml, flags=re.DOTALL)
                    
                    mtr_parts.append(f'    <mtd>{content.strip()}</mtd>')
                    
                except Exception as e:
                    logger.warning(f"Failed to convert cell [{row_idx},{cell_idx}]: {e} | LaTeX: {cell_latex[:50]}")
                    # Fallback: wrap in mtext
                    mtr_parts.append(f'    <mtd><mtext>{cell_latex}</mtext></mtd>')
        
        mtr_parts.append('  </mtr>')
        return '\n'.join(mtr_parts)
    
    def _convert_multiline_aligned(self, latex: str, info: MultilineInfo) -> str:
        """
        Convert multiline LaTeX to MathML using alignment information (ENHANCED).
        
        This uses the comprehensive MultilineInfo to preserve mathematical structure
        with proper <mtable columnalign="..."> attributes.
        
        Args:
            latex: LaTeX string  
            info: MultilineInfo from detect_multiline_equation()
            
        Returns:
            MathML with proper table structure
        """
        try:
            logger.info(f"[Multiline] Converting with alignment: {info}")
            
            # Get column alignment
            columnalign = self._get_column_alignment(info)
            
            # Repair LaTeX first
            latex = self._repair_latex_line(latex)
            
            # CRITICAL: If the entire input is wrapped in a multiline environment, unwrap it first
            # to allow _split_latex_smart to see the internal line breaks.
            env_was_unwrapped = False
            if info.environment and info.environment not in ['manual', 'visual']:
                # Use raw string concatenation to avoid f-string brace hell
                env_name_esc = re.escape(info.environment)
                prefix = r'^\s*(?:\\\[|\$\$)?\s*\\begin\{'
                suffix = r'\s*(?:\\\]|\$\$)?\s*$'
                pattern = prefix + env_name_esc + r'\*?\}(.*?)\\end\{' + env_name_esc + r'\*?\}' + suffix
                env_match = re.search(pattern, latex, re.DOTALL | re.IGNORECASE)
                if env_match:
                    logger.info(f"[Multiline] Unwrapping dominant {info.environment} environment")
                    latex = env_match.group(1).strip()
                    env_was_unwrapped = True
            
            # Split into lines using smart splitting
            if info.environment == 'visual' and '\n' in latex and '\\\\' not in latex:
                logger.info("[Multiline] Splitting visual multiline by newline")
                lines = [l.strip() for l in latex.split('\n') if l.strip()]
            else:
                lines = self._split_latex_smart(latex)
                
                # Fallback check
                if len(lines) <= 1 and ("\\\\" in latex or "\\cr" in latex) and not env_was_unwrapped:
                     aggressive_parts = self._split_latex_aggressive(latex)
                     if len(aggressive_parts) > 1:
                         logger.info("[Multiline] aligned conversion: Smart split failed (likely unbalanced), used aggressive split")
                         lines = aggressive_parts
            
            if not lines:
                logger.warning("[Multiline] No lines after splitting, falling back to single-line")
                return self._convert_single_line(latex)
            
            # Remove empty lines
            lines = [line.strip() for line in lines if line.strip()]
            
            if len(lines) <= 1 and not env_was_unwrapped:
                # If only one line, and no environment was unwrapped, it's not truly a multiline 
                # equation that needs our manual table structure (e.g., just f(x) = \begin{cases}...\end{cases})
                logger.info("[Multiline] Only one line detected and no environment was unwrapped, falling back to single-line")
                # But wait, if it's 'manual' but only one line? Fallback is still good.
                return self._convert_single_line(latex)
            
            logger.info(f"[Multiline] Processing {len(lines)} lines with columnalign='{columnalign}'")
            
            # Build <mtable> structure
            mtable_parts = [
                '<math xmlns="http://www.w3.org/1998/Math/MathML" display="block">',
                f'<mtable columnalign="{columnalign}" displaystyle="true">'
            ]
            
            # Process each line
            for row_idx, line_latex in enumerate(lines):
                # Clean up line
                line_latex = self._normalize_pix2tex_noise(line_latex)
                line_latex = self._strip_outer_braces(line_latex)
                
                logger.debug(f"[Multiline] Line {row_idx+1}/{len(lines)}: {line_latex[:80]}")
                
                # Parse line into cells based on & markers
                cells = self._parse_aligned_line(line_latex, info.environment or 'manual')
                
                logger.debug(f"[Multiline] Parsed into {len(cells)} cells: {cells}")
                
                # Create table row
                try:
                    row_mathml = self._create_mtable_row(cells, row_idx)
                    mtable_parts.append(row_mathml)
                except Exception as row_error:
                    logger.error(f"[Multiline] Failed to create row {row_idx}: {row_error}")
                    # Add error row
                    mtable_parts.append(f'  <mtr><mtd><mtext>Error in row {row_idx+1}</mtext></mtd></mtr>')
            
            mtable_parts.append('</mtable>')
            mtable_parts.append('</math>')
            
            mathml = '\n'.join(mtable_parts)
            
            # Post-process: Clean and normalize
            mathml = self._clean_invalid_mathml(mathml)
            mathml = self._normalize_operator_tags(mathml)
            
            logger.info(f"[Multiline] Generated MathML with {len(lines)} lines, alignment={columnalign}")
            
            return mathml
            
        except Exception as e:
            logger.error(f"[Multiline] Alignment-aware conversion failed: {e}", exc_info=True)
            # Fallback to old multiline method
            logger.warning("[Multiline] Falling back to legacy multiline conversion")
            return self._convert_multiline(latex)

    def _convert_multiline(self, latex: str) -> str:
        """Convert multi-line LaTeX equation to structured MathML with mtable (LEGACY)."""
        try:
            # CRITICAL: Repair the entire LaTeX first before splitting into lines
            # This ensures \left/\right pairs that span multiple lines are fixed
            latex = self._repair_latex_line(latex)
            
            # Parse lines from LaTeX first (this may extract labels from individual lines)
            lines = self._parse_multiline_latex(latex)
            
            if not lines:
                # Fallback to single-line conversion
                return self._convert_single_line(latex)
            
            # Normalize pix2tex noise and outer braces per line
            for line in lines:
                ln = line.get("latex", "")
                ln = self._normalize_pix2tex_noise(ln)
                ln = self._strip_outer_braces(ln)
                # Also repair each line individually (in case of line-specific issues)
                ln = self._repair_latex_line(ln)
                line["latex"] = ln

            # Extract equation label from first line if not already extracted
            equation_label = None
            if lines and lines[0].get("label"):
                equation_label = lines[0].get("label")
            else:
                # Try extracting from entire latex string
                equation_label = self._extract_equation_label(latex)
                # If found, remove from first line
                if equation_label and lines:
                    first_line = lines[0].get("latex", "")
                    # Remove label pattern from start
                    first_line = re.sub(r'^\([^)]+\)\s*', '', first_line).strip()
                    lines[0]["latex"] = first_line
            
            # Create mtable structure
            math_elem = ET.Element("math", xmlns="http://www.w3.org/1998/Math/MathML", display="block")
            mtable = ET.SubElement(math_elem, "mtable", align="left")
            
            # Process each line (support up to 5 lines as requested)
            logger.info("Multiline conversion: processing %d lines (max 5 supported)", len(lines))
            if len(lines) > 5:
                logger.warning("Equation has %d lines, but only processing first 5", len(lines))
                lines = lines[:5]  # Limit to 5 lines
            
            for idx, line_data in enumerate(lines):
                line_latex = line_data.get("latex", "").strip()
                line_label = line_data.get("label", None)
                
                logger.debug("Processing line %d/%d: %s", idx + 1, len(lines), line_latex[:80] if line_latex else "(empty)")
                
                if not line_latex:
                    logger.debug("Skipping empty line %d", idx + 1)
                    continue
                
                # CRITICAL: Check for truncated LaTeX BEFORE attempting conversion
                # Detect incomplete commands, unmatched braces, etc.
                is_line_truncated = False
                truncated_patterns = [
                    r'\\[a-z]{1,3}$',  # Incomplete commands (1-3 letters)
                    r'\\lef$', r'\\rig$', r'\\fra$',  # Common truncated commands
                    r'\{+\s*$',  # Ends with unmatched opening braces
                ]
                for pattern in truncated_patterns:
                    if re.search(pattern, line_latex):
                        is_line_truncated = True
                        logger.warning("Line %d/%d is truncated (pattern: %s): %s", 
                                     idx+1, len(lines), pattern, line_latex[:100])
                        break
                
                # Check for unbalanced braces/delimiters
                if not is_line_truncated:
                    open_braces = line_latex.count('{')
                    close_braces = line_latex.count('}')
                    if open_braces > close_braces and re.search(r'\{+\s*$', line_latex):
                        is_line_truncated = True
                        logger.warning("Line %d/%d is truncated (unmatched braces): %s", 
                                     idx+1, len(lines), line_latex[:100])
                
                # If line is truncated, try to repair it first before skipping
                # CRITICAL: Follow Mathpix process - attempt repair before giving up
                if is_line_truncated:
                    logger.warning("Line %d/%d appears truncated - attempting repair before conversion. LaTeX: %s", 
                               idx+1, len(lines), line_latex[:200])
                    # Try to repair the truncated line
                    repaired_latex = self._repair_latex_line(line_latex)
                    if repaired_latex != line_latex:
                        logger.info("Repaired truncated line %d/%d, will attempt conversion", idx+1, len(lines))
                        line_latex = repaired_latex
                        # Reset truncation flag after repair
                        is_line_truncated = False
                    else:
                        # Repair didn't help, but we'll still try conversion below
                        # Don't skip immediately - let the conversion attempt handle it
                        logger.warning("Could not repair truncated line %d/%d, will still attempt conversion", idx+1, len(lines))
                
                # Convert line to MathML
                line_root = None
                conversion_success = False
                original_line_latex = line_latex
                
                try:
                    line_mathml = latex2mathml_convert(line_latex)
                    # CRITICAL: Normalize operators BEFORE parsing (ensures ; and other operators are <mo>)
                    line_mathml = self._normalize_operator_tags(line_mathml)
                    # CRITICAL: Clean invalid MathML (literal LaTeX commands, corrupted text)
                    line_mathml = self._clean_invalid_mathml(line_mathml)
                    # Parse the MathML to extract content
                    line_root = ET.fromstring(line_mathml)
                    conversion_success = True
                    logger.debug("Successfully converted line %d/%d (length: %d chars)", idx+1, len(lines), len(line_latex))
                except Exception as exc:
                    logger.warning("Failed to convert line %d/%d: %s | Error: %s | LaTeX: %s", 
                               idx+1, len(lines), line_latex[:100], str(exc)[:100], line_latex[:200])
                    
                    # CRITICAL: Try to repair the LaTeX before giving up
                    # This follows Mathpix process - we should attempt repair, not skip
                    repaired_latex = self._repair_latex_line(line_latex)
                    
                    if repaired_latex != line_latex:
                        logger.info("Attempting to repair line %d/%d LaTeX and retry conversion", idx+1, len(lines))
                        try:
                            line_mathml = latex2mathml_convert(repaired_latex)
                            line_mathml = self._normalize_operator_tags(line_mathml)
                            line_mathml = self._clean_invalid_mathml(line_mathml)
                            line_root = ET.fromstring(line_mathml)
                            conversion_success = True
                            logger.info("Successfully converted line %d/%d after repair", idx+1, len(lines))
                        except Exception as repair_exc:
                            logger.warning("Repair attempt failed for line %d/%d: %s", idx+1, len(lines), str(repair_exc)[:100])
                    
                    # If repair didn't work, try one more time with simplified LaTeX
                    if not conversion_success:
                        # Try removing problematic commands that might cause issues
                        simplified_latex = line_latex
                        # Remove extra \displaystyle that might cause issues
                        # Use lambda to avoid escape sequence issues in Python 3.13
                        simplified_latex = re.sub(r'\\displaystyle\s*\\displaystyle+', lambda m: r'\displaystyle', simplified_latex)
                        # Try to balance any remaining unmatched delimiters
                        if simplified_latex != line_latex:
                            try:
                                line_mathml = latex2mathml_convert(simplified_latex)
                                line_mathml = self._normalize_operator_tags(line_mathml)
                                line_mathml = self._clean_invalid_mathml(line_mathml)
                                line_root = ET.fromstring(line_mathml)
                                conversion_success = True
                                logger.info("Successfully converted line %d/%d with simplified LaTeX", idx+1, len(lines))
                            except Exception:
                                pass
                    
                    # If all attempts failed, create a minimal placeholder MathML
                    # This ensures the line is still included in the output (following Mathpix process)
                    if not conversion_success:
                        logger.error("All conversion attempts failed for line %d/%d. Creating placeholder MathML to preserve line structure.", 
                                   idx+1, len(lines))
                        # Create a minimal valid MathML structure for this line
                        # Use an empty mrow as placeholder - better than skipping entirely
                        # This should never fail, but wrap in try-except for safety
                        try:
                            # Create a minimal mrow with error indicator
                            placeholder_root = ET.Element("mrow")
                            error_mi = ET.SubElement(placeholder_root, "mi")
                            error_mi.text = "⋯"  # Ellipsis to indicate incomplete conversion
                            line_root = placeholder_root
                            conversion_success = True
                            logger.warning("Created placeholder MathML for line %d/%d to preserve structure", idx+1, len(lines))
                        except Exception as placeholder_exc:
                            # Even if placeholder creation fails (shouldn't happen), create a basic one
                            logger.error("Unexpected failure creating placeholder for line %d/%d: %s. Creating basic fallback.", 
                                       idx+1, len(lines), placeholder_exc)
                            # Create the most basic possible MathML - this should never fail
                            placeholder_root = ET.Element("mrow")
                            line_root = placeholder_root
                            conversion_success = True
                            logger.warning("Created basic fallback MathML for line %d/%d", idx+1, len(lines))
                
                # Ensure we have a valid line_root before proceeding
                # With our repair logic, this should rarely happen, but create a final fallback if needed
                if not conversion_success or line_root is None:
                    logger.error("CRITICAL: No valid MathML for line %d/%d after all attempts. Creating final fallback.", idx+1, len(lines))
                    # Create a basic mrow as absolute last resort - this ensures the line is never skipped
                    line_root = ET.Element("mrow")
                    conversion_success = True
                    logger.warning("Created final fallback MathML for line %d/%d", idx+1, len(lines))
                
                # Create table row
                mtr = ET.SubElement(mtable, "mtr")
                
                # First cell: label or empty
                mtd_label = ET.SubElement(mtr, "mtd")
                if idx == 0 and equation_label:
                    # First line with equation label
                    label_open = ET.SubElement(mtd_label, "mo")
                    label_open.text = "("
                    label_mi = ET.SubElement(mtd_label, "mi")
                    label_mi.text = equation_label
                    label_close = ET.SubElement(mtd_label, "mo")
                    label_close.text = ")"
                elif line_label:
                    # Line has its own label
                    label_open = ET.SubElement(mtd_label, "mo")
                    label_open.text = "("
                    label_mi = ET.SubElement(mtd_label, "mi")
                    label_mi.text = line_label
                    label_close = ET.SubElement(mtd_label, "mo")
                    label_close.text = ")"
                # Otherwise, empty cell for alignment
                
                # Second cell: equation content
                mtd_content = ET.SubElement(mtr, "mtd")
                
                # Move all children from line_root to mtd_content
                for child in list(line_root):
                    mtd_content.append(child)
            
            # CRITICAL: Check if mtable is empty (all lines failed conversion)
            # Count actual rows (mtr elements with content)
            rows_with_content = 0
            for mtr in mtable:
                # Check if row has any content (not just empty cells)
                for mtd in mtr:
                    if len(mtd) > 0 or (mtd.text and mtd.text.strip()):
                        rows_with_content += 1
                        break
            
            # If no rows have content, return empty MathML (fail safely)
            if rows_with_content == 0:
                logger.warning("All lines failed conversion - returning empty MathML")
                return '<math xmlns="http://www.w3.org/1998/Math/MathML" display="block"></math>'
            
            # Convert to string
            try:
                ET.indent(math_elem, space="  ")
            except AttributeError:
                pass  # Python < 3.9
            
            mathml_str = ET.tostring(math_elem, encoding="unicode", method="xml")
            mathml_str = self._normalize_operator_tags(mathml_str)
            return mathml_str
            
        except Exception as exc:
            logger.exception("Failed to convert multi-line equation: %s", exc)
            return self._convert_single_line(latex)

    def _extract_equation_label(self, latex: str) -> str | None:
        """Extract equation label like (ii), (2.1), etc. from LaTeX."""
        # Pattern: (ii), (2.1), (a), etc. at the beginning
        patterns = [
            r'^\(([a-z]+)\)',  # (ii), (a), etc.
            r'^\((\d+\.\d+)\)',  # (2.1), (3.4), etc.
            r'^\((\d+)\)',  # (1), (2), etc.
            r'\(([a-z]+)\)',  # (ii) anywhere
            r'\((\d+\.\d+)\)',  # (2.1) anywhere
        ]
        
        for pattern in patterns:
            match = re.search(pattern, latex)
            if match:
                return match.group(1)
        
        return None

    def _parse_multiline_latex(self, latex: str) -> list[dict]:
        """Parse multi-line LaTeX into individual lines with labels."""
        lines = []
        
        # Remove environment wrappers if present
        latex_clean = latex
        
        # Extract from align/aligned environments
        align_match = re.search(r'\\begin\{(align|aligned|eqnarray|split|multline|gather)\*?\}(.*?)\\end\{(align|aligned|eqnarray|split|multline|gather)\*?\}', 
                               latex, re.DOTALL | re.IGNORECASE)
        if align_match:
            latex_clean = align_match.group(2)
        
        # CRITICAL: Also extract from array environments
        # Array format: \begin{array}{c} line1 \\ line2 \\ ... \end{array}
        array_match = re.search(r'\\begin\{array\}\{[^}]*\}(.*?)\\end\{array\}', 
                               latex, re.DOTALL | re.IGNORECASE)
        if array_match:
            latex_clean = array_match.group(1)
        
        # First, try splitting using smart logic that respects environments
        # This handles \\ and \cr but avoids breaking inside cases/matrices
        line_breaks = self._split_latex_smart(latex_clean)
        
        # Fallback: If minimal split detected but LaTeX contains line breaks, try aggressive split
        # This handles cases where braces/delimiters are unbalanced or wrapping lines
        if len(line_breaks) <= 1 and ("\\\\" in latex_clean or "\\cr" in latex_clean):
             aggressive_parts = self._split_latex_aggressive(latex_clean)
             if len(aggressive_parts) > 1:
                 logger.warning("[Multiline] Smart split failed (likely unbalanced braces). Using aggressive split.")
                 line_breaks = aggressive_parts

        
        # If we have multiple parts, process them
        if len(line_breaks) > 1 or (len(line_breaks) == 1 and ("\\\\" in latex_clean or "\\cr" in latex_clean)):
            # Process all lines (support up to 5 lines as requested)
            max_lines = 5  # Support up to 5 lines as requested
            
            for idx, line in enumerate(line_breaks):
                # Warn if exceeding 5 lines but still process first 5
                if idx >= max_lines:
                    remaining = len(line_breaks) - max_lines
                    if remaining > 0:
                        logger.warning("Equation has more than %d lines (%d total). Processing first %d lines only.", 
                                     max_lines, len(line_breaks), max_lines)
                    break
                
                line = line.strip()
                
                # CRITICAL: Handle empty lines in arrays (e.g., {{}})
                # These are valid placeholders and should be preserved as empty lines
                if not line or line == "{{}}" or line == "{}":
                    # Empty line - add it but mark as empty
                    lines.append({
                        "latex": "",
                        "label": None
                    })
                    continue
                
                # Strip outer braces that often wrap pix2tex rows: {{ ... }}
                if line.startswith("{{") and line.endswith("}}"):
                    line = line[2:-2].strip()
                elif line.startswith("{") and line.endswith("}"):
                    line = line[1:-1].strip()
                
                # Skip if still empty after stripping braces
                if not line:
                    lines.append({
                        "latex": "",
                        "label": None
                    })
                    continue
                
                # Remove alignment markers (&)
                line = re.sub(r'&', '', line).strip()
                
                # Extract label if present in this line
                label = self._extract_equation_label(line)
                if label:
                    # Remove label from line (handle both at start and embedded)
                    line = re.sub(r'^\([^)]+\)\s*', '', line).strip()
                    line = re.sub(r'\s*\([^)]+\)\s*$', '', line).strip()
                
                # Clean up trailing commas, semicolons (but preserve them if they're operators in the equation)
                # Only remove trailing punctuation, not operators in the middle
                line = re.sub(r'[,;]\s*$', '', line).strip()
                
                if line:
                    lines.append({
                        "latex": line,
                        "label": label
                    })
        
        # If no lines were found from explicit breaks, try intelligent splitting
        # This handles equations that are naturally multi-line but don't have explicit separators
        if not lines and len(latex_clean.strip()) > 50:  # Only for longer equations
            # Look for patterns that suggest multiple lines:
            # 1. Multiple = signs (could be multiple equations)
            # 2. Multiple \leq, \geq, etc. (could be chained inequalities)
            # 3. Natural breaks at operators like =, \leq, \geq
            equals_count = latex_clean.count('=')
            leq_count = latex_clean.count('\\leq') + latex_clean.count('\\le')
            geq_count = latex_clean.count('\\geq') + latex_clean.count('\\ge')
            
            # If there are multiple equality/inequality operators, try splitting
            if equals_count + leq_count + geq_count >= 2:
                # Try splitting at =, \leq, \geq, \le, \ge
                potential_lines = re.split(r'(?<!\\)(?:=|\\leq|\\geq|\\le|\\ge)', latex_clean)
                if len(potential_lines) >= 2 and len(potential_lines) <= 5:
                    logger.debug("Attempting intelligent splitting into %d lines", len(potential_lines))
                    # Reconstruct lines with operators
                    split_points = list(re.finditer(r'(?<!\\)(?:=|\\leq|\\geq|\\le|\\ge)', latex_clean))
                    if split_points:
                        current_pos = 0
                        for i, match in enumerate(split_points):
                            if i < len(potential_lines) - 1:
                                line_content = latex_clean[current_pos:match.end()].strip()
                                if line_content:
                                    label = self._extract_equation_label(line_content)
                                    if label:
                                        line_content = re.sub(r'^\([^)]+\)\s*', '', line_content).strip()
                                    lines.append({
                                        "latex": line_content,
                                        "label": label
                                    })
                                current_pos = match.end()
                        
                        # Add last line
                        if current_pos < len(latex_clean):
                            line_content = latex_clean[current_pos:].strip()
                            if line_content:
                                label = self._extract_equation_label(line_content)
                                if label:
                                    line_content = re.sub(r'^\([^)]+\)\s*', '', line_content).strip()
                                lines.append({
                                    "latex": line_content,
                                    "label": label
                                })
        
        # Limit to 5 lines maximum as requested
        if len(lines) > 5:
            # Limit to 5 lines maximum as requested
            if len(lines) > 5:
                logger.warning("Equation has %d lines, limiting to first 5 lines", len(lines))
                lines = lines[:5]
            
            return lines

    def _is_multiline_equation(self, latex: str) -> bool:
        """
        Detect if LaTeX is a multiline equation.
        ENHANCED: Now detects ALL types including literal newlines.
        """
        # Standard multiline environments
        multiline_envs = ['align', 'aligned', 'eqnarray', 'gather', 'multline', 'split']
        for env in multiline_envs:
            if f'\\begin{{{env}' in latex:
                return True
        
        # Check for \\ line breaks (but not \\command)
        # Pattern: \\ followed by non-letter or end of string
        if re.search(r'\\\\(?![a-zA-Z])', latex):
            return True
        
        # Check for \cr line breaks
        if r'\cr' in latex:
            return True
        
        # ENHANCED: Check for literal newlines WITHIN the latex (not just wrapping)
        # If there are 2+ lines AND they contain math operators, likely multiline
        lines = latex.split('\n')
        if len(lines) >= 2:
            # Count how many lines have math content (not just whitespace/labels)
            math_lines = [line for line in lines if line.strip() and any(c in line for c in ['=', '+', '-', '\\', '{', '}'])]
            if len(math_lines) >= 2:
                logger.info(f"[Multiline] Detected {len(math_lines)} lines with math content (literal newlines)")
                return True
        
        return False

    def _is_matrix_equation(self, latex: str) -> bool:
        """Detect if LaTeX contains a matrix equation."""
        # Check for matrix environments
        matrix_patterns = [
            r'\\begin\{(bmatrix|pmatrix|vmatrix|Vmatrix|matrix|array)',
            r'\\left\s*\[.*?\\begin\s*\{array\}',
            r'\\left\s*\(.*?\\begin\s*\{array\}',
        ]
        
        for pattern in matrix_patterns:
            if re.search(pattern, latex, re.IGNORECASE):
                return True
        
        # Also check for standalone array environments (even without \left[)
        if re.search(r'\\begin\s*\{array\}', latex, re.IGNORECASE):
            return True
        
        # CRITICAL: Detect bracket-based matrices (e.g., [a b] = [c d])
        # Pattern: something = [content] where content suggests multiple rows/columns
        bracket_matrix_pattern = r'\[([^\]]+)\]\s*=\s*\[([^\]]+)\]'
        bracket_match = re.search(bracket_matrix_pattern, latex)
        if bracket_match:
            left_content = bracket_match.group(1)
            right_content = bracket_match.group(2)
            
            # Check if right side has multiple elements that suggest a matrix
            # Count summation operators, subscripts, or other math elements
            # If there are 4+ elements (suggesting 2x2 matrix), treat as matrix
            right_elements = re.findall(r'\\sum|\\prod|\\int|\w+_\{\w+\}|\w+\^\{\w+\}', right_content)
            if len(right_elements) >= 4:
                logger.debug("Detected bracket-based matrix equation with %d elements", len(right_elements))
                return True
            
            # Also check if content has explicit row separators (\\)
            if "\\\\" in right_content or "\\cr" in right_content:
                return True
        
        # Check for multiple bracket pairs that suggest matrix structure
        # Pattern: [row1] = [row1_content] followed by [row2] = [row2_content]
        multiple_brackets = re.findall(r'\[[^\]]+\]', latex)
        if len(multiple_brackets) >= 2:
            # Check if brackets are on separate lines or have matrix-like structure
            bracket_positions = [m.start() for m in re.finditer(r'\[[^\]]+\]', latex)]
            if len(bracket_positions) >= 2:
                # Check spacing between brackets (if they're close, might be matrix)
                for i in range(len(bracket_positions) - 1):
                    gap = bracket_positions[i+1] - bracket_positions[i]
                    # If brackets are reasonably spaced and content suggests matrix, treat as matrix
                    if 50 < gap < 500:  # Reasonable gap for matrix rows
                        return True
        
        return False

    def _convert_matrix_equation(self, latex: str) -> str:
        """Convert matrix equation to structured MathML with mtable."""
        try:
            # Parse the equation: variable = matrix
            # Pattern: something = \begin{...} ... \end{...}
            matrix_match = re.search(
                r'^(.+?)\s*=\s*(\\begin\{(bmatrix|pmatrix|vmatrix|Vmatrix|matrix|array).*?\\end\{(?:bmatrix|pmatrix|vmatrix|Vmatrix|matrix|array)\})',
                latex,
                re.DOTALL | re.IGNORECASE
            )
            trailing_after_matrix = ""
            matrix_content = None  # Initialize to None
            skip_parsing = False  # Flag to skip re-parsing if we already parsed
            
            if not matrix_match:
                # Try with \left[ \begin{array} ... \end{array} \right]
                matrix_match = re.search(
                    r'^(.+?)\s*=\s*(\\left\s*\[.*?\\begin\s*\{array\}.*?\\end\s*\{array\}.*?\\right\s*\])',
                    latex,
                    re.DOTALL | re.IGNORECASE
                )
            
            if not matrix_match:
                # Fallback: try to find matrix environment anywhere
                matrix_match = re.search(
                    r'(\\begin\{(bmatrix|pmatrix|vmatrix|Vmatrix|matrix|array).*?\\end\{(?:bmatrix|pmatrix|vmatrix|Vmatrix|matrix|array)\})',
                    latex,
                    re.DOTALL | re.IGNORECASE
                )
                if matrix_match:
                    # Extract everything before the matrix as the variable
                    var_part = latex[:matrix_match.start()].strip()
                    # Remove trailing = and whitespace
                    var_part = re.sub(r'\s*=\s*$', '', var_part).strip()
                    matrix_part = matrix_match.group(1)
                    trailing_after_matrix = latex[matrix_match.end():].strip()
                else:
                    # CRITICAL: Try bracket-based matrix detection (e.g., [T_{1,1} T_{1,2}] = [sum ... sum ...])
                    bracket_matrix_match = re.search(
                        r'^(.+?)\s*=\s*\[([^\]]+)\]',
                        latex,
                        re.DOTALL
                    )
                    if bracket_matrix_match:
                        var_part = bracket_matrix_match.group(1).strip()
                        var_part = re.sub(r'\s*=\s*$', '', var_part).strip()
                        right_content = bracket_matrix_match.group(2).strip()
                        
                        # Check if right content has multiple elements suggesting a matrix
                        # Count summation operators or other repeating patterns
                        sum_count = right_content.count('\\sum') + right_content.count('\\prod')
                        if sum_count >= 4:
                            # Likely a 2x2 matrix - split into rows
                            logger.info("Detected bracket-based matrix with %d summation operators, attempting 2x2 structure", sum_count)
                            
                            # Try splitting by counting sums - each sum typically represents a cell
                            sum_positions = []
                            for match in re.finditer(r'\\sum', right_content):
                                sum_positions.append(match.start())
                            
                            if len(sum_positions) == 4:
                                # Split into 4 cells based on sum positions
                                # Find boundaries between sums (look for end of previous sum expression)
                                cells = []
                                
                                # Method: Find where each sum expression ends
                                # A sum expression typically ends before the next sum or at end of string
                                for i in range(len(sum_positions)):
                                    start = sum_positions[i]
                                    if i < len(sum_positions) - 1:
                                        # Find the end of this sum expression (before next sum)
                                        # Look for patterns like: sum ... x_i (end of cell)
                                        end = sum_positions[i+1]
                                        # Try to find a better boundary (e.g., after x_i or similar)
                                        cell_content = right_content[start:end].strip()
                                        cells.append(cell_content)
                                    else:
                                        # Last cell
                                        cell_content = right_content[start:].strip()
                                        cells.append(cell_content)
                                
                                if len(cells) == 4:
                                    # Organize into 2x2 matrix
                                    matrix_content = [
                                        [cells[0], cells[1]],
                                        [cells[2], cells[3]]
                                    ]
                                    
                                    # Also check left side - might have matrix structure too
                                    left_bracket_match = re.search(r'\[([^\]]+)\]', var_part)
                                    if left_bracket_match:
                                        left_content = left_bracket_match.group(1).strip()
                                        var_part = var_part[:left_bracket_match.start()].strip()
                                    
                                    # Convert to proper matrix LaTeX format for processing
                                    matrix_part = "\\begin{array}{cc} " + " & ".join(cells[0:2]) + " \\\\ " + " & ".join(cells[2:4]) + " \\end{array}"
                                    logger.info("Converted bracket matrix to array format with 2x2 structure")
                                    
                                    # Set flag to skip re-parsing since we already have matrix_content
                                    skip_parsing = True
                                    # Continue to process this matrix_content below
                                else:
                                    logger.warning("Failed to split bracket matrix into 4 cells")
                                    return self._convert_single_line(latex)
                            else:
                                # Not exactly 4 sums - try alternative parsing
                                logger.warning("Bracket matrix has %d sums, not 4. Trying alternative parsing.", len(sum_positions))
                                # Fall back to treating as single-line for now
                                return self._convert_single_line(latex)
                        else:
                            # Not enough elements to be a matrix
                            return self._convert_single_line(latex)
                    else:
                        # No matrix found, try direct conversion (might be malformed)
                        logger.warning("Matrix pattern detected but couldn't extract matrix content, trying direct conversion")
                        return self._convert_single_line(latex)
            else:
                var_part = matrix_match.group(1).strip()
                # Remove trailing = if present
                var_part = re.sub(r'\s*=\s*$', '', var_part).strip()
                
                # CRITICAL: If var_part has an unclosed \left\{ or similar, move it to matrix_part
                # Example: \mathbf{D} = { \left\{ \begin{array} ...
                if var_part.endswith(r'\left\{') or var_part.endswith(r'{ \left\{'):
                    move_match = re.search(r'(\{?\s*\\left\\\{\s*)$', var_part)
                    if move_match:
                        to_move = move_match.group(1)
                        var_part = var_part[:-len(to_move)].strip()
                        matrix_part = to_move + matrix_match.group(2)
                else:
                    matrix_part = matrix_match.group(2)
                
                trailing_after_matrix = latex[matrix_match.end():].strip()
                # Remove trailing } if we moved a corresponding {
                if matrix_part.startswith('{') and trailing_after_matrix.endswith('}'):
                    matrix_part = matrix_part + "}"
                    trailing_after_matrix = trailing_after_matrix[:-1].strip()
            
            # If no variable part (standalone matrix), create empty variable
            if not var_part:
                var_part = ""
            
            # Convert variable part (e.g., M_1) if present
            var_root = None
            if var_part:
                try:
                    var_mathml = latex2mathml_convert(var_part)
                    var_root = ET.fromstring(var_mathml)
                except Exception as exc:
                    logger.warning("Failed to convert variable part: %s | Error: %s", var_part[:50], exc)
                    # Continue without variable part (standalone matrix)
                    var_root = None
            
            # Determine bracket type
            bracket_open = "["
            bracket_close = "]"
            
            if "pmatrix" in matrix_part:
                bracket_open = "("
                bracket_close = ")"
            elif "vmatrix" in matrix_part:
                bracket_open = "|"
                bracket_close = "|"
            elif "Vmatrix" in matrix_part:
                bracket_open = "‖"
                bracket_close = "‖"
            elif r"\left\{" in matrix_part or r"\left\{" in latex:
                bracket_open = "{"
                bracket_close = "}"
            elif r"\left(" in matrix_part:
                bracket_open = "("
                bracket_close = ")"
            elif r"\left|" in matrix_part:
                bracket_open = "|"
                bracket_close = "|"
            elif "array" in matrix_part and "\\left[" not in matrix_part:
                # Standalone array without brackets - use square brackets by default
                bracket_open = "["
                bracket_close = "]"
            
            # ------------------------------------------------------------------
            # Balance unmatched \left\{ ... \right\} that pix2tex often omits
            # ------------------------------------------------------------------
            if "\\left\\{" in matrix_part and "\\right\\}" not in matrix_part:
                matrix_part = matrix_part + " \\right\\}"
            # If braces are still unbalanced, append missing closing braces conservatively
            brace_diff = matrix_part.count("{") - matrix_part.count("}")
            if brace_diff > 0 and brace_diff <= 3:
                matrix_part = matrix_part + "}" * brace_diff

            # Parse matrix content (unless we already parsed it for bracket-based matrices)
            if not skip_parsing:
                matrix_content = self._parse_matrix_content(matrix_part)
            # else: matrix_content is already set from bracket-based parsing above

            # Append trailing text (after the matrix) to the last row cell so we don't lose content
            if trailing_after_matrix:
                if matrix_content:
                    if matrix_content[-1]:
                        matrix_content[-1][-1] = (matrix_content[-1][-1] + " " + trailing_after_matrix).strip()
                    else:
                        matrix_content[-1].append(trailing_after_matrix)
                else:
                    matrix_content = [[trailing_after_matrix]]
            
            # If parser yielded too few rows but we detect explicit row separators, force split
            if (not matrix_content or len(matrix_content) < 2) and ("\\\\" in matrix_part or "\n" in matrix_part):
                forced = self._force_array_split(matrix_part)
                if forced:
                    matrix_content = forced

            # If the matrix content is 2x2 and each cell is a product of two h-hat terms,
            # attempt structured mtable conversion (preserve 2-line matrix).
            if matrix_content and len(matrix_content) == 2 and all(len(r) == 2 for r in matrix_content):
                structured = self._convert_matrix_content_to_mathml(matrix_content)
                if structured:
                    # Prepend variable/equals if present
                    if var_root or var_part:
                        math_elem = ET.Element("math", xmlns="http://www.w3.org/1998/Math/MathML", display="block")
                        mrow = ET.SubElement(math_elem, "mrow")
                        if var_root:
                            for child in list(var_root):
                                mrow.append(child)
                        elif var_part:
                            try:
                                var_mathml = latex2mathml_convert(var_part)
                                var_root2 = ET.fromstring(var_mathml)
                                for child in list(var_root2):
                                    mrow.append(child)
                            except Exception:
                                pass
                        mo_eq = ET.SubElement(mrow, "mo")
                        mo_eq.text = "="
                        # Attach structured mtable
                        try:
                            struct_root = ET.fromstring(structured)
                            for child in list(struct_root):
                                mrow.append(child)
                        except Exception:
                            return structured
                        try:
                            ET.indent(math_elem, space="  ")
                        except AttributeError:
                            pass
                        return ET.tostring(math_elem, encoding="unicode", method="xml")
                    return structured

            # If this is effectively a single-column stack (common from pix2tex arrays),
            # treat it as a multiline equation instead of a matrix to avoid mtable/mtext noise.
            if matrix_content:
                max_cols = max(len(row) for row in matrix_content if row)
                total_rows = len(matrix_content)
                if max_cols <= 1 and total_rows >= 1:
                    multiline_latex = " \\\\ ".join(" ".join(row) for row in matrix_content if row)
                    return self._convert_multiline(multiline_latex)

            if not matrix_content:
                # Fallback: try converting entire matrix with latex2mathml
                logger.warning("Could not parse matrix content, trying direct conversion")
                try:
                    full_mathml = latex2mathml_convert(latex)
                    full_mathml = self._ensure_namespace(full_mathml)
                    full_mathml = self._normalize_operator_tags(full_mathml)
                    full_mathml = self._clean_invalid_mathml(full_mathml)
                    if '<math' in full_mathml and 'display=' not in full_mathml:
                        full_mathml = full_mathml.replace('<math', '<math display="block"', 1)
                    return full_mathml
                except Exception as exc:
                    logger.warning("Direct conversion also failed: %s", exc)
                    return self._convert_single_line(latex)
            
            # Create MathML structure
            math_elem = ET.Element("math", xmlns="http://www.w3.org/1998/Math/MathML", display="block")
            mrow = ET.SubElement(math_elem, "mrow")
            
            # Add variable (e.g., M_1) if present
            if var_root:
                for child in list(var_root):
                    mrow.append(child)
                
                # Add equals sign
                mo_eq = ET.SubElement(mrow, "mo")
                mo_eq.text = "="
            
            # Add opening bracket
            mo_open = ET.SubElement(mrow, "mo")
            mo_open.text = bracket_open
            
            # Add matrix table
            mtable = ET.SubElement(mrow, "mtable")
            
            cell_failure = False

            # Add rows
            for row_data in matrix_content:
                mtr = ET.SubElement(mtable, "mtr")
                
                # Add cells in this row
                for cell_latex in row_data:
                    mtd = ET.SubElement(mtr, "mtd")
                    
                    # Clean the cell LaTeX first to fix common OCR errors
                    cleaned_cell = self._clean_array_cell_latex(cell_latex)
                    
                    # Convert cell content to MathML
                    cell_converted = False
                    try:
                        cell_mathml = latex2mathml_convert(cleaned_cell)
                        cell_root = ET.fromstring(cell_mathml)
                        
                        # Move all children from cell_root to mtd
                        for child in list(cell_root):
                            mtd.append(child)
                        cell_converted = True
                    except Exception as exc:
                        # If cleaned version failed, try original
                        if cleaned_cell != cell_latex.strip():
                            try:
                                cell_mathml = latex2mathml_convert(cell_latex.strip())
                                cell_root = ET.fromstring(cell_mathml)
                                for child in list(cell_root):
                                    mtd.append(child)
                                cell_converted = True
                            except Exception:
                                pass
                        
                        if not cell_converted:
                            cell_failure = True
                            logger.warning("Failed to convert matrix cell: %s | Error: %s", cell_latex[:30], exc)
                            # Instead of putting LaTeX in mtext (which triggers gatekeeper violations),
                            # try to extract plain text or use an empty cell
                            # Remove LaTeX commands and braces to get plain text
                            plain_text = re.sub(r'\\[a-zA-Z]+\{?[^}]*\}?', '', cleaned_cell)
                            plain_text = re.sub(r'[{}]', '', plain_text)
                            plain_text = plain_text.strip()
                            
                            if plain_text:
                                # Use mtext only for plain text (no LaTeX commands)
                                mtext = ET.SubElement(mtd, "mtext")
                                mtext.text = plain_text[:50]  # Limit length
                            else:
                                # Empty cell - add a space to maintain structure
                                mtext = ET.SubElement(mtd, "mtext")
                                mtext.text = " "
            
            # If any cell failed, attempt direct conversion of the original LaTeX as a fallback
            if cell_failure:
                try:
                    fallback_mathml = latex2mathml_convert(latex)
                    fallback_mathml = self._ensure_namespace(fallback_mathml)
                    fallback_mathml = self._normalize_operator_tags(fallback_mathml)
                    fallback_mathml = self._clean_invalid_mathml(fallback_mathml)
                    if '<math' in fallback_mathml and 'display=' not in fallback_mathml:
                        fallback_mathml = fallback_mathml.replace('<math', '<math display="block"', 1)
                    return fallback_mathml
                except Exception as exc:
                    logger.warning("Direct fallback conversion failed after cell errors: %s", exc)

            # Add closing bracket
            mo_close = ET.SubElement(mrow, "mo")
            mo_close.text = bracket_close
            
            # Convert to string
            try:
                ET.indent(math_elem, space="  ")
            except AttributeError:
                pass  # Python < 3.9
            
            mathml_str = ET.tostring(math_elem, encoding="unicode", method="xml")
            mathml_str = self._normalize_operator_tags(mathml_str)
            return mathml_str
            
        except Exception as exc:
            logger.exception("Failed to convert matrix equation: %s", exc)
            return self._convert_single_line(latex)

    def _clean_array_cell_latex(self, cell_latex: str) -> str:
        """
        Clean up array cell LaTeX by removing excessive braces and fixing common OCR errors.
        
        Fixes:
        - Removes excessive double braces: {{...}} -> {...}
        - Removes triple+ braces: {{{...}}} -> {...}
        - Fixes incomplete commands at the end
        - Balances braces
        - Removes trailing incomplete LaTeX commands
        - Removes leftover column spec tokens like {l}, {cc}
        """
        if not cell_latex or not cell_latex.strip():
            return cell_latex
        
        cleaned = cell_latex.strip()
        
        # Remove column specification artifacts inside cells: {l}, {cc}, {lll}, etc.
        cleaned = re.sub(r'^\{\s*[^}]+\s*\}\s*', '', cleaned)

        # Collapse extreme pix2tex verbosity: repeated \displaystyle
        cleaned = re.sub(r'(\\displaystyle\s*){2,}', lambda m: r'\displaystyle ', cleaned)

        # Step 1: Remove excessive outer braces (common OCR error)
        # Pattern: {{text}} or {{{text}}} at the start/end
        # Count leading opening braces
        leading_braces = 0
        for char in cleaned:
            if char == '{':
                leading_braces += 1
            else:
                break
        
        # Count trailing closing braces
        trailing_braces = 0
        for char in reversed(cleaned):
            if char == '}':
                trailing_braces += 1
            else:
                break
        
        # If we have matching excessive braces (2+ on each side), remove one level
        if leading_braces >= 2 and trailing_braces >= 2 and leading_braces == trailing_braces:
            # Remove one level of outer braces
            cleaned = cleaned[1:-1].strip()
            # Recursively clean if there are still excessive braces
            if cleaned.startswith('{{') and cleaned.endswith('}}'):
                cleaned = self._clean_array_cell_latex(cleaned)
        
        # Step 2: Fix excessive braces in command arguments
        # Pattern: \command{{{arg}}} -> \command{{arg}} or \command{arg}
        # But be careful - some commands legitimately use nested braces
        
        # Fix patterns like \overline{{{h}}} -> \overline{h} or \overline{{h}}
        # Only fix if it's clearly excessive (3+ braces)
        def fix_excessive_command_braces(text: str) -> str:
            """Fix excessive braces in LaTeX command arguments."""
            result = text
            # Pattern: \command{{{...}}} -> \command{{...}} (reduce by one level)
            # We need to match commands with excessive braces in their arguments
            # Strategy: Find commands and check if their arguments have excessive braces
            
            # Find all LaTeX commands: \command{...}
            command_pattern = r'\\([a-zA-Z]+)\{'
            commands = list(re.finditer(command_pattern, result))
            
            # Process from right to left to avoid index shifting
            for cmd_match in reversed(commands):
                cmd_start = cmd_match.start()
                cmd_name = cmd_match.group(1)
                arg_start = cmd_match.end()  # Position after \command{
                
                # Find the matching closing brace for this command
                brace_depth = 1
                arg_end = arg_start
                while arg_end < len(result) and brace_depth > 0:
                    if result[arg_end] == '{':
                        brace_depth += 1
                    elif result[arg_end] == '}':
                        brace_depth -= 1
                    arg_end += 1
                
                if brace_depth == 0:
                    # Found the matching closing brace
                    arg_content = result[arg_start:arg_end-1]  # Content without final }
                    
                    # Check if argument starts and ends with excessive braces
                    if arg_content.startswith('{{') and arg_content.endswith('}}'):
                        # Count leading/trailing braces
                        leading = 0
                        for char in arg_content:
                            if char == '{':
                                leading += 1
                            else:
                                break
                        
                        trailing = 0
                        for char in reversed(arg_content):
                            if char == '}':
                                trailing += 1
                            else:
                                break
                        
                        # If we have 2+ matching braces on each side, reduce by one level
                        if leading >= 2 and trailing >= 2 and leading == trailing:
                            inner_content = arg_content[1:-1]  # Remove one level
                            # Replace the command argument
                            new_cmd = f'\\{cmd_name}{{{inner_content}}}'
                            result = result[:cmd_start] + new_cmd + result[arg_end:]
            
            return result
        
        cleaned = fix_excessive_command_braces(cleaned)
        
        # Step 3: Fix simple double-brace patterns that aren't commands
        # Pattern: {{text}} where text doesn't start with backslash -> {text}
        # Only fix if it's clearly not a command
        if not cleaned.startswith('\\'):
            # Check if entire content is wrapped in double braces
            if cleaned.startswith('{{') and cleaned.endswith('}}'):
                # Check if inner content is simple (no backslashes or complex structure)
                inner = cleaned[2:-2]
                if '\\' not in inner and '{' not in inner and '}' not in inner:
                    cleaned = inner
                elif inner.count('{') == inner.count('}'):  # Balanced inner braces
                    cleaned = '{' + inner + '}'
        else:
            # Remove a single outer brace layer around a leading \displaystyle block: {\displaystyle ...} -> \displaystyle ...
            if cleaned.startswith('{\\displaystyle') and cleaned.endswith('}'):
                inner = cleaned[1:-1].strip()
                cleaned = inner
        
        # Step 4: Balance braces (add missing closing braces)
        open_braces = cleaned.count('{')
        close_braces = cleaned.count('}')
        if open_braces > close_braces:
            diff = open_braces - close_braces
            if diff <= 5:  # Only fix if difference is small
                cleaned = cleaned + '}' * diff
        elif close_braces > open_braces:
            diff = close_braces - open_braces
            if diff <= 5:
                # Remove trailing closing braces
                while diff > 0 and cleaned.endswith('}'):
                    cleaned = cleaned[:-1]
                    diff -= 1
        
        # Step 5: Remove trailing incomplete commands
        # Pattern: ends with \command{... without closing brace
        incomplete_pattern = r'\\[a-zA-Z]+\{[^}]*$'
        if re.search(incomplete_pattern, cleaned):
            # Find last backslash
            last_backslash = cleaned.rfind('\\')
            if last_backslash >= 0:
                remaining = cleaned[last_backslash:]
                # Check if it's an incomplete command (has { but not enough })
                if '{' in remaining:
                    open_in_remaining = remaining.count('{')
                    close_in_remaining = remaining.count('}')
                    if open_in_remaining > close_in_remaining:
                        # Incomplete command - try to complete it or remove it
                        # If it's just missing closing braces, add them
                        missing = open_in_remaining - close_in_remaining
                        if missing <= 3:
                            cleaned = cleaned + '}' * missing
                        else:
                            # Too many missing - remove the incomplete command
                            cleaned = cleaned[:last_backslash].rstrip()
        
        return cleaned.strip()
    
    def _parse_matrix_content(self, matrix_latex: str) -> list[list[str]]:
        """Parse matrix LaTeX content into rows and cells."""
        rows = []
        
        # Extract content between \begin and \end
        begin_match = re.search(r'\\begin\{(bmatrix|pmatrix|vmatrix|Vmatrix|matrix|array)\*?\}', matrix_latex, re.IGNORECASE)
        if begin_match:
            # Extract content between begin and end
            content_start = begin_match.end()
            end_match = re.search(r'\\end\{(?:bmatrix|pmatrix|vmatrix|Vmatrix|matrix|array)\*?\}', matrix_latex[content_start:], re.IGNORECASE)
            
            if end_match:
                content = matrix_latex[content_start:content_start + end_match.start()].strip()
            else:
                content = matrix_latex[content_start:].strip()
        else:
            # Try \left[ \begin{array} pattern
            left_match = re.search(r'\\left\s*\[.*?\\begin\s*\{array\}', matrix_latex, re.DOTALL | re.IGNORECASE)
            if left_match:
                # Find the array content
                array_start_match = re.search(r'\\begin\s*\{array\}', matrix_latex[left_match.end():], re.IGNORECASE)
                if array_start_match:
                    array_start = left_match.end() + array_start_match.end()
                    # Skip column specification if present: {cc} or {ll}
                    col_spec_match = re.search(r'\{[^}]+\}', matrix_latex[array_start:])
                    if col_spec_match:
                        array_start += col_spec_match.end()
                    
                    array_end_match = re.search(r'\\end\s*\{array\}', matrix_latex[array_start:], re.IGNORECASE)
                    if array_end_match:
                        content = matrix_latex[array_start:array_start + array_end_match.start()].strip()
                    else:
                        content = matrix_latex[array_start:].strip()
                else:
                    content = matrix_latex[left_match.end():].strip()
            else:
                content = matrix_latex.strip()
        
        # Remove leading column specification like {l}, {cc}, {llrr}, etc.
        # This often appears as the first token and breaks cell conversion.
        content = re.sub(r'^\{\s*[^}]+\s*\}\s*', '', content)

        # Remove \right] or \right) if present at the end
        content = re.sub(r'\\right\s*[\]\)]?\s*$', '', content).strip()
        
        # Strip leading/trailing stray braces that often wrap pix2tex arrays and block row splitting
        if content.startswith("{") and content.count("{") > content.count("}"):
            content = content.lstrip("{").strip()
        if content.endswith("}") and content.count("}") > content.count("{"):
            content = content.rstrip("}").strip()

        # Split by row separators (\\ or \cr or newlines)
        row_separators = re.split(r'\\\\|\n|\r\n|\r', content)
        
        for row_str in row_separators:
            row_str = row_str.strip()
            if not row_str:
                continue
            
            # Remove row-level column specification if still present
            row_str = re.sub(r'^\{\s*[^}]+\s*\}\s*', '', row_str)

            # Collapse redundant displaystyle noise in row
            row_str = self._normalize_pix2tex_noise(row_str)

            # Remove trailing backslashes
            row_str = re.sub(r'\\+$', '', row_str).strip()
            
            # Split by column separators (&)
            # Handle both & and \& (escaped ampersand)
            cells = []
            current_cell = ""
            i = 0
            while i < len(row_str):
                if row_str[i] == '&' and (i == 0 or row_str[i-1] != '\\'):
                    cells.append(current_cell.strip())
                    current_cell = ""
                else:
                    current_cell += row_str[i]
                i += 1
            
            # Add the last cell
            if current_cell.strip():
                cells.append(current_cell.strip())
            
            # Filter out empty cells at the end
            while cells and not cells[-1].strip():
                cells.pop()
            
            # If no & found, treat entire row as single cell (might be a 1-column matrix)
            if not cells and row_str:
                cells = [row_str]
            
            if cells:
                # Remove column specs in cells before storing
                normalized_cells = [re.sub(r'^\{\s*[^}]+\s*\}\s*', '', c).strip() for c in cells]
                rows.append(normalized_cells)

        # Remove leading empty cells (but only if there is more than one cell in the row)
        cleaned_rows = []
        for r in rows:
            if len(r) > 1 and r[0] == "":
                r = r[1:]
            # Drop rows that become empty after cleaning
            if r:
                cleaned_rows.append(r)
        rows = cleaned_rows

        # Drop leading label-only row (e.g., (ii), (v), roman numerals) when there is real content after it
        if len(rows) > 1:
            first_cells = rows[0]
            if len(first_cells) == 1:
                lbl = first_cells[0].replace(" ", "")
                if re.match(r'^\(?[ivxlcdmIVXLCDM]+\)?$', lbl) or re.match(r'^\(\s*[0-9]+\s*\)$', first_cells[0]):
                    rows = rows[1:]
        
        return rows

    # ------------------------------------------------------------------ #
    # Pix2Tex noise normalizer                                           #
    # ------------------------------------------------------------------ #
    def _fix_corrupted_latex_commands(self, text: str) -> str:
        """
        Fix corrupted LaTeX commands that appear in OCR output.
        
        Common OCR errors:
        - \\j → j (when it's clearly meant to be just j, not dotless j)
        - \\subseteqT\\leqt → 0 \\leq \\tau \\leq t (corrupted inequality chains)
        - \\inE → \\in E (missing spaces)
        - Other corrupted command patterns
        """
        if not text:
            return text
        
        fixed = text
        
        # Fix \j when it appears in contexts where it should be just j
        # Pattern: \j followed by punctuation, closing braces, or operators (not a valid dotless j context)
        # But preserve \j when it's clearly meant to be dotless j (e.g., in integrals)
        # Common case: (i, \j) → (i, j) in set notation
        fixed = re.sub(r'\(([^,]+),\s*\\j\s*\)', r'(\1, j)', fixed)  # (i, \j) → (i, j)
        fixed = re.sub(r'\\j([,}\])}\s])', r'j\1', fixed)  # \j} → j}, \j, → j,
        fixed = re.sub(r'\\j\s*([a-zA-Z])', r'j \1', fixed)  # \j followed by letter → j (space)
        fixed = re.sub(r'\\j\s*\\in', r'j \\in', fixed)  # \j\in → j \in
        
        # Fix corrupted inequality chains: \subseteqT\leqt → 0 \leq \tau \leq t
        # This is a common OCR error where "0 ≤ τ ≤ t" gets mangled
        fixed = re.sub(r'\\subseteqT\\leqt', r'0 \\leq \\tau \\leq t', fixed)
        fixed = re.sub(r'\\subseteqT\s*\\leqt', r'0 \\leq \\tau \\leq t', fixed)
        
        # Fix missing spaces after operators: \inE → \in E
        fixed = re.sub(r'\\in([A-Z])', r'\\in \1', fixed)
        fixed = re.sub(r'\\subseteq([A-Z])', r'\\subseteq \1', fixed)
        fixed = re.sub(r'\\subset([A-Z])', r'\\subset \1', fixed)
        
        # Fix corrupted \leq patterns: \leqt → \leq t (missing space)
        fixed = re.sub(r'\\leq([a-zA-Z])', r'\\leq \1', fixed)
        fixed = re.sub(r'\\geq([a-zA-Z])', r'\\geq \1', fixed)
        
        # Fix corrupted \tau: \subseteqT → \subseteq \tau (when T should be tau)
        # But be careful - only fix when it's clearly part of an inequality chain
        fixed = re.sub(r'\\subseteqT(?!\\leq)', r'\\subseteq \\tau', fixed)
        
        # Fix other common OCR errors: commands merged with following text
        # Pattern: \commandLetter → \command Letter (when command should be separate)
        fixed = re.sub(r'\\(subseteq|subset|supseteq|supset)([A-Z])', r'\\\1 \2', fixed)
        
        return fixed

    def _normalize_pix2tex_noise(self, text: str) -> str:
        r"""
        Collapse extremely redundant pix2tex wrappers that bloat arrays and
        sometimes cause brace imbalances.

        - Collapse runs of \\displaystyle (2+) into a single occurrence.
        - Remove superfluous outer double braces when they only wrap a token.
        - Sanitize stray \left. / \right. and delimiter artifacts.
        """
        if not text:
            return text

        normalized = text
        
        # CRITICAL: Fix corrupted LaTeX commands FIRST before other normalization
        normalized = self._fix_corrupted_latex_commands(normalized)

        # Collapse repeated \displaystyle tokens
        normalized = re.sub(r'(\\displaystyle\s*){2,}', lambda m: r'\displaystyle ', normalized)

        # Remove outer braces if they wrap the entire expression and are balanced
        # Example: {\left\{ ... \right\}} -> \left\{ ... \right\}
        # Example: {{\displaystyle X}} -> \displaystyle X
        while normalized.startswith("{") and normalized.endswith("}"):
            inner = normalized[1:-1].strip()
            # Ensure braces are balanced in the inner part
            depth = 0
            balanced = True
            for ch in inner:
                if ch == "{": depth += 1
                elif ch == "}": depth -= 1
                if depth < 0:
                    balanced = False
                    break
            if balanced and depth == 0:
                normalized = inner
            else:
                break

        # Sanitize delimiter noise: \left. / \right. often appear and break parsing
        normalized = re.sub(r'\\left\.', '', normalized)
        normalized = re.sub(r'\\right\.', '', normalized)

        # Fix doubled pipe delimiters like \left\| -> \left| (same for right)
        normalized = normalized.replace(r'\left\|', r'\left|')
        normalized = normalized.replace(r'\right\|', r'\right|')

        # Remove lone \left or \right without delimiter (common OCR artifact)
        normalized = re.sub(r'\\left\s+(?=\\)', lambda m: r'\left', normalized)  # tighten spacing
        normalized = re.sub(r'\\right\s+(?=\\)', lambda m: r'\right', normalized)
        normalized = re.sub(r'\\left\s*$', '', normalized)
        normalized = re.sub(r'\\right\s*$', '', normalized)

        return normalized

    def _collapse_quads(self, text: str) -> str:
        r"""Collapse long runs of \qquad into a single space."""
        return re.sub(r'(\\qquad\s*){2,}', ' ', text)

    def _extract_unclosed_array_body(self, text: str) -> str | None:
        r"""
        Detect \begin{array}{...} without a matching \end{array} (or with corrupted end),
        unwrap its content, and return the inner body. Returns None if not detected.
        """
        begin_matches = list(re.finditer(r'\\begin\{array\}\{[^}]*\}', text))
        end_matches = list(re.finditer(r'\\end\{array\}', text))

        if not begin_matches:
            return None

        # If counts match, treat as normal array (handled elsewhere)
        if len(begin_matches) == len(end_matches):
            return None

        # Take the first begin; try to find a matching end after it
        begin = begin_matches[0]
        after_begin = text[begin.end():]
        end_match = re.search(r'\\end\{array\}', after_begin)

        if end_match:
            body = after_begin[:end_match.start()]
        else:
            # No closing end -> take the remainder as body
            body = after_begin

        body = body.strip()
        if not body:
            return None

        # Remove any trailing unmatched \end fragments like "\end{a"
        body = re.sub(r'\\end\{?[a-zA-Z]*\}?', '', body)
        return body

    def _strip_outer_braces(self, text: str) -> str:
        """
        Remove one level of outer braces if they wrap the entire expression and are balanced.
        """
        if not text:
            return text
        if text.startswith("{") and text.endswith("}"):
            # Ensure braces are balanced
            depth = 0
            balanced = True
            for ch in text:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                if depth < 0:
                    balanced = False
                    break
            if balanced and depth == 0:
                return text[1:-1].strip()
        return text

    def _repair_latex_line(self, latex: str) -> str:
        """
        Attempt to repair common LaTeX issues that cause conversion failures.
        
        This function tries to fix:
        - Corrupted LaTeX commands (like \\j, \\subseteqT\\leqt)
        - Unbalanced braces (conservatively)
        - Unmatched \\left/\\right pairs
        - Common command issues
        - Extra closing braces/delimiters
        
        Returns repaired LaTeX, or original if repair is not safe.
        """
        if not latex:
            return latex
        
        repaired = latex
        
        # CRITICAL: Fix corrupted LaTeX commands first
        repaired = self._fix_corrupted_latex_commands(repaired)
        
        # Count braces
        open_braces = repaired.count('{')
        close_braces = repaired.count('}')
        brace_diff = open_braces - close_braces
        
        # If we have unmatched opening braces at the end, try to close them conservatively
        # Only if the difference is small (1-3) to avoid over-correction
        if brace_diff > 0 and brace_diff <= 3:
            # Check if it ends with unmatched opening braces
            if re.search(r'\{+\s*$', repaired):
                # Append closing braces
                repaired = repaired + "}" * brace_diff
                logger.debug("Repaired unbalanced braces: added %d closing braces", brace_diff)
        
        # If we have unmatched closing braces at the start, try to remove them
        # But be very conservative - only if it's clearly a prefix issue
        if brace_diff < 0 and abs(brace_diff) <= 2:
            # Check if it starts with closing braces
            if re.match(r'^\s*\}+', repaired):
                # Remove excess closing braces from start
                repaired = re.sub(r'^\s*\}+', '', repaired, count=abs(brace_diff))
                logger.debug("Repaired unbalanced braces: removed %d closing braces from start", abs(brace_diff))
        
        # Fix unmatched \left/\right pairs
        left_count = repaired.count('\\left')
        right_count = repaired.count('\\right')
        
        # If we have \left without matching \right
        if left_count > right_count and (left_count - right_count) <= 3:
            # Try to add missing \right} or \right] or \right)
            # Look for all \left commands to determine what delimiters to use
            left_matches = list(re.finditer(r'\\left([\\{[(|.])', repaired))
            if left_matches:
                # Find the last unmatched \left
                unmatched_count = left_count - right_count
                # Get the last N \left commands (where N = unmatched_count)
                unmatched_lefts = left_matches[-unmatched_count:] if len(left_matches) >= unmatched_count else left_matches
                
                # Build the closing sequence in reverse order (last opened, first closed)
                closing_sequence = []
                for left_match in reversed(unmatched_lefts):
                    delimiter = left_match.group(1)
                    # Map opening to closing delimiter
                    delimiter_map = {
                        '{': '}',
                        '[': ']',
                        '(': ')',
                        '|': '|',
                        '.': '.',
                        '\\{': '\\}'
                    }
                    closing = delimiter_map.get(delimiter, '}')
                    closing_sequence.append(f"\\right{closing}")
                
                # Add missing \right commands
                repaired = repaired + ''.join(closing_sequence)
                logger.debug("Repaired unmatched \\left/\\right: added %d \\right commands", unmatched_count)
        
        # Fix common command issues: incomplete commands at the end
        # Remove incomplete commands (e.g., \fra, \lef, \rig)
        repaired = re.sub(r'\\fra\s*$', '', repaired)
        repaired = re.sub(r'\\lef\s*$', '', repaired)
        repaired = re.sub(r'\\rig\s*$', '', repaired)
        
        # Remove trailing incomplete command patterns
        repaired = re.sub(r'\\[a-z]{1,3}\s*$', '', repaired)
        
        # Fix double closing braces/delimiters that might cause issues
        # But be conservative - only fix obvious duplicates
        repaired = re.sub(r'\}\s*\}\s*\}\s*$', '}}', repaired)  # Triple closing -> double
        repaired = re.sub(r'\\right\}\s*\\right\}\s*$', '\\right}', repaired)  # Double \right}
        
        return repaired.strip()

    # ------------------------------------------------------------------ #
    # Structured matrix 2x2 (h-hat products) helper                      #
    # ------------------------------------------------------------------ #
    def _convert_matrix_content_to_mathml(self, matrix_content: list[list[str]]) -> str | None:
        """
        Convert 2x2 matrix content into MathML mtable, handling h-hat products cleanly.
        Expects matrix_content as list of rows, each a list of LaTeX strings.
        """
        try:
            math_elem = ET.Element("math", xmlns="http://www.w3.org/1998/Math/MathML", display="block")
            mrow = ET.SubElement(math_elem, "mrow")
            mo_open = ET.SubElement(mrow, "mo")
            mo_open.text = "["
            mtable = ET.SubElement(mrow, "mtable", rowspacing="0.6em", columnspacing="1.2em")

            for row_data in matrix_content:
                mtr = ET.SubElement(mtable, "mtr")
                for cell_latex in row_data:
                    mtd = ET.SubElement(mtr, "mtd")
                    # Clean cell
                    cleaned = self._clean_array_cell_latex(cell_latex)
                    # Convert with latex2mathml
                    try:
                        cell_mathml = latex2mathml_convert(cleaned)
                        cell_root = ET.fromstring(cell_mathml)
                        for child in list(cell_root):
                            mtd.append(child)
                    except Exception:
                        mtext = ET.SubElement(mtd, "mtext")
                        mtext.text = cleaned

            mo_close = ET.SubElement(mrow, "mo")
            mo_close.text = "]"

            try:
                ET.indent(math_elem, space="  ")
            except AttributeError:
                pass

            return ET.tostring(math_elem, encoding="unicode", method="xml")
        except Exception as exc:
            logger.warning("Structured matrix conversion failed: %s", exc)
            return None

    def _force_array_split(self, matrix_latex: str) -> list[list[str]]:
        """
        Fallback splitter for array content when standard parsing yields too few rows.
        Splits rows on '\\\\' or newlines, columns on '&'.
        """
        # Extract content between begin/end if possible
        content = matrix_latex
        begin = re.search(r'\\begin\{array\}\{[^}]*\}', matrix_latex)
        if begin:
            rest = matrix_latex[begin.end():]
            end = re.search(r'\\end\{array\}', rest)
            if end:
                content = rest[:end.start()]
            else:
                content = rest

        content = content.strip()
        if not content:
            return []

        rows = []
        for row_str in re.split(r'\\\\|\n|\r\n|\r', content):
            row_str = row_str.strip()
            if not row_str:
                continue
            cells = []
            for cell in re.split(r'(?<!\\)&', row_str):
                c = cell.strip()
                if c:
                    cells.append(c)
            if cells:
                rows.append(cells)
        return rows

    def _convert_single_line(self, latex: str) -> str:
        """Convert single-line LaTeX to MathML."""
        # Normalize whitespace (collapse multiple spaces/newlines to single space)
        # This ensures single-line equations stay single-line even if they have formatting newlines
        latex = " ".join(latex.split())
        
        # Extract equation label if present (e.g., "(ii)", "(2.1)") and handle separately
        label_match = re.match(r'^\(([^)]+)\)\s*(.*)$', latex)
        equation_label = None
        if label_match:
            equation_label = label_match.group(1)
            latex = label_match.group(2).strip()
        
        try:
            # Convert the main equation
            mathml = latex2mathml_convert(latex)
            mathml = self._ensure_namespace(mathml)
            mathml = self._normalize_operator_tags(mathml)
            mathml = self._clean_invalid_mathml(mathml)
            
            # If there's a label, wrap the entire equation in <mrow> and prepend label as <mtext>
            if equation_label:
                try:
                    root = ET.fromstring(mathml)
                    # Get the content inside <math> tag
                    math_content = list(root)
                    
                    # Create new structure: <mrow><mtext>(ii)</mtext><mspace/><content/></mrow>
                    mrow = ET.Element("mrow")
                    
                    # Add label
                    mtext_label = ET.SubElement(mrow, "mtext")
                    mtext_label.text = f"({equation_label})"
                    
                    # Add spacing
                    mspace = ET.SubElement(mrow, "mspace", width="0.5em")
                    
                    # Move all original content into mrow
                    for elem in math_content:
                        mrow.append(elem)
                    
                    # Replace content in root
                    root.clear()
                    root.append(mrow)
                    
                    mathml = ET.tostring(root, encoding="unicode", method="xml")
                except Exception as label_exc:
                    logger.warning("Failed to add equation label to MathML: %s", label_exc)
                    # Continue with unlabeled MathML
            
            if '<math' in mathml and 'display=' not in mathml:
                mathml = mathml.replace('<math', '<math display="block"', 1)
            return mathml
        except Exception as exc:
            # CRITICAL: NEVER create MathML with LaTeX in <mtext> - this violates gatekeeper rules
            # Re-raise to let pipeline handle recovery
            error_msg = f"{type(exc).__name__}: {str(exc)}"
            raise ValueError(f"LaTeX→MathML conversion failed: {error_msg}. LaTeX: {latex[:200]}")

    def _ensure_block_display(self, mathml: str) -> str:
        """Ensure the math tag has display="block" attribute."""
        if not mathml or '<math' not in mathml:
            return mathml
            
        if 'display=' not in mathml:
            return mathml.replace('<math', '<math display="block"', 1)
        return mathml

    def _ensure_namespace(self, mathml: str) -> str:
        """Ensure proper xmlns and mml prefix if needed."""
        # Delegate to post_processor if available, otherwise simple fix
        if hasattr(self, 'post_processor'):
            return self.post_processor.ensure_namespace(mathml)
            
        if 'xmlns=' not in mathml and '<math' in mathml:
             return mathml.replace('<math', '<math xmlns="http://www.w3.org/1998/Math/MathML"', 1)
        return mathml

    def _extract_label(self, latex: str) -> Tuple[Optional[str], str]:
        """
        Extract equation labels like \\tag{...} or (1.2) from the end of the string.
        Returns (label, clean_latex).
        """
        if not latex:
            return None, latex
            
        # 1. Check for \\tag{...}
        tag_match = re.search(r'\\tag\{((?:[^{}]|\\{|\\})*)\}', latex)
        if tag_match:
            label = tag_match.group(1)
            # Remove the tag from latex
            clean_latex = latex[:tag_match.start()] + latex[tag_match.end():]
            return label.strip(), clean_latex.strip()

        # 2. Check for (number) at the end of string
        # Careful not to match (a+b)
        # We look for (digits.digits) or (digits) at the very end
        label_match = re.search(r'\s*\((\d+(?:\.\d+)?)\)\s*$', latex)
        if label_match:
            label = label_match.group(1)
            clean_latex = latex[:label_match.start()]
            return label.strip(), clean_latex.strip()
            
        return None, latex

    def _attach_label(self, mathml: str, label: str) -> str:
        """
        Attach an equation label to the MathML.
        Creates an <mtable> structure if needed.
        """
        if not mathml or '<math' not in mathml:
            return mathml
            
        try:
            # Parse XML
            root = ET.fromstring(mathml)
            
            # We want to wrap the content in a table with the label on the right
            # <mtable width="100%"><mtr><mtd>{content}</mtd><mtd>(label)</mtd></mtr></mtable>
            # But standard MathML doesn't support "width=100%" cleanly in all renderers.
            # We'll generate a simple structure.
            
            ns = "{http://www.w3.org/1998/Math/MathML}"
            
            # Create new root mtable
            new_root = ET.Element(f"{ns}math" if root.tag.startswith(ns) else "math")
            if 'display' in root.attrib:
                new_root.set('display', root.attrib['display'])
            else:
                new_root.set('display', 'block')
                
            mtable = ET.SubElement(new_root, f"{ns}mtable" if root.tag.startswith(ns) else "mtable")
            # Set simpler attributes
            mtable.set('columnalign', 'center right')
            
            mtr = ET.SubElement(mtable, f"{ns}mtr" if root.tag.startswith(ns) else "mtr")
            
            # Content cell
            mtd_content = ET.SubElement(mtr, f"{ns}mtd" if root.tag.startswith(ns) else "mtd")
            
            # Copy all children of original root to mtd_content
            # If original root was math, its children are the expression
            for child in root:
                mtd_content.append(child)
                
            # Label cell
            mtd_label = ET.SubElement(mtr, f"{ns}mtd" if root.tag.startswith(ns) else "mtd")
            # Add padding
            mtd_label.set('style', 'padding-left: 2em;') 
            
            mtext = ET.SubElement(mtd_label, f"{ns}mtext" if root.tag.startswith(ns) else "mtext")
            mtext.text = f"({label})"
            
            return ET.tostring(new_root, encoding="unicode", method="xml")
            
        except Exception as e:
            logger.warning(f"Failed to attach label: {e}")
            return mathml

    def _fallback_text_mathml(self, text: str) -> str:
        """
        DEPRECATED: This method creates invalid MathML (LaTeX in <mtext>).
        
        CRITICAL RULE: NEVER place LaTeX commands in <mtext> tags.
        This violates gatekeeper rules and will be rejected by validation.
        
        Instead of using this fallback, the pipeline should:
        1. Detect conversion failure
        2. Attempt LaTeX repair/reconstruction
        3. Retry conversion
        4. If all fails, return empty MathML (fail safely)
        
        This method is kept for backward compatibility but should NOT be used.
        """
        # CRITICAL: Check if text contains LaTeX commands
        if re.search(r'\\[a-zA-Z]+\{?', text):
            # Contains LaTeX - DO NOT create invalid MathML
            logger.error("_fallback_text_mathml called with LaTeX - this creates invalid MathML!")
            logger.error("LaTeX in <mtext> violates gatekeeper rules - returning empty MathML")
            return '<math xmlns="http://www.w3.org/1998/Math/MathML" display="block"></math>'
        
        # Only allow plain text (no LaTeX commands)
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return (
            f'<math xmlns="http://www.w3.org/1998/Math/MathML" display="block">'
            f'<mtext>{text}</mtext>'
            f'</math>'
        )

    def _openai_latex_to_mathml(self, latex: str) -> str:
        """
        Use OpenAI GPT-4 to convert LaTeX to MathML.
        
        This is a fallback for complex multiline equations that latex2mathml cannot handle.
        """
        try:
            # Phase 2: Use the robust OCR-specific converter
            from services.ocr.openai_mathml_converter import OpenAIMathMLConverter
            
            # Use gpt-4o-mini for speed and cost-effectiveness (semantic repair)
            converter = OpenAIMathMLConverter(model="gpt-4o-mini")
            
            # The new converter returns a dict with 'mathml', 'latex', 'confidence'
            result = converter.convert_latex_to_mathml(latex)
            
            mathml = result.get("mathml", "")
            
            if not mathml or not mathml.strip():
                logger.warning("OpenAI returned empty MathML")
                return ""
            
            # Validate that it's actually MathML
            if '<math' not in mathml:
                logger.warning("OpenAI did not return valid MathML")
                return ""
            
            # Additional validation: ensure no LaTeX commands leaked into MathML
            if re.search(r'<mtext>.*\\[a-zA-Z]+\{', mathml):
                logger.warning("OpenAI MathML contains LaTeX in <mtext> - cleaning")
                mathml = self._clean_invalid_mathml(mathml)
            
            return mathml
            
        except ImportError:
            logger.error("OpenAIMathMLConverter not available - cannot use AI fallback")
            return ""
        except Exception as e:
            logger.error("OpenAI MathML conversion failed: %s", e)
            return ""


