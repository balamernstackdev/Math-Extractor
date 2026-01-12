from __future__ import annotations
from pathlib import Path
from PyQt6 import QtCore
from core.logger import logger
from core.config import settings
from services.ocr.equation_cache import get_equation_cache

class OCRWorker(QtCore.QThread):
    """Background worker for OCR and pipeline processing tasks."""
    # FINAL result signal (full MathML, validated)
    result_ready = QtCore.pyqtSignal(str, str, str, bool, float, object) # image_path, latex, mathml, is_valid, confidence_score, ast_node
    
    # PROGRESSIVE result signal (raw LaTeX, fast)
    partial_result_ready = QtCore.pyqtSignal(str, str) # image_path, raw_latex
    
    # STATUS update signal (for UI messaging)
    status_update = QtCore.pyqtSignal(str) # message
    
    error_occurred = QtCore.pyqtSignal(str, str) # error_message, image_path
    
    def __init__(self, image_path: str, latex_ocr, pipeline, mode="ocr", latex_input=None, handwriting_mode=False, table_mode=False):
        super().__init__()
        self.image_path = image_path
        self.latex_ocr = latex_ocr
        self.pipeline = pipeline
        self.mode = mode # "ocr" or "latex"
        self.latex_input = latex_input
        self.handwriting_mode = handwriting_mode
        self.table_mode = table_mode
        
    def run(self):
        try:
            self.status_update.emit("Reading image...")
            # PERFORMANCE: Check cache first (skip for handwriting/table mode to force fresh vision)
            cache = get_equation_cache()
            if not self.handwriting_mode and not self.table_mode:
                cached_result = cache.get(self.image_path)
                
                if cached_result:
                    logger.info(f"[OCRWorker] Using cached result for {Path(self.image_path).name}")
                    
                    # Fix artifacts even in cached results
                    latex_out = cached_result["latex"]
                    mathml_out = cached_result["mathml"]
                    
                    # RETROACTIVE FIX: Replace \equiv with =
                    latex_out = latex_out.replace(r'\equiv', '=')
                    latex_out = latex_out.replace('≡', '=')
                    
                    # RETROACTIVE FIX: Replace \bigcup with \sum (Contextual fix for this OCR)
                    latex_out = latex_out.replace(r'\bigcup', r'\sum')
                    latex_out = latex_out.replace('⋃', '∑')
                    
                    if mathml_out:
                        mathml_out = mathml_out.replace('&#x2261;', '=')
                        mathml_out = mathml_out.replace('≡', '=')
                        # Fix bigunion in mathml if present as entity or char
                        mathml_out = mathml_out.replace('&#x22C3;', '∑')
                        mathml_out = mathml_out.replace('⋃', '∑')
                    
                    # Use stored score or default to 1.0 for cache hits
                    score = cached_result.get("corruption_score", 0.0) 
                    confidence = 1.0 - score
                    self.result_ready.emit(
                        self.image_path,
                        latex_out,
                        mathml_out,
                        cached_result["is_valid"],
                        confidence,
                        None # No AST for cached results (yet)
                    )
                    return
            
            # Unified Pipeline (Delegates to StrictMathpixPipeline)
            # Step 1: Get LaTeX (either via OCR or direct input)
            if self.mode == "ocr":
                try:
                    # START LOCAL OCR
                    latex = self.latex_ocr.image_to_latex(Path(self.image_path), handwriting_mode=self.handwriting_mode, table_mode=self.table_mode)
                    
                    if self.isInterruptionRequested():
                        logger.info(f"[OCRWorker] Interrupted after local OCR for {self.image_path}")
                        return

                    # PROGRESSIVE FEEDBACK: Emit partial results immediately
                    if latex and latex.strip() and latex != r"\text{OCR failed}":
                        # We have raw text - let the UI render it ASAP
                        self.partial_result_ready.emit(self.image_path, latex)
                        self.status_update.emit("Refining equation...")
                        
                except Exception as ocr_err:
                    logger.error(f"[OCRWorker] OCR failed: {ocr_err}")
                    self.error_occurred.emit(f"OCR failed: {str(ocr_err)}", self.image_path)
                    return
                    
                if not latex or latex.strip() == "" or latex == r"\text{OCR failed}":
                    self.error_occurred.emit("OCR failed to read the formula.", self.image_path)
                    return
            else:
                latex = self.latex_input
                
            if not latex:
                self.error_occurred.emit("No LaTeX input provided.", self.image_path)
                return

            if self.isInterruptionRequested():
                logger.info(f"[OCRWorker] Interrupted before pipeline for {self.image_path}")
                return

            # Step 2: Process through strict pipeline
            # This handles cleaning, semantic rewrite (OpenAI), and MathML conversion
            try:
                logger.info(f"[OCRWorker] Processing LaTeX through pipeline: {latex[:100]}")
                result = self.pipeline.process_latex(latex)
                
                clean_latex = result.get("clean_latex", latex)
                mathml = result.get("mathml", "")
                is_valid = result.get("is_valid", False)
                corruption_score = result.get("corruption_score", 0.0)
                used_ai = result.get("used_ai", False)
                
                # Confidence is inverse of corruption
                confidence = max(0.0, 1.0 - corruption_score)
                
                # If valid but score is low, boost it slightly (trust the validator)
                if is_valid and confidence < 0.8:
                    confidence = 0.85
                
                logger.info(f"[OCRWorker] Pipeline complete: valid={is_valid}, conf={confidence:.2f}, AI={used_ai}")
                
                # PERFORMANCE: Cache the result
                cache.put(self.image_path, clean_latex, mathml, is_valid, corruption_score=corruption_score)
                
                self.result_ready.emit(self.image_path, clean_latex, mathml, is_valid, confidence, None)
            except Exception as pipe_err:
                logger.error(f"[OCRWorker] Pipeline failed: {pipe_err}")
                logger.exception("[OCRWorker] Full pipeline exception:")
                # Use raw latex as fallback if pipeline fails
                # Emit result_ready so UI doesn't hang
                error_mathml = f'<math xmlns="http://www.w3.org/1998/Math/MathML" data-error="pipeline-worker-failure" data-details="{str(pipe_err)[:100]}"/>'
                self.result_ready.emit(self.image_path, latex, error_mathml, False, 0.0, None)
            
        except Exception as e:
            logger.exception(f"[OCRWorker] Critical task failure: {e}")
            # Emit error signal to update UI
            self.error_occurred.emit(str(e), self.image_path)
