# services/ocr/mathml_recovery_pro.py
"""
ULTRA MathML Recovery Engine (ultra_mathml_recover)

Purpose:
    Rebuild heavily corrupted MathML (or MathML-wrapped LaTeX in <mtext>)
    into clean LaTeX and validated MathML where possible.

API:
    from services.ocr.mathml_recovery_pro import ultra_mathml_recover
    result = ultra_mathml_recover(corrupted_mathml_string)

Return:
    {
        "latex": "<best-effort LaTeX string>",
        "mathml": "<valid MathML string or fallback mtext wrapper>",
        "confidence": float(0..1),
        "log": [str, ...]
    }
"""

from __future__ import annotations
import re
import xml.etree.ElementTree as ET
import html
from typing import Dict, List, Tuple

from core.logger import logger

# Optional latex->MathML converter
try:
    from latex2mathml.converter import convert as latex2mathml_convert  # type: ignore
    HAS_LATEX2MATHML = True
except Exception:
    HAS_LATEX2MATHML = False
    logger.info("latex2mathml not available — ULTRA will return LaTeX and best-effort MathML wrappers")


# -----------------------
# Config / Repairs maps
# -----------------------
# Targeted shredded-pattern repairs (regex -> replacement)
SHRED_REPAIR = {
    # Complex \mathrm patterns with nested subscripts - must match before simple patterns
    r'\\m_\{a\}t_\{h\}r_\{m\}\{e_\{r\}r_\{o\}r\}': r'\\mathrm{error}',  # \m_{a}t_{h}r_{m}{e_{r}r_{o}r} -> \mathrm{error}
    r'\\m_\{a\}t_\{h\}r_\{m\}\{P_\{r\}\}': r'\\mathrm{Pr}',  # \m_{a}t_{h}r_{m}{P_{r}} -> \mathrm{Pr}
    r'\\m_\{a\}t_\{h\}r_\{m\}': r'\\mathrm',  # \m_{a}t_{h}r_{m} -> \mathrm (fallback)
    
    # \mathbb patterns - MUST come before \mathbf (both start with m_{a}t_{h}, but \mathbb has b_{b})
    r'\\+m_\{a\}\\?t_\{h\}\\?b_\{b\}': r'\\mathbb',  # \m_{a}\t_{h}\b_{b} or \m_{a}t_{h}b_{b} -> \mathbb
    r'\\+m_\{a\}\s*t_\{h\}\s*b_\{b\}': r'\\mathbb',  # \m_{a} t_{h} b_{b} -> \mathbb (with spaces)
    r'\\+m_\{a\}t_\{h\}\s*b_\{b\}': r'\\mathbb',  # \m_{a}t_{h} b_{b} -> \mathbb (partial spacing)
    r'\\+m_\{a\}t_\{h\}b_\{b\}': r'\\mathbb',  # \m_{a}t_{h}b_{b} -> \mathbb (no spaces)
    r'\\?m_\{a\}t_\{h\}b_\{b\}': r'\\mathbb',     # m_{a}t_{h}b_{b} -> \mathbb (no spaces)
    
    # \mathbf patterns (mathbf can be shredded as m_{a}t_{h}b_{f} or m_{a}t_{h}b_{s})
    # Handle both single and double backslashes, with optional spaces
    # Pattern: \m_{a}\t_{h}\b_{f} or \m_{a}t_{h}b_{f} (mixed backslashes)
    r'\\+m_\{a\}\\?t_\{h\}\\?b_\{[fs]\}': r'\\mathbf',  # \m_{a}\t_{h}\b_{f} or \m_{a}t_{h}b_{f} -> \mathbf
    r'\\+m_\{a\}\s*t_\{h\}\s*b_\{[fs]\}': r'\\mathbf',  # \m_{a} t_{h} b_{f} -> \mathbf (with spaces)
    r'\\+m_\{a\}t_\{h\}\s*b_\{[fs]\}': r'\\mathbf',  # \m_{a}t_{h} b_{f} -> \mathbf (partial spacing)
    r'\\+m_\{a\}t_\{h\}b_\{[fs]\}': r'\\mathbf',  # \m_{a}t_{h}b_{f} -> \mathbf (no spaces)
    r'\\?m_\{a\}t_\{h\}b_\{[fs]\}': r'\\mathbf',  # m_{a}t_{h}b_{f} or m_{a}t_{h}b_{s} -> \mathbf (no spaces)
    
    # \math pattern (fallback)
    r'\\+m_\{a\}\\?t_\{h\}': r'\\math',  # \m_{a}\t_{h} or \m_{a}t_{h} -> \math
    r'\\+m_\{a\}\s*t_\{h\}': r'\\math',  # \m_{a} t_{h} -> \math (with spaces)
    r'\\?m_\{a\}t_\{h\}': r'\\math',              # m_{a}t_{h} -> \math (no spaces)
    
    # Left/right patterns - handle spaces and mixed backslashes
    r'\\+l_\{e\}\\?f_\{t\}': r'\\left',  # \l_{e}\f_{t} or \l_{e}f_{t} -> \left
    r'\\+l_\{e\}\s*f_\{t\}': r'\\left',  # \l_{e} f_{t} -> \left (with spaces)
    r'\\+l_\{e\}f_\{t\}': r'\\left',  # \l_{e}f_{t} -> \left (no spaces)
    r'\\?l_\{e\}f_\{t\}': r'\\left',  # l_{e}f_{t} -> \left (no spaces)
    r'\\+r_\{i\}\\?g_\{h\}\\?t\}?': r'\\right',  # \r_{i}\g_{h}\t or \r_{i}g_{h}t -> \right
    r'\\+r_\{i\}\s*g_\{h\}\s*t\}?': r'\\right',  # \r_{i} g_{h} t -> \right (with spaces)
    r'\\+r_\{i\}g_\{h\}t\}?': r'\\right',  # \r_{i}g_{h}t -> \right (no spaces)
    r'\\?r_\{i\}g_\{h\}t\}?': r'\\right',         # allow optional trailing brace
    
    # Sum, frac, Pr - handle spaces
    r'\\+s_\{u\}\s*m': r'\\sum',  # \s_{u} m -> \sum
    r'\\?s_\{u\}m': r'\\sum',  # s_{u}m -> \sum (no spaces)
    r'\\+f_\{r\}\s*a_\{c\}': r'\\frac',  # \f_{r} a_{c} -> \frac
    r'\\?f_\{r\}a_\{c\}': r'\\frac',  # f_{r}a_{c} -> \frac (no spaces)
    r'\\?p_\{r\}': r'\\Pr',
    
    # Bigcup pattern - handle spaces
    r'\\+b_\{i\}\s*g_\{c\}\s*u_\{p\}': r'\\bigcup',  # \b_{i} g_{c} u_{p} -> \bigcup
    r'\\?b_\{i\}g_\{c\}u_\{p\}': r'\\bigcup',  # b_{i}g_{c}u_{p} -> \bigcup (no spaces)
    
    # \in pattern - handle spaces
    r'\\+i_\{n\}': r'\\in',  # \i_{n} -> \in
    r'\\?i_\{n\}': r'\\in',  # i_{n} -> \in (no spaces)
    
    # Neq pattern - handle spaces
    r'\\+n_\{e\}\s*q': r'\\neq',  # \n_{e} q -> \neq
    r'\\?n_\{e\}q': r'\\neq',  # n_{e}q -> \neq (no spaces)
    
    # Dots/ldots patterns
    r'\\?l_\{d\}o_\{t\}s': r'\\ldots',
    r'\\?d_\{o\}t_\{s\}': r'\\ldots',
    
    # \forall pattern (for all) - handle spaces and mixed backslashes
    r'\\+f_\{o\}\\?r_\{a\}\\?l_\{l\}': r'\\forall',  # \f_{o}\r_{a}\l_{l} or \f_{o}r_{a}l_{l} -> \forall
    r'\\+f_\{o\}\s*r_\{a\}\s*l_\{l\}': r'\\forall',  # \f_{o} r_{a} l_{l} -> \forall (with spaces)
    r'\\+f_\{o\}r_\{a\}\s*l_\{l\}': r'\\forall',  # \f_{o}r_{a} l_{l} -> \forall (partial spacing)
    r'\\+f_\{o\}r_\{a\}l_\{l\}': r'\\forall',  # \f_{o}r_{a}l_{l} -> \forall (no spaces)
    r'\\?f_\{o\}r_\{a\}l_\{l\}': r'\\forall',  # f_{o}r_{a}l_{l} -> \forall (no spaces)
    
    # \quad pattern (quad space) - handle spaces
    r'\\+q_\{q\}\s*u_\{a\}\s*d': r'\\quad',  # \q_{q} u_{a} d -> \quad
    r'\\?q_\{q\}u_\{a\}d': r'\\quad',  # q_{q}u_{a}d -> \quad (no spaces)
    r'\\?q_\{u\}a_\{d\}': r'\\quad',   # Alternative pattern
    
    # \end{array} pattern - handle "end array" text
    # Pattern: \e_{n} d array (with space and plain "d" and "array")
    # Must handle: \\e_{n} d array (double backslash, space, d, space, array)
    r'\\+e_\{n\}\s+d\s+array': r'\\end\{array\}',  # \e_{n} d array -> \end{array} (with spaces)
    r'\\+e_\{n\}d\s+array': r'\\end\{array\}',  # \e_{n}d array -> \end{array}
    r'\\+e_\{n\}d\s+\\?a_\{r\}\\?r_\{a\}y': r'\\end\{array\}',  # \e_{n}d \a_{r}\r_{a}y -> \end{array}
    r'\\+e_\{n\}darray': r'\\end\{array\}',  # \e_{n}darray -> \end{array} (no space)
    r'\\?e_\{n\}d\s+array': r'\\end\{array\}',  # e_{n}d array -> \end{array}
    r'\\?e_\{n\}darray': r'\\end\{array\}',  # e_{n}darray -> \end{array} (no space)
    # Also handle case where "array" might be separate word after space normalization
    r'\\+e_\{n\}\s+d\s*array': r'\\end\{array\}',  # \e_{n} d array (flexible spacing)
    
    # Fix "array" text that's shredded: \a_{r}\r_{a}y -> array (must come before \end patterns)
    r'\\?a_\{r\}\\?r_\{a\}y': r'array',  # \a_{r}\r_{a}y -> array
    
    # \end pattern (generic fallback - must come after \end{array})
    r'\\+e_\{n\}\s+d(?!\s+array)': r'\\end ',  # \e_{n} d (not followed by array) -> \end
    r'\\+e_\{n\}d(?!\s+array)': r'\\end',  # \e_{n}d (not followed by array) -> \end
    r'\\?e_\{n\}d(?!\s+array)': r'\\end',  # e_{n}d (not followed by array) -> \end
}

# Generic letter-subscript pattern (a_{b} pairs)
LETTER_SUB_PATTERN = re.compile(r'([A-Za-z])_\{([A-Za-z0-9])\}')

# Pattern to detect runs of <mi> single letters (for MathML payload)
MI_SEQ_PATTERN = re.compile(r'(?:<mi>\s*([A-Za-z])\s*</mi>\s*){2,}', re.DOTALL | re.IGNORECASE)

# Minimal safe MathML wrapper using mtext fallback
def _wrap_as_mathml_from_latex(latex: str) -> str:
    esc = html.escape(latex)
    return (
        '<math xmlns="http://www.w3.org/1998/Math/MathML">'
        '<mrow><mtext>' + esc + '</mtext></mrow>'
        '</math>'
    )


# -----------------------
# Helpers
# -----------------------
def _is_well_formed_xml(s: str) -> bool:
    try:
        ET.fromstring(s)
        return True
    except Exception:
        return False


def _extract_text_from_mathml(mathml: str) -> str:
    """
    Extract meaningful textual payload from MathML. 
    Handles both <mtext> contents and structured MathML with shredded commands.
    Converts MathML structure to LaTeX-like text for recovery.
    """
    if not mathml:
        return ""
    try:
        root = ET.fromstring(mathml)
        # Find <mtext> in the MathML namespace
        mtext = root.find('.//{http://www.w3.org/1998/Math/MathML}mtext')
        if mtext is not None and mtext.text and mtext.text.strip():
            return mtext.text.strip()
        
        # No mtext: convert MathML structure to LaTeX-like text
        # This handles shredded commands in <msub> elements
        def extract_from_node(node, skip_children=False):
            """Recursively extract text from MathML nodes, handling structure."""
            parts = []
            tag = node.tag.split('}')[-1] if '}' in node.tag else node.tag
            
            if tag == 'msub' and not skip_children:
                # Handle shredded commands: <msub><mi>\m</mi><mrow><mi>a</mi></mrow></msub>
                base = node[0] if len(node) > 0 else None
                sub = node[1] if len(node) > 1 else None
                if base is not None and sub is not None:
                    base_text = (base.text or '').strip() if base.text else ''
                    # Get text from subscript (skip base to avoid duplication)
                    sub_text = ''
                    for sub_el in sub.iter():
                        if sub_el.text and sub_el.tag.split('}')[-1] in ['mi', 'mn']:
                            sub_text += sub_el.text.strip()
                    if base_text and sub_text:
                        # Convert to LaTeX-like pattern: \m_{a}
                        parts.append(f"\\{base_text}_{{{sub_text}}}")
                        return parts  # Skip processing children to avoid duplication
                    elif base_text:
                        parts.append(f"\\{base_text}")
                        return parts
            
            elif tag == 'mi' and not skip_children:
                text = (node.text or '').strip()
                if text:
                    # Always add text from <mi> tags, including backslash tokens
                    # The parent check prevents duplication when inside msub
                    parent_tag = None
                    try:
                        parent = list(node.iterancestors())[0] if list(node.iterancestors()) else None
                        if parent is not None:
                            parent_tag = parent.tag.split('}')[-1] if '}' in parent.tag else parent.tag
                    except:
                        pass
                    
                    # Add text if not inside msub (msub is handled separately)
                    if parent_tag != 'msub':
                        parts.append(text)
            
            elif tag == 'mo' and not skip_children:
                text = (node.text or '').strip()
                if text:
                    # Decode HTML entities
                    text = html.unescape(text)
                    parts.append(text)
            
            elif tag == 'mn' and not skip_children:
                text = (node.text or '').strip()
                if text:
                    parts.append(text)
            
            elif tag == 'mtext' and not skip_children:
                text = (node.text or '').strip()
                if text:
                    parts.append(text)
            
            # Process children only if we didn't handle this node specially
            if not skip_children:
                for child in node:
                    child_parts = extract_from_node(child, skip_children=(tag == 'msub'))
                    parts.extend(child_parts)
            
            return parts
        
        parts = extract_from_node(root)
        if parts:
            text = ' '.join(parts).strip()
            # Early detection: if we see many repeated patterns like \q_{q}u_{a}d, collapse them
            # This prevents the extraction from creating massive repetitions
            if text.count('\\q_{q}u_{a}d') > 10:
                # Collapse excessive repetitions early (keep max 2)
                text = re.sub(r'\\q_\{q\}u_\{a\}d(\s*\\q_\{q\}u_\{a\}d){5,}', 
                             r'\\q_{q}u_{a}d\\q_{q}u_{a}d', text)
            return text
    except Exception as exc:
        logger.debug(f"[FORCE] MathML extraction failed: {exc}")
    
    # fallback: naive strip tags
    s = re.sub(r'<[^>]+>', ' ', mathml)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _collapse_letter_subscripts(tex: str, log: List[str]) -> str:
    """
    Collapse sequences like m_{a}t_{h}r_{m} -> \\mathrm{math} (heuristic).
    Also handles complex patterns like m_{a}t_{h}r_{m}{e_{r}r_{o}r} -> \\mathrm{error}.
    """
    if not tex:
        return tex

    cur = tex
    changed = False

    # First, handle specific complex patterns using SHRED_REPAIR (applied in _repair_shredded_commands)
    # The SHRED_REPAIR patterns will handle: \m_{a}t_{h}r_{m}{e_{r}r_{o}r} -> \mathrm{error}
    # So we don't need a separate complex pattern matcher here

    # Then handle simple patterns: m_{a}t_{h}r_{m} -> \mathrm{math}
    simple_pattern = re.compile(r'(?:[A-Za-z]_\{[A-Za-z0-9]\}){2,}')
    
    def _merge_simple(match: re.Match) -> str:
        seq = match.group(0)
        pairs = re.findall(r'([A-Za-z])_\{([A-Za-z0-9])\}', seq)
        base = ''.join(a for a, b in pairs)
        subs = ''.join(b for a, b in pairs)
        candidate = base + subs
        if len(candidate) >= 2:
            return r'\mathrm{' + candidate + r'}'
        return seq

    for _ in range(3):
        new = simple_pattern.sub(_merge_simple, cur)
        if new == cur:
            break
        cur = new
        changed = True

    if changed:
        log.append("collapsed letter-by-letter subscript runs")
    return cur


def _repair_shredded_commands(tex: str, log: List[str]) -> str:
    """Attempt targeted repairs for common shredded OCR LaTeX fragments."""
    s = tex or ""
    
    # Special case: Handle \end{array} pattern BEFORE space normalization
    # Pattern: \e_{n} d array -> \end{array}
    s_before_special = s
    s = re.sub(r'\\+e_\{n\}\s+d\s+array', r'\\end{array}', s, flags=re.IGNORECASE)
    if s != s_before_special:
        log.append("repaired \\end{array} pattern (before space normalization)")
    
    # First, normalize spaces around subscript patterns to help pattern matching
    # Convert "\\m_{a} \t_{h} \b_{f}" or "\\m_{a} t_{h} b_{f}" to "\\m_{a}\t_{h}\b_{f}"
    # Handle both cases: with and without backslashes before letters
    # Pattern: letter_sub{...} space letter_sub{...} -> letter_sub{...}letter_sub{...}
    s_before = s
    # Remove spaces between letter_sub patterns (handles both \letter and plain letter)
    # Iteratively remove spaces to handle all cases
    for _ in range(3):  # Multiple passes to catch all spacing variations
        s_new = re.sub(r'([\\]?[a-z])\s*_\s*\{([^}]+)\}\s+([\\]?[a-z])\s*_\s*\{', r'\1_{\2}\3_{', s)
        if s_new == s:
            break
        s = s_new
    # Also handle sequences of 3+ letter_sub patterns
    s = re.sub(r'([\\]?[a-z])\s*_\s*\{([^}]+)\}\s+([\\]?[a-z])\s*_\s*\{([^}]+)\}\s+([\\]?[a-z])\s*_\s*\{', r'\1_{\2}\3_{\4}\5_{', s)
    # Handle "array" text after letter_sub patterns: \a_{r}\r_{a} y -> \a_{r}\r_{a}y (then we'll fix to array)
    s = re.sub(r'([\\]?[a-z])\s*_\s*\{([^}]+)\}\s*([\\]?[a-z])\s*_\s*\{([^}]+)\}\s+([a-z]+)', r'\1_{\2}\3_{\4}\5', s)
    # Remove spaces between backslash-letter patterns: \m \t \b -> \m\t\b
    s = re.sub(r'\\([a-z])\s+\\?([a-z])\s+\\?([a-z])', r'\\\1\\\2\\\3', s)
    if s != s_before:
        log.append("normalized spaces between letter-subscript patterns")
    
    # Apply SHRED_REPAIR patterns - apply multiple passes to catch all variations
    max_passes = 3
    for pass_num in range(max_passes):
        changed = False
        for pat, repl in SHRED_REPAIR.items():
            new, n = re.subn(pat, repl, s, flags=re.IGNORECASE)
            if n:
                if pass_num == 0:  # Only log on first pass to avoid spam
                    log.append(f"repaired shredded pattern {pat[:50]}... -> {repl} ({n} occurrences)")
                s = new
                changed = True
        if not changed:
            break

    # Collapse spaced characters in backslash-commands: "\ l e f t" -> "\left"
    # Step 1: replace sequences like '\ l e f t' or '\\ l e f t' etc.
    s_before = s
    s = re.sub(r'\\\s*([a-zA-Z])(?:\s+([a-zA-Z])){2,}', lambda m: '\\' + ''.join([m.group(1)] + [g for g in m.groups()[1:] if g]), s)
    # Step 2: collapse plain 'l e f t' to 'left' (only when preceded by backslash or inside LaTeX-like payload)
    # Use a simpler pattern without variable-width lookbehind
    s = re.sub(r'\\?\b(l)\s+e\s+f\s+t\b', r'\\left', s, flags=re.IGNORECASE)
    # fix '\ f r a c' style
    s, n = re.subn(r'\\\s*f\s*r\s*a\s*c', r'\\frac', s, flags=re.IGNORECASE)
    if n:
        log.append(f"collapsed spaced '\\ f r a c' -> '\\frac' ({n})")
    s, n = re.subn(r'\\\s*s\s*u\s*m', r'\\sum', s, flags=re.IGNORECASE)
    if n:
        log.append(f"collapsed spaced '\\ s u m' -> '\\sum' ({n})")

    # tidy repeated left/rights
    s = s.replace('\\left\\left', '\\left').replace('\\right\\right', '\\right')
    
    # Collapse repeated \quad patterns - OCR often produces many repeated \quad
    # Pattern: \quad\quad\quad... -> single \quad (or remove if excessive)
    s_before_quad = s
    # Collapse 2+ consecutive \quad into a single \quad
    s = re.sub(r'\\quad(\s*\\quad)+', r'\\quad', s)
    # If there are still many \quad patterns (more than 5), reduce to max 2
    quad_count = len(re.findall(r'\\quad', s))
    if quad_count > 5:
        # Replace excessive quads - keep only first 2, remove the rest
        # Split by \quad, keep first part, add max 2 quads, then join rest without quads
        parts = re.split(r'\\quad+', s)
        if len(parts) > 1:
            # Keep first part, add max 2 quads, then rest joined with space
            s = parts[0] + '\\quad\\quad' + ' '.join([p for p in parts[1:] if p.strip()])
            log.append(f"collapsed {quad_count} \\quad patterns to 2")
    
    if s != s_before:
        log.append("applied generic shredded-command cleanup")
    if s != s_before_quad:
        log.append("collapsed repeated \\quad patterns")

    return s


def _repair_common_ocr_symbols(tex: str, log: List[str]) -> str:
    """Fix common OCR symbol misrecognitions in a LaTeX-like payload."""
    s = tex or ""
    # ellipsis -> \ldots
    s, n = re.subn(r'\.{3,}', r'\\ldots', s)
    if n:
        log.append(f"converted {n} occurrences of '...' -> \\ldots")
    # common inequality fixes
    s, n = re.subn(r'\!\=', r'\\neq', s)
    if n:
        log.append(f"converted '!=' -> '\\neq' ({n})")
    s, n = re.subn(r'≤|<=', r'\\le', s)
    if n:
        log.append(f"converted <=/≤ -> '\\le' ({n})")
    s, n = re.subn(r'≥|>=', r'\\ge', s)
    if n:
        log.append(f"converted >=/≥ -> '\\ge' ({n})")
    # tidy whitespace and NBSPs
    s = s.replace('\u00A0', ' ')
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _try_latex_to_mathml(latex: str, log: List[str]) -> Tuple[str, float]:
    """Attempt conversion via latex2mathml; return (mathml, confidence_increment)."""
    if not latex:
        return "", 0.0
    if not HAS_LATEX2MATHML:
        log.append("latex2mathml not installed — skipping MathML conversion")
        return "", 0.0
    try:
        mathml = latex2mathml_convert(latex)
        log.append("latex2mathml conversion succeeded")
        return mathml, 0.9
    except Exception as exc:
        log.append(f"latex2mathml conversion failed: {exc}")
        return "", 0.0


# -----------------------
# FORCE Recovery Mode Detection
# -----------------------
def _detect_corruption_indicators(mathml: str) -> Tuple[bool, List[str]]:
    """Detect all corruption indicators. Returns (is_corrupted, reasons)."""
    reasons = []
    is_corrupted = False
    
    # Check for mtext with LaTeX
    if re.search(r'<mtext\b[^>]*>.*\\[A-Za-z]', mathml, re.IGNORECASE):
        reasons.append("mtext contains LaTeX commands")
        is_corrupted = True
    
    # Check for shredded letter sequences in <mi> tags
    if re.search(r"(?:<mi>\s*\\?[a-zA-Z]\s*</mi>\s*){4,}", mathml):
        reasons.append("shredded letter sequences in <mi> tags")
        is_corrupted = True
    
    # Check for letter-by-letter subscript patterns
    if re.search(r'[a-z]_\{[a-z0-9]\}[a-z]_\{[a-z0-9]\}', mathml):
        reasons.append("letter-by-letter subscript patterns")
        is_corrupted = True
    
    # Check for backslash tokens in tags
    if re.search(r"<m[iot][^>]*>\\[A-Za-z]", mathml):
        reasons.append("backslash tokens in MathML tags")
        is_corrupted = True
    
    # Check for double-escaped LaTeX
    if "\\\\left" in mathml or "\\\\right" in mathml or "\\\\frac" in mathml:
        reasons.append("double-escaped LaTeX commands")
        is_corrupted = True
    
    # Check for shredded command patterns
    shredded_patterns = [
        r"l\s*e\s*f\s*t", r"r\s*i\s*g\s*h\s*t", r"s\s*u\s*m", 
        r"f\s*r\s*a\s*c", r"m\s*a\s*t\s*h\s*b\s*b"
    ]
    for pattern in shredded_patterns:
        if re.search(pattern, mathml, re.IGNORECASE):
            reasons.append(f"shredded pattern: {pattern}")
            is_corrupted = True
            break
    
    return is_corrupted, reasons


# -----------------------
# FORCE mtext Extraction
# -----------------------
def _force_extract_mtext_latex(mathml: str) -> str:
    """Extract LaTeX from <mtext> tags, handling $...$ delimiters."""
    # First try to find <mtext> content
    mtext_match = re.search(r'<mtext[^>]*>(.*?)</mtext>', mathml, re.DOTALL | re.IGNORECASE)
    if mtext_match:
        content = mtext_match.group(1)
        # Unescape HTML entities
        content = html.unescape(content)
        # Extract $...$ if present
        dollar_match = re.search(r'\$([^$]+)\$', content)
        if dollar_match:
            return dollar_match.group(1).strip()
        return content.strip()
    return ""


# -----------------------
# Main ULTRA FORCE function
# -----------------------
def ultra_mathml_recover(
    corrupted_mathml: str,
    force_mode: bool = True,
    use_openai_fallback: bool = False,
    openai_api_key: str | None = None,
    openai_model: str = "gpt-4o-mini"
) -> Dict:
    """
    FORCE ULTRA MathML Recovery Engine
    
    ALWAYS attempts to reconstruct LaTeX from corrupted MathML.
    NEVER returns raw shredded MathML.
    
    Args:
        corrupted_mathml: Input MathML (may be corrupted)
        force_mode: If True, always attempt recovery even for seemingly valid MathML
    
    Returns:
        {
            "latex": "<reconstructed LaTeX>",
            "mathml": "<valid MathML or safe mtext wrapper>",
            "confidence": float(0..1),
            "log": [str, ...],
            "before_latex": "<original extracted text>",
            "after_latex": "<repaired LaTeX>",
            "corruption_detected": bool,
            "corruption_reasons": [str, ...]
        }
    """
    log: List[str] = []
    confidence = 0.0
    before_latex = ""
    after_latex = ""
    corruption_detected = False
    corruption_reasons = []

    if not corrupted_mathml or not corrupted_mathml.strip():
        log.append("[FORCE] empty input")
        return {
            "latex": "", 
            "mathml": "", 
            "confidence": 0.0, 
            "log": log,
            "before_latex": "",
            "after_latex": "",
            "corruption_detected": False,
            "corruption_reasons": []
        }

    raw = corrupted_mathml.strip()
    log.append(f"[FORCE] input length={len(raw)}")
    
    # FORCE MODE: Always check for corruption indicators
    if force_mode:
        corruption_detected, corruption_reasons = _detect_corruption_indicators(raw)
        if corruption_detected:
            log.append(f"[FORCE] corruption detected: {', '.join(corruption_reasons)}")
        else:
            log.append("[FORCE] no obvious corruption indicators, but checking anyway")
    
    # FORCE MODE: Always extract and attempt recovery if mtext with LaTeX is found
    contains_mtext = bool(re.search(r'<mtext\b', raw, flags=re.IGNORECASE))
    contains_backslash = bool(re.search(r'\\[A-Za-z]', raw))
    
    if contains_mtext and contains_backslash:
        log.append("[FORCE] detected LaTeX in <mtext> - extracting and repairing")
        before_latex = _force_extract_mtext_latex(raw)
        if before_latex:
            log.append(f"[FORCE] extracted LaTeX from mtext: {before_latex[:100]!r}")
            # Use extracted LaTeX as payload
            payload = before_latex
            confidence += 0.1
        else:
            # Fallback to general extraction
            payload = _extract_text_from_mathml(raw)
            log.append(f"[FORCE] extracted payload len={len(payload)}: {payload[:160]!r}")
    else:
        # Check if it's well-formed MathML without corruption
        if not force_mode and not corruption_detected:
            try:
                root = ET.fromstring(raw)
                tags = [ (el.tag if isinstance(el.tag, str) else "") for el in root.iter() ]
                tag_join = " ".join(tags).lower()
                has_structural = any(x in tag_join for x in ("mfrac", "mrow", "msup", "msub", "mo"))
                shredded_indicators = bool(re.search(r'([a-z]\s+){2,}[a-z]', raw, flags=re.IGNORECASE)) or bool(re.search(r'\\?_[{]', raw))
                if has_structural and not shredded_indicators:
                    log.append("[FORCE] well-formed structural MathML (no recovery needed)")
                    return {
                        "latex": "", 
                        "mathml": raw, 
                        "confidence": 0.8, 
                        "log": log,
                        "before_latex": "",
                        "after_latex": "",
                        "corruption_detected": False,
                        "corruption_reasons": []
                    }
            except Exception as exc:
                log.append(f"[FORCE] XML parse failed: {exc}; proceeding to recovery")
        
        # Extract textual payload
        payload = _extract_text_from_mathml(raw)
        log.append(f"[FORCE] extracted payload len={len(payload)}: {payload[:160]!r}")
        before_latex = payload

    # Extract textual payload to operate on
    payload = _extract_text_from_mathml(raw)
    log.append(f"extracted payload len={len(payload)}: {payload[:160]!r}")

    # Extract LaTeX delimiters if present
    m = re.search(r'\$([^$]+)\$', payload)
    if m:
        payload = m.group(1).strip()
        log.append("[FORCE] extracted $...$ LaTeX payload")
        confidence += 0.05
    else:
        m2 = re.search(r'\\\((.+?)\\\)', payload)
        if m2:
            payload = m2.group(1).strip()
            log.append("[FORCE] extracted \\( .. \\) LaTeX payload")
            confidence += 0.05
        else:
            m3 = re.search(r'\\\[(.+?)\\\]', payload, flags=re.DOTALL)
            if m3:
                payload = m3.group(1).strip()
                log.append("[FORCE] extracted \\[ .. \\] LaTeX payload")
                confidence += 0.05

    # FORCE RECOVERY PIPELINE - Always attempt full reconstruction
    candidate = payload
    log.append(f"[FORCE] starting recovery pipeline on: {candidate[:100]!r}")

    # 1) First repair specific shredded command patterns (before collapsing)
    # This ensures patterns like \m_{a}t_{h}r_{m}{e_{r}r_{o}r} are matched correctly
    candidate_before = candidate
    candidate = _repair_shredded_commands(candidate, log)
    if candidate != candidate_before:
        log.append(f"[FORCE] after shredded command repair: {candidate[:100]!r}")

    # 2) Then collapse remaining letter-by-letter subscript runs like m_{a}t_{h}...
    candidate_before = candidate
    candidate = _collapse_letter_subscripts(candidate, log)
    if candidate != candidate_before:
        log.append(f"[FORCE] after letter subscript collapse: {candidate[:100]!r}")

    # 3) Repair common OCR symbols and spacing
    candidate_before = candidate
    candidate = _repair_common_ocr_symbols(candidate, log)
    if candidate != candidate_before:
        log.append(f"[FORCE] after OCR symbol repair: {candidate[:100]!r}")
    
    # 3.5) Collapse excessive repeated patterns (especially \quad)
    candidate_before = candidate
    # Remove excessive \quad repetitions (more than 2 consecutive)
    candidate = re.sub(r'\\quad(\s*\\quad){2,}', r'\\quad\\quad', candidate)
    # If still too many quads overall, limit to reasonable amount
    quad_matches = list(re.finditer(r'\\quad', candidate))
    if len(quad_matches) > 10:
        # Keep first 2 quads, remove excessive ones
        parts = re.split(r'\\quad+', candidate)
        if len(parts) > 1:
            candidate = parts[0] + '\\quad\\quad' + ' '.join([p.strip() for p in parts[1:] if p.strip()])
            log.append(f"[FORCE] collapsed excessive \\quad patterns (had {len(quad_matches)})")
    if candidate != candidate_before:
        log.append(f"[FORCE] after excessive pattern collapse: {candidate[:100]!r}")

    # 4) If candidate has many single letters separated by spaces, join plausible tokens
    #    e.g., "l e f t" -> "left" (when preceded by backslash or in LaTeX context)
    def _join_spaced_letters(s: str) -> str:
        # join runs of single letters (2+) separated by spaces into a single token
        return re.sub(r'\b([A-Za-z])(?:\s+([A-Za-z])){2,}\b', lambda m: ''.join([m.group(1)] + [g for g in m.groups()[1:] if g]), s)
    joined = _join_spaced_letters(candidate)
    if joined != candidate:
        log.append("joined spaced letter runs into tokens")
        candidate = joined

    # 5) Ensure basic balanced braces/parentheses to avoid conversion crashes
    openb = candidate.count('{')
    closeb = candidate.count('}')
    if openb > closeb:
        candidate += '}' * (openb - closeb)
        log.append(f"balanced braces by appending {openb - closeb} '}}'")
    elif closeb > openb:
        candidate = '{' * (closeb - openb) + candidate
        log.append(f"balanced braces by prepending {closeb - openb} '{{'")

    openp = candidate.count('(')
    closep = candidate.count(')')
    if openp > closep:
        candidate += ')' * (openp - closep)
        log.append(f"balanced parentheses by appending {openp - closep} ')'")
    elif closep > openp:
        candidate = '(' * (closep - openp) + candidate
        log.append(f"balanced parentheses by prepending {closep - openp} '('")

    candidate = candidate.strip().rstrip(',')

    # Store after_latex for debugging
    after_latex = candidate
    
    # Decide if payload already looks LaTeX-ish
    if re.search(r'\\(sum|frac|left|right|Pr|bigcup|neq|ldots|mathrm|mathbb|[a-zA-Z]+)', candidate):
        log.append("[FORCE] payload contains LaTeX-like commands — treating as LaTeX")
        confidence += 0.15
    else:
        log.append("[FORCE] payload not strongly LaTeX; treating as loose LaTeX candidate")
        confidence += 0.05

    # FORCE: Always try to convert to MathML
    log.append(f"[FORCE] attempting LaTeX→MathML conversion on: {candidate[:100]!r}")
    mathml_out, conv_conf = _try_latex_to_mathml(candidate, log)
    confidence += conv_conf

    # FORCE: If conversion failed, attempt aggressive second-pass repairs
    if not mathml_out:
        log.append("[FORCE] first conversion attempt failed, trying second-pass repairs")
        # collapse spaced backslash commands one more time
        s = candidate
        s2, n = re.subn(r'\\\s*([a-zA-Z])\s*([a-zA-Z])\s*([a-zA-Z])\s*([a-zA-Z])', r'\\\1\2\3\4', s)
        if n:
            log.append(f"[FORCE] second-pass collapsed spaced backslash-commands ({n})")
            candidate = s2
            after_latex = candidate
            mathml_out, conv_conf = _try_latex_to_mathml(candidate, log)
            confidence += conv_conf
        
        # If still failed, try one more aggressive repair pass
        if not mathml_out:
            log.append("[FORCE] second-pass also failed, trying third-pass aggressive repairs")
            # Remove extra spaces around commands
            candidate = re.sub(r'\\\s+([a-zA-Z]+)', r'\\\1', candidate)
            # Fix common broken patterns
            candidate = re.sub(r'\\mathrm\{([^}]+)\}', lambda m: r'\mathrm{' + m.group(1).replace(' ', '') + '}', candidate)
            after_latex = candidate
            mathml_out, conv_conf = _try_latex_to_mathml(candidate, log)
            confidence += conv_conf

    # FORCE: Try OpenAI fallback if enabled and rule-based recovery failed
    if not mathml_out and use_openai_fallback and HAS_OPENAI and OpenAIMathMLConverter:
        try:
            log.append("[FORCE] attempting OpenAI fallback for MathML conversion")
            converter = OpenAIMathMLConverter(
                api_key=openai_api_key,
                model=openai_model
            )
            ai_result = converter.convert_corrupted_mathml(
                corrupted_mathml if not candidate else f"<math><mtext>${candidate}$</mtext></math>",
                target_format="mathml",
                include_latex=True
            )
            if ai_result.get("mathml"):
                mathml_out = ai_result["mathml"]
                if ai_result.get("latex"):
                    candidate = ai_result["latex"]
                confidence = max(confidence, ai_result.get("confidence", 0.7))
                log.append(f"[FORCE] OpenAI fallback succeeded (confidence: {ai_result.get('confidence', 0.7):.3f})")
            else:
                log.append("[FORCE] OpenAI fallback returned no MathML")
        except Exception as exc:
            log.append(f"[FORCE] OpenAI fallback failed: {exc}")
            logger.debug("OpenAI fallback error", exc_info=True)
    
    # FORCE: Final fallback - NEVER return raw shredded MathML
    if not mathml_out:
        log.append("[FORCE] all conversion attempts failed, using safe <mtext> wrapper")
        mathml_out = _wrap_as_mathml_from_latex(candidate)
        confidence += 0.05
        log.append("[FORCE] WARNING: Using mtext fallback - LaTeX may need manual review")

    # clamp confidence
    if confidence > 1.0:
        confidence = 1.0

    out = {
        "latex": candidate,
        "mathml": mathml_out,
        "confidence": float(round(confidence, 3)),
        "log": log,
        "before_latex": before_latex,
        "after_latex": after_latex,
        "corruption_detected": corruption_detected,
        "corruption_reasons": corruption_reasons,
    }

    logger.info("[FORCE ULTRA] recovery finished: confidence=%.3f, steps=%d, corruption=%s", 
                out["confidence"], len(log), corruption_detected)
    if corruption_detected:
        logger.info("[FORCE ULTRA] corruption reasons: %s", ', '.join(corruption_reasons))
    logger.debug("[FORCE ULTRA] before: %s", before_latex[:200] if before_latex else "N/A")
    logger.debug("[FORCE ULTRA] after: %s", after_latex[:200] if after_latex else "N/A")
    
    return out
