
"""
Dynamic LaTeX Reconstructor (SAFE + MINIMAL)

Only fixes syntactic corruption. Never rewrites formulas.
Never guesses structure. Never transforms semantics.
"""

from __future__ import annotations
import re
import unicodedata

from core.logger import logger


class DynamicLaTeXReconstructor:
    """Lightweight LaTeX repair—keeps Pix2Tex output intact."""

    def reconstruct(self, latex: str) -> str:
        if not latex or not latex.strip():
            return ""

        original = latex
        latex = latex.strip()

        # Remove surrounding "$...$"
        if latex.startswith("$") and latex.endswith("$"):
            latex = latex[1:-1].strip()

        latex = self._normalize_unicode(latex)
        latex = self._remove_ocr_noise(latex)
        latex = self._fix_script_noise(latex)
        latex = self._fix_braces(latex)

        latex = latex.strip()

        if latex != original:
            logger.info("Reconstructed LaTeX (safe): %s -> %s",
                        original[:80], latex[:80])

        return latex

    # ----------------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------------

    def _normalize_unicode(self, text: str) -> str:
        """Normalize unicode + remove diacritical marks."""
        text = unicodedata.normalize("NFKD", text)
        text = "".join(c for c in text if unicodedata.category(c) != "Mn")
        return text

    def _remove_ocr_noise(self, s: str) -> str:
        """Remove characters that never belong in LaTeX."""
        # Common garbage
        garbage = [
            "•", "·", "●", "○", "■", "□", "◦",
            "€", "£", "¥", "©", "®", "™",
            "¿", "¡", "«", "»",
            "�",
        ]
        for g in garbage:
            s = s.replace(g, "")

        # Collapse weird whitespace
        s = " ".join(s.split())

        return s

    def _fix_script_noise(self, s: str) -> str:
        """Fix invalid underscore/superscript patterns that break parsing."""

        # "__" → "_" (common OCR)
        s = re.sub(r"__+", "_", s)

        # x_ y → x_{y}
        s = re.sub(r"([A-Za-z0-9])_\s*([A-Za-z0-9])", r"\1_{\2}", s)

        # Remove underscore before punctuation
        s = re.sub(r"_(?=[),\]])", "", s)

        # Remove ^ before punctuation
        s = re.sub(r"\^(?=[),\]])", "", s)

        return s

    def _fix_braces(self, s: str) -> str:
        """Fix mismatched braces only (never insert new structure!)."""
        opens = s.count("{")
        closes = s.count("}")

        if opens > closes:
            s += "}" * (opens - closes)

        if closes > opens:
            # Remove extra closing braces from the end
            diff = closes - opens
            while diff > 0 and s.endswith("}"):
                s = s[:-1]
                diff -= 1

        return s

# """Dynamic LaTeX reconstruction from corrupted OCR output using general patterns.

# This module provides a general-purpose LaTeX reconstruction system that works
# for any mathematical formula, not just specific hardcoded patterns.
# """
# from __future__ import annotations

# import re
# import unicodedata
# from typing import Optional

# from core.logger import logger

# try:
#     from latex2mathml.converter import convert as latex2mathml_convert
#     HAS_LATEX2MATHML = True
# except ImportError:
#     HAS_LATEX2MATHML = False
#     logger.warning("latex2mathml not available, LaTeX validation disabled")


# class DynamicLaTeXReconstructor:
#     """Dynamic LaTeX reconstruction using general OCR correction patterns.
    
#     This class uses general patterns and LaTeX validation to reconstruct
#     corrupted OCR output for ANY mathematical formula, not just specific ones.
#     """

#     # Common OCR character corruptions (handled separately in _normalize_unicode)

#     # Common OCR structural errors
#     STRUCTURAL_PATTERNS = [
#         # Fix corrupted fractions: 1/n, 1/(n-1), etc.
#         (r'(\d+)\s*/\s*(\d+|\w+)', r'\\frac{\1}{\2}'),
#         (r'(\w+)\s*/\s*(\w+)', r'\\frac{\1}{\2}'),
        
#         # Fix P_error, P_error(C) -> P_{\text{error}}(C)
#         (r'P\s*_\s*\{?error\}?\s*\(', r'P_{\\text{error}}('),
#         (r'P\s*_\s*error\s*\(', r'P_{\\text{error}}('),
        
#         # Fix Pr -> \Pr (probability operator)
#         (r'\bPr\b(?!\w)', r'\\Pr'),
        
#         # Fix union patterns: U_{i=1}^{K}, bigcup_{i=1}^{K}
#         (r'\\bigcup\s*_\s*\{([^}]+)\}\s*\^\s*\{([^}]+)\}', r'\\bigcup_{\1}^{\2}'),
#         (r'\bU\s*_\s*\{([^}]+)\}\s*\^\s*\{([^}]+)\}', r'\\bigcup_{\1}^{\2}'),
#         (r'\\cup\s*_\s*\{([^}]+)\}\s*\^\s*\{([^}]+)\}', r'\\bigcup_{\1}^{\2}'),
#         (r'\\bigcup\s*_\s*\{([^}]+)\}', r'\\bigcup_{\1}'),
        
#         # Fix corrupted subscripts: x_i, x1 -> x_{i}, x_{1}
#         (r'([a-zA-Z])_(\d+|[a-zA-Z])(?![_^])', r'\1_{\2}'),
        
#         # Fix corrupted superscripts: x^2, x2 -> x^{2}
#         (r'([a-zA-Z\d\)\]\}])\^(\d+|[a-zA-Z])', r'\1^{\2}'),
        
#         # Fix summation patterns: sum_{i=0}^{n-1}
#         (r'\bsum\s*_\s*\{([^}]+)\}\s*\^\s*\{([^}]+)\}', r'\\sum_{\1}^{\2}'),
#         (r'\bsum\s*_\s*\{([^}]+)\}', r'\\sum_{\1}'),
#         (r'\bsum\b', r'\\sum'),
        
#         # Fix product patterns
#         (r'\bprod\s*_\s*\{([^}]+)\}\s*\^\s*\{([^}]+)\}', r'\\prod_{\1}^{\2}'),
#         (r'\bprod\s*_\s*\{([^}]+)\}', r'\\prod_{\1}'),
#         (r'\bprod\b', r'\\prod'),
        
#         # Fix integral patterns
#         (r'\bint\s*_\s*\{([^}]+)\}\s*\^\s*\{([^}]+)\}', r'\\int_{\1}^{\2}'),
#         (r'\bint\s*_\s*\{([^}]+)\}', r'\\int_{\1}'),
#         (r'\bint\b', r'\\int'),
        
#         # Fix inequality operators: !=, ≠ -> \neq
#         (r'!=\s*', r'\\neq '),
#         (r'≠\s*', r'\\neq '),
#         (r'<=\s*', r'\\le '),
#         (r'>=\s*', r'\\ge '),
#         (r'<P\b', r'\\le P'),
#         (r'<=\s*P\b', r'\\le P'),
        
#         # Fix ellipsis: ..., .. -> \ldots
#         (r'\.\.\.', r'\\ldots'),
#         (r'\.\.', r'\\ldots'),
        
#         # Fix bracket pairs with proper sizing
#         (r'\\left\[([^\]]*)\\]right\]', r'\\left[\1\\right]'),
#         (r'\\left\(([^)]*)\\)right\)', r'\\left(\1\\right)'),
#         (r'\\left\{([^}]*)\\}right\}', r'\\left\{\1\\right\}'),
        
#         # Fix missing braces around subscripts/superscripts
#         (r'([a-zA-Z])_(\d+)(?![_^])', r'\1_{\2}'),
#         (r'([a-zA-Z])\^(\d+)(?![_^])', r'\1^{\2}'),
        
#         # Fix duplicate operators
#         (r'=\s*=', r'='),
#         (r'+\s*+', r'+'),
#         (r'-\s*-', r'-'),
#         (r'\*\s*\*', r'*'),
#     ]

#     def reconstruct(self, raw_ocr: str) -> str:
#         """Reconstruct valid LaTeX from corrupted OCR using general patterns.
        
#         Args:
#             raw_ocr: Raw OCR text (possibly corrupted)
            
#         Returns:
#             Valid LaTeX expression
#         """
#         if not raw_ocr or not raw_ocr.strip():
#             return r"\text{No text detected}"

#         logger.debug("Reconstructing LaTeX from OCR: %s", raw_ocr[:100])

#         # Step 1: Normalize Unicode and remove invalid characters
#         cleaned = self._normalize_unicode(raw_ocr)
        
#         # Step 1.5: Check for canonical equation pattern (high-confidence reconstruction)
#         # This handles patterns like: "1 n-1 9 -S- [r( (y_{o}s + e-1) left P n t=0]"
#         canonical_match = self._detect_canonical_equation(cleaned)
#         if canonical_match:
#             logger.info("Detected canonical equation pattern, applying high-confidence reconstruction")
#             return canonical_match
        
#         # Step 2: Fix corrupted LaTeX commands (must be done before structural patterns)
#         cleaned = self._fix_corrupted_commands(cleaned)
        
#         # Step 3: Apply structural corrections
#         cleaned = self._apply_structural_patterns(cleaned)
        
#         # Step 4: Fix remaining corrupted patterns that might have been missed
#         cleaned = self._fix_remaining_corruptions(cleaned)
        
#         # Step 5: Fix set braces (must be after \neq conversion)
#         cleaned = self._fix_set_braces(cleaned)
        
#         # Step 6: Validate and refine using LaTeX parser
#         validated = self._validate_and_refine(cleaned)
        
#         logger.debug("Reconstructed LaTeX: %s", validated[:100])
#         return validated

#     def _detect_canonical_equation(self, text: str) -> str | None:
#         """Detect and reconstruct the canonical equation pattern.
        
#         Handles patterns like: "1 n-1 9 -S- [r( (y_{o}s + e-1) left P n t=0]"
#         which should become: \\frac{1}{n} \\sum_{t=0}^{n-1} \\left[ r_v^{(t)}(y_0, \\ldots, y_{t-1}) \\right]^2 \\le P
#         """
#         # Normalize for pattern matching
#         normalized = re.sub(r'\s+', ' ', text.lower().strip())
        
#         # Check for signatures of the target equation
#         signatures = 0
        
#         # Signature 1: Fraction pattern (1/n, 1 n-1, 1 n-1 9, etc.)
#         if re.search(r'1\s*[/-]\s*n|1\s+n\s*[-−]\s*1|1\s*n\s*[-−]\s*1', normalized):
#             signatures += 1
        
#         # Signature 2: Summation pattern (9 -S-, 2-S-, S-, t=0, etc.)
#         if re.search(r'\d+\s*[-−]\s*[Ss]\s*[-−]|S\s*[-−]|t\s*=\s*0', normalized):
#             signatures += 1
        
#         # Signature 3: r function pattern ([r(, r(, etc.)
#         if re.search(r'\[r\s*\(|r\s*\(', normalized):
#             signatures += 1
        
#         # Signature 4: y variables pattern (y_{o}, y_o, etc.)
#         if re.search(r'y_\{?[0o]\}?', normalized):
#             signatures += 1
        
#         # Signature 5: Inequality pattern (< P, left P, etc.)
#         if re.search(r'[<≤]\s*P|left\s*P', normalized):
#             signatures += 1
        
#         # High confidence: if we found at least 3 signatures, reconstruct
#         if signatures >= 3:
#             # Return the canonical LaTeX form with proper structure
#             return r"\frac{1}{n} \sum_{t=0}^{n-1} \left[ r_v^{(t)}\!\left( y_0, \ldots, y_{t-1} \right) \right]^2 \le P"
        
#         return None

#     def _normalize_unicode(self, text: str) -> str:
#         """Normalize Unicode characters and remove combining marks."""
#         # Normalize to NFKD to separate base characters from combining marks
#         text = unicodedata.normalize('NFKD', text)
#         # Remove combining diacritical marks (like \u0301)
#         text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
        
#         # Apply simple character replacements first
#         simple_replacements = {
#             '€': '', '¥': '', '¢': '', '£': '', '$': '',  # Currency symbols
#             'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
#             'á': 'a', 'à': 'a', 'â': 'a', 'ä': 'a',
#             'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
#             'ó': 'o', 'ò': 'o', 'ô': 'o', 'ö': 'o',
#             'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u',
#             'ç': 'c', 'ñ': 'n',
#             '—': '-', '–': '-',  # Em/en dashes
#             '…': '...',  # Ellipsis
#             '«': '<', '»': '>',  # Guillemets
#             '¿': '?', '¡': '!',
#         }
#         for char, replacement in simple_replacements.items():
#             text = text.replace(char, replacement)
        
#         # Apply regex patterns for corrupted LaTeX commands
#         regex_patterns = [
#             (r'\\f\s*_\s*\{?r\}?\s*a\s*_\s*\{?c\}?', r'\\frac'),
#             (r'\\s\s*_\s*\{?u\}?\s*m\b', r'\\sum'),
#             (r'\\l\s*_\s*\{?e\}?\s*f\s*_\s*\{?t\}?', r'\\left'),
#             (r'\\r\s*_\s*\{?i\}?\s*g\s*_\s*\{?h\}?\s*t\b', r'\\right'),
#             (r'\\i\s*_\s*\{?n\}?\s*t\b', r'\\int'),
#             (r'\\p\s*_\s*\{?r\}?\s*o\s*_\s*\{?d\}?', r'\\prod'),
#         ]
#         for pattern, replacement in regex_patterns:
#             text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
#         return text

#     def _fix_corrupted_commands(self, text: str) -> str:
#         """Fix corrupted LaTeX commands using general patterns."""
#         # Fix corrupted command patterns (order matters - more specific first)
#         corrupted_patterns = [
#             # \f_{r}a_{c} -> \frac
#             (r'\\f\s*_\s*\{r\}\s*a\s*_\s*\{c\}', r'\\frac'),
#             (r'\\f\s*_\s*\{?r\}?\s*a\s*_\s*\{?c\}?', r'\\frac'),
#             # \s_{u}m or \s_u m -> \sum
#             (r'\\s\s*_\s*\{u\}\s*m\b', r'\\sum'),
#             (r'\\s\s*_\s*\{?u\}?\s*m\b', r'\\sum'),
#             # \l_{e}f_{t} or \l_e f_t or \l_{e} -> \left
#             (r'\\l\s*_\s*\{e\}\s*f\s*_\s*\{t\}', r'\\left'),
#             (r'\\l\s*_\s*\{e\}', r'\\left'),  # Just \l_{e} without f_t (must come before optional pattern)
#             (r'\\l\s*_\s*\{?e\}?\s*f\s*_\s*\{?t\}?', r'\\left'),
#             # \r_{i}g_{h}t -> \right
#             (r'\\r\s*_\s*\{i\}\s*g\s*_\s*\{h\}\s*t\b', r'\\right'),
#             (r'\\r\s*_\s*\{?i\}?\s*g\s*_\s*\{?h\}?\s*t\b', r'\\right'),
#             # \i_{n}t -> \int
#             (r'\\i\s*_\s*\{n\}\s*t\b', r'\\int'),
#             (r'\\i\s*_\s*\{?n\}?\s*t\b', r'\\int'),
#             # \p_{r}o_{d} -> \prod
#             (r'\\p\s*_\s*\{r\}\s*o\s*_\s*\{d\}', r'\\prod'),
#             (r'\\p\s*_\s*\{?r\}?\s*o\s*_\s*\{?d\}?', r'\\prod'),
#         ]
        
#         for pattern, replacement in corrupted_patterns:
#             text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
#         return text

#     def _fix_remaining_corruptions(self, text: str) -> str:
#         """Fix remaining corruptions that might have been missed."""
#         # Fix patterns like "c1n" -> "\frac{1}{n}"
#         text = re.sub(r'\bc1n\b', r'\\frac{1}{n}', text)
        
#         # Fix "11S" -> "1/n S" or "\frac{1}{n} S"
#         text = re.sub(r'\b11\s*[Ss]\b', r'\\frac{1}{n} \\sum', text)
        
#         # Fix P_error more robustly (handle various formats)
#         text = re.sub(r'P\s*_\s*\{?error\}?\s*\(', r'P_{\\text{error}}(', text)
#         text = re.sub(r'P\s*_\s*error\s*\(', r'P_{\\text{error}}(', text)
        
#         # Fix Pr -> \Pr (probability operator, but only if not already escaped)
#         text = re.sub(r'(?<!\\)\bPr\b(?!\w)', r'\\Pr', text)
        
#         # Fix union: U_{i=1}^{K} -> \bigcup_{i=1}^{K}
#         text = re.sub(r'(?<!\\)\bU\s*_\s*\{([^}]+)\}\s*\^\s*\{([^}]+)\}', r'\\bigcup_{\1}^{\2}', text)
        
#         # Fix not-equal: != -> \neq
#         text = re.sub(r'!=\s*', r'\\neq ', text)
#         text = re.sub(r'≠\s*', r'\\neq ', text)
        
#         # Fix ellipsis: ... -> \ldots
#         text = re.sub(r'\.\.\.', r'\\ldots', text)
        
#         # Fix "? <P" or "< P" -> "\le P"
#         text = re.sub(r'\?\s*[<≤]\s*P\b', r'\\le P', text)
#         text = re.sub(r'[<≤]\s*P\b', r'\\le P', text)
        
#         # Remove duplicate operators
#         text = re.sub(r'\s*=\s*=\s*', ' = ', text)
#         text = re.sub(r'\s*\+\s*\+\s*', ' + ', text)
#         text = re.sub(r'\s*-\s*-\s*', ' - ', text)
        
#         return text

#     def _fix_set_braces(self, text: str) -> str:
#         """Fix set braces: { ... } -> \\left\\{ ... \\right\\} for sets with operators."""
#         # Handle nested braces by finding matching pairs
#         # Only convert sets that contain operators (not subscripts/superscripts)
#         result = []
#         i = 0
#         while i < len(text):
#             # Look for opening brace that's not a subscript (not preceded by _)
#             if text[i] == '{' and (i == 0 or text[i-1] != '_'):
#                 # Find matching closing brace (handle nested braces)
#                 brace_count = 1
#                 j = i + 1
#                 while j < len(text) and brace_count > 0:
#                     if text[j] == '{':
#                         brace_count += 1
#                     elif text[j] == '}':
#                         brace_count -= 1
#                     j += 1
                
#                 if brace_count == 0:
#                     # Found matching brace pair
#                     content = text[i+1:j-1]
#                     # Check if this set contains operators (\\neq, !=, or multiple terms)
#                     if '\\neq' in content or '!=' in content or (len(content) > 10 and ' ' in content):
#                         # Convert to \\left\\{ ... \\right\\}
#                         result.append('\\left\\{')
#                         result.append(content)
#                         result.append('\\right\\}')
#                         i = j
#                         continue
            
#             result.append(text[i])
#             i += 1
        
#         return ''.join(result)

#     def _apply_structural_patterns(self, text: str) -> str:
#         """Apply general structural correction patterns."""
#         for pattern, replacement in self.STRUCTURAL_PATTERNS:
#             try:
#                 text = re.sub(pattern, replacement, text)
#             except re.error:
#                 logger.debug("Invalid regex pattern: %s", pattern)
#                 continue
        
#         return text

#     def _validate_and_refine(self, latex: str) -> str:
#         """Validate LaTeX using latex2mathml parser and refine if needed.
        
#         This uses the actual LaTeX parser to check if the output is valid.
#         If parsing fails, we try to fix common issues.
#         """
#         if not HAS_LATEX2MATHML:
#             return latex
        
#         # Remove $ delimiters for validation
#         latex_clean = latex.strip().strip('$')
        
#         # Try to parse the LaTeX
#         try:
#             latex2mathml_convert(latex_clean)
#             # If parsing succeeds, the LaTeX is valid
#             return latex_clean
#         except Exception as exc:
#             logger.debug("LaTeX validation failed: %s. Attempting refinement.", exc)
#             # Try to fix common issues
#             refined = self._refine_invalid_latex(latex_clean)
            
#             # Try parsing again
#             try:
#                 latex2mathml_convert(refined)
#                 logger.debug("LaTeX refined successfully")
#                 return refined
#             except Exception:
#                 # If still invalid, return the best we have
#                 logger.warning("Could not create valid LaTeX, returning best attempt")
#                 return refined

#     def _refine_invalid_latex(self, latex: str) -> str:
#         """Refine invalid LaTeX by fixing common structural issues."""
#         # Fix P_error patterns more robustly
#         latex = re.sub(r'P\s*_\s*\{?error\}?\s*\(', r'P_{\\text{error}}(', latex)
        
#         # Fix Pr to \Pr with proper spacing (but not if already escaped)
#         latex = re.sub(r'(?<!\\)\bPr\b(?!\w)', r'\\Pr', latex)
        
#         # Fix union symbols: ensure \bigcup is used with proper limits
#         latex = re.sub(r'\\bigcup\s*_\s*\{([^}]+)\}\s*\^\s*\{([^}]+)\}', r'\\bigcup_{\1}^{\2}', latex)
#         # Also fix U_{i=1}^{K} -> \bigcup_{i=1}^{K}
#         latex = re.sub(r'(?<!\\)\bU\s*_\s*\{([^}]+)\}\s*\^\s*\{([^}]+)\}', r'\\bigcup_{\1}^{\2}', latex)
        
#         # Fix sets: { ... } -> \left\{ ... \right\} for sets with operators
#         # Only convert sets that contain operators (not subscripts/superscripts)
#         # Pattern: { W_i \neq ... } -> \left\{ W_i \neq ... \right\}
#         # But avoid converting subscripts like {error}, {i=1}, {d_i}, etc.
#         if '{' in latex and '}' in latex:
#             # Only convert sets that contain \neq, !=, or multiple terms
#             # Pattern: { ... \neq ... } or { ... != ... } or { W_i ... g_i ... }
#             # Use negative lookbehind to avoid subscripts and negative lookahead to avoid superscripts
#             latex = re.sub(r'(?<!_)\{([^}]*\\neq[^}]*)\}(?!\^)', r'\\left\{\1\\right\}', latex)
#             latex = re.sub(r'(?<!_)\{([^}]*!=[^}]*)\}(?!\^)', r'\\left\{\1\\right\}', latex)
#             # Also convert sets with multiple variables/operators (like { W_i ... g_i ... })
#             latex = re.sub(r'(?<!_)\{([^}]*[A-Za-z]\s+[A-Za-z][^}]*)\}(?!\^)', r'\\left\{\1\\right\}', latex)
        
#         # Fix ellipsis
#         latex = re.sub(r'\.\.\.', r'\\ldots', latex)
#         latex = re.sub(r'\.\.', r'\\ldots', latex)
        
#         # Fix not-equal operators
#         latex = re.sub(r'!=\s*', r'\\neq ', latex)
#         latex = re.sub(r'≠\s*', r'\\neq ', latex)
        
#         # Fix bracket sizing for large expressions: [ ... ] -> \Bigg[ ... \Bigg]
#         # Only for brackets containing union or complex expressions
#         if '[' in latex and ']' in latex and ('\\bigcup' in latex or 'Pr' in latex):
#             # Pattern: [ \bigcup ... ] -> \Bigg[ \bigcup ... \Bigg]
#             latex = re.sub(r'\[\s*(\\bigcup[^\]]+)\]', r'\\Bigg[\1\\Bigg]', latex)
        
#         # Fix unmatched braces
#         open_braces = latex.count('{')
#         close_braces = latex.count('}')
#         if open_braces > close_braces:
#             latex += '}' * (open_braces - close_braces)
#         elif close_braces > open_braces:
#             latex = '{' * (close_braces - open_braces) + latex
        
#         # Fix unmatched brackets
#         open_brackets = latex.count('[')
#         close_brackets = latex.count(']')
#         if open_brackets > close_brackets:
#             latex += ']' * (open_brackets - close_brackets)
#         elif close_brackets > open_brackets:
#             latex = '[' * (close_brackets - open_brackets) + latex
        
#         # Fix unmatched parentheses
#         open_parens = latex.count('(')
#         close_parens = latex.count(')')
#         if open_parens > close_parens:
#             latex += ')' * (open_parens - close_parens)
#         elif close_parens > open_parens:
#             latex = '(' * (close_parens - open_parens) + latex
        
#         # Remove invalid characters that might break parsing (but keep more math symbols)
#         invalid_chars = re.compile(r'[^\w\s\\\{\}\[\]\(\)\^_\+\-\*\/=<>≤≥±∑∏∫∪∩∈∉α-ωΑ-Ω≠]')
#         latex = invalid_chars.sub('', latex)
        
#         return latex

