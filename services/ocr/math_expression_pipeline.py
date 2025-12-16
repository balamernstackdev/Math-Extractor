Y_{j}[t]\underline{{{-}}}~\sum_{i\in\overline{{{Z}}}(j)}^{\qquad\qquad\qquad\qquad\qquad\qquad\qquad}~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# services/ocr/math_expression_pipeline.py
"""
MathExpressionPipeline (FORCE-ULTRA for MathML only)

Behavior:
 - If input contains dollar delimiters or LaTeX commands -> treat as LaTeX (no ULTRA).
 - If input looks like MathML -> clean with OCRMathMLCleaner.
    - If cleaned MathML is **corrupted**, run ULTRA recovery (rebuild-from-scraps).
    - If ULTRA produces LaTeX, we return both clean LaTeX and validated MathML.
 - If input is plain text -> treat as LaTeX candidate via DynamicLaTeXReconstructor.
 - NEVER convert MathML -> LaTeX unless ULTRA recovery was explicitly invoked.
"""

from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from typing import Literal, Optional, TypedDict, List

from core.logger import logger
from services.ocr.dynamic_latex_reconstructor import DynamicLaTeXReconstructor
from services.ocr.latex_to_mathml import LatexToMathML
from services.ocr.ocr_mathml_cleaner import OCRMathMLCleaner

# ULTRA recovery — optional
try:
    from services.ocr.mathml_recovery_pro import ultra_mathml_recover
except Exception:
    ultra_mathml_recover = None
    logger.warning("[PIPELINE] ULTRA MathML recovery module not available")


SourceType = Literal["mathml", "latex", "plain", "empty"]


class PipelineResult(TypedDict, total=False):
    source_type: SourceType
    clean_latex: str
    mathml: str
    intermediate_mathml: Optional[str]
    raw_input: str
    recovery_confidence: float
    recovery_log: List[str]


class MathExpressionPipeline:
    """Unified ingestion pipeline with FORCE-ULTRA applied only for MathML."""

    def __init__(
        self,
        reconstructor: Optional[DynamicLaTeXReconstructor] = None,
        mathml_converter: Optional[LatexToMathML] = None,
        mathml_cleaner: Optional[OCRMathMLCleaner] = None,
    ) -> None:
        self.reconstructor = reconstructor or DynamicLaTeXReconstructor()
        self.mathml_converter = mathml_converter or LatexToMathML()
        self.mathml_cleaner = mathml_cleaner or OCRMathMLCleaner()

    # -------------------------
    # Input detection
    # -------------------------
    def detect_input_type(self, raw: str) -> SourceType:
        """Detect strong input type. Prioritize explicit LaTeX markers ($ or backslash)."""
        if not raw or not raw.strip():
            return "empty"
        t = raw.strip()

        # If explicit LaTeX delimiter -> LaTeX
        if "$" in t:
            return "latex"

        # If appears to contain LaTeX commands (backslash + letters)
        if re.search(r"\\[A-Za-z]+", t):
            return "latex"

        # If looks like MathML root/structure -> MathML
        if t.startswith("<math") or "<mrow" in t or "<msub" in t or "<mi>" in t or "<mo>" in t:
            return "mathml"

        # Default -> plain
        return "plain"

    # -------------------------
    # XML well-formedness
    # -------------------------
    def _is_well_formed_xml(self, xml_text: str) -> bool:
        try:
            ET.fromstring(xml_text)
            return True
        except Exception:
            return False

    # -------------------------
    # Corruption heuristics (ULTRA-aware)
    # -------------------------
    def _is_corrupted_mathml(self, mathml: str) -> bool:
        """
        Detect severe corruption: shredded letters, too many <mi> single letters,
        very few <mo>, broken XML, or presence of backslash-escaped TeX fragments.
        """
        if not mathml or len(mathml) < 40:
            return False

        # If not well-formed XML -> consider corrupted
        if not self._is_well_formed_xml(mathml):
            logger.debug("[PIPELINE] MathML not well-formed XML -> corrupted")
            return True

        # letter-by-letter patterns (e.g., <mi>l</mi><mi>e</mi><mi>f</mi><mi>t</mi>)
        if re.search(r'<mi>\s*[A-Za-z]\s*</mi>\s*(?:<mi>\s*[A-Za-z]\s*</mi>\s*){3,}', mathml):
            logger.debug("[PIPELINE] Detected many single-letter <mi> tokens -> corrupted")
            return True

        # shredded command words
        shredded_checks = [r'l\s*e\s*f\s*t', r'r\s*i\s*g\s*h\s*t', r's\s*u\s*m', r'f\s*r\s*a\s*c', r'm\s*a\s*t\s*h\s*b\s*b']
        for pat in shredded_checks:
            if re.search(pat, mathml, re.IGNORECASE):
                logger.debug("[PIPELINE] Detected shredded command pattern -> corrupted: %s", pat)
                return True

        # too many <mi> vs <mo>
        mi_count = len(re.findall(r'<mi>', mathml))
        mo_count = len(re.findall(r'<mo>', mathml))
        if mi_count > 12 and mo_count < 2:
            logger.debug("[PIPELINE] Unbalanced <mi>/<mo> -> corrupted (mi=%d mo=%d)", mi_count, mo_count)
            return True

        # presence of TeX escapes inside MathML (broken)
        if "\\" in mathml:
            logger.debug("[PIPELINE] Backslash found inside MathML -> likely corrupted")
            return True

        return False

    # -------------------------
    # ULTRA recovery wrapper
    # -------------------------
    def _recover_mathml(self, broken_mathml: str) -> PipelineResult:
        if ultra_mathml_recover is None:
            logger.error("[PIPELINE] ULTRA recovery module not installed")
            return PipelineResult(
                source_type="mathml",
                clean_latex="",
                mathml='<math xmlns="http://www.w3.org/1998/Math/MathML" data-error="ultra-missing"/>',
                intermediate_mathml=broken_mathml,
                raw_input=broken_mathml,
                recovery_confidence=0.0,
                recovery_log=["ULTRA recovery module not installed"],
            )

        logger.info("[PIPELINE] ULTRA recovery invoked for MathML")
        try:
            res = ultra_mathml_recover(broken_mathml)
        except Exception as exc:
            logger.exception("[PIPELINE] ULTRA engine crashed during recovery")
            return PipelineResult(
                source_type="mathml",
                clean_latex="",
                mathml='<math xmlns="http://www.w3.org/1998/Math/MathML" data-error="ultra-crash"/>',
                intermediate_mathml=broken_mathml,
                raw_input=broken_mathml,
                recovery_confidence=0.0,
                recovery_log=[f"ULTRA crash: {exc}"],
            )

        # Normalize result keys
        clean_ml = res.get("mathml") or res.get("clean_mathml") or ""
        clean_latex = res.get("latex") or res.get("clean_latex") or ""
        confidence = float(res.get("confidence", 0.0) or 0.0)
        log = list(res.get("log", [])) if res.get("log") else []

        # If ULTRA returned LaTeX but no MathML, try to convert LaTeX -> MathML safely
        if clean_latex and not clean_ml:
            try:
                converted = self.mathml_converter.convert(clean_latex)
                clean_ml = converted
                log.append("Converted ULTRA-provided LaTeX -> MathML via mathml_converter")
                confidence = min(1.0, confidence + 0.15)
            except Exception as exc:
                log.append(f"LaTeX->MathML conversion of ULTRA output failed: {exc}")

        return PipelineResult(
            source_type="mathml",
            clean_latex=clean_latex,
            mathml=clean_ml or '<math xmlns="http://www.w3.org/1998/Math/MathML" data-error="ultra-no-output"/>',
            intermediate_mathml=broken_mathml,
            raw_input=broken_mathml,
            recovery_confidence=confidence,
            recovery_log=log,
        )

    # -------------------------
    # Safe LaTeX -> MathML conversion
    # -------------------------
    def _safe_latex_to_mathml(self, latex: str) -> str:
        try:
            return self.mathml_converter.convert(latex)
        except Exception as exc:
            logger.warning("[PIPELINE] latex->MathML conversion failed: %s", exc)
            # Return an empty valid MathML root with an error flag (no <mtext> fallback)
            return '<math xmlns="http://www.w3.org/1998/Math/MathML" data-error="conversion-failed"/>'

    # -------------------------
    # Public helper: ingest from fields (latex preferred if present)
    # -------------------------
    def ingest_from_fields(self, latex: Optional[str] = None, mathml: Optional[str] = None) -> PipelineResult:
        """
        Convenience: if both LaTeX and MathML are present, prefer LaTeX.
        This prevents corrupted MathML from overriding a correct LaTeX from OCR.
        """
        if latex and latex.strip():
            return self.ingest(latex)
        if mathml and mathml.strip():
            return self.ingest(mathml)
        return PipelineResult(source_type="empty", clean_latex="", mathml="", raw_input="")

    # -------------------------
    # Main ingest entry
    # -------------------------
    def ingest(self, raw_text: str) -> PipelineResult:
        source = self.detect_input_type(raw_text)
        logger.debug("[PIPELINE] Detected input type: %s", source)

        if source == "empty":
            return PipelineResult(source_type="empty", clean_latex="", mathml="", raw_input=raw_text)

        # -------------------------
        # MathML branch (ULTRA only for corrupted MathML)
        # -------------------------
        if source == "mathml":
            logger.info("[PIPELINE] MathML branch - cleaning first")
            try:
                cleaned = self.mathml_cleaner.clean(raw_text)
                cleaned_mathml = cleaned.get("mathml") if isinstance(cleaned, dict) else cleaned
                cleaned_mathml = cleaned_mathml or raw_text
            except Exception as exc:
                logger.exception("[PIPELINE] MathML cleaner failed, falling back to raw input")
                cleaned_mathml = raw_text

            # If corrupted -> FORCE ULTRA recovery (MathML-only mode)
            if self._is_corrupted_mathml(cleaned_mathml):
                logger.warning("[PIPELINE] Corrupted MathML detected -> running ULTRA recovery (FORCE MathML only)")
                return self._recover_mathml(cleaned_mathml)

            # Clean mathml is good — return it, do NOT produce guessed LaTeX
            return PipelineResult(
                source_type="mathml",
                clean_latex="",
                mathml=cleaned_mathml,
                intermediate_mathml=cleaned_mathml,
                raw_input=raw_text,
                recovery_confidence=1.0,
                recovery_log=[],
            )

        # -------------------------
        # LaTeX branch
        # -------------------------
        if source == "latex":
            logger.info("[PIPELINE] LaTeX branch - reconstructing if needed")
            clean_latex = self.reconstructor.reconstruct(raw_text)
            mathml = self._safe_latex_to_mathml(clean_latex)
            return PipelineResult(
                source_type="latex",
                clean_latex=clean_latex,
                mathml=mathml,
                intermediate_mathml=None,
                raw_input=raw_text,
                recovery_confidence=1.0,
                recovery_log=[],
            )

        # -------------------------
        # Plain OCR branch
        # -------------------------
        if source == "plain":
            logger.info("[PIPELINE] Plain OCR branch - treating as LaTeX candidate")
            clean_latex = self.reconstructor.reconstruct(raw_text)
            mathml = self._safe_latex_to_mathml(clean_latex)
            return PipelineResult(
                source_type="plain",
                clean_latex=clean_latex,
                mathml=mathml,
                intermediate_mathml=None,
                raw_input=raw_text,
                recovery_confidence=1.0,
                recovery_log=[],
            )

        raise RuntimeError("[PIPELINE] Unhandled input type: %s" % source)
