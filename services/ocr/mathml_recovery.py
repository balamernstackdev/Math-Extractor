"""
mathml_recovery_pro.py — ULTRA MathML recovery engine (rules + heuristics + multi-pass)

Provides:
    - ultra_mathml_recover(broken_mathml: str) -> dict
    - recover_from_corrupted_mathml(...) alias for compatibility

Return schema (dict):
{
    "mathml": "<math ...>...</math>",       # best-effort cleaned MathML (may be "")
    "latex": "LaTeX string (best-effort)", # best-effort LaTeX (may be "")
    "confidence": 0.0..1.0,                # heuristic confidence score
    "log": ["step1 ...", "step2 ...", ...] # trace of operations
}
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple

from core.logger import logger

# Optional validator/converter
try:
    from latex2mathml.converter import convert as latex2mathml_convert  # type: ignore
    HAS_LATEX2MATHML = True
except Exception:
    HAS_LATEX2MATHML = False
    logger.debug("latex2mathml not available — recovery will skip LaTeX validation")

# Known command words that often get shredded into single-letter <mi> nodes.
# Map textual reconstructed token -> LaTeX replacement
_COMMAND_MAP = {
    "left": r"\left",
    "right": r"\right",
    "sum": r"\sum",
    "prod": r"\prod",
    "int": r"\int",
    "frac": r"\frac",
    "ldots": r"\ldots",
    "cdot": r"\cdot",
    "mathbb": r"\mathbb",
    "mathrm": r"\mathrm",
    "Pr": r"\Pr",
    "neq": r"\neq",
    "le": r"\le",
    "ge": r"\ge",
    "in": r"\in",
    # Add more as you see shredded in your pipeline
}

# Patterns that indicate shredded command sequences (letters separated/individual <mi>)
_SHREDDED_INDICATORS = [
    r"l\s*e\s*f\s*t",
    r"r\s*i\s*g\s*h\s*t",
    r"f\s*r\s*a\s*c",
    r"s\s*u\s*m",
    r"m\s*a\s*t\s*h\s*b\s*b",
    r"c\s*d\s*o\s*t",
    r"l\s*d\s*o\s*t\s*s",
]

# Heuristics parameters
_MIN_SINGLE_MI_SEQ = 3  # minimum consecutive single-letter mi nodes to consider collapsing
_MAX_LOG_ENTRIES = 200


def ultra_mathml_recover(broken_mathml: str) -> Dict:
    """
    Attempt to recover a corrupted MathML fragment into cleaned MathML and LaTeX.

    Returns:
        dict with keys: mathml, latex, confidence, log
    """
    log: List[str] = []
    if not broken_mathml or not broken_mathml.strip():
        log.append("empty input")
        return {"mathml": "", "latex": "", "confidence": 0.0, "log": log}

    # 1) Quick sanity - if well-formed and looks good, return early (clean path)
    try:
        root = ET.fromstring(broken_mathml)
        # If well-formed and contains structural tags, and doesn't look shredded, return it
        if _looks_structural(root) and not _contains_shredded_patterns(broken_mathml):
            log.append("input well-formed and structural — returning original MathML")
            return {"mathml": broken_mathml, "latex": "", "confidence": 0.9, "log": log}
    except ET.ParseError as e:
        log.append(f"XML parse failed: {e}")

    # 2) Multi-pass reconstruction
    # Pass A: attempt to extract a LaTeX-like string by collapsing sequences of <mi> single letters
    try:
        tokens, provenance = _extract_tokens_from_raw_xml(broken_mathml)
        log.append(f"extracted {len(tokens)} tokens from XML (provenance: {provenance})")
    except Exception as exc:
        log.append(f"token extraction failed: {exc}")
        tokens = []
        provenance = "extraction-error"

    # Pass B: collapse shredded letter sequences into commands / words
    try:
        collapsed, collapse_log = _collapse_shredded_tokens(tokens)
        log.extend(collapse_log)
    except Exception as exc:
        collapsed = tokens
        log.append(f"collapse_shredded_tokens failed: {exc}")

    # Pass C: build LaTeX from collapsed token stream (best-effort)
    try:
        latex_candidate = _tokens_to_latex(collapsed)
        log.append(f"built LaTeX candidate (len={len(latex_candidate)}): {latex_candidate[:200]!r}")
    except Exception as exc:
        latex_candidate = ""
        log.append(f"_tokens_to_latex failed: {exc}")

    # Pass D: validate/canonicalize LaTeX and convert to MathML (if possible)
    mathml_candidate = ""
    confidence = 0.0
    if latex_candidate:
        if HAS_LATEX2MATHML:
            try:
                mathml_candidate = latex2mathml_convert(latex_candidate)
                confidence = _estimate_confidence_from_transforms(broken_mathml, latex_candidate, mathml_candidate)
                log.append("latex2mathml conversion succeeded")
            except Exception as exc:
                log.append(f"latex2mathml conversion failed: {exc}")
                # fallback: try to minimally sanitize latex and attempt again once
                latex_sanitized = _sanitize_latex(latex_candidate)
                try:
                    mathml_candidate = latex2mathml_convert(latex_sanitized)
                    latex_candidate = latex_sanitized
                    confidence = _estimate_confidence_from_transforms(broken_mathml, latex_candidate, mathml_candidate) * 0.8
                    log.append("latex2mathml conversion succeeded after sanitization")
                except Exception as exc2:
                    log.append(f"latex2mathml conversion still failed after sanitization: {exc2}")
                    mathml_candidate = ""
        else:
            log.append("latex2mathml unavailable — returning LaTeX candidate without MathML")
            confidence = 0.35

    # Pass E: If no latex candidate produced, try best-effort XML repairs
    if not mathml_candidate and not latex_candidate:
        try:
            repaired_xml = _repair_malformed_xml(broken_mathml)
            if repaired_xml:
                log.append("attempted XML repair; testing structural heuristics")
                try:
                    # ensure well-formed
                    ET.fromstring(repaired_xml)
                    mathml_candidate = repaired_xml
                    confidence = 0.25
                    log.append("XML repair produced well-formed MathML (low confidence)")
                except ET.ParseError:
                    log.append("XML repair did not produce well-formed XML")
        except Exception as exc:
            log.append(f"XML repair failed: {exc}")

    # Final heuristics: bump confidence if many fixes were small
    if mathml_candidate:
        confidence = min(0.99, max(confidence, 0.2))
    elif latex_candidate:
        confidence = max(confidence, 0.15)
    else:
        confidence = 0.0

    # Limit log length
    if len(log) > _MAX_LOG_ENTRIES:
        log = log[:_MAX_LOG_ENTRIES] + ["...truncated log..."]

    return {
        "mathml": mathml_candidate,
        "latex": latex_candidate,
        "confidence": float(confidence),
        "log": log,
    }


# --- Helper functions -------------------------------------------------


def _looks_structural(root: ET.Element) -> bool:
    """Return True if parsed MathML element contains structural tags indicative of proper MathML."""
    structural_tags = {"mfrac", "msub", "msup", "mrow", "munder", "mover", "mo", "mi", "mn", "msubsup", "mstyle"}
    for el in root.iter():
        tag = el.tag.lower()
        # remove namespace if present
        if "}" in tag:
            tag = tag.split("}", 1)[1]
        if tag in structural_tags:
            return True
    return False


def _contains_shredded_patterns(text: str) -> bool:
    """Quick check for the presence of shredded letter patterns."""
    for pat in _SHREDDED_INDICATORS:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def _extract_tokens_from_raw_xml(xml_text: str) -> Tuple[List[Dict], str]:
    """
    Parse MathML-ish text and return a token stream.
    Token: dict with fields {type: "mi"|"mo"|"mtext"|"other", text: str}
    Provenance string explains which path was used: 'etree' or 'strip'
    """
    tokens: List[Dict] = []
    try:
        root = ET.fromstring(xml_text)
        provenance = "etree"
        for node in root.iter():
            tag = node.tag
            if "}" in tag:
                tag = tag.split("}", 1)[1]
            tag = tag.lower()
            text = (node.text or "").strip()
            if tag == "mi":
                tokens.append({"type": "mi", "text": text})
            elif tag == "mo":
                tokens.append({"type": "mo", "text": text})
            elif tag == "mn":
                tokens.append({"type": "mn", "text": text})
            elif tag == "mtext":
                tokens.append({"type": "mtext", "text": text})
            else:
                # pick up visible tail text if present
                tail = (node.tail or "").strip()
                if tail:
                    tokens.append({"type": "text", "text": tail})
        return tokens, provenance
    except ET.ParseError:
        # fallback: very noisy OCR output — strip tags and heuristically split
        provenance = "strip"
        # Grab content inside tags and also plain letters
        content = re.sub(r"<[^>]+>", " ", xml_text)
        # Normalize whitespace
        content = re.sub(r"\s+", " ", content).strip()
        # Tokenize by space and punctuation, but preserve single letters
        parts = re.findall(r"\\?[A-Za-z]+|\\?.|[0-9]+|[^\s]", content)
        for p in parts:
            if re.fullmatch(r"[A-Za-z]", p):
                tokens.append({"type": "mi", "text": p})
            elif re.fullmatch(r"[0-9]+", p):
                tokens.append({"type": "mn", "text": p})
            else:
                tokens.append({"type": "mo", "text": p})
        return tokens, provenance


def _collapse_shredded_tokens(tokens: List[Dict]) -> Tuple[List[Dict], List[str]]:
    """
    Collapse sequences of single-letter <mi> tokens into words and map them to LaTeX commands where applicable.

    Returns (collapsed_tokens, log_lines)
    """
    out: List[Dict] = []
    i = 0
    n = len(tokens)
    log: List[str] = []
    while i < n:
        t = tokens[i]
        # Collapse runs of single-letter mi tokens
        if t["type"] == "mi":
            run_chars = [t["text"]]
            j = i + 1
            while j < n and tokens[j]["type"] == "mi" and len(tokens[j]["text"]) == 1:
                run_chars.append(tokens[j]["text"])
                j += 1
            if len(run_chars) >= _MIN_SINGLE_MI_SEQ:
                word = "".join(run_chars)
                lowered = word.lower()
                # If word matches a known command -> replace with a single token (mo? or mi representing command)
                if lowered in _COMMAND_MAP:
                    out.append({"type": "command", "text": _COMMAND_MAP[lowered], "raw": word})
                    log.append(f"collapsed shredded letters '{word}' -> command {_COMMAND_MAP[lowered]}")
                else:
                    # Heuristic: if the run looks like 'math' or 'left' etc, produce \mathrm{...} or plain identifier
                    if lowered.isalpha() and len(lowered) >= 3:
                        # If all letters, consider it's a word, use \mathrm{word}
                        out.append({"type": "mi_word", "text": word})
                        log.append(f"collapsed letters '{word}' -> mi_word")
                    else:
                        # fallback: push each back as individual
                        for ch in run_chars:
                            out.append({"type": "mi", "text": ch})
                i = j
                continue
            else:
                # single or two-letter run -> keep as individual mi tokens
                out.append(t)
                i += 1
                continue
        else:
            out.append(t)
            i += 1
    return out, log


def _tokens_to_latex(tokens: List[Dict]) -> str:
    """
    Convert a token stream to a best-effort LaTeX string.

    Strategy:
    - Commands tokens (type "command") are inserted as-is.
    - mi_word -> \mathrm{word}
    - mi -> token.text
    - mo -> token.text (escaped if necessary)
    - mn -> number
    - Simple heuristics for subscripts/superscripts if encountered in sequence like X i -> X_i
    """
    out_parts: List[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        t = tokens[i]
        typ = t.get("type")
        txt = (t.get("text") or "").strip()
        if typ == "command":
            out_parts.append(txt)
        elif typ == "mi_word":
            # use \mathrm{name}
            safe = re.sub(r"[^A-Za-z0-9_]", "", txt)
            out_parts.append(r"\mathrm{" + safe + "}")
        elif typ == "mi":
            # If next token is a single-letter mi, maybe "X i" meaning X_i
            # but don't assume; we only convert when pattern fits: <mi X><mi i> and next not mo
            if i + 1 < n and tokens[i + 1]["type"] == "mi" and len(tokens[i + 1]["text"]) == 1:
                base = txt
                sub = tokens[i + 1]["text"]
                out_parts.append(f"{base}_{{{sub}}}")
                i += 1  # skip next
            else:
                out_parts.append(txt)
        elif typ == "mn":
            out_parts.append(txt)
        elif typ == "mo":
            # Escape backslashes and braces in mo
            out_parts.append(txt)
        else:
            out_parts.append(txt)
        i += 1
    # Join with spaces but normalize common patterns
    latex = " ".join(p for p in out_parts if p)
    latex = re.sub(r"\s+\\", r" \\", latex)  # keep backslash tokens tidy
    latex = re.sub(r"\s+", " ", latex).strip()
    # Some heuristic replacements: "mi_word" often should be inside parentheses or commands
    latex = _post_process_latex(latex)
    return latex


def _post_process_latex(latex: str) -> str:
    # Fix duplicated spaces, handle sequences like '\left [' -> '\left['
    s = latex.replace("\\left [", "\\left[").replace("\\right ]", "\\right]")
    s = s.replace("\\left (", "\\left(").replace("\\right )", "\\right)")
    # If we produced things like 'X_{i} [' fix space
    s = re.sub(r"_\{([^\}]+)\}\s+\[", r"_{\1}[", s)
    return s


def _sanitize_latex(latex: str) -> str:
    # Remove stray unescaped characters that commonly break latex2mathml
    s = latex
    # Convert common textual ellipsis
    s = s.replace("....", r"\ldots").replace("...", r"\ldots")
    # Remove control characters
    s = re.sub(r"[\x00-\x1f]", "", s)
    # Ensure balanced braces
    open_b = s.count("{")
    close_b = s.count("}")
    if open_b > close_b:
        s = s + "}" * (open_b - close_b)
    elif close_b > open_b:
        s = "{" * (close_b - open_b) + s
    return s


def _estimate_confidence_from_transforms(orig: str, latex: str, mathml: str) -> float:
    """
    Heuristic confidence: higher if many structural tags appeared in mathml,
    if latex contains known commands (\sum, \frac,..), and if orig had shredded patterns.
    """
    score = 0.2
    # presence of structural MathML tags
    if "<mfrac" in mathml or "<munder" in mathml or "<msubsup" in mathml or "<msub" in mathml:
        score += 0.4
    # presence of top-level operators in latex
    if re.search(r"\\sum|\\frac|\\mathbb|\\left|\\right|\\Pr|\\neq", latex):
        score += 0.3
    # penalize if original had extremely shredded indicators
    if _contains_shredded_patterns(orig):
        score *= 0.85
    return min(0.99, score)


def _repair_malformed_xml(xml_text: str) -> str:
    """
    Try a minimal repair: close unclosed tags, normalize stray backslashes inside <mi> content,
    and remove exotic control chars. This is deliberately conservative.
    """
    # Remove control characters
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", xml_text)
    # Replace common OCR fragments like '\l' stored inside <mi> as text -> 'l'
    s = re.sub(r"<mi>\\([A-Za-z])</mi>", r"<mi>\1</mi>", s)
    # Replace multiple consecutive closing tags mistakes like </msub></msub> -> keep one
    s = re.sub(r"(</msub>){2,}", r"</msub>", s)
    # Try to balance simple angle-bracket truncation: if there's a trailing '<' drop it
    s = s.strip()
    if s.endswith("<"):
        s = s[:-1]
    return s


# Backwards-compatible alias
recover_from_corrupted_mathml = ultra_mathml_recover


# If run as script, run a small local test/demo
if __name__ == "__main__":  # pragma: no cover
    sample = """
    <math xmlns="http://www.w3.org/1998/Math/MathML" display="inline">
      <mrow>
        <msub><mi>Y</mi><mi>j</mi></msub>
        <mo>[</mo><mi>t</mi><mo>]</mo>
        <msub><mi>\\l</mi><mi>e</mi></msub>
        <msub><mi>f</mi><mi>t</mi></msub>
        <msub><mi>\\s</mi><mi>u</mi></msub>
        <msub><mi>m</mi><mi>i</mi></msub>
      </mrow>
    </math>
    """
    res = ultra_mathml_recover(sample)
    print("RESULT:")
    print("latex:", res["latex"])
    print("mathml:", res["mathml"][:400])
    print("confidence:", res["confidence"])
    print("log:")
    for L in res["log"]:
        print(" -", L)
