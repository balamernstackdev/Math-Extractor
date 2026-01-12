from __future__ import annotations
import re
import time
from functools import wraps
from typing import Optional, List, Tuple, Dict
from core.logger import logger
from core.config import settings
from .pipeline_components import (
    run_latex_pipeline,
    run_mathml_pipeline,
    StrictPipelineResult
)

class StrictMathpixPipeline:
    def __init__(self):
        self.log = []
        self._mathml_cache = {}  # Performance cache for MathML results
        logger.info("[StrictPipeline] Initialized with performance cache")

    def process_latex(self, latex: str) -> StrictPipelineResult:
        """
        MANDATORY Pipeline: Process LaTeX with ZERO tolerance for corruption.
        Delegates to modular run_latex_pipeline with caching.
        """
        if not latex:
            return {
                "source_type": "latex", "clean_latex": "", "mathml": "", "human_readable": "",
                "is_valid": False, "corruption_score": 0.0, "validation_errors": ["Empty input"],
                "corruption_detected": [], "stage_failed": "input_validation", "used_ai": False, "log": []
            }

        # 1. Performance Cache Check (Stable across sessions)
        import hashlib
        cache_key = hashlib.blake2b(latex.strip().encode('utf-8'), digest_size=16).hexdigest()
        
        if cache_key in self._mathml_cache:
            cached_result = self._mathml_cache[cache_key]
            new_result = cached_result.copy()
            new_result['log'] = cached_result['log'] + [f"[Cache] Hit for input: {latex[:30]}..."]
            logger.info(f"[Cache] Hit for input: {latex[:30]}...")
            return new_result
            
        # 2. Call Modular Orchestrator
        result = run_latex_pipeline(latex, settings)
        
        # 3. AI Repair Fallback (Phase 3)
        # If deterministic parsing fails, try to repair syntax with AI
        use_ai_fallback = getattr(settings, 'use_ai_fallback', True)
        openai_key = getattr(settings, 'openai_api_key', None)

        if not result.get("is_valid") and use_ai_fallback and openai_key and not settings.turbo_mode:
            logger.warning(f"[StrictPipeline] Parsing failed for: {latex[:30]}... Attempting AI Repair.")
            
            try:
                from services.ocr.openai_mathml_converter import OpenAIMathMLConverter
                converter = OpenAIMathMLConverter(api_key=openai_key)
                
                # Use STRICT mode to fix syntax only
                repair_result = converter.convert_latex_to_mathml_strict(latex)
                repaired_latex = repair_result.get("latex", "")
                
                if repaired_latex and repaired_latex != latex:
                    logger.info(f"[StrictPipeline] AI Repaired LaTeX: {repaired_latex}")
                    # Re-run pipeline on repaired latex
                    result = run_latex_pipeline(repaired_latex, settings)
                    result["restored_by_ai"] = True
                    result["original_latex"] = latex
                    result["log"].append("AI Repair Successful")
                else:
                    logger.warning("[StrictPipeline] AI Repair returned identical or empty LaTeX.")
                    result["log"].append("AI Repair Failed (No change)")
                    
            except Exception as e:
                logger.error(f"[StrictPipeline] AI Repair Exception: {e}")
                result["log"].append(f"AI Repair Error: {e}")

        # 4. Update Cache & State
        if result.get("is_valid"):
            self._mathml_cache[cache_key] = result
            
        self.log = result.get("log", [])
        return result

    def process_mathml(self, mathml: str) -> StrictPipelineResult:
        """
        MANDATORY Pipeline: Process MathML input with ZERO tolerance for corruption.
        Delegates to modular run_mathml_pipeline.
        """
        result = run_mathml_pipeline(mathml, settings)
        self.log = result.get("log", [])
        return result

    # Helper methods (if still needed by external callers)
    def _extract_latex_from_mathml(self, mathml: str) -> str:
        """Simple extractor helper."""
        if not mathml: return ""
        text = re.sub(r'<[^>]+>', ' ', mathml)
        return re.sub(r'\s+', ' ', text).strip()
