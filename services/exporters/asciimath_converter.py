"""Service for converting LaTeX to AsciiMath."""
import re
from core.logger import logger

def latex_to_asciimath(latex: str) -> str:
    """
    Convert LaTeX math string to AsciiMath.
    Supports common symbols, operators, and structures.
    """
    if not latex:
        return ""
        
    text = latex.strip()
    
    # Remove math delimiters if present
    if text.startswith("$$") and text.endswith("$$"):
        text = text[2:-2].strip()
    elif text.startswith("$") and text.endswith("$"):
        text = text[1:-1].strip()
        
    # Basic replacements
    replacements = [
        (r'\\alpha', 'alpha'), (r'\\beta', 'beta'), (r'\\gamma', 'gamma'),
        (r'\\delta', 'delta'), (r'\\epsilon', 'epsilon'), (r'\\zeta', 'zeta'),
        (r'\\eta', 'eta'), (r'\\theta', 'theta'), (r'\\iota', 'iota'),
        (r'\\kappa', 'kappa'), (r'\\lambda', 'lambda'), (r'\\mu', 'mu'),
        (r'\\nu', 'nu'), (r'\\xi', 'xi'), (r'\\pi', 'pi'), (r'\\rho', 'rho'),
        (r'\\sigma', 'sigma'), (r'\\tau', 'tau'), (r'\\upsilon', 'upsilon'),
        (r'\\phi', 'phi'), (r'\\chi', 'chi'), (r'\\psi', 'psi'), (r'\\omega', 'omega'),
        (r'\\Gamma', 'Gamma'), (r'\\Delta', 'Delta'), (r'\\Theta', 'Theta'),
        (r'\\Lambda', 'Lambda'), (r'\\Xi', 'Xi'), (r'\\Pi', 'Pi'),
        (r'\\Sigma', 'Sigma'), (r'\\Phi', 'Phi'), (r'\\Psi', 'Psi'),
        (r'\\Omega', 'Omega'),
        
        (r'\\infty', 'oo'),
        (r'\\le', '<='), (r'\\ge', '>='), (r'\\neq', '!='),
        (r'\\pm', '+-'), (r'\\mp', '-+'),
        (r'\\times', 'xx'), (r'\\div', '-:'),
        (r'\\cdot', '*'), (r'\\ast', '*'),
        (r'\\star', 'star'), (r'\\circ', 'o'),
        (r'\\sqrt', 'sqrt'),
        (r'\\sin', 'sin'), (r'\\cos', 'cos'), (r'\\tan', 'tan'),
        (r'\\log', 'log'), (r'\\ln', 'ln'),
        (r'\\sum', 'sum'), (r'\\prod', 'prod'), (r'\\int', 'int'),
        (r'\\text', 'text'),
        
        (r'\\left\(', '('), (r'\\right\)', ')'),
        (r'\\left\[', '['), (r'\\right\]', ']'),
        (r'\\left\{', '{'), (r'\\right\}', '}'),
        (r'\\left', ''), (r'\\right', ''),
        
        (r'\\frac\{([^}]*)\}\{([^}]*)\}', r'(\1)/(\2)'),
        (r'\\hat\{([^}]*)\}', r'hat(\1)'),
        (r'\\bar\{([^}]*)\}', r'bar(\1)'),
        (r'\\vec\{([^}]*)\}', r'vec(\1)'),
        (r'\\dot\{([^}]*)\}', r'dot(\1)'),
        (r'\\ddot\{([^}]*)\}', r'ddot(\1)'),
    ]
    
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
        
    # Clean up braces that AREN'T part of commands now
    text = text.replace('{', '(').replace('}', ')')
    
    # Fix backslashes for remaining commands
    text = text.replace('\\', '')
    
    return text.strip()

class AsciiMathConverter:
    """Service to handle LaTeX -> AsciiMath conversion including AI fallback."""
    
    def convert(self, latex: str) -> str:
        """Main entry point for conversion."""
        try:
            # Try fast local conversion
            result = latex_to_asciimath(latex)
            
            # If still contains complex LaTeX-isms, maybe fallback to OpenAI
            # In Phase 4, we prioritize correctness.
            if "\\" in result or "begin{" in result:
                return self._ai_fallback(latex)
            
            return result
        except Exception as e:
            logger.error(f"AsciiMath conversion failed: {e}")
            return self._ai_fallback(latex)

    def _ai_fallback(self, latex: str) -> str:
        """Use OpenAI to convert complex LaTeX to AsciiMath."""
        try:
            from services.ocr.openai_mathml_converter import OpenAIMathMLConverter
            converter = OpenAIMathMLConverter()
            
            prompt = (
                "Convert the following LaTeX math expression to AsciiMath format. "
                "Output ONLY the raw AsciiMath string, no explanations, no markdown blocks."
            )
            
            # Reusing the converter structure
            response = converter.convert_with_openai(
                system_prompt="You are a mathematical notation expert. Convert LaTeX to AsciiMath.",
                user_content=f"{prompt}\n\nLaTeX: {latex}"
            )
            
            if response:
                return response.strip()
            return latex # Final fallback
        except Exception:
            return latex
