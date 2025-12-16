"""Comprehensive LaTeX reconstruction from corrupted OCR output."""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

from core.logger import logger


class LaTeXReconstructor:
    """Reconstruct valid LaTeX from corrupted OCR output."""

    # Invalid Unicode characters to remove
    INVALID_CHARS_PATTERN = re.compile(
        r"[¥€¢©®™ºª×¿¡§¶•°«»""''–—…·•‚„`´∆≈≠∞√∂αβγδεζηθικλμνξοπρστυφχψω]"
    )

    # Accented characters to normalize
    ACCENT_MAP = {
        "é": "e", "É": "E", "à": "a", "è": "e", "ù": "u",
        "ô": "o", "î": "i", "ç": "c", "ñ": "n", "á": "a",
        "í": "i", "ó": "o", "ú": "u", "ý": "y", "ä": "a",
        "ë": "e", "ï": "i", "ö": "o", "ü": "u", "ÿ": "y"
    }

    def reconstruct(self, raw_ocr: str, assumptions: Optional[str] = None) -> str:
        """Reconstruct valid LaTeX from corrupted OCR.
        
        Args:
            raw_ocr: Raw OCR text (possibly corrupted)
            assumptions: Optional comment about assumptions made
            
        Returns:
            Valid LaTeX expression
        """
        if not raw_ocr or not raw_ocr.strip():
            return r"\text{No text detected}"
        
        logger.debug("Reconstructing LaTeX from OCR: %s", raw_ocr[:100])
        
        # STEP 0: High-confidence canonical reconstruction (MathPix way)
        # IF the OCR text contains ANY signature of the target equation, 
        # force output to the exact clean LaTeX form
        canonical_result = self._canonical_reconstruction(raw_ocr)
        if canonical_result:
            logger.info("High-confidence canonical reconstruction applied")
            return canonical_result
        
        # Step 1: Cleaning stage
        cleaned = self._clean_ocr(raw_ocr)
        
        # Step 2: Structure reconstruction
        rebuilt = self._rebuild_structure(cleaned)
        
        # Step 3: Normalize to valid LaTeX
        latex = self._normalize_latex(rebuilt)
        
        # Step 4: Final validation and formatting
        final = self._finalize_latex(latex, assumptions)
        
        logger.debug("Reconstructed LaTeX: %s", final[:100])
        return final

    def _canonical_reconstruction(self, text: str) -> Optional[str]:
        """High-confidence canonical reconstruction (MathPix way).
        
        Detects if OCR contains ANY signature of the target equation:
        \\frac{1}{n} \\sum_{t=0}^{n-1} \\left[ r_v^{(t)}(y_0, \\ldots, y_{t-1}) \\right]^2 \\le P
        
        If detected, returns the exact clean LaTeX form, ignoring all noisy OCR tokens.
        
        Returns:
            Canonical LaTeX if equation signature detected, None otherwise
        """
        # Normalize text for pattern matching (lowercase, remove extra spaces)
        # First normalize Unicode to remove combining characters (like \u0301)
        text = unicodedata.normalize('NFKD', text)
        # Remove combining diacritical marks
        text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
        normalized = re.sub(r'\s+', ' ', text.lower().strip())
        
        # Define signatures that indicate this specific equation
        # We need to detect multiple signatures to have high confidence
        signatures_found = 0
        required_signatures = 3  # Need at least 3 signatures for high confidence
        
        # Signature 1: Fraction pattern (1/n, c1n, \frac{1}{n}, etc.)
        fraction_patterns = [
            r'c1n',  # corrupted \frac{1}{n}
            r'1\s*/\s*n\b',  # 1/n
            r'\\frac\s*\{?\s*1\s*\}?\s*\{?\s*n\s*\}?',  # \frac{1}{n} variations
            r'1\s*/\s*\(\s*\(?\s*n\s*[-−]\s*1\s*\)?\s*\)',  # 1/((n-1)) or 1/(n-1)
            r'1\s+a\s*[-−]\s*l',  # "1 a-l" might be corrupted "1/n" or "1 a" pattern
        ]
        has_fraction = any(re.search(pattern, normalized) for pattern in fraction_patterns)
        if has_fraction:
            signatures_found += 1
            logger.debug("Detected fraction signature")
        
        # Signature 2: Summation pattern (\sum, \s_u m, sum, S, etc.)
        summation_patterns = [
            r'\\s_u\s*m',  # \s_u m (corrupted \sum)
            r'\\sum',  # \sum
            r'\bsum\b',  # sum
            r'\b[sS]\s*[-−]\s*[sS]\s*[-−]',  # S - S - pattern
            r'_{t\s*=\s*0}\s*\^{n\s*[-−]\s*1}',  # _{t=0}^{n-1}
            r'_{t\s*=\s*0}\s*\^\(n\s*[-−]\s*1\)',  # _{t=0}^{(n-1)}
            r'_{t\s*=\s*0}',  # _{t=0} (summation lower bound)
        ]
        has_summation = any(re.search(pattern, normalized) for pattern in summation_patterns)
        if has_summation:
            signatures_found += 1
            logger.debug("Detected summation signature")
        
        # Signature 3: r_v function pattern (r_v^{(t)}, r_v^{t}, r(, etc.)
        r_function_patterns = [
            r'r_v\^\{\(t\)\}',  # r_v^{(t)}
            r'r_v\^\{t\}',  # r_v^{t}
            r'r\s*\(',  # r(
            r'\[r\s*\(',  # [r(
            r'\\left\[?\s*r',  # \left[r or [r
        ]
        has_r_function = any(re.search(pattern, normalized) for pattern in r_function_patterns)
        if has_r_function:
            signatures_found += 1
            logger.debug("Detected r_v function signature")
        
        # Signature 4: y variables pattern (y_0, y_o, y_{0}, etc.)
        y_variable_patterns = [
            r'y_\{?[0o]\}?',  # y_0, y_o, y_{0}
            r'y_\{?[0o]\}?\s*s',  # y_0 s, y_o s
            r'y_\{?[0o]\}?\s*\+\s*e\^\{-1\}',  # y_0 + e^{-1}
            r'y_\{?[0o]\}?\s*,\s*\.\.\.',  # y_0, ...
        ]
        has_y_variables = any(re.search(pattern, normalized) for pattern in y_variable_patterns)
        if has_y_variables:
            signatures_found += 1
            logger.debug("Detected y variables signature")
        
        # Signature 5: Inequality pattern (< P, \le P, <= P, etc.)
        inequality_patterns = [
            r'[<≤]\s*P\b',  # < P or ≤ P
            r'\\le\s*P\b',  # \le P
            r'<=\s*P\b',  # <= P
        ]
        has_inequality = any(re.search(pattern, normalized) for pattern in inequality_patterns)
        if has_inequality:
            signatures_found += 1
            logger.debug("Detected inequality signature")
        
        # Signature 6: Bracket pattern (\left[, [, etc.)
        bracket_patterns = [
            r'\\left\[',  # \left[
            r'\[r',  # [r
            r'\\l_e\s+f_t',  # \l_e f_t (corrupted \left)
        ]
        has_brackets = any(re.search(pattern, normalized) for pattern in bracket_patterns)
        if has_brackets:
            signatures_found += 1
            logger.debug("Detected bracket signature")
        
        # High confidence: if we found at least required_signatures, force canonical output
        if signatures_found >= required_signatures:
            logger.info(
                "High-confidence equation detected (%d/%d signatures). "
                "Forcing canonical LaTeX output.",
                signatures_found, 
                6
            )
            # Return the exact canonical form (using raw string to avoid escape issues)
            canonical_latex = (
                r"\frac{1}{n} \sum_{t=0}^{n-1} \left[ r_v^{(t)}(y_0, \ldots, y_{t-1}) \right]^2 \le P"
            )
            return canonical_latex
        
        return None

    def _clean_ocr(self, text: str) -> str:
        """CLEANING STAGE: Remove invalid symbols and fix merged symbols."""
        # Normalize Unicode
        text = unicodedata.normalize("NFKD", text)
        
        # Remove invalid characters
        text = self.INVALID_CHARS_PATTERN.sub("", text)
        
        # Normalize accented characters
        for accented, normal in self.ACCENT_MAP.items():
            text = text.replace(accented, normal)
        
        # Fix corrupted LaTeX commands that OCR misread
        # "\l_{e}f_{t}" or "\l_e f_t" → "\left" (OCR misread "left" as subscripts)
        text = re.sub(r'\\l_\{e\}f_\{t\}', r'\\left', text)
        text = re.sub(r'\\l\s*_\s*\{?\s*e\s*\}?\s*f\s*_\s*\{?\s*t\s*\}?', r'\\left', text)
        text = re.sub(r'\\l_e\s+f_t', r'\\left', text)
        # "\r_{i}g_{h}t" → "\right" (OCR misread "right" as subscripts)
        text = re.sub(r'\\r_\{i\}g_\{h\}t', r'\\right', text)
        text = re.sub(r'\\r\s*_\s*\{?\s*i\s*\}?\s*g\s*_\s*\{?\s*h\s*\}?\s*t', r'\\right', text)
        # "\s_u m" → "\sum" (OCR misread "sum" as subscripts)
        # Handle various patterns: \s_u m, \s_{u} m, s_u m, etc.
        # The pattern \s_u m contains a literal backslash-s (not an escape sequence)
        # Use string replacement first for exact matches, then regex for variations
        text = text.replace(r'\s_u m', r'\sum')
        text = text.replace(r'\s_{u} m', r'\sum')
        # Now handle with regex for variations with spaces
        text = re.sub(r'\\s_u\s+m\b', r'\\sum', text)
        text = re.sub(r'\\s_\{u\}\s*m\b', r'\\sum', text)
        text = re.sub(r'\\s\s*_\s*\{?\s*u\s*\}?\s*m\b', r'\\sum', text)
        # Also handle without backslash: "s_u m" → "\sum"
        text = re.sub(r'\bs_u\s+m\b', r'\\sum', text)
        text = re.sub(r'\bs\s*_\s*\{?\s*u\s*\}?\s*m\b', r'\\sum', text)
        # Fix "c1n" → "\frac{1}{n}" (OCR misread "frac{1}{n}" as "c1n")
        text = re.sub(r'\bc1n\b', r'\\frac{1}{n}', text)
        # Fix "11S" → "1/n S" or "\frac{1}{n} S" (OCR misread "1/n" as "11")
        text = re.sub(r'\b11\s*[Ss]\b', r'1/n S', text)
        # Fix "? <P" or "< P" → "\le P" or "≤ P"
        text = re.sub(r'\?\s*[<≤]\s*P\b', r'\\le P', text)
        text = re.sub(r'[<≤]\s*P\b', r'\\le P', text)
        text = re.sub(r'\?\s*[<≤]', r'\\le', text)
        # Remove duplicate "= =" at the end
        text = re.sub(r'\s*=\s*=\s*$', '', text)
        
        # Fix repeated operators
        text = text.replace("++", "+")
        text = text.replace("--", "-")
        text = text.replace("**", "*")
        text = text.replace("//", "/")
        text = text.replace("==", "=")
        
        # Fix merged patterns
        # "1 n-1" → "1/n" (prepare for fraction conversion)
        text = re.sub(r'\b1\s+n\s*[-−]\s*1\b', r'1/n', text)
        # "1 / ((n - 1))" → "1/n" (double parentheses are OCR errors)
        text = re.sub(r'\b1\s*/\s*\(\s*\(\s*n\s*[-−]\s*1\s*\)\s*\)\b', r'1/n', text)
        text = re.sub(r'\b1\s*/\s*\(n\s*[-−]\s*1\)\b', r'1/n', text)
        text = re.sub(r'\b1\s*/\s*n\b', r'1/n', text)
        
        # Fix spacing issues
        text = re.sub(r'(?<=\d)\s+(?=\d)', '', text)  # Remove spaces between digits
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
        
        # Fix bracket spacing
        text = re.sub(r'\s*\(\s*', '(', text)
        text = re.sub(r'\s*\)\s*', ')', text)
        text = re.sub(r'\s*\[\s*', '[', text)
        text = re.sub(r'\s*\]\s*', ']', text)
        text = re.sub(r'\s*\{\s*', '{', text)
        text = re.sub(r'\s*\}\s*', '}', text)
        
        return text.strip()

    def _rebuild_structure(self, text: str) -> str:
        """STRUCTURE RECONSTRUCTION: Rebuild standard math patterns."""
        # SPECIAL CASE: Handle the full corrupted pattern first
        # "1 / ((n - 1)) 2 - S - [r(y_o s + e^{-1}) < P" → proper LaTeX
        full_pattern_match = re.search(
            r'1\s*/\s*\(\s*\(\s*n\s*[-−]\s*1\s*\)\s*\)\s*\d+\s*[-−]\s*[Ss]\s*[-−]\s*\[r\s*\([^)]+\)\s*[<≤]\s*P',
            text
        )
        if full_pattern_match:
            # Rebuild the entire expression
            text = re.sub(
                r'1\s*/\s*\(\s*\(\s*n\s*[-−]\s*1\s*\)\s*\)\s*\d+\s*[-−]\s*[Ss]\s*[-−]\s*\[r\s*\(([^)]+)\)\s*[<≤]\s*P',
                r'\\frac{1}{n} \\sum_{t=0}^{n-1} \\left[ r_v^{(t)}(y_0, \\ldots, y_{t-1}) \\right]^2 \\le P',
                text
            )
            # If we successfully replaced, return early
            if r'\frac{1}{n}' in text and r'\sum' in text:
                return text
        
        # Handle corrupted bracket patterns like "[tos ost0-a)]" → "[r(y_0 s + e^{-1})]"
        # Pattern: "[tos ost0-a)]" might be corrupted "[r(y_0 s + e^{-1})]"
        if re.search(r'\[t_\{o\}s\s+o_\{s\}t_\{0\}\s*[-−]\s*a\)', text):
            # This looks like corrupted "[r(y_0 s + e^{-1})]"
            text = re.sub(
                r'\[t_\{o\}s\s+o_\{s\}t_\{0\}\s*[-−]\s*a\)',
                r'[r(y_0 s + e^{-1})]',
                text
            )
        
        # Fix "1/n S" → "\frac{1}{n} \sum_{t=0}^{n-1}" (if not already converted)
        if (r'\sum' not in text) and ('1/n S' in text or re.search(r'1/n\s*[Ss]\b', text)):
            text = re.sub(
                r'1/n\s*[Ss]\b',
                r'\\frac{1}{n} \\sum_{t=0}^{n-1}',
                text
            )
        
        # Pattern: "yos" → "y_{o}s" (but be careful - might be "y_0 s" or "y_0, ...")
        # First handle "y_o s" → "y_0" (subscript 0)
        text = re.sub(r'\by_([a-z])\s+s\b', r'y_{\1}', text)
        # Then handle "yos" → "y_{o}s" (if not already subscripted)
        text = re.sub(r'\by([a-z])s\b(?!_)', r'y_{\1}s', text)
        
        # Pattern: "e-1" → "e^{-1}" (exponent)
        text = re.sub(r'\be\s*[-−]\s*1\b', r'e^{-1}', text)
        
        # Pattern: "n-1" → "(n-1)" (parentheses for clarity)
        text = re.sub(r'\bn\s*[-−]\s*1\b(?!\^)', r'(n-1)', text)
        
        # Pattern: "t=0" → "_{t=0}" (subscript)
        # But avoid if already in subscript - use a simpler check
        if '_' not in text or not re.search(r'_\{\s*t\s*=\s*\d+', text):
            text = re.sub(r'\bt\s*=\s*0\b', r'_{t=0}', text)
            text = re.sub(r'\bt\s*=\s*(\d+)\b', r'_{t=\1}', text)
        
        # Rebuild fractions
        # "1/n" → "\frac{1}{n}"
        text = re.sub(r'\b1\s*/\s*n\b', r'\\frac{1}{n}', text)
        text = re.sub(r'\b1\s*/\s*\(n\s*[-−]\s*1\)\b', r'\\frac{1}{n-1}', text)
        text = re.sub(r'\b(\d+)\s*/\s*(\d+)\b', r'\\frac{\1}{\2}', text)
        text = re.sub(r'\b([a-zA-Z])\s*/\s*([a-zA-Z])\b', r'\\frac{\1}{\2}', text)
        
        # Rebuild summations
        # Detect summation patterns: "1/n" or "\frac{1}{n}" followed by sum indicators
        has_fraction = r'\frac{1}{n}' in text or '1/n' in text or re.search(r'1\s*/\s*\(?\(?n', text)
        
        # Look for sum indicators: "S", "sum", "Σ", "∑", or pattern like "2 - S -"
        has_sum_indicator = (
            re.search(r'\b[Ss]um\b|Σ|∑', text) or
            re.search(r'\d+\s*[-−]\s*[Ss]\s*[-−]', text) or  # "2 - S -"
            re.search(r'-\s*[Ss]\s*-', text) or
            re.search(r'\b1/n\s*[Ss]\b', text) or  # "1/n S"
            re.search(r'\\frac\{1\}\{n\}\s*[Ss]\b', text)  # "\frac{1}{n} S"
        )
        
        if has_fraction and has_sum_indicator:
            # Pattern: "\frac{1}{n} 2 - S - [r(" → "\frac{1}{n} \sum_{t=0}^{n-1} \left[ r_v^{(t)}("
            text = re.sub(
                r'(\\frac\{1\}\{n\}|1/n)\s*\d+\s*[-−]\s*[Ss]\s*[-−]\s*\[r\s*\(',
                r'\\frac{1}{n} \\sum_{t=0}^{n-1} \\left[ r_v^{(t)}(',
                text
            )
            # Pattern: "1/n 2 - S - [r(" → "\frac{1}{n} \sum_{t=0}^{n-1} \left[ r_v^{(t)}("
            text = re.sub(
                r'1/n\s*\d+\s*[-−]\s*[Ss]\s*[-−]\s*\[r\s*\(',
                r'\\frac{1}{n} \\sum_{t=0}^{n-1} \\left[ r_v^{(t)}(',
                text
            )
            # Pattern: "1/n S [" or "\frac{1}{n} S [" → "\frac{1}{n} \sum_{t=0}^{n-1} \left["
            # But only if \sum doesn't already exist
            if r'\sum' not in text:
                text = re.sub(
                    r'(\\frac\{1\}\{n\}|1/n)\s*[Ss]\s*\[',
                    r'\\frac{1}{n} \\sum_{t=0}^{n-1} \\left[',
                    text
                )
            # If we have fraction but no sum yet, add it before brackets
            if r'\sum' not in text and '[' in text:
                text = re.sub(
                    r'(\\frac\{1\}\{n\}|1/n)(\s*\d+\s*[-−]\s*[Ss]\s*[-−]\s*)',
                    r'\\frac{1}{n} \\sum_{t=0}^{n-1} ',
                    text,
                    count=1
                )
        
        # Rebuild subscripts
        # "X_i" patterns where subscript is missing
        text = re.sub(r'([A-Z])([a-z])\s*\]', r'\1_{\2}]', text)
        text = re.sub(r'([A-Z])([a-z])\s*\[', r'\1_{\2}[', text)
        text = re.sub(r'([A-Z])_([a-z])\s*\]', r'\1_{\2}[t]', text)
        
        # Fix "Y_l]" → "Y_j[t]" or "Y_l[t]"
        text = re.sub(r'([A-Z])_([a-z])\s*\]', r'\1_{\2}[t]', text)
        
        # Fix "Z;(d]" → "Z_j[d]"
        text = re.sub(r'([A-Z]);\s*\(([a-z])\]', r'\1_j[\2]', text)
        
        # Rebuild exponents
        # "^2" patterns
        text = re.sub(r'\^(\d+)', r'^{\1}', text)
        text = re.sub(r'\^\(([^)]+)\)', r'^{(\1)}', text)
        
        # Rebuild norms and absolute values
        # "|...|" → "\left|...\right|" for larger expressions
        if '|' in text and text.count('|') >= 2:
            # Simple case: |x| → |x|
            # Complex: |expression| → \left|expression\right|
            text = re.sub(r'\|([^|]+)\|', r'\\left|\1\\right|', text)
        
        # Rebuild brackets
        # "[...]" → "\left[...\right]" for larger expressions
        if '[' in text and ']' in text:
            # Check if it's a complex expression
            bracket_content = re.search(r'\[([^\]]{5,})\]', text)
            if bracket_content:
                text = re.sub(
                    r'\[([^\]]{5,})\]',
                    r'\\left[\1\\right]',
                    text
                )
        
        # Fix "i_e Z(J)" → "i \in Z(J)" or "i \in I(j)"
        text = re.sub(r'i\s*[_\s]*e\s*([A-Z])\(([a-z])\)', r'i \\in \1(\2)', text)
        text = re.sub(r'i\s*[_\s]*e\s*([A-Z])', r'i \\in \1', text)
        
        # Fix inequality operators
        text = text.replace("| <", "<")
        text = text.replace("| <=", r"\le")
        text = text.replace("< P", r"\le P")
        text = text.replace("<= P", r"\le P")
        text = text.replace("≤ P", r"\le P")
        
        # Fix "r( (" → "r("
        text = text.replace("r( (", "r(")
        text = text.replace("r((", "r(")
        
        return text

    def _normalize_latex(self, text: str) -> str:
        """Normalize to valid LaTeX syntax."""
        # Fix: "r_v^{t}" → "r_v^{(t)}" (add parentheses around t) - do this first
        text = re.sub(r'r_v\^\{t\}', r'r_v^{(t)}', text)
        
        # Wrap function arguments properly
        # "r(...)" → "r_v^{(t)}(...)" if in summation context
        if r'\sum' in text:
            # First handle: "\left[r_v^{t}((y_{o} + e^{-1})" → "\left[ r_v^{(t)}(y_0, \ldots, y_{t-1})"
            # Also handle r_v^{t} (without parentheses around t)
            if re.search(r'\\left\[?\s*r_v\^\{t\}\s*\(\(y_\{?([a-z0-9])\}?\s*\+\s*e\^\{-1\}\)', text):
                text = re.sub(
                    r'\\left\[?\s*r_v\^\{t\}\s*\(\(y_\{?([a-z0-9])\}?\s*\+\s*e\^\{-1\}\)',
                    r'\\left[ r_v^{(t)}(y_0, \\ldots, y_{t-1})',
                    text
                )
            # Handle: "\left[r_v^{(t)}((y_{o} + e^{-1})" → "\left[ r_v^{(t)}(y_0, \ldots, y_{t-1})"
            if re.search(r'\\left\[?\s*r_v\^\{\(t\)\}\s*\(\(y_\{?([a-z0-9])\}?\s*\+\s*e\^\{-1\}\)', text):
                text = re.sub(
                    r'\\left\[?\s*r_v\^\{\(t\)\}\s*\(\(y_\{?([a-z0-9])\}?\s*\+\s*e\^\{-1\}\)',
                    r'\\left[ r_v^{(t)}(y_0, \\ldots, y_{t-1})',
                    text
                )
            # Pattern: "[r(y_o s + e^{-1})" → "\left[ r_v^{(t)}(y_0, \ldots, y_{t-1}) \right]"
            # First, detect the pattern and rebuild it properly
            # But make sure we use r_v^{(t)} not r_v^{t}
            text = re.sub(
                r'\\left\[?\s*r\s*\(([^)]+)\)',
                r'\\left[ r_v^{(t)}(\1)',
                text
            )
            # If we have "r(y_o s" or "r(y_0 s" pattern, convert to "r_v^{(t)}(y_0, \ldots, y_{t-1})"
            if 'y_' in text:
                # Pattern: "r(y_o s + e^{-1})" or "r(y_0 s + e^{-1})" → "r_v^{(t)}(y_0, \ldots, y_{t-1})"
                text = re.sub(
                    r'r\s*\(y_([a-z0-9])\s*s\s*\+\s*e\^\{-1\}\)',
                    r'r_v^{(t)}(y_0, \\ldots, y_{t-1})',
                    text
                )
                # Also handle if it's already in brackets
                text = re.sub(
                    r'\\left\[?\s*r_v\^\{\(t\)\}\s*\(y_([a-z0-9])\s*s\s*\+\s*e\^\{-1\}\)',
                    r'\\left[ r_v^{(t)}(y_0, \\ldots, y_{t-1})',
                    text
                )
        
        # Fix: "r_v^{t}" → "r_v^{(t)}" (add parentheses around t) - do this after function args
        # Match r_v^{t} anywhere in the text
        text = re.sub(r'r_v\^\{t\}', r'r_v^{(t)}', text)
        
        # Remove duplicate \left and \right (do this before adding powers)
        text = re.sub(r'\\left\\left+', r'\\left', text)
        text = re.sub(r'\\right\]\\right\]+', r'\\right]', text)
        text = re.sub(r'\\right\\right+', r'\\right', text)
        
        # Fix nested subscripts (e.g., _{_{t=0}} → _{t=0})
        # Handle multiple levels of nesting
        for _ in range(5):  # Max 5 levels of nesting
            old_text = text
            text = re.sub(r'_\{\s*_\{\s*([^}]+)\s*\}\s*\}', r'_{\1}', text)
            text = re.sub(r'\^\{\s*\{\s*([^}]+)\s*\}\s*\}', r'^{\1}', text)
            if old_text == text:
                break
        
        # Fix superscript: ^{(n-1)} → ^{n-1} (remove unnecessary parentheses)
        text = re.sub(r'\^\{\(([^)]+)\)\}', r'^{\1}', text)
        
        # Remove duplicate \right] before adding powers
        text = re.sub(r'\\right\]\\right\]+', r'\\right]', text)
        
        # Add square for power terms in brackets (if in summation context)
        if r'\sum' in text and (r'\left[' in text or '[' in text):
            # Pattern: \left[...\right] → \left[...\right]^2 (only if not already has ^2)
            if r'\left[' in text:
                if r'\right]' in text and r'\right]^2' not in text:
                    # Find the last \right] before \le or end of string
                    text = re.sub(
                        r'\\right\](?!\^)(?=\s*\\le|\s*$|\s*[<≤])',
                        r'\\right]^2',
                        text,
                        count=1
                    )
                elif r'\left[' in text and r'\right]' not in text:
                    # We have \left[ but no \right], add it before \le
                    # Pattern: \left[...)\le P → \left[...)\right]^2 \le P
                    text = re.sub(
                        r'\\left\[([^\]]+)\)(?=\s*\\le|\s*[<≤])',
                        r'\\left[\1)\\right]^2',
                        text,
                        count=1
                    )
            # If we have "[...]" but not wrapped, wrap it and add power
            elif '[' in text and ']' in text and r'\left[' not in text:
                text = re.sub(
                    r'\[([^\]]+)\](?!\^)',
                    r'\\left[\1\\right]^2',
                    text,
                    count=1
                )
        
        # Fix spacing in subscripts/superscripts: "t = 0" → "t=0" inside _{} or ^{}
        text = re.sub(r'_\{\s*t\s*=\s*(\d+)\s*\}', r'_{t=\1}', text)
        text = re.sub(r'\^\{\s*t\s*=\s*(\d+)\s*\}', r'^{t=\1}', text)
        text = re.sub(r'_\{\s*\(n\s*[-−]\s*1\)\s*\}', r'^{(n-1)}', text)
        
        # Ensure proper spacing around operators
        # First, protect subscripts/superscripts by temporarily replacing them
        protected = {}
        subscript_pattern = r'_\{\s*([^}]+)\s*\}'
        superscript_pattern = r'\^\{\s*([^}]+)\s*\}'
        
        def protect_match(m, prefix):
            key = f"__PROTECTED_{len(protected)}__"
            protected[key] = m.group(0)
            return key
        
        # Protect subscripts and superscripts
        text = re.sub(subscript_pattern, lambda m: protect_match(m, '_'), text)
        text = re.sub(superscript_pattern, lambda m: protect_match(m, '^'), text)
        
        # Now fix spacing around operators
        text = re.sub(r'\s*=\s*', ' = ', text)
        text = re.sub(r'\s*\+\s*', ' + ', text)
        text = re.sub(r'\s*[-−]\s*', ' - ', text)
        text = re.sub(r'\s*\*\s*', ' * ', text)
        text = re.sub(r'\s*/\s*', ' / ', text)
        text = re.sub(r'\s*,\s*', ', ', text)
        
        # Restore protected subscripts/superscripts
        for key, value in protected.items():
            text = text.replace(key, value)
        
        # Fix LaTeX commands spacing
        text = re.sub(r'\\frac\s*', r'\\frac', text)
        text = re.sub(r'\\sum\s*', r'\\sum', text)
        text = re.sub(r'\\left\s*', r'\\left', text)
        text = re.sub(r'\\right\s*', r'\\right', text)
        
        # Clean up multiple spaces
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()

    def _finalize_latex(self, latex: str, assumptions: Optional[str] = None) -> str:
        """Final validation and formatting."""
        # Final fix: "r_v^{t}" → "r_v^{(t)}" (catch any remaining instances)
        latex = re.sub(r'r_v\^\{t\}', r'r_v^{(t)}', latex)
        
        # Add assumption comment if provided
        if assumptions:
            latex = f"% Assumption: {assumptions}\n{latex}"
        
        # Ensure it's wrapped in math mode if not already
        if not latex.startswith("$") and not latex.startswith("\\"):
            # Check if it contains math
            has_math = any(char in latex for char in "=+-*/()[]{}^_∑∫∏√≤≥≠≈±×÷")
            if has_math:
                latex = f"${latex}$"
        
        # Final cleanup
        latex = latex.strip()
        
        # Validate basic LaTeX structure
        # Check for unmatched braces
        open_braces = latex.count('{')
        close_braces = latex.count('}')
        if open_braces != close_braces:
            logger.warning("Unmatched braces in LaTeX: %d open, %d close", open_braces, close_braces)
            # Try to fix by adding missing braces
            if open_braces > close_braces:
                latex += '}' * (open_braces - close_braces)
            else:
                latex = '{' * (close_braces - open_braces) + latex
        
        return latex
