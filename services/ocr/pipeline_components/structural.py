
import re
import xml.etree.ElementTree as ET
from typing import Tuple, Optional

def apply_structural_mathml_fixes(mathml_string: str) -> Tuple[str, Optional[str]]:
    """
    Logic Fix: Converts side-aligned indices to vertical stacks
    to prevent symbol overlapping in summations and limits.
    Also handles invalid XML entities that might crash the parser.
    
    Returns: (fixed_mathml, log_message)
    """
    if not mathml_string or "<math" not in mathml_string:
        return mathml_string, None

    ET.register_namespace('', "http://www.w3.org/1998/Math/MathML")
    
    def _parse_and_fix(xml_str):
        root = ET.fromstring(xml_str)
        
        # Promotion to munderover
        for node in root.iter():
            if any(tag in node.tag for tag in ['msub', 'msubsup']):
                if len(node) > 0:
                    base = node[0]
                    display_ops = ['∑', 'lim', 'sup', 'max', 'min', '&#x2211;', '&#x220F;']
                    if base.text and any(op in base.text for op in display_ops):
                        node.tag = node.tag.replace('msub', 'munderover').replace('msubsup', 'munderover')
        
        # Fix nested fraction collisions
        for mfrac in root.findall(".//{http://www.w3.org/1998/Math/MathML}mfrac"):
            if len(mfrac) > 1 and mfrac[1].find(".//{http://www.w3.org/1998/Math/MathML}mfrac") is not None:
                mfrac.set('linethickness', '1.1')

        # LaTeX commands in <mo> to Unicode entities
        latex_map = {
            r'\le': '&#x2264;', r'\leq': '&#x2264;',
            r'\ge': '&#x2265;', r'\geq': '&#x2265;',
            r'\in': '&#x2208;',
            r'\notin': '&#x2209;',
            r'\neq': '&#x2260;',
            r'\approx': '&#x2248;',
            r'\times': '&#x00D7;',
            r'\cdot': '&#x22C5;',
            r'\to': '&#x2192;', r'\rightarrow': '&#x2192;',
            r'\longrightarrow': '&#x2196;', # Note: Correcting to long right arrow below
            r'\longleftrightarrow': '&#x2194;',
            r'\infty': '&#x221E;',
            r'\pm': '&#x00B1;',
            r'\{': '{', r'\}': '}',
            r'\forall': '&#x2200;', r'\exists': '&#x2203;',
            r'\subset': '&#x2282;', r'\supset': '&#x2283;',
            r'\setminus': '&#x2216;',
        }
        # Correct mapping for long arrows
        latex_map[r'\longrightarrow'] = '&#x27F6;'
        latex_map[r'\longleftarrow'] = '&#x27F5;'
        for mo in root.iter("{http://www.w3.org/1998/Math/MathML}mo"):
            if mo.text and mo.text.strip().startswith('\\'):
                cmd = mo.text.strip()
                if cmd in latex_map:
                    mo.text = latex_map[cmd]

        return ET.tostring(root, encoding='unicode')

    try:
        return _parse_and_fix(mathml_string), None
    except Exception as e:
        error_msg = str(e)
        if "char" in error_msg or "entity" in error_msg or "reference" in error_msg:
            sanitized = mathml_string
            
            def fix_hex_entity(match):
                try:
                    val = int(match.group(1), 16)
                    return "?" if val > 0x10FFFF else match.group(0)
                except ValueError:
                    return match.group(0)

            sanitized = re.sub(r'&#x([0-9A-Fa-f]+);', fix_hex_entity, sanitized)
            
            def fix_dec_entity(match):
                try:
                    val = int(match.group(1))
                    return "?" if val > 0x10FFFF else match.group(0)
                except ValueError:
                    return match.group(0)

            sanitized = re.sub(r'&#([0-9]+);', fix_dec_entity, sanitized)
            
            try:
                return _parse_and_fix(sanitized), f"Sanitized invalid XML characters: {error_msg}"
            except Exception as retry_e:
                return sanitized, f"Structural fix failed after sanitization: {retry_e}"
        
        return mathml_string, f"Structural fix failed: {e}"

def audit_structural_integrity(latex: str) -> Tuple[bool, str, Optional[str]]:
    """
    Ensures complex structures (sets, matrices) are closed before conversion.
    
    Returns: (is_fixed, fixed_latex, optional_log_msg)
    """
    fixed_latex = latex
    log_msg = None
    try:
        # Detect unclosed set
        if "\\left\\{" in latex and "\\right\\}" not in latex:
            log_msg = "GATEKEEPER: Unclosed set detected. Forcing closure."
            fixed_latex += " \\right\\}"
            
        # Detect dangling environment starts (e.g., array)
        if "\\begin{" in latex and "\\end{" not in latex:
            match = re.search(r'\\begin\{([^}]+)\}', latex)
            if match:
                env_name = match.group(1)
                fixed_latex += f" \\end{{{env_name}}}"
                if not log_msg:
                    log_msg = f"GATEKEEPER: Unclosed environment \\begin{{{env_name}}} detected. Forcing closure."
            
        return fixed_latex != latex, fixed_latex, log_msg
    except Exception as e:
        return False, latex, f"Structural audit error: {e}"
