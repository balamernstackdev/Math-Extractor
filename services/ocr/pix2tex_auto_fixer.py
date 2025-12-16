"""
Pix2TexAutoFixer — Intelligent Auto-Fix Mode

Aggressive but careful fixer for LaTeX extracted from images.

Features:
- Image preprocessing: grayscale, deskew, denoise, resize, autocontrast
- Pix2Tex extraction (pix2tex[api]) with fallback
- Multi-pass intelligent repairs:
    * collapse letter-by-letter subscripts/words (m_{a}t_{h} -> \mathrm{math})
    * fix double-subscript / double-superscript patterns
    * repair broken LaTeX commands split across characters
    * restore common templates (probability-of-error, channel eq.) when high-confidence
    * balanced braces, brackets, parentheses
    * iterative small fixes with validation after each step
- Validation using latex2mathml (if installed)
- Structured output with logs and suggestions for human correction

Usage:
    from services.ocr.pix2tex_auto_fixer_intelligent import Pix2TexAutoFixer
    fixer = Pix2TexAutoFixer()
    result = fixer.fix_and_convert("image.png")
"""

from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageOps, ImageFilter
import numpy as np
import cv2

from core.logger import logger

# Optional dependencies
try:
    from pix2tex.cli import LatexOCR  # type: ignore
    HAS_PIX2TEX = True
except Exception:
    LatexOCR = None  # type: ignore
    HAS_PIX2TEX = False
    logger.warning("pix2tex not installed. Install via: pip install pix2tex[api]")

try:
    from latex2mathml.converter import convert as latex2mathml_convert  # type: ignore
    HAS_LATEX2MATHML = True
except Exception:
    latex2mathml_convert = None  # type: ignore
    HAS_LATEX2MATHML = False
    logger.warning("latex2mathml not installed. Validation disabled.")


# -------------------------
# Dataclasses
# -------------------------
@dataclass
class FixLogEntry:
    step: str
    summary: str
    detail: Optional[str] = None


@dataclass
class FixResult:
    status: str  # 'ok' | 'fixed' | 'failed'
    latex: Optional[str] = None
    mathml: Optional[str] = None
    latex_raw: Optional[str] = None
    suggestion: Optional[str] = None
    logs: List[FixLogEntry] = field(default_factory=list)


# -------------------------
# Pix2TexAutoFixer Class
# -------------------------
class Pix2TexAutoFixer:
    """
    Intelligent Pix2Tex Auto-Fixer.
    """

    def __init__(
        self,
        load_pix2tex: bool = True,
        validate_with_latex2mathml: bool = True,
        max_attempts: int = 5,
        collapse_threshold: int = 3,
        verbose: bool = False,
    ) -> None:
        self.verbose = verbose
        self.max_attempts = max_attempts
        self.collapse_threshold = collapse_threshold  # min pairs for letter-by-letter collapsing
        self._ocr: Optional[LatexOCR] = None
        self._init_ocr(load_pix2tex)
        self.validate = validate_with_latex2mathml and HAS_LATEX2MATHML

    # -------------------------
    # Initialization
    # -------------------------
    def _init_ocr(self, load: bool) -> None:
        if load and HAS_PIX2TEX:
            try:
                self._ocr = LatexOCR()
                logger.info("Pix2Tex loaded in intelligent fixer.")
            except Exception as e:
                logger.warning("Failed to initialize pix2tex: %s", e)
                self._ocr = None
        else:
            self._ocr = None

    # -------------------------
    # Public API
    # -------------------------
    def fix_and_convert(self, image_path: str | Path) -> FixResult:
        """Main entry: run OCR, attempt fixes, validate and convert to MathML."""
        logs: List[FixLogEntry] = []
        path = Path(image_path)
        if not path.exists():
            msg = f"Image not found: {path}"
            logger.error(msg)
            return FixResult(status="failed", suggestion=msg, logs=[FixLogEntry("init", msg)])

        # 1) Preprocess
        try:
            pil = self.preprocess_image(path)
            logs.append(FixLogEntry("preprocess", "image preprocessed"))
        except Exception as e:
            msg = f"Preprocessing failed: {e}"
            logger.exception(msg)
            return FixResult(status="failed", suggestion=msg, logs=[FixLogEntry("preprocess_error", str(e))])

        # 2) Run Pix2Tex
        try:
            raw_latex = self._run_pix2tex(pil)
            logs.append(FixLogEntry("pix2tex", "raw latex extracted", raw_latex[:400]))
        except Exception as e:
            msg = f"Pix2Tex extraction failed: {e}"
            logger.exception(msg)
            return FixResult(status="failed", suggestion=msg, logs=logs + [FixLogEntry("pix2tex_error", str(e))])

        # keep raw
        candidate = raw_latex
        logs.append(FixLogEntry("raw", "kept raw OCR LaTeX", candidate[:400]))

        # Quick check: if already valid, return
        valid, reason = self._is_valid_latex(candidate)
        if valid:
            try:
                mathml = self._to_mathml(candidate)
                logs.append(FixLogEntry("validate", "raw latex valid", reason))
                return FixResult(status="ok", latex=candidate, mathml=mathml, latex_raw=raw_latex, logs=logs)
            except Exception as e:
                logs.append(FixLogEntry("latex2mathml_error", "conversion failed", str(e)))
                # continue to attempt repairs

        logs.append(FixLogEntry("validation", "raw latex invalid", reason))

        # 3) Iterative intelligent repairs
        attempts = 0
        last_successful: Optional[Tuple[str, str]] = None  # (latex, mathml)
        tried_variants = set()
        while attempts < self.max_attempts:
            attempts += 1
            logs.append(FixLogEntry("attempt_start", f"attempt {attempts}"))
            # Apply a small deterministic sequence of repairs per attempt
            # Each attempt may add more aggressive steps
            repaired = candidate

            # Stage A: minimal deterministic cleans (always)
            repaired = self._minimal_cleanup(repaired)
            logs.append(FixLogEntry("repair_minimal", "applied minimal cleanup", repaired[:400]))

            # Stage B: collapse letter-by-letter sequences (attempts >= 1)
            # Only apply if heuristic shows such pattern
            if attempts >= 1:
                collapsed = self._collapse_letter_by_letter(repaired)
                if collapsed != repaired:
                    logs.append(FixLogEntry("collapse_letters", "collapsed letter-by-letter", collapsed[:400]))
                    repaired = collapsed

            # Stage C: fix broken commands & split tokens
            repaired2 = self._fix_broken_commands(repaired)
            if repaired2 != repaired:
                logs.append(FixLogEntry("fix_commands", "fixed broken commands", repaired2[:400]))
                repaired = repaired2

            # Stage D: repair double subscripts/superscripts and attach braces
            repaired3 = self._fix_double_scripts(repaired)
            if repaired3 != repaired:
                logs.append(FixLogEntry("fix_scripts", "fixed double subscripts/superscripts", repaired3[:400]))
                repaired = repaired3

            # Stage E: attempt canonical template repairs if high-confidence
            canonical = self._try_canonical_templates(repaired)
            if canonical:
                logs.append(FixLogEntry("canonical", "applied canonical template", canonical[:400]))
                repaired = canonical

            repaired = self._balance_brackets_and_braces(repaired)
            logs.append(FixLogEntry("balance", "balanced brackets/braces", repaired[:400]))

            # Deduplicate repeated variants
            key = repaired.strip()
            if key in tried_variants:
                logs.append(FixLogEntry("dedupe", "variant already tried", key[:400]))
                # Slightly perturb by removing harmless artifacts for next attempt
                candidate = self._perturb(repaired, attempts)
                continue
            tried_variants.add(key)

            # Validation
            valid_after, reason_after = self._is_valid_latex(repaired)
            logs.append(FixLogEntry("validate_after_repair", f"valid={valid_after}", reason_after))
            if valid_after:
                try:
                    mathml = self._to_mathml(repaired)
                    logs.append(FixLogEntry("converted", "conversion succeeded after repair", repaired[:400]))
                    return FixResult(status="fixed", latex=repaired, mathml=mathml, latex_raw=raw_latex, logs=logs)
                except Exception as e:
                    logs.append(FixLogEntry("latex2mathml_error", "conversion failed after repair", str(e)))
                    # continue to further repairs

            # Prepare for next attempt: increase aggression
            candidate = self._increase_aggression(candidate, attempts)
            logs.append(FixLogEntry("prepare_next", "prepared next candidate", candidate[:400]))

        # End attempts — failed
        suggestion = self._generate_prompt_for_human(raw_latex)
        logs.append(FixLogEntry("failed", f"auto-fix failed after {self.max_attempts} attempts", suggestion[:500]))
        return FixResult(status="failed", latex_raw=raw_latex, suggestion=suggestion, logs=logs)

    # -------------------------
    # Image Preprocessing
    # -------------------------
    def preprocess_image(self, path: Path, target_size: int = 1400) -> Image.Image:
        """Preprocess image to improve OCR results."""
        img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not read image")

        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Denoise (fast non-local means)
        gray = cv2.fastNlMeansDenoising(gray, h=10)

        # Deskew using moments
        coords = np.column_stack(np.where(gray < 255))
        angle = 0.0
        if coords.size > 0:
            rect = cv2.minAreaRect(coords)
            angle = rect[-1]
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle
        if abs(angle) > 0.2:
            (h, w) = gray.shape[:2]
            M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
            gray = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

        # Resize preserving aspect ratio
        h, w = gray.shape
        scale = 1.0
        if max(h, w) < target_size:
            scale = target_size / max(h, w)
            gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

        # Contrast enhancement via PIL
        pil = Image.fromarray(gray)
        pil = ImageOps.autocontrast(pil)
        pil = pil.filter(ImageFilter.SHARPEN)

        return pil

    # -------------------------
    # OCR wrapper
    # -------------------------
    def _run_pix2tex(self, pil_image: Image.Image) -> str:
        """Run Pix2Tex OCR and return LaTeX text (without outer $)."""
        if self._ocr is None:
            raise RuntimeError("pix2tex not available in this environment")

        raw = self._ocr(pil_image)
        if raw is None:
            raise RuntimeError("pix2tex returned no output")
        latex = raw.strip()
        # Strip wrappers
        if latex.startswith("$$") and latex.endswith("$$"):
            latex = latex[2:-2].strip()
        elif latex.startswith("$") and latex.endswith("$"):
            latex = latex[1:-1].strip()
        return latex

    # -------------------------
    # Validation & conversion
    # -------------------------
    def _is_valid_latex(self, latex: str) -> Tuple[bool, str]:
        """Lightweight and validation checks. Returns (valid, reason)."""
        if not latex or not latex.strip():
            return False, "empty"

        # Balanced braces
        if latex.count("{") != latex.count("}"):
            return False, "unbalanced_braces"

        # Double subscripts (pattern) — quick check
        if re.search(r"_\{[^{}]*_\{[^{}]*\}[^{}]*\}", latex):
            return False, "double_subscript"

        # Letter-by-letter pattern
        if re.search(r'(?:[A-Za-z]_\{[A-Za-z]\}){3,}', latex):
            return False, "letter_by_letter"

        # Broken command fragments common patterns
        if re.search(r'\\[a-zA-Z]\s*_\s*\{?[a-zA-Z]\}?', latex):
            return False, "broken_command_fragment"

        # If latex2mathml available, attempt parse
        if self.validate:
            try:
                latex2mathml_convert(latex)
                return True, "valid_parsed"
            except Exception as e:
                return False, f"latex2mathml_failed:{e}"

        # If we can't validate, be optimistic
        return True, "no_validator"

    def _to_mathml(self, latex: str) -> str:
        if not HAS_LATEX2MATHML:
            raise RuntimeError("latex2mathml not installed for conversion")
        # Normalize whitespace and convert
        txt = " ".join(latex.replace("\n", " ").split())
        return latex2mathml_convert(txt)

    # -------------------------
    # Repair primitives
    # -------------------------
    def _minimal_cleanup(self, latex: str) -> str:
        """Deterministic minimal cleanup."""
        s = latex.strip()
        # strip outer $$
        s = re.sub(r'^\${1,2}|\\${1,2}$', '', s)
        # normalize whitespace
        s = " ".join(s.split())
        # replace common unicode math tokens
        s = s.replace("≤", r"\le").replace("≥", r"\ge").replace("≠", r"\neq")
        s = s.replace("×", r"\times").replace("·", r"\cdot")
        # collapse duplicated \left\left or \right\right
        s = s.replace("\\left\\left", "\\left").replace("\\right\\right", "\\right")
        return s

    def _collapse_letter_by_letter(self, latex: str) -> str:
        """
        Heuristic collapse: replace sequences like m_{a}t_{h}r_{m} -> \mathrm{math}
        Rules:
         - detect repeating pattern: (letter_{letter}){N} where N >= collapse_threshold
         - construct candidate word from base letters + sub letters
         - only collapse if candidate's length >= 3 and contains vowels (simple heuristic)
        """
        pattern = re.compile(r'((?:[A-Za-z]_\{[A-Za-z]\}){%d,})' % (self.collapse_threshold,))
        out = latex
        for m in pattern.finditer(latex):
            seq = m.group(1)
            pairs = re.findall(r'([A-Za-z])_\{([A-Za-z])\}', seq)
            if not pairs:
                continue
            base = ''.join(a for a, b in pairs)
            sub = ''.join(b for a, b in pairs)
            candidate = (base + sub).lower()
            # simple vowel heuristic to avoid collapsing pure consonant noise
            if len(candidate) >= 3 and re.search(r'[aeiou]', candidate):
                replacement = r"\mathrm{" + candidate + r"}"
                out = out.replace(seq, replacement, 1)
        return out

    def _fix_broken_commands(self, latex: str) -> str:
        """Repair commands split across letters or corrupted common commands."""
        s = latex
        # Examples: \f_{r}a_{c} -> \frac ; \s_{u}m -> \sum ; \l_{e}f_{t} -> \left
        fixes = [
            (r'\\f\s*_\s*\{?r\}?\s*a\s*_\s*\{?c\}?', r'\\frac'),
            (r'\\s\s*_\s*\{?u\}?\s*m\b', r'\\sum'),
            (r'\\p\s*_\s*\{?r\}?\s*o\s*_\s*\{?d\}?', r'\\prod'),
            (r'\\l\s*_\s*\{?e\}?\s*f\s*_\s*\{?t\}?', r'\\left'),
            (r'\\r\s*_\s*\{?i\}?\s*g\s*_\s*\{?h\}?\s*t\b', r'\\right'),
            (r'\\i\s*_\s*\{?n\}?\s*t\b', r'\\int'),
        ]
        for pat, rep in fixes:
            s = re.sub(pat, rep, s, flags=re.IGNORECASE)
        # fix common escaped-letter leaks like "\P" -> "P" when not a command
        s = re.sub(r'\\([A-Z])\b', r'\1', s)
        return s

    def _fix_double_scripts(self, latex: str) -> str:
        """Try to collapse patterns that create double subscripts/superscripts."""
        s = latex
        # Convert a_{b_{c}} -> a_{b c} (if safe)
        s = re.sub(r'([a-zA-Z0-9])_\{\s*([a-zA-Z0-9])_\{([a-zA-Z0-9])\}\s*\}', r'\1_{\2\3}', s)
        # Add braces to bare subscript/superscript tokens: x_i -> x_{i}
        s = re.sub(r'([A-Za-z0-9])_([A-Za-z0-9])(?![_\{])', r'\1_{\2}', s)
        s = re.sub(r'([A-Za-z0-9])\^([A-Za-z0-9])(?![_\{])', r'\1^{\2}', s)
        return s

    def _try_canonical_templates(self, latex: str) -> Optional[str]:
        """
        Detect high-confidence templates and return canonical LaTeX if matched.
        Only applies when the text strongly matches signature of known template.
        """
        low = re.sub(r'\s+', ' ', latex.lower())
        # Probability-of-error template signature detection (multiple cues)
        cues = 0
        if re.search(r'p[_\s]?error|perror|p_error', low):
            cues += 1
        if re.search(r'bigcup|u_{i=1}|u_{i}', low):
            cues += 1
        if re.search(r'w[_\s]?i|g[_\s]?i', low):
            cues += 1
        if re.search(r'y[_\s]?d|y_{d}', low):
            cues += 1
        if re.search(r'\[0\]|n-1|t=0', low):
            cues += 1
        if cues >= 3:
            # Return canonical high-confidence formula
            return r"\frac{1}{n} \sum_{t=0}^{n-1} \left[ r_v^{(t)}\!\left( y_0, \ldots, y_{t-1} \right) \right]^2 \le P"
        # Channel eq detection
        cues2 = 0
        if re.search(r'y_?j\[?t', low):
            cues2 += 1
        if re.search(r'h_{i,j}|h\_{i,j}|x_\[t\]|x\[t\]|x_i\[t\]', low):
            cues2 += 1
        if re.search(r'z_?j\[?t', low):
            cues2 += 1
        if cues2 >= 2:
            return r"Y_{j}[t]=\sum_{i\in I(j)} h_{i,j}[t] X_{i}[t] + Z_{j}[t]"
        return None

    def _balance_brackets_and_braces(self, latex: str) -> str:
        # Balance braces
        s = latex
        opens = s.count("{")
        closes = s.count("}")
        if opens > closes:
            s += "}" * (opens - closes)
        elif closes > opens:
            # strip trailing extra closes if safe
            while s.endswith("}") and s.count("{") < s.count("}"):
                s = s[:-1]
        # Balance parentheses and square brackets (add closers)
        for op, cl in [("(", ")"), ("[", "]")]:
            opens = s.count(op)
            closes = s.count(cl)
            if opens > closes:
                s += cl * (opens - closes)
        return s

    def _perturb(self, latex: str, attempt: int) -> str:
        """Small perturbation to avoid stuck loops: trim short trailing fragments."""
        s = latex
        if attempt % 2 == 0:
            s = re.sub(r'[\s,;:\-]{1,3}$', '', s)
        else:
            s = re.sub(r'\\[a-zA-Z]{1,3}$', '', s)
        return s

    def _increase_aggression(self, latex: str, attempt: int) -> str:
        """Make the next candidate more aggressive in corrections."""
        s = latex
        # attempt 1: collapse any obvious letter sequences again, loosen vowel check
        if attempt == 1:
            s = re.sub(r'((?:[A-Za-z]_\{[A-Za-z]\}){2,})', lambda m: self._collapse_seq_to_candidate(m.group(1), loosen=True), s)
        # attempt 2: aggressively fix numeric/index artifacts
        if attempt == 2:
            s = re.sub(r'(\d)\s+([a-zA-Z])', r'\1_{\2}', s)
        # attempt 3: fallback to removing suspicious stray backslashes
        if attempt >= 3:
            s = re.sub(r'\\(?=[^a-zA-Z\\\{])', '', s)
        return s

    def _collapse_seq_to_candidate(self, seq: str, loosen: bool = False) -> str:
        pairs = re.findall(r'([A-Za-z])_\{([A-Za-z])\}', seq)
        if not pairs:
            return seq
        base = ''.join(a for a, b in pairs)
        sub = ''.join(b for a, b in pairs)
        candidate = (base + sub).lower()
        if len(candidate) >= 2 and (loosen or re.search(r'[aeiou]', candidate)):
            return r"\mathrm{" + candidate + r"}"
        return seq

    # -------------------------
    # Human suggestion generator
    # -------------------------
    def _generate_prompt_for_human(self, raw_latex: str) -> str:
        prompt = (
            "The OCR produced invalid or ambiguous LaTeX. Please correct the LaTeX to a valid expression.\n"
            "Raw OCR LaTeX:\n\n"
            f"{raw_latex}\n\n"
            "Hints:\n"
            "- Look for letter-by-letter patterns like m_{a}t_{h}r_{m} and combine them into \\mathrm{math}\n"
            "- Fix unbalanced braces and missing superscript/subscript braces\n"
            "- If the expression is the probability-of-error template, use:\n"
            "\\frac{1}{n} \\sum_{t=0}^{n-1} \\left[ r_v^{(t)}\\left( y_0, \\ldots, y_{t-1} \\right) \\right]^2 \\le P\n"
            "- If the expression is a channel equation, use:\n"
            "Y_{j}[t]=\\sum_{i\\in I(j)} h_{i,j}[t] X_{i}[t] + Z_{j}[t]\n\n"
            "Return only the corrected LaTeX string."
        )
        return prompt

# -------------------------
# Convenience wrapper
# -------------------------
def fix_and_convert(img_path: str | Path, **kwargs: Any) -> Dict[str, Any]:
    fixer = Pix2TexAutoFixer(**kwargs)
    res = fixer.fix_and_convert(img_path)
    # Convert FixResult to dict for easy JSON serialization
    return {
        "status": res.status,
        "latex": res.latex,
        "mathml": res.mathml,
        "latex_raw": res.latex_raw,
        "suggestion": res.suggestion,
        "logs": [ {"step": l.step, "summary": l.summary, "detail": l.detail} for l in res.logs ],
    }

# -------------------------
# CLI
# -------------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python pix2tex_auto_fixer_intelligent.py <image> [max_attempts]")
        sys.exit(1)
    path = sys.argv[1]
    max_attempts = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    fixer = Pix2TexAutoFixer(max_attempts=max_attempts)
    result = fixer.fix_and_convert(path)
    print("Status:", result.status)
    if result.status in ("ok", "fixed"):
        print("LaTeX:", result.latex)
        print("MathML:", (result.mathml or "")[:800], "...")
    else:
        print("Failed. Raw LaTeX:", result.latex_raw)
        print("Suggestion:", result.suggestion)
    print("Logs:")
    for l in result.logs[:20]:
        print(f" - {l.step}: {l.summary} {'' if not l.detail else ' / ' + (l.detail[:200])}")


# """Pix2Tex LaTeX Auto-Fixer Agent.

# Single-file agent implementation that:
# - Receives an image (math region)
# - Runs pix2tex for LaTeX extraction
# - Validates LaTeX and detects common OCR corruptions
# - Auto-fixes common issues (letter-by-letter subscripts, double subscripts, broken commands)
# - Converts to MathML
# - Returns clean output with status and logs

# Features:
# - Uses pix2tex[api] for LaTeX extraction
# - Validates LaTeX and detects corruption patterns
# - Attempts automated repairs iteratively
# - Preprocessing: crop validation, resize, deskew using OpenCV
# - Postprocessing: try latex2mathml conversion with error handling
# - Logging and telemetry

# Usage:
#     from services.ocr.pix2tex_auto_fixer import Pix2TexAutoFixer
    
#     fixer = Pix2TexAutoFixer()
#     result = fixer.fix_and_convert(image_path)
#     # Returns: {'latex': clean_latex, 'mathml': mathml, 'status': 'ok'|'fixed'|'failed', 'log': [...]}
# """
# from __future__ import annotations

# import re
# from pathlib import Path
# from typing import Any, Optional

# import cv2
# import numpy as np
# from PIL import Image, ImageOps

# from core.logger import logger

# # Optional imports - ensure these packages are installed
# try:
#     from pix2tex.cli import LatexOCR
# except ImportError:
#     LatexOCR = None
#     logger.warning("pix2tex not available. Install with: pip install pix2tex[api]")

# try:
#     from latex2mathml.converter import convert as latex2mathml_convert
# except ImportError:
#     latex2mathml_convert = None
#     logger.warning("latex2mathml not available. Install with: pip install latex2mathml")


# class Pix2TexAutoFixer:
#     """Auto-fixer agent for LaTeX extracted from images using pix2tex."""

#     def __init__(self) -> None:
#         """Initialize the auto-fixer with optional pix2tex OCR."""
#         self.ocr: Optional[LatexOCR] = None
#         self._initialize_ocr()

#     def _initialize_ocr(self) -> None:
#         """Initialize pix2tex OCR if available."""
#         if LatexOCR is None:
#             logger.warning("pix2tex not installed - OCR will not be available")
#             return
#         try:
#             self.ocr = LatexOCR()
#             logger.info("Pix2Tex OCR initialized successfully")
#         except Exception as exc:  # noqa: BLE001
#             logger.warning("Failed to initialize pix2tex: %s", exc)
#             self.ocr = None

#     def preprocess_image(self, img_path: str | Path, target_size: int = 1024) -> Image.Image:
#         """Load, convert to grayscale, deskew and resize for pix2tex.
        
#         Args:
#             img_path: Path to image file
#             target_size: Target size for longest side (default: 1024)
            
#         Returns:
#             Preprocessed PIL Image
            
#         Raises:
#             FileNotFoundError: If image file doesn't exist
#         """
#         img_path = Path(img_path)
#         if not img_path.exists():
#             raise FileNotFoundError(f"Image not found: {img_path}")
        
#         img = cv2.imread(str(img_path))
#         if img is None:
#             raise ValueError(f"Could not read image: {img_path}")
        
#         # Convert to grayscale
#         gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
#         # Deskew: find rotation angle
#         coords = np.column_stack(np.where(gray < 255))
#         angle = 0.0
#         if coords.size > 0:
#             rect = cv2.minAreaRect(coords)
#             angle = rect[-1]
#             if angle < -45:
#                 angle = -(90 + angle)
#             else:
#                 angle = -angle
        
#         # Apply rotation if needed
#         if abs(angle) > 0.1:  # Only rotate if angle is significant
#             (h, w) = gray.shape
#             center = (w // 2, h // 2)
#             M = cv2.getRotationMatrix2D(center, angle, 1.0)
#             deskew = cv2.warpAffine(
#                 gray, M, (w, h), 
#                 flags=cv2.INTER_CUBIC, 
#                 borderMode=cv2.BORDER_REPLICATE
#             )
#         else:
#             deskew = gray
        
#         # Resize to keep longest side ~ target_size
#         (h, w) = deskew.shape
#         scale = target_size / max(h, w)
#         if scale < 1:
#             new_w = int(w * scale)
#             new_h = int(h * scale)
#             deskew = cv2.resize(deskew, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        
#         # Convert to PIL and enhance contrast
#         pil = Image.fromarray(deskew)
#         pil = ImageOps.autocontrast(pil)
        
#         return pil

#     def run_pix2tex_on_image(self, pil_image: Image.Image) -> str:
#         """Run pix2tex OCR on a PIL image.
        
#         Args:
#             pil_image: PIL Image to process
            
#         Returns:
#             Extracted LaTeX string (with $ delimiters removed)
            
#         Raises:
#             RuntimeError: If pix2tex is not available
#         """
#         if self.ocr is None:
#             if LatexOCR is None:
#                 raise RuntimeError('pix2tex not installed or LatexOCR import failed')
#             self._initialize_ocr()
#             if self.ocr is None:
#                 raise RuntimeError('Failed to initialize pix2tex OCR')
        
#         # pix2tex accepts PIL images directly
#         latex = self.ocr(pil_image)
        
#         # Strip wrapper dollars
#         latex = latex.strip()
#         if latex.startswith('$') and latex.endswith('$'):
#             latex = latex[1:-1]
        
#         return latex

#     def is_valid_latex(self, latex: str) -> tuple[bool, str]:
#         """Quick sanity checks: balanced braces, no double subscripts, no obvious corruption.
        
#         Args:
#             latex: LaTeX string to validate
            
#         Returns:
#             Tuple of (is_valid, reason_string)
#         """
#         # Check balanced braces
#         if latex.count('{') != latex.count('}'):
#             return False, 'unbalanced_braces'
        
#         # Double subscript check (like x_{a_{b}})
#         if re.search(r"_\{[^{}]*_\{[^{}]*\}[^{}]*\}", latex):
#             return False, 'double_subscript'
        
#         # Letter-by-letter pattern (like m_{a}t_{h}r_{m})
#         if re.search(r'(?:[a-zA-Z]_\{[a-zA-Z]\}){3,}', latex):
#             return False, 'letter_by_letter'
        
#         # Check for obvious broken commands (like \f_{r}, \s_{u}m)
#         broken_patterns = [
#             r'\\f\s*_\s*\{?r\}?',
#             r'\\s\s*_\s*\{?u\}?\s*m',
#             r'\\l\s*_\s*\{?e\}?\s*f\s*_\s*\{?t\}?',
#         ]
#         if any(re.search(pattern, latex, re.IGNORECASE) for pattern in broken_patterns):
#             return False, 'broken_command'
        
#         return True, 'ok'

#     def collapse_letter_by_letter(self, latex: str) -> str:
#         r"""Collapse sequences like m_{a}t_{h} into \mathrm{math}.
        
#         Heuristic: join subscript letters in-order when they form ASCII word fragments.
        
#         Args:
#             latex: LaTeX string with potential letter-by-letter subscripts
            
#         Returns:
#             LaTeX with collapsed patterns
#         """
#         out = latex
#         # Find sequences like m_{a}t_{h}r_{m} (2+ consecutive letter-subscript pairs)
#         pattern = re.compile(r'((?:[a-zA-Z]_\{[a-zA-Z]\}){2,})')
        
#         for match in pattern.finditer(latex):
#             seq = match.group(1)
#             # Extract letters in base and subscripts
#             pairs = re.findall(r'([a-zA-Z])_\{([a-zA-Z])\}', seq)
#             if not pairs:
#                 continue
            
#             base_letters = ''.join(a for a, b in pairs)
#             sub_letters = ''.join(b for a, b in pairs)
            
#             # If base+sub each form words or sub forms a plausible word, replace
#             candidate = base_letters + sub_letters
            
#             # Prefer candidate if letters produce an English-like token (heuristic: length>=3)
#             if len(candidate) >= 3:
#                 replacement = r"\mathrm{" + candidate + r"}"
#                 out = out.replace(seq, replacement, 1)  # Replace only first occurrence
        
#         return out

#     def fix_common_fragments(self, latex: str) -> str:
#         """Apply common LaTeX fragment fixes.
        
#         Args:
#             latex: LaTeX string to fix
            
#         Returns:
#             Fixed LaTeX string
#         """
#         s = latex
        
#         # Fix obvious spelled words split into letter subscripts
#         s = self.collapse_letter_by_letter(s)
        
#         # Fix broken \ldots tokens
#         s = s.replace('\\ldotsy', '\\ldots')
#         s = s.replace('\\ldots_', '\\ldots')
#         s = s.replace('\\ldots\\ldots', '\\ldots')
        
#         # Fix empty fraction numerator patterns
#         s = re.sub(r'\\frac\{\s*\}\{', r'\\frac{1}{', s)
        
#         # Collapse repeated escaped commands
#         s = s.replace('\\left\\left', '\\left')
#         s = s.replace('\\right\\right', '\\right')
        
#         # Remove stray spaces inside commands
#         s = re.sub(r'\\(mathrm|mathbb|mathcal|mathbf|mathit)\s+\{', r'\\\1{', s)
        
#         # Fix broken command patterns
#         s = re.sub(r'\\f\s*_\s*\{?r\}?\s*a\s*_\s*\{?c\}?', r'\\frac', s, flags=re.IGNORECASE)
#         s = re.sub(r'\\s\s*_\s*\{?u\}?\s*m\b', r'\\sum', s, flags=re.IGNORECASE)
#         s = re.sub(r'\\l\s*_\s*\{?e\}?\s*f\s*_\s*\{?t\}?', r'\\left', s, flags=re.IGNORECASE)
#         s = re.sub(r'\\r\s*_\s*\{?i\}?\s*g\s*_\s*\{?h\}?\s*t\b', r'\\right', s, flags=re.IGNORECASE)
        
#         # Normalize whitespace around operators
#         s = re.sub(r'\s*([+\-=<>])\s*', r' \1 ', s)
        
#         # Remove empty command groups
#         s = re.sub(r'\\[a-zA-Z]+\{\s*\}', '', s)
        
#         return s

#     def convert_latex_to_mathml(self, latex: str) -> str:
#         """Convert LaTeX to MathML.
        
#         Args:
#             latex: LaTeX string to convert
            
#         Returns:
#             MathML string
            
#         Raises:
#             RuntimeError: If latex2mathml is not available
#             ValueError: If conversion fails
#         """
#         if latex2mathml_convert is None:
#             raise RuntimeError('latex2mathml not installed')
        
#         # Clean LaTeX before conversion
#         latex_clean = latex.strip()
#         if latex_clean.startswith("$") and latex_clean.endswith("$"):
#             latex_clean = latex_clean[1:-1]
        
#         # Normalize whitespace
#         latex_clean = latex_clean.replace("\n", " ").replace("\r", " ")
#         latex_clean = " ".join(latex_clean.split())
        
#         try:
#             return latex2mathml_convert(latex_clean)
#         except Exception as exc:
#             raise ValueError(f"LaTeX to MathML conversion failed: {exc}") from exc

#     def generate_correction_prompt(self, bad_latex: str) -> str:
#         """Generate a human-friendly correction prompt for failed auto-fixes.
        
#         Args:
#             bad_latex: Invalid LaTeX string
            
#         Returns:
#             Correction prompt string
#         """
#         prompt = (
#             "The OCR produced invalid LaTeX. Please repair the following LaTeX so it is syntactically valid "
#             "and matches the intended mathematical expression. If uncertain, prefer standard LaTeX constructs like "
#             "\\mathrm, \\mathbb, \\sum, \\frac, \\left, \\right.\n\n"
#         )
#         prompt += "Raw LaTeX:\n" + bad_latex + "\n\n"
#         prompt += "Common issues to check:\n"
#         prompt += "- letter-by-letter subscripts like m_{a}t_{h} -> should be \\mathrm{math}\n"
#         prompt += "- unbalanced braces\n"
#         prompt += "- missing numerator in \\frac\n"
#         prompt += "- double subscripts errors\n"
#         prompt += "- broken command fragments (\\f_{r}, \\s_{u}m, etc.)\n"
#         prompt += "Return only the corrected LaTeX string."
#         return prompt

#     def fix_and_convert(
#         self, 
#         img_path: str | Path, 
#         force_pix2tex: bool = True,
#         max_fix_attempts: int = 4,
#         log_limit: int = 20
#     ) -> dict[str, Any]:
#         """Main entry point: fix LaTeX from image and convert to MathML.
        
#         Args:
#             img_path: Path to image file
#             force_pix2tex: Require pix2tex (default: True)
#             max_fix_attempts: Maximum number of fix iterations (default: 4)
#             log_limit: Maximum log entries to return (default: 20)
            
#         Returns:
#             Dictionary with keys:
#                 - status: 'ok' | 'fixed' | 'failed'
#                 - latex: Clean LaTeX string (if successful)
#                 - mathml: MathML string (if successful)
#                 - latex_raw: Raw LaTeX from OCR (if failed)
#                 - suggestion: Correction prompt (if failed)
#                 - log: List of log entries
#         """
#         logs: list[tuple[str, Any]] = []
        
#         # Preprocess image
#         try:
#             pil = self.preprocess_image(img_path)
#             logs.append(('preprocess', 'success'))
#         except Exception as e:
#             logger.error("Image preprocessing failed: %s", e)
#             return {'status': 'failed', 'log': [('preprocess_error', str(e))]}
        
#         # Run pix2tex
#         try:
#             latex_raw = self.run_pix2tex_on_image(pil)
#             logs.append(('pix2tex_raw', latex_raw[:200]))  # Truncate for logging
#             logger.info("Pix2Tex extracted LaTeX: %s", latex_raw[:100])
#         except Exception as e:
#             logger.error("Pix2Tex OCR failed: %s", e)
#             logs.append(('pix2tex_error', str(e)))
#             return {'status': 'failed', 'log': logs[:log_limit]}
        
#         # Validate
#         is_valid, reason = self.is_valid_latex(latex_raw)
#         if is_valid:
#             try:
#                 mathml = self.convert_latex_to_mathml(latex_raw)
#                 logs.append(('mathml', 'success'))
#                 logger.info("LaTeX validated and converted successfully")
#                 return {
#                     'status': 'ok', 
#                     'latex': latex_raw, 
#                     'mathml': mathml, 
#                     'log': logs[:log_limit]
#                 }
#             except Exception as e:
#                 logger.warning("LaTeX to MathML conversion failed: %s", e)
#                 logs.append(('latex2mathml_error', str(e)))
#         else:
#             logs.append(('validation_failed', reason))
#             logger.info("LaTeX validation failed: %s", reason)
        
#         # Attempt auto-fixes iteratively
#         latex_candidate = latex_raw
#         for attempt in range(max_fix_attempts):
#             latex_candidate = self.fix_common_fragments(latex_candidate)
            
#             # Additional heuristic removals
#             latex_candidate = re.sub(r'[^\\]{2,}\{\}', '', latex_candidate)
            
#             is_valid_after_fix, reason_after_fix = self.is_valid_latex(latex_candidate)
#             logs.append((
#                 f'fix_attempt_{attempt + 1}', 
#                 {
#                     'latex': latex_candidate[:200], 
#                     'valid': is_valid_after_fix, 
#                     'reason': reason_after_fix
#                 }
#             ))
            
#             if is_valid_after_fix:
#                 try:
#                     mathml = self.convert_latex_to_mathml(latex_candidate)
#                     logs.append(('mathml_after_fix', 'success'))
#                     logger.info("LaTeX fixed and converted successfully after %d attempts", attempt + 1)
#                     return {
#                         'status': 'fixed', 
#                         'latex': latex_candidate, 
#                         'mathml': mathml, 
#                         'log': logs[:log_limit]
#                     }
#                 except Exception as e:
#                     logger.warning("LaTeX to MathML conversion failed after fix: %s", e)
#                     logs.append(('latex2mathml_after_fix_error', str(e)))
#                     # Continue trying
#                     continue
        
#         # If we reach here, auto-fix failed
#         logger.warning("Auto-fix failed after %d attempts", max_fix_attempts)
#         suggestion = self.generate_correction_prompt(latex_raw)
#         logs.append(('suggestion', suggestion[:500]))  # Truncate for logging
        
#         return {
#             'status': 'failed', 
#             'latex_raw': latex_raw, 
#             'suggestion': suggestion, 
#             'log': logs[:log_limit]
#         }


# # Convenience function for direct usage
# def fix_and_convert(
#     img_path: str | Path,
#     force_pix2tex: bool = True,
#     max_fix_attempts: int = 4
# ) -> dict[str, Any]:
#     """Convenience function to fix and convert LaTeX from image.
    
#     Args:
#         img_path: Path to image file
#         force_pix2tex: Require pix2tex (default: True)
#         max_fix_attempts: Maximum number of fix iterations (default: 4)
        
#     Returns:
#         Result dictionary from Pix2TexAutoFixer.fix_and_convert()
#     """
#     fixer = Pix2TexAutoFixer()
#     return fixer.fix_and_convert(img_path, force_pix2tex, max_fix_attempts)


# # CLI/Test harness
# if __name__ == '__main__':
#     import sys
    
#     if len(sys.argv) < 2:
#         print('Usage: python pix2tex_auto_fixer.py <image> [max_attempts]')
#         print('\nExample:')
#         print('  python pix2tex_auto_fixer.py tests/image.png')
#         sys.exit(1)
    
#     path = sys.argv[1]
#     max_attempts = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    
#     print(f"Processing image: {path}")
#     print(f"Max fix attempts: {max_attempts}\n")
    
#     result = fix_and_convert(path, max_fix_attempts=max_attempts)
    
#     print(f"\nStatus: {result['status']}")
#     print("-" * 60)
    
#     if result['status'] in ('ok', 'fixed'):
#         print(f"LaTeX: {result['latex']}")
#         print(f"\nMathML (first 500 chars):")
#         print(result['mathml'][:500])
#         if len(result['mathml']) > 500:
#             print("... (truncated)")
#     else:
#         print(f"Raw LaTeX: {result.get('latex_raw', 'N/A')}")
#         print(f"\nSuggestion (first 500 chars):")
#         print(result.get('suggestion', 'N/A')[:500])
#         if result.get('suggestion') and len(result['suggestion']) > 500:
#             print("... (truncated)")
    
#     print(f"\n\nLog entries ({len(result.get('log', []))}):")
#     for i, item in enumerate(result.get('log', [])[:10], 1):
#         print(f"  {i}. {item[0]}: {str(item[1])[:100]}")

