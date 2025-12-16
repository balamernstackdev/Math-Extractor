# services/ocr/math_expression_pipeline.py
"""
SAFE & CORRECT Unified ingestion pipeline for MathML / LaTeX / Plain OCR inputs.

Guarantees:
 - MathML is never converted back to LaTeX except when explicitly using the
   ULTRA recovery module (recover_from_mathml).
 - OCRMathMLCleaner only cleans XML structure and doesn't guess math.
 - DynamicLaTeXReconstructor is used only for LaTeX/plain OCR inputs.
 - latex2mathml conversion returns a real MathML root (no <mtext> fallback).
 - Corruption detection is strict and uses ULTRA recovery when needed.
"""

from __future__ import annotations

import re
from typing import Literal, Optional, TypedDict, List

from core.logger import logger

from services.ocr.dynamic_latex_reconstructor import DynamicLaTeXReconstructor
from services.ocr.latex_to_mathml import LatexToMathML
from services.ocr.ocr_mathml_cleaner import OCRMathMLCleaner

# ULTRA recovery (optional)
try:
    from services.ocr.mathml_recovery_pro import ultra_mathml_recover as recover_from_mathml  # type: ignore
except Exception:
    recover_from_mathml = None
    logger.debug("[PIPELINE] ULTRA MathML recovery module not available")

SourceType = Literal["mathml", "latex", "plain", "empty"]


class PipelineResult(TypedDict, total=False):
    source_type: SourceType
    clean_latex: str
    mathml: str
    intermediate_mathml: Optional[str]
    raw_input: str
    recovery_confidence: Optional[float]
    recovery_log: Optional[List[str]]


# ---------------------------------------------------------------------
# Pipeline implementation
# ---------------------------------------------------------------------
class MathExpressionPipeline:
    """Unified ingestion pipeline with robust MathML corruption detection and ULTRA recovery."""

    def __init__(
        self,
        reconstructor: Optional[DynamicLaTeXReconstructor] = None,
        mathml_converter: Optional[LatexToMathML] = None,
        mathml_cleaner: Optional[OCRMathMLCleaner] = None,
    ) -> None:
        self.reconstructor = reconstructor or DynamicLaTeXReconstructor()
        self.mathml_converter = mathml_converter or LatexToMathML()
        self.mathml_cleaner = mathml_cleaner or OCRMathMLCleaner()

    # ---------------------
    # Input detection
    # ---------------------
    def detect_input_type(self, raw: str) -> SourceType:
        """Return one of: 'mathml', 'latex', 'plain', 'empty'."""
        if not raw or not raw.strip():
            return "empty"

        text = raw.strip()
        # Strong MathML detection — prefer explicit structural tags
        if (text.startswith("<math") and "</math" in text) or any(tag in text for tag in ("<mrow", "<msub", "<msup", "<mfrac", "<mi>", "<mo>")):
            return "mathml"

        # LaTeX detection: commands, markers, or typical LaTeX constructs
        if re.search(r"\\[A-Za-z]+", text) or re.search(r"[_^]\{?", text) or "$" in text:
            return "latex"

        return "plain"

    # ---------------------
    # MathML corruption heuristics (ULTRA-ready)
    # ---------------------
    def _is_corrupted_mathml(self, mathml: str) -> bool:
        """Detect heavy OCR corruption in MathML requiring recovery."""
        if not mathml or len(mathml) < 40:
            return False

        # Letter-by-letter shredded sequences, e.g. <mi>l</mi><mi>e</mi><mi>f</mi><mi>t</mi>
        if re.search(r"(?:<mi>\s*\\?[a-zA-Z]\s*</mi>\s*){4,}", mathml):
            return True

        # explicit shredded textual patterns (loose)
        shredded = [
            r"l\s*e\s*f\s*t", r"r\s*i\s*g\s*h\s*t", r"s\s*u\s*m", r"f\s*r\s*a\s*c", r"m\s*a\s*t\s*h\s*b\s*b"
        ]
        for p in shredded:
            if re.search(p, mathml, re.IGNORECASE):
                return True

        # Many <mi> and almost no <mo> -> operator tokens likely missing
        mi_count = len(re.findall(r"<mi\b", mathml))
        mo_count = len(re.findall(r"<mo\b", mathml))
        if mi_count > 12 and mo_count < 2:
            return True

        # Double-closed subscripts or obvious nested-tag errors
        if re.search(r"</msub>\s*</msub>", mathml):
            return True

        # Double-escaped latex fragments in MathML (broken)
        if "\\\\left" in mathml or "\\\\right" in mathml or "\\\\frac" in mathml:
            return True

        # Backslash tokens in <mi>/<mo>/<mtext> tags indicate OCR shreds
        if re.search(r"<m[iot][^>]*>\\[A-Za-z]", mathml):
            return True
        
        # Pattern: <mi>\f</mi> or <mi>\s</mi> or <mi>\l</mi> (shredded commands)
        if re.search(r"<mi>\\[a-z]</mi>", mathml, re.IGNORECASE):
            return True
        
        # Pattern: <msub><mi>\f</mi>... (shredded commands in subscripts)
        if re.search(r"<msub[^>]*>\s*<mi>\\[a-z]</mi>", mathml, re.IGNORECASE):
            return True

        return False

    # ---------------------
    # Recover using ULTRA engine (if available)
    # ---------------------
    def _recover_mathml(self, raw_mathml: str, force_mode: bool = True) -> PipelineResult:
        """
        FORCE ULTRA MathML Recovery
        
        ALWAYS attempts to reconstruct LaTeX from corrupted MathML.
        NEVER returns raw shredded MathML.
        
        Args:
            raw_mathml: Input MathML (may be corrupted)
            force_mode: If True, always attempt recovery even for seemingly valid MathML
        """
        if recover_from_mathml is None:
            logger.error("[PIPELINE] FORCE ULTRA recovery module not installed")
            return PipelineResult(
                source_type="mathml",
                clean_latex="",
                mathml='<math xmlns="http://www.w3.org/1998/Math/MathML" data-error="ultra-missing"/>',
                intermediate_mathml=raw_mathml,
                raw_input=raw_mathml,
                recovery_confidence=0.0,
                recovery_log=["FORCE ULTRA recovery module not installed"],
            )

        logger.info("[PIPELINE] Running FORCE ULTRA MathML recovery (force_mode=%s)", force_mode)
        try:
            # Get OpenAI settings from config if available
            from core.config import settings
            openai_key = getattr(settings, 'openai_api_key', None)
            openai_model = getattr(settings, 'openai_model', 'gpt-4o-mini')
            
            # ALWAYS use OpenAI if API key is available (auto-enable)
            use_openai = openai_key is not None
            if use_openai:
                logger.info("[PIPELINE] OpenAI fallback enabled (API key available)")
            
            # Always use FORCE mode for recovery, with OpenAI fallback if available
            out = recover_from_mathml(
                raw_mathml,
                force_mode=force_mode,
                use_openai_fallback=use_openai,
                openai_api_key=openai_key,
                openai_model=openai_model
            )
            
            # Log recovery details for debugging
            if out.get("corruption_detected"):
                logger.warning("[PIPELINE] FORCE recovery detected corruption: %s", 
                             ', '.join(out.get("corruption_reasons", [])))
            logger.debug("[PIPELINE] FORCE recovery confidence: %.3f", out.get("confidence", 0.0))
            logger.debug("[PIPELINE] FORCE recovery steps: %d", len(out.get("log", [])))
        except Exception as exc:
            logger.exception("[PIPELINE] ULTRA recovery crashed", exc_info=True)
            return PipelineResult(
                source_type="mathml",
                clean_latex="",
                mathml='<math xmlns="http://www.w3.org/1998/Math/MathML" data-error="ultra-crash"/>',
                intermediate_mathml=raw_mathml,
                raw_input=raw_mathml,
                recovery_confidence=0.0,
                recovery_log=[f"ULTRA crash: {exc}"],
            )

        # Normalise keys and defensive access
        clean_mathml = out.get("mathml") or out.get("clean_mathml") or ""
        clean_latex = out.get("latex") or out.get("clean_latex") or ""
        confidence = float(out.get("confidence", 0.0) or 0.0)
        log = out.get("log", []) or []

        if clean_mathml:
            logger.info(f"[PIPELINE] ULTRA recovery succeeded (confidence={confidence:.2f})")
            return PipelineResult(
                source_type="mathml",
                clean_latex=clean_latex,
                mathml=clean_mathml,
                intermediate_mathml=raw_mathml,
                raw_input=raw_mathml,
                recovery_confidence=confidence,
                recovery_log=log,
            )

        logger.warning("[PIPELINE] ULTRA recovery returned no MathML — returning fallback placeholder")
        return PipelineResult(
            source_type="mathml",
            clean_latex=clean_latex,
            mathml='<math xmlns="http://www.w3.org/1998/Math/MathML" data-error="mathml-recovery-failed"/>',
            intermediate_mathml=raw_mathml,
            raw_input=raw_mathml,
            recovery_confidence=confidence,
            recovery_log=log,
        )

    # ---------------------
    # Safe LaTeX → MathML conversion (no <mtext> fallback)
    # ---------------------
    def _safe_latex_to_mathml(self, latex: str) -> str:
        try:
            return self.mathml_converter.convert(latex)
        except Exception as exc:
            logger.error("[PIPELINE] latex→MathML conversion failed: %s", exc)
            # Always return a valid MathML root (machine-readable marker)
            return '<math xmlns="http://www.w3.org/1998/Math/MathML" data-error="conversion-failed"/>'
    
    # ---------------------
    # OpenAI integration helpers
    # ---------------------
    def _is_corrupted_latex(self, latex: str) -> bool:
        """Detect corrupted LaTeX patterns (shredded commands)."""
        if not latex:
            return False
        
        # Check for shredded command patterns like \e_{q}u_{i}v, \m_{a}t_{h}b_{f}
        shredded_patterns = [
            r'\\[a-z]_\{[a-z]\}[a-z]_\{[a-z]\}',  # \e_{q}u_{i} pattern
            r'\\[a-z]_\{[a-z]\}[a-z]_\{[a-z]\}[a-z]_\{[a-z]\}',  # \m_{a}t_{h}b_{f}
            r'\\[a-z]\s+[a-z]\s+[a-z]',  # Spaced commands like \ e q
        ]
        
        for pattern in shredded_patterns:
            if re.search(pattern, latex):
                return True
        
        return False
    
    def _should_use_openai(self) -> bool:
        """Check if OpenAI should be used based on config."""
        try:
            from core.config import settings
            # Use OpenAI if API key is set (auto-enable when key is present)
            has_key = getattr(settings, 'openai_api_key', None) is not None
            if not has_key:
                logger.debug("[PIPELINE] OpenAI not available: API key not set")
            return has_key
        except Exception as exc:
            logger.debug("[PIPELINE] OpenAI check failed: %s", exc)
            return False
    
    def _try_openai_latex_cleanup(self, corrupted_latex: str) -> str:
        """Try to clean corrupted LaTeX using OpenAI."""
        if not self._should_use_openai():
            return corrupted_latex
        
        try:
            from services.ocr.openai_mathml_converter import OpenAIMathMLConverter
            from core.config import settings
            
            logger.info("[PIPELINE] Calling OpenAI to clean corrupted LaTeX")
            converter = OpenAIMathMLConverter(
                api_key=getattr(settings, 'openai_api_key', None),
                model=getattr(settings, 'openai_model', 'gpt-4o-mini')
            )
            
            # Convert LaTeX to clean LaTeX and MathML
            result = converter.convert_latex_to_mathml(corrupted_latex, context="Corrupted OCR LaTeX with shredded commands")
            cleaned = result.get("latex", corrupted_latex)
            confidence = result.get("confidence", 0.0)
            
            if cleaned != corrupted_latex and confidence > 0.5:
                logger.info("[PIPELINE] OpenAI cleaned LaTeX (confidence: %.2f): %s -> %s", 
                           confidence, corrupted_latex[:60], cleaned[:60])
                return cleaned
            else:
                logger.debug("[PIPELINE] OpenAI cleanup did not improve LaTeX significantly (confidence: %.2f)", confidence)
        except Exception as exc:
            logger.warning("[PIPELINE] OpenAI LaTeX cleanup failed: %s", exc)
        
        return corrupted_latex
    
    def _try_openai_conversion(self, latex: str) -> dict | None:
        """
        DEPRECATED: OpenAI should NOT convert LaTeX → MathML.
        
        According to the MANDATORY PIPELINE:
        - OpenAI is ONLY used for LaTeX semantic rewriting
        - MathML MUST come from deterministic LaTeX→MathML compiler (latex2mathml) ONLY
        - OpenAI MUST NOT generate MathML
        - OpenAI MUST NOT fix MathML
        - OpenAI MUST NOT convert LaTeX → MathML
        
        Use StrictMathpixPipeline instead for proper pipeline flow.
        """
        logger.warning("[PIPELINE] 🚫 OpenAI LaTeX→MathML conversion DISABLED - use StrictMathpixPipeline instead")
        logger.warning("[PIPELINE] 🚫 RULE: MathML must come from deterministic LaTeX→MathML compiler only")
        return None

    # ---------------------
    # Public ingest API
    # ---------------------
    def ingest(self, raw_text: str) -> PipelineResult:
        """Master ingestion entrypoint. Returns PipelineResult."""

        source = self.detect_input_type(raw_text)
        logger.debug("[PIPELINE] Detected source type: %s", source)

        # EMPTY
        if source == "empty":
            return PipelineResult(source_type="empty", clean_latex="", mathml="", raw_input=raw_text)

        # MATHML branch - FORCE MODE: Always check for corruption
        if source == "mathml":
            logger.info("[PIPELINE] MathML input branch (FORCE mode enabled)")
            
            # FORCE MODE: Check for corruption BEFORE cleaning
            is_corrupted = self._is_corrupted_mathml(raw_text)
            if is_corrupted:
                logger.warning("[PIPELINE] FORCE: Corruption detected in raw MathML — invoking FORCE recovery immediately")
                return self._recover_mathml(raw_text, force_mode=True)
            
            # Try cleaning first (if cleaner available)
            try:
                cleaned_result = self.mathml_cleaner.clean(raw_text)
                # Cleaner may return dict or string
                cleaned_mathml = cleaned_result.get("mathml") if isinstance(cleaned_result, dict) else cleaned_result
                cleaned_mathml = cleaned_mathml or raw_text
            except (AttributeError, Exception):
                # Fallback if cleaner not available or fails
                cleaned_mathml = raw_text
            
            # FORCE MODE: Check again after cleaning - corruption may still exist
            if self._is_corrupted_mathml(cleaned_mathml):
                logger.warning("[PIPELINE] FORCE: MathML still corrupted after cleaning — invoking FORCE recovery")
                return self._recover_mathml(cleaned_mathml, force_mode=True)
            
            # FORCE MODE: Even if not obviously corrupted, check for mtext with LaTeX (common OCR issue)
            if re.search(r'<mtext\b[^>]*>.*\\[A-Za-z]', cleaned_mathml, re.IGNORECASE):
                logger.warning("[PIPELINE] FORCE: MathML contains mtext with LaTeX — invoking FORCE recovery")
                return self._recover_mathml(cleaned_mathml, force_mode=True)
            
            # MathML is clean - return as-is
            logger.info("[PIPELINE] MathML is clean, returning as-is")
            return PipelineResult(
                source_type="mathml",
                clean_latex="",
                mathml=cleaned_mathml,
                intermediate_mathml=cleaned_mathml,
                raw_input=raw_text,
                recovery_confidence=1.0,
                recovery_log=[],
            )

        # LATEX branch
        if source == "latex":
            logger.info("[PIPELINE] LaTeX input branch")
            logger.debug("[PIPELINE] Raw LaTeX input: %s", raw_text[:150])
            
            # Check if INPUT is already corrupted BEFORE reconstruction
            input_is_corrupted = self._is_corrupted_latex(raw_text)
            if input_is_corrupted:
                logger.warning("[PIPELINE] Input LaTeX is already corrupted, skipping reconstructor to avoid further corruption")
                clean_latex = raw_text  # Skip reconstructor if input is corrupted
            else:
                clean_latex = self.reconstructor.reconstruct(raw_text)
                logger.debug("[PIPELINE] Reconstructed LaTeX: %s", clean_latex[:150])
            
            # Check if LaTeX is corrupted (has shredded patterns)
            is_corrupted = self._is_corrupted_latex(clean_latex)
            should_use_openai = self._should_use_openai()
            
            logger.info("[PIPELINE] LaTeX corruption check: input_corrupted=%s, output_corrupted=%s, should_use_openai=%s", 
                       input_is_corrupted, is_corrupted, should_use_openai)
            
            # ALWAYS use OpenAI for corrupted LaTeX - it handles complex equations better
            if is_corrupted and should_use_openai:
                logger.warning("[PIPELINE] Corrupted LaTeX detected (shredded patterns), using OpenAI for cleanup and conversion")
                logger.info("[PIPELINE] Calling OpenAI conversion for corrupted LaTeX: %s", clean_latex[:100])
                # Use OpenAI to both clean LaTeX AND convert to MathML in one step
                ai_result = self._try_openai_conversion(clean_latex)
                if ai_result and ai_result.get("mathml"):
                    logger.info("[PIPELINE] OpenAI handled corrupted LaTeX successfully (confidence: %.2f)", 
                               ai_result.get("confidence", 0.0))
                    return PipelineResult(
                        source_type="latex",
                        clean_latex=ai_result.get("latex", clean_latex),
                        mathml=ai_result.get("mathml", ""),
                        intermediate_mathml=None,
                        raw_input=raw_text,
                        recovery_confidence=ai_result.get("confidence", 0.8),
                        recovery_log=ai_result.get("log", []),
                    )
                else:
                    logger.warning("[PIPELINE] OpenAI conversion failed or returned no MathML, trying cleanup")
                # If OpenAI failed, try cleanup and continue with standard conversion
                clean_latex = self._try_openai_latex_cleanup(clean_latex)
            elif is_corrupted and not should_use_openai:
                logger.warning("[PIPELINE] Corrupted LaTeX detected but OpenAI not available (API key not set)")
            
            mathml = self._safe_latex_to_mathml(clean_latex)
            
            # Check if resulting MathML is corrupted (even if LaTeX was clean)
            is_mathml_corrupted = False
            if mathml and 'data-error' not in mathml:
                is_mathml_corrupted = self._is_corrupted_mathml(mathml)
                if is_mathml_corrupted:
                    logger.info("[PIPELINE] MathML output contains corruption patterns")
            
            # Log MathML status for debugging
            logger.info("[PIPELINE] MathML conversion result: has_error=%s, is_corrupted=%s, length=%d, should_use_openai=%s", 
                        'data-error' in mathml if mathml else 'no mathml', is_mathml_corrupted, len(mathml) if mathml else 0, self._should_use_openai())
            
            # If MathML conversion failed OR MathML is corrupted, try OpenAI
            should_try_openai = ('data-error' in mathml or not mathml or is_mathml_corrupted) and self._should_use_openai()
            
            # ALWAYS use OpenAI if LaTeX was corrupted (even if conversion "succeeded")
            # Corrupted LaTeX often produces invalid MathML that needs AI fixing
            if is_corrupted and self._should_use_openai() and not should_try_openai:
                logger.info("[PIPELINE] Using OpenAI for corrupted LaTeX (even though conversion appeared to succeed)")
                should_try_openai = True
            
            if should_try_openai:
                if is_mathml_corrupted:
                    logger.info("[PIPELINE] Corrupted MathML detected in output, attempting OpenAI fix")
                elif 'data-error' in mathml or not mathml:
                    logger.info("[PIPELINE] MathML conversion failed, trying OpenAI")
                else:
                    logger.info("[PIPELINE] Attempting OpenAI conversion")
                
                ai_result = self._try_openai_conversion(clean_latex)
                if ai_result and ai_result.get("mathml"):
                    logger.info("[PIPELINE] OpenAI produced clean MathML (confidence: %.2f)", 
                               ai_result.get("confidence", 0.0))
                    return PipelineResult(
                        source_type="latex",
                        clean_latex=ai_result.get("latex", clean_latex),
                        mathml=ai_result.get("mathml", mathml),
                        intermediate_mathml=None,
                        raw_input=raw_text,
                        recovery_confidence=ai_result.get("confidence", 0.8),
                        recovery_log=ai_result.get("log", []),
                    )
                else:
                    logger.debug("[PIPELINE] OpenAI conversion did not produce MathML")
            
            return PipelineResult(
                source_type="latex",
                clean_latex=clean_latex,
                mathml=mathml,
                intermediate_mathml=None,
                raw_input=raw_text,
            )

        # PLAIN OCR branch
        if source == "plain":
            logger.info("[PIPELINE] Plain OCR input branch (treat as text → reconstruct)")
            clean_latex = self.reconstructor.reconstruct(raw_text)
            mathml = self._safe_latex_to_mathml(clean_latex)
            return PipelineResult(
                source_type="plain",
                clean_latex=clean_latex,
                mathml=mathml,
                intermediate_mathml=None,
                raw_input=raw_text,
            )

        # Shouldn't reach here
        raise RuntimeError(f"[PIPELINE] Unhandled pipeline state: {source}")
