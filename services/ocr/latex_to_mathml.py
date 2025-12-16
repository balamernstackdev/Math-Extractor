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


class LatexToMathML:
    """Convert clean LaTeX to MathML, with multi-line equation support."""

    def convert(self, latex: str) -> str:
        if not latex or not latex.strip():
            # Return empty MathML instead of <mtext> with empty string
            return '<math xmlns="http://www.w3.org/1998/Math/MathML" display="block"></math>'

        original = latex

        # Remove math delimiters if present: $ ... $
        latex = latex.strip()
        if latex.startswith("$") and latex.endswith("$"):
            latex = latex[1:-1].strip()

        # Normalize redundant pix2tex verbosity (e.g., repeated \displaystyle)
        latex = self._normalize_pix2tex_noise(latex)

        # CRITICAL: Check for truncated LaTeX BEFORE any repairs
        # If LaTeX ends with unmatched braces (e.g., {{), it's truncated and should be rejected
        open_braces = latex.count('{')
        close_braces = latex.count('}')
        if open_braces > close_braces:
            # Check if LaTeX ends with unmatched opening braces (truncated)
            if re.search(r'\{+\s*$', latex):
                logger.warning("Truncated LaTeX detected (ends with unmatched braces) - rejecting conversion")
                raise ValueError(f"Truncated LaTeX detected: ends with unmatched opening braces (count: {open_braces - close_braces})")

        # Repair common pix2tex truncations before structure checks
        # BUT: Only repair if not already detected as truncated above
        if "\\begin{array" in latex and "\\end{array" not in latex:
            latex = latex + r"\end{array}"
        if r"\left|" in latex and r"\right|" not in latex:
            latex = latex + r"\right|"
        brace_diff = latex.count("{") - latex.count("}")
        if 0 < brace_diff <= 3:
            latex = latex + "}" * brace_diff
        
        # CRITICAL: Only unwrap arrays if they actually contain multiple lines
        # Single-line equations wrapped in arrays should be converted as single-line
        array_unwrapped = self._unwrap_simple_array(latex)
        if array_unwrapped is not None:
            # Check if unwrapped content has actual line breaks (\\ or \n)
            # Count actual non-empty lines after splitting
            split_lines = [line.strip() for line in re.split(r'\\\\|\n|\r\n|\r', array_unwrapped) if line.strip()]
            if len(split_lines) > 1:
                # Multiple lines - convert as multiline
                logger.debug("Array contains %d lines, converting as multiline", len(split_lines))
                return self._convert_multiline(array_unwrapped)
            else:
                # Single line in array - convert as single line (remove array wrapper)
                logger.debug("Array contains single line, converting as single-line equation")
                # The unwrapped content is already the line content, just convert it
                return self._convert_single_line(array_unwrapped)

        # Handle unclosed or malformed array environments by unwrapping to multiline
        unclosed_body = self._extract_unclosed_array_body(latex)
        if unclosed_body is not None:
            # Collapse excessive \qquad runs
            unclosed_body = self._collapse_quads(unclosed_body)
            return self._convert_multiline(unclosed_body)

        # Check if this is a matrix equation
        if self._is_matrix_equation(latex):
            return self._convert_matrix_equation(latex)

        # Check if this is a multi-line equation
        if self._is_multiline_equation(latex):
            return self._convert_multiline(latex)

        # CRITICAL: For single-line equations, normalize whitespace but preserve structure
        # Collapse multiple spaces/newlines to single space to ensure it stays single-line
        latex_normalized = " ".join(latex.split())
        
        # Extract equation label if present (e.g., "(v)", "(ii)") and handle separately
        label_match = re.match(r'^\(([^)]+)\)\s*(.*)$', latex_normalized)
        equation_label = None
        if label_match:
            equation_label = label_match.group(1)
            latex_normalized = label_match.group(2).strip()

        try:
            mathml = latex2mathml_convert(latex_normalized)
            mathml = self._ensure_namespace(mathml)
            mathml = self._normalize_operator_tags(mathml)
            # CRITICAL: Clean invalid MathML (literal LaTeX commands, corrupted text)
            mathml = self._clean_invalid_mathml(mathml)
            
            # If there's a label, wrap the entire equation in <mrow> and prepend label as <mtext>
            if equation_label:
                try:
                    root = ET.fromstring(mathml)
                    # Get the content inside <math> tag
                    math_content = list(root)
                    
                    # Create new structure: <mrow><mtext>(v)</mtext><mspace/><content/></mrow>
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
            
            # Add display="block" for better rendering
            if '<math' in mathml and 'display=' not in mathml:
                mathml = mathml.replace('<math', '<math display="block"', 1)
            return mathml

        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {str(exc)}"
            logger.warning("LaTeX→MathML failed: %s | Input (first 200 chars): %s", error_msg, original[:200])
            logger.debug("Full LaTeX input: %s", original)
            # CRITICAL: NEVER create MathML with LaTeX in <mtext> - this violates gatekeeper rules
            # Instead, raise error to let pipeline handle recovery
            raise ValueError(f"LaTeX→MathML conversion failed: {error_msg}. LaTeX input: {original[:200]}")

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    def _ensure_namespace(self, mathml: str) -> str:
        """Ensure MathML output contains proper namespace."""
        if "<math" not in mathml:
            return f'<math xmlns="http://www.w3.org/1998/Math/MathML">{mathml}</math>'

        # Add namespace if missing
        if 'xmlns="' not in mathml:
            mathml = mathml.replace(
                "<math", '<math xmlns="http://www.w3.org/1998/Math/MathML"'
            )

        # Remove duplicate xmlns attributes (sometimes added upstream)
        mathml = re.sub(r'\s+xmlns="http://www\.w3\.org/1998/Math/MathML"(?![^>]*xmlns)', '', mathml, count=0)

        return mathml

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

    def _is_multiline_equation(self, latex: str) -> bool:
        """Detect if LaTeX represents a multi-line equation."""
        # CRITICAL: Be VERY strict - only treat as multiline if there are explicit line breaks
        # Single equations with labels like "(ii)" should NOT be treated as multiline
        # Equations that flow horizontally (even with formatting line breaks) should be single-line
        
        # Check for explicit line breaks (double backslash or \cr) - these indicate true multiline
        if "\\\\" in latex or "\\cr" in latex:
            # But check if it's just formatting - if there's only one \\ and the equation flows,
            # it might still be semantically single-line
            line_break_count = latex.count("\\\\") + latex.count("\\cr")
            if line_break_count > 0:
                # Check if it's in an array or align environment (definitely multiline)
                if re.search(r'\\begin\{(array|align|aligned|eqnarray|split|multline|gather)', latex, re.IGNORECASE):
                    return True
                # If there are multiple line breaks, it's likely multiline
                if line_break_count > 1:
                    return True
                # Single line break might be formatting - be conservative and treat as single-line
                # unless it's clearly in a multiline structure
                logger.debug("Single line break detected, treating as single-line equation (may be formatting)")
                return False
        
        # Check for align environments (explicit multiline environments)
        if re.search(r'\\begin\{(align|aligned|eqnarray|split|multline|gather)', latex, re.IGNORECASE):
            return True
        
        # Check for array environments with multiple rows
        array_match = re.search(r'\\begin\{array\}', latex, re.IGNORECASE)
        if array_match:
            # Check if array body contains line breaks
            array_body_match = re.search(r'\\begin\{array\}\{[^}]*\}(.*?)\\end\{array\}', latex, re.DOTALL | re.IGNORECASE)
            if array_body_match:
                array_body = array_body_match.group(1)
                # Count actual line breaks in array body
                line_breaks_in_body = array_body.count("\\\\") + array_body.count("\\cr")
                if line_breaks_in_body > 0:
                    return True
        
        # CRITICAL: Do NOT treat single equations with newlines as multiline
        # Many single-line equations have newlines for formatting but are semantically single-line
        # Only treat as multiline if there are explicit line breaks (\\ or \cr) in multiline environments
        
        return False

    def _convert_multiline(self, latex: str) -> str:
        """Convert multi-line LaTeX equation to structured MathML with mtable."""
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
            
            # Process each line
            logger.debug("Multiline conversion: processing %d lines", len(lines))
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
        
        # First, try splitting by explicit line breaks
        if "\\\\" in latex_clean or "\\cr" in latex_clean or "\n" in latex_clean:
            # Split by line breaks
            line_breaks = re.split(r'\\\\|\n|\r\n|\r', latex_clean)
            
            for line in line_breaks:
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
        
        # CRITICAL: Do NOT use intelligent splitting for single-line equations
        # Only split if there are explicit line breaks (\\ or \n)
        # The "intelligent splitting" was causing single equations to be incorrectly split
        # Single equations with operators like ≤ or - should stay as single line
        # Only use multiline if there are explicit line breaks or align environments
        
        return lines

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
                    # No matrix found, try direct conversion (might be malformed)
                    logger.warning("Matrix pattern detected but couldn't extract matrix content, trying direct conversion")
                    return self._convert_single_line(latex)
            else:
                var_part = matrix_match.group(1).strip()
                # Remove trailing = if present
                var_part = re.sub(r'\s*=\s*$', '', var_part).strip()
                matrix_part = matrix_match.group(2)
                trailing_after_matrix = latex[matrix_match.end():].strip()
            
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

            # Parse matrix content
            matrix_content = self._parse_matrix_content(matrix_part)

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

        # Remove outer double braces around simple content (non-command or a single command)
        # Example: {{\displaystyle X}} -> {\displaystyle X}
        if normalized.startswith("{{") and normalized.endswith("}}"):
            inner = normalized[2:-2]
            # Only strip one level if it looks like an over-wrapped token
            if inner and inner.count("{") == inner.count("}"):
                normalized = inner if inner.startswith("\\") else "{" + inner + "}"

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
        - Unmatched \left/\right pairs
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


# """Convert LaTeX to MathML."""
# from __future__ import annotations

# import re
# import xml.etree.ElementTree as ET

# from latex2mathml.converter import convert as latex2mathml_convert

# from core.logger import logger

# # Import entity utilities for proper HTML entity handling in MathML
# try:
#     from utils.html_entity_utils import (
#         decode_html_entities,
#         normalize_mathml_entities,
#         escape_for_mathml,
#     )
#     ENTITY_UTILS_AVAILABLE = True
# except ImportError:
#     # Fallback if entity utilities not available
#     ENTITY_UTILS_AVAILABLE = False
#     logger.warning("HTML entity utilities not available - using basic XML escaping")

# # Avoid ns0 prefixes by registering the default MathML namespace up front
# ET.register_namespace("", "http://www.w3.org/1998/Math/MathML")


# class LatexToMathML:
#     """Service converting LaTeX strings to MathML with Mathpix-like formatting."""

#     def convert(self, latex: str) -> str:
#         """Convert LaTeX to MathML with proper structure like Mathpix."""
#         logger.info("Converting LaTeX to MathML")
#         if not latex:
#             raise ValueError("Empty LaTeX string")
        
#         # STEP 0: Check for corrupted LaTeX patterns and apply canonical reconstruction
#         # This ensures we never convert corrupted LaTeX to MathML
#         # Store original for logging
#         original_latex = latex
#         latex = self._ensure_canonical_latex(latex)
#         latex = self._repair_common_ocr_errors(latex)
#         if latex != original_latex:
#             # Safely encode Unicode for logging (avoid encoding errors)
#             try:
#                 original_safe = original_latex[:80].encode('ascii', 'replace').decode('ascii')
#                 latex_safe = latex[:80].encode('ascii', 'replace').decode('ascii')
#                 logger.info("LaTeX was reconstructed: %s -> %s", original_safe, latex_safe)
#             except Exception:  # noqa: BLE001
#                 logger.info("LaTeX was reconstructed (Unicode in string)")
        
#         # Check if it's plain text wrapped in \text{} - don't convert to MathML
#         if latex.startswith("\\text{") and latex.endswith("}"):
#             # It's plain text, create simple MathML for text
#             text_content = latex[6:-1]  # Remove \text{ and }
#             # Unescape LaTeX special characters
#             text_content = text_content.replace("\\{", "{")
#             text_content = text_content.replace("\\}", "}")
#             text_content = text_content.replace("\\textbackslash", "\\")
#             text_content = text_content.replace("\\$", "$")
#             text_content = text_content.replace("\\&", "&")
#             text_content = text_content.replace("\\%", "%")
#             text_content = text_content.replace("\\#", "#")
#             text_content = text_content.replace("\\textasciicircum", "^")
#             text_content = text_content.replace("\\_", "_")
            
#             # Decode any HTML entities in text content, then escape for XML
#             if ENTITY_UTILS_AVAILABLE:
#                 text_content = decode_html_entities(text_content)
#                 text_content = escape_for_mathml(text_content)
#             else:
#                 # Basic XML escaping
#                 text_content = text_content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            
#             # Return simple MathML for text
#             return f'<math xmlns="http://www.w3.org/1998/Math/MathML"><mtext>{text_content}</mtext></math>'
        
#         # Check if it's just a simple identifier in $...$
#         if latex.startswith("$") and latex.endswith("$") and len(latex) > 2:
#             inner = latex[1:-1].strip()
#             # If it's just alphanumeric, treat as identifier
#             if inner.replace("_", "").replace("^", "").isalnum():
#                 return f'<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>{inner}</mi></math>'
        
#         # Try to convert actual LaTeX
#         try:
#             # Remove $ delimiters if present for conversion
#             latex_clean = latex.strip()
#             if latex_clean.startswith("$") and latex_clean.endswith("$"):
#                 latex_clean = latex_clean[1:-1]
            
#             # Detect equation labels like "(2.1)", "(2.2)", etc. - also handle at end with comma
#             equation_label = None
#             # Pattern: (2.1) or (2.1), at the end, possibly with text before it
#             label_patterns = [
#                 r',\s*\((\d+\.\d+)\)\s*$',  # Comma before label at end: ", (2.1)"
#                 r'\s+\((\d+\.\d+)\)\s*$',   # Space before label at end: " (2.1)"
#                 r'\((\d+\.\d+)\)',          # Anywhere: "(2.1)"
#             ]
#             for pattern in label_patterns:
#                 label_match = re.search(pattern, latex_clean)
#                 if label_match:
#                     equation_label = label_match.group(1)
#                     # Remove label from LaTeX for conversion
#                     latex_clean = re.sub(pattern, '', latex_clean).strip()
#                     # Clean up trailing commas and spaces
#                     latex_clean = re.sub(r',\s*$', '', latex_clean).strip()
#                     break
            
#             # Sanitize LaTeX before conversion
#             latex_clean = latex_clean.replace("\n", " ").replace("\r", " ")
#             latex_clean = " ".join(latex_clean.split())  # Normalize whitespace
            
#             # Convert LaTeX to MathML
#             result = latex2mathml_convert(latex_clean)

#             # Check for corrupted MathML patterns and attempt repair
#             if self._is_corrupted_mathml(result, latex_clean):
#                 logger.warning("Detected potentially corrupted MathML, attempting repair...")
#                 repaired_mathml, repaired_latex = self._repair_with_reconstructor(latex_clean)
#                 if repaired_mathml and not self._is_corrupted_mathml(repaired_mathml, repaired_latex or latex_clean):
#                     result = repaired_mathml
#                     latex_clean = repaired_latex or latex_clean
#                     logger.info("MathML repaired successfully")
            
#             # If the converter fell back to plain text (<mtext>) try one repair pass:
#             # rebuild LaTeX with the dynamic reconstructor and re-convert.
#             if "<mtext>" in result:
#                 repaired_mathml, repaired_latex = self._repair_with_reconstructor(latex_clean)
#                 if repaired_mathml:
#                     result = repaired_mathml
#                     latex_clean = repaired_latex or latex_clean

#             # Post-process to add Mathpix-like structure
#             result = self._enhance_mathml(result, equation_label)
            
#             # Normalize HTML entities in MathML for proper rendering
#             if ENTITY_UTILS_AVAILABLE:
#                 result = normalize_mathml_entities(result)
            
#             logger.debug("Converted LaTeX to MathML: %s -> %s", latex[:50], result[:100] if result else "EMPTY")
#             return result
#         except (ValueError, SyntaxError) as exc:
#             # These are parsing errors from latex2mathml
#             logger.warning("LaTeX parsing failed (invalid syntax): %s. LaTeX: %s", exc, latex[:100])
#             # Try a single repair with the dynamic reconstructor before falling back
#             latex_source = " ".join(latex.replace("\n", " ").split())
#             repaired_mathml, repaired_latex = self._repair_with_reconstructor(latex_source)
#             if repaired_mathml:
#                 logger.info("MathML rebuilt after initial parse failure")
#                 return self._enhance_mathml(repaired_mathml, locals().get("equation_label"))
#             # Fallback: return text as MathML
#             text_content = latex.replace("$", "").strip()
#             # Decode HTML entities if present, then escape for XML
#             if ENTITY_UTILS_AVAILABLE:
#                 text_content = decode_html_entities(text_content)
#                 text_content = escape_for_mathml(text_content)
#             else:
#                 # Basic XML escaping
#                 text_content = text_content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
#             return f'<math xmlns="http://www.w3.org/1998/Math/MathML"><mtext>{text_content}</mtext></math>'
#         except re.error as exc:
#             # Regex pattern errors (like "missing < at position 2")
#             logger.warning("LaTeX regex pattern error: %s. LaTeX: %s", exc, latex[:100])
#             # Fallback: return text as MathML
#             text_content = latex.replace("$", "").strip()
#             # Decode HTML entities if present, then escape for XML
#             if ENTITY_UTILS_AVAILABLE:
#                 text_content = decode_html_entities(text_content)
#                 text_content = escape_for_mathml(text_content)
#             else:
#                 # Basic XML escaping
#                 text_content = text_content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
#             return f'<math xmlns="http://www.w3.org/1998/Math/MathML"><mtext>{text_content}</mtext></math>'
#         except Exception as exc:  # noqa: BLE001
#             # Catch all other errors (including PatternError from latex2mathml internals)
#             error_msg = str(exc)
#             if "missing" in error_msg.lower() and "position" in error_msg.lower():
#                 # This is a regex pattern error from latex2mathml
#                 logger.warning("LaTeX regex pattern error (from latex2mathml): %s. LaTeX: %s", exc, latex[:100])
#             else:
#                 logger.exception("Unexpected conversion error: %s. LaTeX: %s", exc, latex[:100])
#             # Fallback: return text as MathML
#             text_content = latex.replace("$", "").strip()
#             # Decode HTML entities if present, then escape for XML
#             if ENTITY_UTILS_AVAILABLE:
#                 text_content = decode_html_entities(text_content)
#                 text_content = escape_for_mathml(text_content)
#             else:
#                 # Basic XML escaping
#                 text_content = text_content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
#             return f'<math xmlns="http://www.w3.org/1998/Math/MathML"><mtext>{text_content}</mtext></math>'
    
#     def _ensure_canonical_latex(self, latex: str) -> str:
#         """Ensure LaTeX is canonical before MathML conversion.
        
#         Detects corrupted LaTeX patterns (like \\f_r a_c, \\s_u m, \\l_e f_t) and
#         applies canonical reconstruction if the target equation is detected.
        
#         Args:
#             latex: Potentially corrupted LaTeX string
            
#         Returns:
#             Clean canonical LaTeX if equation detected, otherwise original LaTeX
#         """
#         # Check if LaTeX contains corrupted patterns that indicate the target equation
#         # Patterns like: \f_r a_c (corrupted \frac), \s_u m (corrupted \sum), etc.
#         corrupted_patterns = [
#             r'\\f\s*_\s*\{?r\}?\s*a\s*_\s*\{?c\}?',  # \f_r a_c (corrupted \frac)
#             r'\\f\s*_\s*\{r\}\s*a\s*_\s*\{c\}',  # \f_{r}a_{c} (with braces)
#             r'\\s\s*_\s*\{?u\}?\s*m',  # \s_u m (corrupted \sum)
#             r'\\s\s*_\s*\{u\}\s*m',  # \s_{u}m (with braces)
#             r'\\l\s*_\s*\{?e\}?\s*f\s*_\s*\{?t\}?',  # \l_e f_t (corrupted \left)
#             r'\\l\s*_\s*\{e\}\s*f\s*_\s*\{t\}',  # \l_{e}f_{t} (with braces)
#             r'c1n',  # c1n (corrupted \frac{1}{n})
#         ]
        
#         has_corrupted_pattern = any(re.search(pattern, latex, re.IGNORECASE) for pattern in corrupted_patterns)
        
#         # Also check for the specific patterns with direct string matching (faster and more reliable)
#         # These are the exact patterns we see in errors
#         direct_checks = [
#             r'\f_{r}',  # \f_{r}
#             r'\f_{r}a_{c}',  # \f_{r}a_{c}
#             r'\f_r',  # \f_r
#             r'\s_{u}',  # \s_{u}
#             r'\s_u',  # \s_u
#             r'\l_{e}',  # \l_{e}
#             r'\l_e',  # \l_e
#         ]
#         if any(check in latex for check in direct_checks):
#             has_corrupted_pattern = True
        
#         if has_corrupted_pattern:
#             # Safely encode Unicode for logging
#             try:
#                 latex_safe = latex[:100].encode('ascii', 'replace').decode('ascii')
#                 logger.info("Detected corrupted LaTeX patterns, applying canonical reconstruction. LaTeX: %s", latex_safe)
#             except Exception:  # noqa: BLE001
#                 logger.info("Detected corrupted LaTeX patterns, applying canonical reconstruction")
#             try:
#                 # Use dynamic reconstructor (works for any formula)
#                 from services.ocr.dynamic_latex_reconstructor import DynamicLaTeXReconstructor
#                 reconstructor = DynamicLaTeXReconstructor()
#                 reconstructed = reconstructor.reconstruct(latex)
#                 if reconstructed and reconstructed != latex:
#                     logger.info("Dynamic reconstruction applied before MathML conversion")
#                     return reconstructed
#             except ImportError:
#                 # Fallback to old reconstructor if dynamic one not available
#                 try:
#                     from services.ocr.latex_reconstructor import LaTeXReconstructor
#                     reconstructor = LaTeXReconstructor()
#                     canonical = reconstructor._canonical_reconstruction(latex)
#                     if canonical:
#                         logger.info("Canonical reconstruction applied before MathML conversion")
#                         return canonical
#                     reconstructed = reconstructor.reconstruct(latex)
#                     if reconstructed and reconstructed != latex:
#                         logger.info("Full reconstruction applied before MathML conversion")
#                         return reconstructed
#                 except Exception as exc:  # noqa: BLE001
#                     logger.warning("Reconstruction failed during MathML conversion: %s", exc)
#             except Exception as exc:  # noqa: BLE001
#                 logger.warning("Dynamic reconstruction failed during MathML conversion: %s", exc)
        
#         return latex

#     def _repair_common_ocr_errors(self, latex: str) -> str:
#         r"""Repair frequent OCR corruptions for math expressions before conversion.

#         Comprehensive OCR repair system that handles:
        
#         1. **Special Characters**: Unicode garbage, currency symbols, punctuation variants
#         2. **Greek Letters**: All Greek letters (α-ω, Α-Ω) mapped to LaTeX commands
#         3. **Mathematical Operators**: Set operations (∪, ∩, ∈), relations (≤, ≥, ≠), 
#            calculus (∑, ∫, ∂), logic (∧, ∨, →), and more
#         4. **LaTeX Command Corruptions**: Expanded patterns for \sum, \prod, \frac, 
#            \left/\right, \ldots, \sqrt, \int, \partial, \nabla, \infty, etc.
#         5. **Equation Templates**: Channel equations, probability-of-error, power constraints
#         6. **Noise Removal**: Stray digits, punctuation, parentheticals, trailing fragments
        
#         Targets patterns seen in diagram extractions where LaTeX is wrapped in <mtext>
#         and contains broken commands like \\s_{u}m, \\l_{d}o_{t}s, stray \\left, etc.
#         """
#         import re

#         repaired = latex

#         # Basic garbage character cleanup (smart quotes, copyright, question marks)
#         garbage_map = {
#             "“": "",
#             "”": "",
#             "‘": "",
#             "’": "",
#             "©": "",
#             "©": "",
#             "�": "",
#             "?": "",
#         }
#         for bad, good in garbage_map.items():
#             repaired = repaired.replace(bad, good)

#         # ===== COMPREHENSIVE SPECIAL CHARACTER MAPPINGS =====
        
#         # Greek letters: common OCR misreadings -> LaTeX
#         greek_map = {
#             "α": r"\alpha", "β": r"\beta", "γ": r"\gamma", "δ": r"\delta", "Δ": r"\Delta",
#             "ε": r"\epsilon", "θ": r"\theta", "Θ": r"\Theta", "λ": r"\lambda", "Λ": r"\Lambda",
#             "μ": r"\mu", "π": r"\pi", "Π": r"\Pi", "σ": r"\sigma", "Σ": r"\Sigma",
#             "φ": r"\phi", "Φ": r"\Phi", "ω": r"\omega", "Ω": r"\Omega",
#             "η": r"\eta", "ι": r"\iota", "κ": r"\kappa", "ν": r"\nu",
#             "ξ": r"\xi", "Ξ": r"\Xi", "ρ": r"\rho", "τ": r"\tau",
#             "υ": r"\upsilon", "Υ": r"\Upsilon", "χ": r"\chi", "ψ": r"\psi", "Ψ": r"\Psi", "ζ": r"\zeta",
#         }
#         for bad, good in greek_map.items():
#             repaired = repaired.replace(bad, good)

#         # Mathematical operators and symbols: OCR variants -> LaTeX
#         operator_map = {
#             "∪": r"\cup", "∩": r"\cap", "∈": r"\in", "∉": r"\notin",
#             "⊂": r"\subset", "⊃": r"\supset", "⊆": r"\subseteq", "⊇": r"\supseteq", "∅": r"\emptyset",
#             "≤": r"\leq", "≥": r"\geq", "≠": r"\neq", "≈": r"\approx",
#             "≡": r"\equiv", "≅": r"\cong", "∼": r"\sim", "∝": r"\propto",
#             "×": r"\times", "÷": r"\div", "±": r"\pm", "∓": r"\mp",
#             "⋅": r"\cdot", "∗": r"\ast",
#             "∑": r"\sum", "∏": r"\prod", "∫": r"\int", "∂": r"\partial",
#             "∇": r"\nabla", "∞": r"\infty",
#             "∧": r"\land", "∨": r"\lor", "¬": r"\neg",
#             "→": r"\to", "←": r"\leftarrow", "↔": r"\leftrightarrow",
#             "⇒": r"\Rightarrow", "⇐": r"\Leftarrow", "⇔": r"\Leftrightarrow",
#             "√": r"\sqrt", "∛": r"\sqrt[3]", "∜": r"\sqrt[4]",
#             "∠": r"\angle", "′": r"'", "″": r"''",
#             "ℵ": r"\aleph", "℘": r"\wp", "ℜ": r"\Re", "ℑ": r"\Im", "℧": r"\mho",
#         }
#         for bad, good in operator_map.items():
#             repaired = repaired.replace(bad, good)

#         # Probability-of-error template detection and snap to canonical
#         lowered_for_prob = repaired.lower()
#         prob_cues = [
#             "p_error",
#             "perror",
#             "p_e",
#             r"\p_r",
#             "pr[",
#             "pr(",
#             "pr{",
#             r"\cup",
#             "⋃",
#             "!=",
#             "≠",
#             "g_{i}",
#             "y_{a}",
#             "y_{d}",
#             "i=1",
#         ]
#         prob_hits = sum(1 for cue in prob_cues if cue in lowered_for_prob)
#         if prob_hits >= 3:
#             return self.PROB_ERROR_CANONICAL

#         # Expanded LaTeX command corruptions
#         expanded_latex_fixes = [
#             (r"\\s\s*u\s*m\b", r"\\sum"),  # sum without underscores
#             (r"\\p\s*r\s*o\s*d\b", r"\\prod"),  # prod without underscores
#             (r"\\f\s*r\s*a\s*c\b", r"\\frac"),  # frac without underscores
#             (r"\\s\s*q\s*r\s*t\b", r"\\sqrt"),  # sqrt variants
#             (r"\\i\s*n\s*t\b", r"\\int"),  # int variants
#             (r"\\p\s*a\s*r\s*t\s*i\s*a\s*l\b", r"\\partial"),  # partial variants
#             (r"\\n\s*a\s*b\s*l\s*a\b", r"\\nabla"),  # nabla variants
#             (r"\\i\s*n\s*f\s*t\s*y\b", r"\\infty"),  # infty variants
#         ]
#         for pattern, replacement in expanded_latex_fixes:
#             repaired = re.sub(pattern, replacement, repaired, flags=re.IGNORECASE)

#         # Detect the canonical power constraint shape and directly snap to the canonical LaTeX
#         # Pattern cues: r_v, y_0, y_{t-1}, sum-like corruption, fraction 1/n, power 2, and a trailing P
#         lowered = repaired.lower().replace(" ", "")
#         canonical_cues = [
#             "rv", "y0", "t-1",  # variables
#         ]
#         has_cues = all(cue in lowered for cue in canonical_cues)
#         has_sum_like = any(token in lowered for token in ("\\sum", "s_u", "s_{u}", "sum"))
#         has_frac_like = "1n" in lowered or "\\frac" in lowered or "frac{1}{n}" in lowered
#         has_power2 = "]^2" in repaired or "}^{2}" in repaired or "^{2}" in repaired
#         if has_cues and has_sum_like and has_frac_like and has_power2:
#             return (
#                 r"\frac{1}{n}\sum_{t=0}^{n-1}\left[ r_v^{(t)}\left( y_{0}, \ldots, y_{t-1} \right) \right]^2 \le P"
#             )

#         # Detect noisy channel equation and snap to canonical
#         channel_cues = [
#             "y_",
#             "x_",
#             "z_",
#             "l]",
#             "l_{e}",
#             "l_{d}",
#             "l_{l}",
#             "[e]",
#             "hag",
#             "so ",
#             "ss",
#             "sp",
#             "s_p",
#             "251",
#         ]
#         channel_hits = sum(1 for cue in channel_cues if cue in lowered)
#         if channel_hits >= 3:
#             return self.CHANNEL_CANONICAL

#         # Fix corrupted \sum variants: \s_{u}m, \s_u m, etc.
#         repaired = re.sub(r"\\s\s*_\s*\{?u\}?\s*m", r"\\sum", repaired, flags=re.IGNORECASE)
        
#         # Fix corrupted \bigcup: b_{i}g_{c}u_{p} -> \bigcup
#         repaired = re.sub(r"b\s*_\s*\{?i\}?\s*g\s*_\s*\{?c\}?\s*u\s*_\s*\{?p\}?", r"\\bigcup", repaired, flags=re.IGNORECASE)
        
#         # Fix corrupted \neq: n_{e}q -> \neq
#         repaired = re.sub(r"n\s*_\s*\{?e\}?\s*q\b", r"\\neq", repaired, flags=re.IGNORECASE)
        
#         # Fix escaped backslashes in commands (\\left -> \left, but preserve actual escaped backslashes)
#         # Only fix if it's a known command pattern
#         repaired = re.sub(r"\\\\(left|right|bigcup|sum|frac|neq|mathrm|mathbb|mathcal)", r"\\\1", repaired)

#         # Fix corrupted \ldots variants: \l_{d}o_{t}s
#         repaired = re.sub(r"\\l\s*_\s*\{?d\}?\s*o\s*_\s*\{?t\}?\s*s", r"\\ldots", repaired, flags=re.IGNORECASE)

#         # Normalize stray single-letter backslashes like \P or \U
#         repaired = re.sub(r"\\P\b", "P", repaired)
#         repaired = re.sub(r"\\U\b", r"\\cup", repaired)

#         # Fix corrupted \left / \right that were split into individual letters
#         repaired = re.sub(r"\\l\s*_\s*\{?e\}?\s*f\s*_\s*\{?t\}?", r"\\left", repaired, flags=re.IGNORECASE)
#         repaired = re.sub(r"\\l\s*e\s*f\s*t", r"\\left", repaired, flags=re.IGNORECASE)
#         repaired = re.sub(r"\\r\s*_\s*\{?i\}?\s*g\s*_\s*\{?h\}?\s*t", r"\\right", repaired, flags=re.IGNORECASE)
#         repaired = re.sub(r"\\r\s*i\s*g\s*h\s*t", r"\\right", repaired, flags=re.IGNORECASE)

#         # Collapse duplicated fence modifiers (\\left\\left -> \\left)
#         repaired = re.sub(r"\\left\\left", r"\\left", repaired)
#         repaired = re.sub(r"\\right\\right", r"\\right", repaired)
        
#         # Fix letter-by-letter subscript patterns (e.g., m_{a}t_{h}r_{m} -> \mathrm{math})
#         # This handles OCR corruption where words are split into individual letter subscripts
#         def collapse_letter_by_letter_pattern(match: re.Match) -> str:
#             r"""Collapse letter-by-letter subscript sequences into \mathrm{word}."""
#             seq = match.group(1)
#             # Extract letter-subscript pairs
#             pairs = re.findall(r'([a-zA-Z])_\{([a-zA-Z])\}', seq)
#             if not pairs:
#                 return seq
            
#             base_letters = ''.join(a for a, b in pairs)
#             sub_letters = ''.join(b for a, b in pairs)
#             candidate = base_letters + sub_letters
            
#             # If candidate forms a plausible word (length >= 3), replace with \mathrm
#             if len(candidate) >= 3:
#                 return r"\mathrm{" + candidate + r"}"
#             return seq
        
#         # Find and collapse letter-by-letter patterns (2+ consecutive letter-subscript pairs)
#         letter_pattern = re.compile(r'((?:[a-zA-Z]_\{[a-zA-Z]\}){2,})')
#         repaired = letter_pattern.sub(collapse_letter_by_letter_pattern, repaired)
        
#         # Also handle patterns where the word is in subscripts (e.g., P_{m_{a}t_{h}r_{m}})
#         # This handles cases like P_error where "error" is corrupted as m_{a}t_{h}r_{m}
#         # Pattern: P_{m_{a}t_{h}r_{m}} -> P_{\mathrm{math}}
#         # Note: This pattern matches the closing brace, so it handles complete subscript groups
#         subscript_word_pattern = re.compile(r'([A-Za-z])_\{((?:[a-zA-Z]_\{[a-zA-Z]\}){2,})\}')
#         def fix_subscript_word(match: re.Match) -> str:
#             """Fix subscript words that are letter-by-letter."""
#             base = match.group(1)
#             subscript_seq = match.group(2)
#             pairs = re.findall(r'([a-zA-Z])_\{([a-zA-Z])\}', subscript_seq)
#             if pairs:
#                 base_letters = ''.join(a for a, b in pairs)
#                 sub_letters = ''.join(b for a, b in pairs)
#                 candidate = base_letters + sub_letters
#                 if len(candidate) >= 3:
#                     return f"{base}_{{\\mathrm{{{candidate}}}}}}}"
#             return match.group(0)
#         repaired = subscript_word_pattern.sub(fix_subscript_word, repaired)
        
#         # Fix empty bracket patterns: [ ] -> [0] or remove if context suggests
#         repaired = re.sub(r'\[\s*\]', r'[0]', repaired)
        
#         # Fix patterns like Y_{d_{i}}[ ] -> Y_{d_i}[0]
#         # This handles cases where subscripts are nested but valid, but brackets are empty
#         repaired = re.sub(r'(\w+)_\{(\w+)_\{(\w+)\}\}\[\s*\]', r'\1_{\2_\3}[0]', repaired)

#         # Convert stray single-letter backslashed tokens (e.g., \P_r) to plain letters
#         repaired = re.sub(r"\\([A-Za-z])\s*_\s*\{?([A-Za-z0-9]+)\}?", r"\1_{\2}", repaired)
#         repaired = re.sub(r"\\([A-Za-z])\b", r"\1", repaired)

#         # Resolve double-underscore patterns that trigger DoubleSubscriptsError
#         # Examples: "_ -" -> "-", "_," -> ",", "_ )" -> ")"
#         repaired = re.sub(r"_\s*([-+*/=),])", r"\1", repaired)
#         # Remove repeated underscores in a row
#         repaired = re.sub(r"__+", r"_", repaired)

#         # Drop obvious punctuation noise like stray semicolons/colons between symbols
#         repaired = re.sub(r"(?<=\b[A-Za-z0-9}_])\s*[;:]+\s*", " ", repaired)

#         # Remove isolated digits between identifiers (e.g., W_{i} 4 g_{i} -> W_{i} g_{i})
#         repaired = re.sub(r"(?<=\b[A-Za-z}_])\s+\d+\s+(?=[A-Za-z\\])", " ", repaired)

#         # Channel equation OCR cleanup: l_{e}] / l_{d}] / l_{l}] or [e] -> [t]
#         repaired = re.sub(r"l\s*_\s*\{?e\}?\s*\]", r"[t]", repaired, flags=re.IGNORECASE)
#         repaired = re.sub(r"l\s*_\s*\{?d\}?\s*\]", r"[t]", repaired, flags=re.IGNORECASE)
#         repaired = re.sub(r"l\s*_\s*\{?l\}?\s*\]", r"[t]", repaired, flags=re.IGNORECASE)
#         repaired = re.sub(r"\[\s*e\s*\]", r"[t]", repaired, flags=re.IGNORECASE)
#         repaired = re.sub(r"y\s*\]", r"[t]", repaired, flags=re.IGNORECASE)
#         repaired = re.sub(r"l\]", r"[t]", repaired, flags=re.IGNORECASE)
#         # Drop stray semicolons/commas near brackets
#         repaired = re.sub(r";\s*\[", "[", repaired)
#         # Remove trailing noise like "4T (7" or standalone "(7"
#         repaired = re.sub(r"\b\d+\s*T\s*\(\d+\)", "", repaired)
#         repaired = re.sub(r"\(\d+\)\s*$", "", repaired)
#         repaired = re.sub(r"#\s*\d+\s*\(\d+\)", "", repaired)
#         repaired = re.sub(r"\b\d+\s*d\)", "", repaired)

#         # General noise for non-channel OCR: remove "(R:" fragments and trailing i=l
#         repaired = re.sub(r"\(R\s*[:;]\s*", "R ", repaired, flags=re.IGNORECASE)
#         repaired = re.sub(r"\(\s*R\b", "R ", repaired, flags=re.IGNORECASE)
#         repaired = re.sub(r"\bi\s*=\s*l\b", "", repaired, flags=re.IGNORECASE)
#         # Drop parenthetical R_* blocks and stray integers/questions
#         repaired = re.sub(r"\(R[^)]*\)", " ", repaired, flags=re.IGNORECASE)
#         repaired = re.sub(r"\b\d+\b", " ", repaired)
#         repaired = re.sub(r"\s+n\s+", " ", repaired)
#         repaired = repaired.replace("?", "")

#         # Fix corrupted \left ... \right pairs that degraded to "\left P" (should be \le P or plain P)
#         repaired = re.sub(r"\\left\s+P", r"\\le P", repaired, flags=re.IGNORECASE)

#         # Remove lone \left or \right without companions to avoid parser errors
#         # If there's a \left[...] without \right, drop the modifier but keep the bracket
#         repaired = re.sub(r"\\left\s*(\(|\[|\{)", r"\1", repaired)
#         repaired = re.sub(r"\\right\s*(\)|\]|\})", r"\1", repaired)

#         # Balance obvious missing closing brackets if the structure suggests [ ... ]^2
#         # If we have \left[ ... ]^2 without \right], replace trailing "]" with "\right]"
#         repaired = re.sub(r"\\left\[\s*(.*?)\s\]", r"\\left[ \1 \\right]", repaired)

#         # Normalize commas between arguments inside parentheses if corrupted spacing removed them
#         repaired = re.sub(r"\(\s*([a-zA-Z0-9_]+)\s+\\ldots\s+([a-zA-Z0-9_]+)\s*\)", r"( \1, \\ldots, \2 )", repaired)

#         return repaired

#     # --- Probability-of-error template detection/repair ---

#     PROB_ERROR_CANONICAL = (
#         r"P_{\text{error}}(C)=\Pr\!\left[\bigcup_{i=1}^{K}"
#         r"\left\{W_i \ne g_i\!\left(Y_{d_i}[0],\,\ldots,\,Y_{d_i}[n-1]\right)\right\}\right]"
#     )

#     CHANNEL_CANONICAL = (
#         r"Y_{j}[t]=\sum_{i\in I(j)} h_{i,j}[t] X_{i}[t] + Z_{j}[t]"
#     )

#     def detect_probability_of_error(self, latex: str) -> dict | None:
#         """Detect and repair probability-of-error equations from corrupted OCR.

#         Returns JSON-like dict per template when detected, else None.
#         """
#         normalized = latex.lower()
#         cues = [
#             "p_error",
#             "perr",
#             "p_e",
#             r"\p_r",
#             "pr[",
#             "pr(",
#             "pr{",
#             "⋃",
#             r"\cup",
#             "!=",
#             "≠",
#             "w_i",
#             "g_i",
#             "y_{d",
#             "y_a",
#         ]
#         cue_hits = sum(1 for c in cues if c in normalized)
#         if cue_hits == 0:
#             return None

#         fixed = latex
#         substitutions = [
#             (r"\\?P\s*r\s*\[", r"Pr["),
#             (r"\\?P\s*r\s*\(", r"Pr("),
#             (r"\\?P\s*r\s*\{", r"Pr{"),
#             (r"\\P_r", r"Pr"),
#             (r"left\s*\{", r"{"),
#             (r"l\s*e\s*f\s*t\s*\{", r"{"),
#             (r"right\s*\}", r"}"),
#             (r"r\s*i\s*g\s*h\s*t\s*\}", r"}"),
#             (r"W[\s;,_]+i", r"W_i"),
#             (r"W\s*;\s*i", r"W_i"),
#             (r"g[\s;,_]+i\s*\(", r"g_i("),
#             (r"Y\s*a", r"Y_{d_i}"),
#             (r"Y_{a}", r"Y_{d_i}"),
#             (r"Y\:\s*a", r"Y_{d_i}"),
#             (r"#", r""),
#             (r";", r","),
#         ]
#         for pattern, repl in substitutions:
#             fixed = re.sub(pattern, repl, fixed, flags=re.IGNORECASE)

#         # Ensure union and inequality present
#         if r"\cup" not in fixed and "⋃" not in fixed:
#             fixed = fixed.replace(r"\left\{", r"\cup \left\{", 1) if r"\left\{" in fixed else r"\cup " + fixed
#         if r"\ne" not in fixed and "!=" in fixed:
#             fixed = fixed.replace("!=", r"\ne")
#         if r"\ne" not in fixed and r"\neq" not in fixed:
#             fixed = fixed.replace("=", r"\ne", 1) if "=" in fixed else fixed + r" \ne "

#         fixed_latex = self.PROB_ERROR_CANONICAL
#         confidence = min(1.0, 0.5 + 0.05 * cue_hits)
#         return {
#             "fixed_latex": fixed_latex,
#             "detected_template": "probability_of_error",
#             "confidence": round(confidence, 2),
#             "explanation": "OCR repaired and matched probability-of-error template.",
#         }

#     def _repair_with_reconstructor(self, latex_source: str) -> tuple[str | None, str | None]:
#         """Try to repair corrupted LaTeX using the dynamic reconstructor.

#         Returns a tuple of (mathml, repaired_latex). mathml is None when no repair succeeded.
#         """
#         try:
#             math_tokens = ("\\frac", "\\sum", "\\left", "\\right", "^", "_", "\\le", "\\ge", "\\cdot", "\\ldots")
#             if not any(token in latex_source for token in math_tokens):
#                 return None, None

#             from services.ocr.dynamic_latex_reconstructor import DynamicLaTeXReconstructor

#             reconstructor = DynamicLaTeXReconstructor()
#             repaired_latex = reconstructor.reconstruct(latex_source)
#             if repaired_latex and repaired_latex != latex_source:
#                 repaired_mathml = latex2mathml_convert(repaired_latex)
#                 return repaired_mathml, repaired_latex
#         except Exception as exc:  # noqa: BLE001
#             logger.debug("Repair pass failed: %s", exc)

#         return None, None
    
#     def _is_corrupted_mathml(self, mathml: str, original_latex: str) -> bool:
#         """Detect if MathML appears corrupted based on common corruption patterns.
        
#         Checks for:
#         - Missing opening brackets (e.g., Y_i] instead of Y_i[t])
#         - Garbled subscripts (e.g., D_Ohigl instead of sum)
#         - Suspicious operator sequences
#         - Structural inconsistencies
#         """
#         if not mathml or not original_latex:
#             return False
        
#         # Check for common corruption patterns
#         corruption_patterns = [
#             # Missing opening brackets
#             r'<mo stretchy="false">\]</mo>',  # Closing bracket without opening
#             # Garbled subscripts (like D_Ohigl, gigl_xs_ie)
#             r'<mi>[D-Z]</mi>.*?<msub>.*?<mi>[O-Z]</mi>',  # Suspicious capital letter subscripts
#             # Suspicious operator sequences
#             r'<mo stretchy="false">\)</mo>\s*<mo>,</mo>',  # Closing paren followed by comma
#             r'<mo stretchy="false">\(</mo>\s*<mo stretchy="false">\)</mo>',  # Empty parentheses
#         ]
        
#         for pattern in corruption_patterns:
#             if re.search(pattern, mathml):
#                 return True
        
#         # Check if MathML structure doesn't match LaTeX intent
#         # If LaTeX has sum but MathML doesn't
#         if r'\sum' in original_latex and '<mo>∑</mo>' not in mathml and 'sum' not in mathml.lower():
#             # Check if there are suspicious capital letters that might be corrupted sum
#             if re.search(r'<mi>[D-Z]</mi>.*?<msub>', mathml):
#                 return True
        
#         # Check for missing opening brackets when LaTeX has brackets
#         if '[' in original_latex and ']' in original_latex:
#             # Count brackets in LaTeX
#             open_brackets = original_latex.count('[')
#             close_brackets = original_latex.count(']')
#             # Count in MathML (approximate - looking for bracket operators)
#             mathml_open = mathml.count('<mo stretchy="false">[</mo>') + mathml.count('<mo>[</mo>')
#             mathml_close = mathml.count('<mo stretchy="false">]</mo>') + mathml.count('<mo>]</mo>')
            
#             # If we have closing brackets but significantly fewer opening brackets
#             if mathml_close > 0 and mathml_open < mathml_close - 1:
#                 return True
        
#         return False
    
#     def _enhance_mathml(self, mathml: str, equation_label: str | None = None) -> str:
#         """Enhance MathML to match Mathpix format with display block and equation labels.
        
#         Produces format like:
#         <math xmlns="http://www.w3.org/1998/Math/MathML" display="block">
#           <mtable displaystyle="true">
#             <mlabeledtr>
#               <mtd id="mjx-eqn:2.1">
#                 <mtext>(2.1)</mtext>
#               </mtd>
#               <mtd>
#                 <!-- formula content -->
#               </mtd>
#             </mlabeledtr>
#           </mtable>
#         </math>
#         """
#         try:
#             # Parse the MathML
#             root = ET.fromstring(mathml)
            
#             # Add display="block" attribute to math element
#             root.set("display", "block")
            
#             # If there's an equation label, wrap in mtable with mlabeledtr
#             if equation_label:
#                 # Create mtable structure like Mathpix
#                 mtable = ET.Element("mtable", displaystyle="true")
#                 mlabeledtr = ET.SubElement(mtable, "mlabeledtr")
                
#                 # Add label cell with proper ID
#                 mtd_label = ET.SubElement(mlabeledtr, "mtd", id=f"mjx-eqn:{equation_label}")
#                 mtext_label = ET.SubElement(mtd_label, "mtext")
#                 mtext_label.text = f"({equation_label})"
                
#                 # Add equation content cell
#                 mtd_content = ET.SubElement(mlabeledtr, "mtd")
                
#                 # Move all children from root to mtd_content
#                 for child in list(root):
#                     mtd_content.append(child)
                
#                 # Replace root's children with mtable
#                 root.clear()
#                 root.append(mtable)
            
#             # Convert back to string with proper formatting
#             try:
#                 ET.indent(root, space="  ")  # Python 3.9+
#             except AttributeError:
#                 pass  # Older Python versions - no indent method
            
#             # Generate XML string with proper formatting
#             mathml_str = ET.tostring(root, encoding="unicode", method="xml")
            
#             # Ensure proper namespace (always add it)
#             if 'xmlns="http://www.w3.org/1998/Math/MathML"' not in mathml_str:
#                 mathml_str = mathml_str.replace('<math', '<math xmlns="http://www.w3.org/1998/Math/MathML"')
            
#             # Normalize HTML entities in the final MathML
#             if ENTITY_UTILS_AVAILABLE:
#                 mathml_str = normalize_mathml_entities(mathml_str)
            
#             return mathml_str
            
#         except ET.ParseError as exc:
#             logger.warning("Failed to parse MathML for enhancement: %s", exc)
#             # Return original with display="block" added manually
#             if 'display="block"' not in mathml:
#                 mathml = mathml.replace('<math', '<math display="block"')
#             return mathml
#         except Exception as exc:  # noqa: BLE001
#             logger.warning("Failed to enhance MathML: %s", exc)
#             # Return original with display="block" added manually
#             if 'display="block"' not in mathml:
#                 mathml = mathml.replace('<math', '<math display="block"')
#             return mathml

