from __future__ import annotations
import time
import re
from typing import Tuple, List, Optional
from core.logger import logger
from .orchestration_types import PipelineContext, StrictPipelineResult
from .normalization import normalize_latex_semantics, strip_typographic_spacing, ensure_double_struck_sets, normalize_mathml_entities, strip_invisible_characters, strip_ai_artifacts
from .corruption import is_semantically_clean_latex, pre_openai_regex_corruption_checker, has_spelling_hack, detect_latex_corruption, is_corrupted_mathml, mathml_has_spelled_words
from .validation import (
    validate_latex_ast_rules, 
    validate_latex_syntax, 
    validate_mathml_strict, 
    validate_mathml_ast_rules, 
    validate_multiline_mathml, 
    is_llm_generated_mathml, 
    validate_operators_in_mathml
)
from .cleanup import normalize_latex_to_valid_commands, apply_truncation_fixes
from .structural import apply_structural_mathml_fixes
from .ai_logic import mandatory_openai_cleanup

def create_pipeline_context(input_data: str, source_type: str, settings) -> PipelineContext:
    """Initialize a fresh pipeline context."""
    return {
        "original_input": input_data,
        "source_type": source_type,
        "clean_latex": input_data if source_type == "latex" else "",
        "mathml": input_data if source_type == "mathml" else "",
        "is_valid": False,
        "corruption_score": 0.0,
        "validation_errors": [],
        "corruption_detected": [],
        "stage_failed": None,
        "used_ai": False,
        "log": [],
        "fast_mode": getattr(settings, "fast_mode", False),
        "cache_hit": False,
        "start_time": time.time()
    }

def stage_input_normalization(context: PipelineContext):
    """Normalize input (strip delimiters, basic semantic fixes)."""
    latex = context["clean_latex"]
    if not latex:
        return

    # Strip AI/OCR artifacts
    latex = strip_ai_artifacts(latex)

    # Strip $ delimiters
    if latex.startswith("$") and latex.endswith("$"):
        latex = latex[1:-1].strip()
        context["log"].append("STEP 1.5: Stripped $ delimiters from LaTeX")
    
    # Initial semantic normalization
    before = latex
    latex = normalize_latex_semantics(latex)
    if latex != before:
        context["log"].append("STEP 1.6: Applied semantic normalization")
    
    context["clean_latex"] = latex

def stage_corruption_gate(context: PipelineContext, settings):
    """Detect corruption and perform AI recovery if needed."""
    latex = context["clean_latex"]
    context["log"].append("STEP 2: REGEX + AST CORRUPTION GATE (CRITICAL)")
    
    # Rule 1: Clean check
    if is_semantically_clean_latex(latex) and "begin{array}" not in latex and len(latex) < 100:
        context["log"].append("✅ RULE 1: LaTeX is semantically clean - SKIPPING corruption checks")
        return

    # Perform detectors
    is_pre, pre_patterns = pre_openai_regex_corruption_checker(latex)
    is_hack, hack_patterns = has_spelling_hack(latex)
    is_ast_ok, ast_violations = validate_latex_ast_rules(latex)
    is_corrupted, corruption_patterns = detect_latex_corruption(latex)
    
    context["corruption_detected"].extend(pre_patterns + hack_patterns + ast_violations + corruption_patterns)
    
    # Check for critical corruption types that maximize score
    has_critical_corruption = any("split command" in p.lower() or "shredded" in p.lower() for p in context["corruption_detected"])
    
    # Calculate score
    base_score = min(1.0, len(context["corruption_detected"]) / 10.0)
    
    if has_critical_corruption:
        # Boost score significantly for split commands (harder to fix deterministically)
        base_score = max(base_score, 0.8)
        
    penalty = 0.4 if len(latex) > 50 else (0.2 if len(latex) > 30 else 0.0)
    context["corruption_score"] = min(1.0, base_score + penalty)
    
    # Trigger OpenAI if corrupted
    if is_pre or is_hack or not is_ast_ok or is_corrupted:
        if context["fast_mode"] and context["corruption_score"] < 0.3:
            context["log"].append(f"⚡ FAST MODE - Skipping OpenAI (Score: {context['corruption_score']:.2f})")
            return
            
        context["log"].append("🚨 CORRUPTION GATE TRIGGERED - OpenAI semantic repair")
        fixed_latex = mandatory_openai_cleanup(latex, context["corruption_detected"], context["log"])
        context["used_ai"] = True
        
        if not fixed_latex or fixed_latex == latex:
            context["log"].append("STEP 3 WARNING: OpenAI rewrite did not improve LaTeX")
        else:
            context["clean_latex"] = fixed_latex
            context["log"].append("STEP 3 PASSED: OpenAI semantic rewrite successful")

def stage_syntax_validation(context: PipelineContext):
    """Validate LaTeX syntax and auto-balance braces."""
    latex = context["clean_latex"]
    
    # Structural repair (braces, \left/\right)
    from .cleanup import fix_unbalanced_delimiters
    latex, f_logs = fix_unbalanced_delimiters(latex)
    if f_logs:
        context["log"].extend([f"STEP 4: {log}" for log in f_logs])
    
    ok, errs = validate_latex_syntax(latex)
    if not ok:
        context["validation_errors"].extend(errs)
        # Be lenient if it looks like an array/matrix
        if re.search(r'\\begin\{(array|matrix|bmatrix|pmatrix)', latex, re.IGNORECASE):
            context["log"].append("STEP 4: Array detected - attempting conversion despite errors")
        else:
            context["stage_failed"] = "latex_validation"
    
    context["clean_latex"] = latex

def stage_post_validation_cleanup(context: PipelineContext):
    """Extra normalization and spacing strip before conversion."""
    latex = context["clean_latex"]
    
    # Semantic normalization
    latex = normalize_latex_semantics(latex)
    
    # Mandatory spacing strip
    latex = strip_typographic_spacing(latex)
    latex = strip_invisible_characters(latex)
    context["log"].append("STEP 4.6: Stripped typographic spacing & invisible chars")
    
    # Truncation repair
    repaired, t_logs = apply_truncation_fixes(latex)
    if t_logs:
        context["log"].extend(t_logs)
        latex = repaired
        
    context["clean_latex"] = latex

def stage_deterministic_conversion(context: PipelineContext):
    """Convert LaTeX to MathML using deterministic converter."""
    from services.ocr.latex_to_mathml import LatexToMathML
    converter = LatexToMathML()
    
    try:
        mathml = converter.convert(context["clean_latex"])
        # Apply structural fixes (AttributeError prevention)
        mathml, msg = apply_structural_mathml_fixes(mathml)
        if msg: context["log"].append(f"[Structural] {msg}")
        
        # Ensure boilerplate attributes
        if 'xmlns=' not in mathml:
            mathml = mathml.replace('<math', '<math xmlns="http://www.w3.org/1998/Math/MathML"')
        if 'display=' not in mathml:
             mathml = mathml.replace('<math ', '<math display="block" ')
             
        context["mathml"] = mathml
    except Exception as e:
        context["log"].append(f"STEP 5 FAILED: Conversion error: {str(e)}")
        context["stage_failed"] = "latex_to_mathml"

def stage_mathml_validation(context: PipelineContext, settings):
    """Validate generated MathML and attempt AI fallback if failing/missing."""
    mathml = context.get("mathml", "")
    latex = context.get("clean_latex", "")
    
    # CASE 1: MathML is missing (Deterministic conversion failed)
    if not mathml:
        if not latex: return
        
        # Turbo Mode: Skip AI fallback
        if getattr(settings, 'turbo_mode', False):
             context["log"].append("STEP 6: MathML missing - [TURBO] Skipping AI recovery")
             context["stage_failed"] = "conversion_failed"
             return

        context["log"].append("STEP 6: MathML missing - attempting AI recovery from LaTeX")
        from .ai_logic import try_ai_fallback_strict
        ai_res = try_ai_fallback_strict(latex, "")
        
        if ai_res and ai_res.get("mathml"):
            context["mathml"] = ai_res["mathml"]
            context["used_ai"] = True
            context["stage_failed"] = None # Recovered!
            context["log"].append("STEP 6.1 PASSED: AI recovered MathML from LaTeX")
        else:
            context["stage_failed"] = "conversion_and_fallback_failed"
        return

    # CASE 2: MathML exists but might be invalid
    is_ok, errs = validate_mathml_strict(mathml)
    if not is_ok:
        context["validation_errors"].extend(errs)
        
        # Turbo Mode: Skip AI fallback
        if getattr(settings, 'turbo_mode', False):
             context["log"].append("STEP 6 FAILED: MathML validation failed - [TURBO] Skipping AI fallback")
             context["stage_failed"] = "mathml_validation"
             return

        context["log"].append("STEP 6 FAILED: MathML validation failed - attempting AI fallback")
        
        from .ai_logic import try_ai_fallback_strict
        ai_res = try_ai_fallback_strict(latex, mathml)
        
        if ai_res and ai_res.get("mathml"):
            context["mathml"] = ai_res["mathml"]
            context["used_ai"] = True
            context["stage_failed"] = None # Recovered!
            context["log"].append("STEP 6.2 PASSED: AI fallback recovered valid MathML")
        else:
            context["stage_failed"] = "mathml_validation"

def stage_final_normalization(context: PipelineContext):
    """Apply final entities and namespace cleanup."""
    mathml = context.get("mathml", "")
    if not mathml: return
    
    # normalize_mathml_entities and ensure_double_struck_sets are already imported at module level
    
    # Structural fixes (Always clean AI and deterministic output of LaTeX leakage)
    mathml, msg = apply_structural_mathml_fixes(mathml)
    if msg: context["log"].append(f"[Final Structural] {msg}")

    # Entities
    mathml = normalize_mathml_entities(mathml)
    # Double-struck sets
    mathml = ensure_double_struck_sets(mathml)
    # Namespace cleanup
    mathml = mathml.replace('<mml:', '<').replace('</mml:', '</')
    
    context["mathml"] = mathml
    context["is_valid"] = True if not context["stage_failed"] else False

def stage_final_safety_check(context: PipelineContext):
    """Deep scan for any remaining hallucinations in final outputs."""
    latex = context.get("clean_latex", "")
    mathml = context.get("mathml", "")
    
    from .corruption import detect_latex_corruption, is_corrupted_mathml
    
    # 1. LaTeX Check
    is_l_corr, l_patterns = detect_latex_corruption(latex)
    if is_l_corr:
        context["stage_failed"] = "hallucination_detected"
        context["log"].append(f"🚨 FINAL SAFETY FAILED: {', '.join(l_patterns[:3])}")
        context["is_valid"] = False
        return

    # 2. MathML Check
    if is_corrupted_mathml(mathml):
        context["stage_failed"] = "hallucination_detected"
        context["log"].append("🚨 FINAL SAFETY FAILED: MathML contains tag hallucinations")
        context["is_valid"] = False

def run_latex_pipeline(latex: str, settings) -> StrictPipelineResult:
    """Main entry point for LaTeX processing."""
    context = create_pipeline_context(latex, "latex", settings)
    
    stage_input_normalization(context)
    stage_corruption_gate(context, settings)
    
    if context["stage_failed"]:
        return finalize_result(context)
        
    stage_syntax_validation(context)
    stage_post_validation_cleanup(context)
    stage_deterministic_conversion(context)
    
    if context["stage_failed"]:
        stage_mathml_validation(context, settings) # Try AI fallback even if deterministic failed
    else:
        stage_mathml_validation(context, settings)
        
    stage_final_normalization(context)
    stage_final_safety_check(context) # Final guard
    return finalize_result(context)

def run_mathml_pipeline(mathml: str, settings) -> StrictPipelineResult:
    """Main entry point for MathML processing."""
    context = create_pipeline_context(mathml, "mathml", settings)
    context["log"].append("MANDATORY PIPELINE: Processing MathML input")
    
    # 1. MathML Validation & Corruption Gate
    is_corrupted = is_corrupted_mathml(mathml)
    has_words, word_viols = mathml_has_spelled_words(mathml)
    is_llm, llm_inds = is_llm_generated_mathml(mathml)
    
    if is_llm:
         context["log"].append("🛑 GATEKEEPER: LLM-GENERATED MathML DETECTED - REJECTING")
         context["stage_failed"] = "gatekeeper_llm_detection"
         return finalize_result(context)

    # 2. If corrupted, reconstruct to LaTeX
    if is_corrupted or has_words:
        context["log"].append("🚨 CORRUPTION DETECTED in MathML input")
        # Reuse existing Logic from StrictMathpixPipeline (to be moved to ai_logic if needed)
        # For now, we'll assume there's a reconstruct_latex_from_mathml in ai_logic
        from .ai_logic import reconstruct_latex_from_mathml
        reconstructed_latex = reconstruct_latex_from_mathml(mathml, context["log"])
        if reconstructed_latex:
            context["clean_latex"] = reconstructed_latex
            context["used_ai"] = True
            # Delegate to latex pipeline
            return run_latex_pipeline(reconstructed_latex, settings)
    
    # 3. If clean, extract and run latex pipeline
    # (Simplified for now - real extractor needed)
    context["log"].append("STEP 1 PASSED: MathML is clean, extracting LaTeX")
    return run_latex_pipeline(mathml, settings) # Temporary placeholder

def finalize_result(context: PipelineContext) -> StrictPipelineResult:
    """Consolidate context into a final result object."""
    return {
        "source_type": context["source_type"],
        "clean_latex": context["clean_latex"],
        "mathml": context["mathml"],
        "human_readable": context["clean_latex"], # Simple mirror for now
        "is_valid": context["is_valid"],
        "corruption_score": context["corruption_score"],
        "validation_errors": context["validation_errors"],
        "corruption_detected": context["corruption_detected"],
        "stage_failed": context["stage_failed"],
        "used_ai": context["used_ai"],
        "log": context["log"]
    }
