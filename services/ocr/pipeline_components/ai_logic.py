
import re
from typing import List, Tuple, Dict, Optional
from core.logger import logger

def build_openai_math_context(corrupted_latex: str, corruption_patterns: List[str], is_truncated: bool) -> str:
    """
    Builds the detailed context/prompt for OpenAI LaTeX cleanup.
    """
    truncation_note = ""
    if is_truncated:
        truncation_note = """
⚠️ CRITICAL: The input LaTeX appears to be INCOMPLETE/TRUNCATED (ends abruptly or has unbalanced braces).
- Complete the equation based on mathematical context
- Close any unclosed braces {} or brackets [] with meaningful content if needed
- If the equation ends with missing terms (e.g. infinite sums, logic conditions), reconstruct them
- Common truncations: \\q (likely \\quad), \\su (likely \\sum), incomplete operators
"""

    corruption_list = chr(10).join(f"- {p}" for p in corruption_patterns[:15])
    
    context = f"""You are a MathOCR semantic reconstruction engine.
{truncation_note}

Input may contain CORRUPTED LaTeX where operators are spelled using subscripts
(e.g., f_r a_c, s_u m, l_e f_t, r_i g_h t, l_{{e}}f_{{t}}, r_{{i}}g_{{h}}t).

🚫 MANDATORY RULES:
- NEVER preserve broken tokens.
- NEVER output LaTeX that spells words via subscripts.
- NEVER output literal 'munderover', 'munder', 'mover' as plain text; these are internal MathML tag names, not LaTeX text.
- ALWAYS reconstruct correct mathematical operators.
- FIX missing or corrupted special characters (braces, brackets, operators).
- ENSURE all LaTeX commands are complete and valid.

CORRUPTION DETECTED:
{corruption_list}

✅ REWRITE RULES (RECONSTRUCT FROM SEMANTICS):
- f_r a_c → \\frac
- s_u_m → \\sum
- l_e_f_t or l_{{e}}f_{{t}} → \\left
- r_i_g_h_t or r_{{i}}g_{{h}}t → \\right
- l_e_q → \\leq
- m_a_t_h_b_b → \\mathbb
- e_q_u_i_v → \\equiv
- l_o_n_g → \\longrightarrow
- b_f → \\mathbf
- i n Z → i \\in \\mathbb{{Z}}
- Z(j) → \\mathbb{{Z}}(j)
- 'munderover' text artifact → \\munderover command or correct script structure
- FIX missing operators (+, -, =) based on semantic context

OUTPUT FORMAT (JSON ONLY - CRITICAL):
{{
  "latex": "<clean semantic latex>",
  "confidence": 0.90
}}

🚫 CRITICAL: Output ONLY valid JSON text. NO markdown blocks, NO explanations.
🚫 ABSOLUTE PROHIBITION: DO NOT HALLUCINATE OR INVENT CHARACTERS. IF UNSURE, RETURN ORIGINAL."""
    return context

def execute_openai_math_cleanup(latex: str, context: str, api_key: str, model: str) -> Tuple[str, float, List[str]]:
    """
    Executes the actual OpenAI API call for LaTeX cleanup.
    """
    from services.ocr.openai_mathml_converter import OpenAIMathMLConverter
    
    try:
        converter = OpenAIMathMLConverter(api_key=api_key, model=model)
        result = converter.convert_latex_to_mathml(latex, context=context)
        
        cleaned_latex = result.get("latex", latex)
        confidence = result.get("confidence", 0.0)
        logs = result.get("log", [])
        
        return cleaned_latex, confidence, logs
    except Exception as e:
        logger.error(f"OpenAI cleanup execution failed: {e}")
        return latex, 0.0, [f"Error during OpenAI execution: {e}"]

def mandatory_openai_cleanup(latex: str, corruption_patterns: List[str], log: List[str]) -> str:
    """Orchestrates the OpenAI cleanup for corrupted LaTeX."""
    from core.config import settings
    
    api_key = getattr(settings, 'openai_api_key', None)
    if not api_key:
        log.append("STEP 3 FAILED: OpenAI API key not found")
        return latex
        
    context = build_openai_math_context(latex, corruption_patterns, is_truncated=False)
    cleaned, confidence, ai_logs = execute_openai_math_cleanup(
        latex, context, api_key, getattr(settings, 'openai_model', 'gpt-4o-mini')
    )
    
    log.extend(ai_logs)
    return cleaned if cleaned else latex

def reconstruct_latex_from_mathml(mathml: str, log: List[str]) -> Optional[str]:
    """Reconstruct clean LaTeX from corrupted MathML using OpenAI."""
    from services.ocr.openai_mathml_converter import OpenAIMathMLConverter
    from core.config import settings
    
    api_key = getattr(settings, 'openai_api_key', None)
    if not api_key:
        log.append("ERROR: OpenAI API key required for MathML reconstruction but not found")
        return None
        
    log.append("MANDATORY: Initializing OpenAI for MathML → LaTeX reconstruction")
    converter = OpenAIMathMLConverter(
        api_key=api_key,
        model=getattr(settings, 'openai_model', 'gpt-4o-mini')
    )
    
    try:
        if hasattr(converter, 'convert_corrupted_mathml'):
            result = converter.convert_corrupted_mathml(mathml, target_format="latex", include_latex=True)
        else:
            # Fallback to a prompt-based approach if specialized method is missing
            result = converter.convert_latex_to_mathml_strict(mathml, context="Reconstruct clean LaTeX from this corrupted MathML.")
            
        clean_latex = result.get("latex", "") or result.get("clean_latex", "")
        return clean_latex
    except Exception as e:
        log.append(f"MANDATORY: MathML reconstruction failed: {e}")
        return None

def mandatory_openai_mathml_fix(latex: str, mathml: str, log: List[str]) -> Optional[str]:
    """Fallback: Ask OpenAI to fix MathML directly from LaTeX if deterministic conversion fails."""
    from services.ocr.openai_mathml_converter import OpenAIMathMLConverter
    from core.config import settings
    
    api_key = getattr(settings, 'openai_api_key', None)
    if not api_key: return None
    
    converter = OpenAIMathMLConverter(api_key=api_key, model=getattr(settings, 'openai_model', 'gpt-4o-mini'))
    try:
        result = converter.convert_latex_to_mathml(latex)
        return result.get("mathml")
    except Exception as e:
        log.append(f"AI MathML Fallback failed: {e}")
        return None

def try_ai_fallback_strict(latex: str, failing_mathml: str) -> Dict:
    """Attempt a strict AI fallback for failing MathML."""
    # Wrapper for orchestrator usage
    from core.config import settings
    api_key = getattr(settings, 'openai_api_key', None)
    if not api_key: return {}
    
    from services.ocr.openai_mathml_converter import OpenAIMathMLConverter
    converter = OpenAIMathMLConverter(api_key=api_key, model=getattr(settings, 'openai_model', 'gpt-4o-mini'))
    try:
        return converter.convert_latex_to_mathml(latex)
    except:
        return {}
