"""
ULTRA-FORCE MathML Recovery Engine
---------------------------------

This variant ALWAYS reconstructs, even when MathML is clean.

Use for:
    - High-recall OCR pipelines
    - Standardizing all equations (clean or corrupt)
    - ML pipelines that expect both LaTeX + rebuilt MathML

Behavior:
    - Extracts payload from ANY MathML
    - Rebuilds shredded LaTeX pieces
    - Always attempts LaTeX → MathML conversion
    - Ensures structural, standard MathML output
"""

from __future__ import annotations
import re
import xml.etree.ElementTree as ET
import html
from typing import Dict, List, Tuple

from core.logger import logger

try:
    from latex2mathml.converter import convert as latex2mathml_convert
    HAS_LATEX2MATHML = True
except Exception:
    HAS_LATEX2MATHML = False
    logger.warning("latex2mathml unavailable — FORCE engine will use <mtext> wrappers")

# ------------------------
# Repair maps
# ------------------------
SHRED_REPAIR = {
    r'm_\{a\}t_\{h\}b_\{b\}': r'\\mathbb',
    r'm_\{a\}t_\{h\}': r'\\math',
    r'l_\{e\}f_\{t\}': r'\\left',
    r'r_\{i\}g_\{h\}t\}?': r'\\right',
    r's_\{u\}m': r'\\sum',
    r'f_\{r\}a_\{c\}': r'\\frac',
    r'p_\{r\}': r'\\Pr',
    r'b_\{i\}g_\{c\}u_\{p\}': r'\\bigcup',
    r'n_\{e\}q': r'\\neq',
    r'l_\{d\}o_\{t\}s': r'\\ldots',
}

# ------------------------
# Helpers
# ------------------------
def _extract_text_from_mathml(mathml: str) -> str:
    if not mathml:
        return ""
    try:
        root = ET.fromstring(mathml)
        # Prefer <mtext>
        for el in root.iter():
            if el.tag.endswith("mtext") and el.text:
                return el.text.strip()
        # Otherwise collect all text
        parts = []
        for el in root.iter():
            if el.text and el.text.strip():
                parts.append(el.text.strip())
        return " ".join(parts).strip()
    except Exception:
        return re.sub(r'<[^>]+>', ' ', mathml).strip()


def _collapse_letter_runs(tex: str, log: List[str]) -> str:
    pattern = re.compile(r'(?:[A-Za-z]_\{[A-Za-z0-9]\}){2,}')
    def _merge(m):
        seq = m.group(0)
        pairs = re.findall(r'([A-Za-z])_\{([A-Za-z0-9])\}', seq)
        combined = ''.join(a for a, _ in pairs) + ''.join(b for _, b in pairs)
        return r'\mathrm{' + combined + '}'
    new = pattern.sub(_merge, tex)
    if new != tex:
        log.append("collapsed shredded letter-subscript runs")
    return new


def _repair_shreds(tex: str, log: List[str]) -> str:
    s = tex
    for pat, repl in SHRED_REPAIR.items():
        new, n = re.subn(pat, repl, s)
        if n:
            log.append(f"patched shredded: {pat} → {repl} ({n}x)")
            s = new

    # Fix spaced commands like "\ f r a c"
    s, n = re.subn(r'\\\s*f\s*r\s*a\s*c', r'\\frac', s)
    if n:
        log.append("repaired spaced \\frac")

    s, n = re.subn(r'\\\s*s\s*u\s*m', r'\\sum', s)
    if n:
        log.append("repaired spaced \\sum")

    return s


def _repair_symbols(tex: str, log: List[str]) -> str:
    s = tex

    # ellipsis
    s, n = re.subn(r'\.{3,}', r'\\ldots', s)
    if n: log.append("converted '...' → \\ldots")

    # inequalities
    s, n = re.subn(r'!=', r'\\neq', s)
    if n: log.append("converted != → \\neq")

    s, n = re.subn(r'≤|<=', r'\\le', s)
    if n: log.append("converted <= → \\le")

    s, n = re.subn(r'≥|>=', r'\\ge', s)
    if n: log.append("converted >= → \\ge")

    return " ".join(s.split())


def _try_convert(latex: str, log: List[str]) -> Tuple[str, float]:
    if not latex:
        return "", 0.0
    if not HAS_LATEX2MATHML:
        log.append("latex2mathml not installed — using wrapper fallback")
        return "", 0.0
    try:
        m = latex2mathml_convert(latex)
        log.append("latex2mathml succeeded")
        return m, 0.9
    except Exception as e:
        log.append(f"latex2mathml failed: {e}")
        return "", 0.0


def _wrap_mtext(latex: str) -> str:
    return (
        '<math xmlns="http://www.w3.org/1998/Math/MathML">'
        '<mrow><mtext>' + html.escape(latex) + '</mtext></mrow></math>'
    )


# ----------------------------------------------------------
# MAIN FORCE ENGINE
# ----------------------------------------------------------
def ultra_mathml_recover_force(any_mathml: str) -> Dict:
    """
    FORCE variant:
    ALWAYS reconstructs from text, regardless of input quality.
    Never returns the input MathML directly.
    """

    log: List[str] = []
    confidence = 0.0

    if not any_mathml or not any_mathml.strip():
        return {"latex": "", "mathml": "", "confidence": 0.0, "log": ["empty input"]}

    raw = any_mathml.strip()
    log.append(f"received length={len(raw)}")

    # --------------------------------------------------
    # STEP 1 — Extract textual payload from MathML
    # --------------------------------------------------
    payload = _extract_text_from_mathml(raw)
    log.append(f"payload extracted={payload[:120]!r}")

    # Extract $...$
    m = re.search(r'\$([^$]+)\$', payload)
    if m:
        payload = m.group(1)
        log.append("found $...$ LaTeX block")

    # --------------------------------------------------
    # STEP 2 — Heuristic reconstruction pipeline
    # --------------------------------------------------
    candidate = payload

    candidate = _collapse_letter_runs(candidate, log)
    candidate = _repair_shreds(candidate, log)
    candidate = _repair_symbols(candidate, log)

    # Join "l e f t" → "left"
    candidate = re.sub(
        r'\b([A-Za-z])(?:\s+([A-Za-z])){2,}\b',
        lambda m: ''.join([m.group(1)] + [g for g in m.groups()[1:] if g]),
        candidate
    )

    # Balance braces
    diff = candidate.count('{') - candidate.count('}')
    if diff > 0:
        candidate += '}' * diff
        log.append(f"balanced {diff} braces")
    elif diff < 0:
        candidate = '{' * (-diff) + candidate
        log.append(f"prepended {-diff} braces")

    candidate = candidate.strip().rstrip(',')

    # --------------------------------------------------
    # STEP 3 — Convert LaTeX → MathML (forced)
    # --------------------------------------------------
    mathml_out, conv_conf = _try_convert(candidate, log)
    confidence += conv_conf

    if not mathml_out:
        # fallback
        mathml_out = _wrap_mtext(candidate)
        confidence += 0.05
        log.append("used <mtext> fallback")

    if confidence > 1.0:
        confidence = 1.0

    # --------------------------------------------------
    # RETURN FORCE RESULT
    # --------------------------------------------------
    return {
        "latex": candidate,
        "mathml": mathml_out,
        "confidence": round(confidence, 3),
        "log": log
    }
