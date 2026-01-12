
import re
from typing import List, Tuple, Optional

def apply_letter_by_letter_fixes(latex: str) -> str:
    """
    Helper method to fix letter-by-letter spelling hacks.
    """
    if not latex:
        return latex
    
    fixed_latex = latex
    letter_by_letter_fixes = [
        (r'\\c_\{a\}l\b', r'\\cal'),
        (r'\\c_\{a\}l\s*\{', r'\\mathcal{'),
        (r'\\l_\{o\}n_\{g\}r_\{i\}g_\{h\}t_\{a\}r_\{r\}o_\{w\}', r'\\longrightarrow'),
        (r'\\l_\{o\}\s*n_\{g\}\s*r_\{i\}\s*g_\{h\}\s*t_\{a\}\s*r_\{r\}\s*o_\{w\}', r'\\longrightarrow'),
        (r'\\l_\{e\}f_\{t\}', r'\\left'),
        (r'\\r_\{i\}g_\{h\}t\b', r'\\right'),
        (r'\\s_\{u\}m\b', r'\\sum'),
        (r'\\m_\{a\}t_\{h\}b_{b}', r'\\mathbb'),
        (r'\\e_\{q\}u_{i}v\b', r'\\equiv'),
        (r'\\f_\{r\}a_{c}', r'\\frac'),
        (r'\\b_\{e\}g_{i}n\b', r'\\begin'),
        (r'\\e_\{n\}d\b', r'\\end'),
        (r'\\a_\{r\}r_{a}y\b', r'\\array'),
        (r'\\c_\{d\}o_{t}', r'\\cdot'),
        (r'\\c_\{d\}\s*o_{t}', r'\\cdot'),
    ]
    
    for pattern, replacement in letter_by_letter_fixes:
        fixed_latex = re.sub(pattern, replacement, fixed_latex)
    
    return fixed_latex

def normalize_latex_to_valid_commands(latex: str) -> str:
    """
    STEP 1: Normalize LaTeX into valid math commands.
    Replace spelled tokens with canonical operators BEFORE conversion.
    """
    if not latex:
        return latex
    
    normalized = latex
    
    # Common operators that are often spelled
    operator_replacements = [
        (r'e\s*_\s*\{?\s*q\s*\}?\s*u\s*_\s*\{?\s*i\s*\}?\s*v', r'\\equiv'),
        (r'e\s*_\s*\{?\s*q\s*\}?\s*u\s*_\s*\{?\s*i\s*\}?\s*v\s*a\s*l', r'\\equiv'),
        (r's\s*_\s*\{?\s*u\s*\}?\s*m\s*(?!\s*\{)', r'\\sum'),
        (r'm\s*_\s*\{?\s*i\s*\}?\s*n\s*(?!\s*\{)', r'\\min'),
        (r'm\s*_\s*\{?\s*a\s*\}?\s*x\s*(?!\s*\{)', r'\\max'),
        (r'f\s*_\s*\{?\s*r\s*\}?\s+a\s*_\s*\{?\s*c\s*\}?\b', r'\\frac'),
        (r'f\s*_\s*\{?\s*r\s*\}?\s*a\s*_\s*\{?\s*c\s*\}?\b', r'\\frac'),
        (r'l\s*_\s*\{?\s*e\s*\}?\s*f\s*_\s*\{?\s*t\s*\}?', r'\\left'),
        (r'r\s*_\s*\{?\s*i\s*\}?\s*g\s*_\s*\{?\s*h\s*\}?\s*t', r'\\right'),
        (r'l\s*_\s*\{?\s*o\s*\}?\s*n\s*_\s*\{?\s*g\s*\}?', r'\\long'),
        (r'm\s*_\s*\{?\s*a\s*\}?\s*t\s*_\s*\{?\s*h\s*\}?\s*b\s*_\s*\{?\s*b\s*\}?', r'\\mathbb'),
        (r'n\s*_\s*\{?\s*e\s*\}?\s*q', r'\\neq'),
        (r'l\s*_\s*\{?\s*d\s*\}?\s*o\s*_\s*\{?\s*r\s*\}?\s*t\s*\}?\s*s', r'\\ldots'),
        (r'b\s*_\s*\{?\s*i\s*\}?\s*g\s*_\s*\{?\s*c\s*\}?\s*u\s*_\s*\{?\s*p\s*\}?', r'\\bigcup'),
        (r'i\s*_\s*\{?\s*n\s*\}?\s*(?!\s*\{)', r'\\in'),
    ]
    
    for pattern, replacement in operator_replacements:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    
    return normalized

def get_truncated_patterns() -> List[Tuple[str, str]]:
    """
    Returns the list of regex patterns for detecting incomplete LaTeX commands.
    Patterns match incomplete commands that should be removed or completed.
    """
    return [
        # Incomplete \quad (spacing) - likely meant to be \quad but got cut off
        # Match \q followed by non-letter (digit, space, punctuation, or end)
        # CHANGED: Use [a-zA-Z] to avoid breaking valid commands like \qA if they were valid
        (r'\\q(?![a-zA-Z])', r'\\quad '),  # Add space after \quad for safety
        (r'\\qu(?![a-zA-Z])', r'\\quad '),
        
        # Other incomplete commands at end - just remove them
        (r'\\su$', ''),
        (r'\\le$', ''),
        (r'\\ri$', ''),
        (r'\\fr$', ''),
        (r'\\ma$', ''),
    ]

def apply_truncation_fixes(latex: str) -> Tuple[str, List[str]]:
    """
    Detects and removes incomplete LaTeX commands at the end of the string.
    Also handles incomplete set definitions and logical conditions.
    """
    cleaned_latex = latex
    logs = []
    
    truncated_patterns = get_truncated_patterns()
    
    # Check for truncated commands
    for pattern, replacement in truncated_patterns:
        if re.search(pattern, cleaned_latex):
            logs.append(f"Detected incomplete LaTeX command, removing: {pattern}")
            cleaned_latex = re.sub(pattern, replacement, cleaned_latex)
    
    # Check for any remaining incomplete commands at end (1-3 letters after backslash)
    if re.search(r'\\[a-z]{1,3}$', cleaned_latex):
        logs.append("Detected LaTeX ending with incomplete command, removing it")
        cleaned_latex = re.sub(r'\\[a-z]{1,3}$', '', cleaned_latex)
    
    # ENHANCED: Check for incomplete set definitions
    # Pattern: \left\{ ... : \forall ... \in ... (missing closing \right\})
    if r'\left\{' in cleaned_latex and r'\right\}' not in cleaned_latex:
        # Check if it looks like a set definition with conditions
        if re.search(r'\\left\\{.*:\\s*\\forall', cleaned_latex):
            logs.append("Detected incomplete set definition, adding closing brace")
            # Add closing for the set
            cleaned_latex += r' \right\}'
    
    # ENHANCED: Check for incomplete logical conditions
    # Pattern: \forall w_1, ..., w_K \in (incomplete - missing rest)
    if re.search(r'\\forall\s+\w+.*,\s*$', cleaned_latex):
        logs.append("Detected incomplete \\forall condition, trimming")
        # Remove the incomplete trailing part
        cleaned_latex = re.sub(r',\s*$', '', cleaned_latex)
    
    # ENHANCED: Remove trailing incomplete \in statements
    # Pattern: \in \mathbb{R} (incomplete - might be missing subscript or condition)
    if re.search(r'\\in\s+\\mathbb\{[A-Z]\}\s*$', cleaned_latex):
        # This might be complete, but if followed by nothing, it's likely truncated
        # Check if there should be more (like subscript or comma)
        if not re.search(r'\\in\s+\\mathbb\{[A-Z]\}_', cleaned_latex):
            # No subscript, might be incomplete - but keep it as is
            pass
    
    return cleaned_latex, logs

def fix_unbalanced_delimiters(latex: str) -> Tuple[str, List[str]]:
    r"""
    Fixes unbalanced braces, brackets, and \left/\right pairs.
    Returns (fixed_latex, log_messages)
    """
    cleaned_latex = latex
    logs = []
    
    # 1. Handle \left/\right pairs (CRITICAL)
    left_matches = re.findall(r'\\left(?:[^a-zA-Z]|\\[a-zA-Z]+)', cleaned_latex)
    right_matches = re.findall(r'\\right(?:[^a-zA-Z]|\\[a-zA-Z]+)', cleaned_latex)
    left_count = len(left_matches)
    right_count = len(right_matches)
    
    if right_count > left_count:
        extra_rights = right_count - left_count
        logs.append(f"Detected {extra_rights} extra \\right commands, removing from end")
        for _ in range(extra_rights):
            match = re.search(r'\\right(?:([}\]\)\|])|(\\(?:rangle|lbrace|rbrace|langle|vert|Vert|brace|paren|brack|ceil|floor)))([^\\]*)$', cleaned_latex)
            if match:
                cleaned_latex = cleaned_latex[:match.start()] + match.group(3)
    
    if left_count > right_count:
        missing_rights = left_count - right_count
        logs.append(f"Detected {missing_rights} missing \\right commands, adding at end")
        last_left_match = list(re.finditer(r'\\left(?:([^a-zA-Z])|(\\(?:rangle|lbrace|vert|Vert|brace|paren|brack|ceil|floor)))', cleaned_latex))
        if last_left_match:
            last_match = last_left_match[-1]
            if last_match.group(1):
                delim_map = {'(': ')', '[': ']', '{': '}', '|': '|', '.': '.'}
                cleaned_latex += '\\right' + delim_map.get(last_match.group(1), '}')
            elif last_match.group(2):
                cmd_map = {
                    '\\langle': '\\rangle', '\\lbrace': '\\rbrace',
                    '\\vert': '\\vert', '\\Vert': '\\Vert',
                    '\\brace': '\\brace', '\\paren': '\\paren',
                    '\\brack': '\\brack', '\\ceil': '\\floor', '\\floor': '\\ceil',
                }
                cleaned_latex += '\\right' + cmd_map.get(last_match.group(2), '\\rangle')
            else:
                cleaned_latex += '\\right}'

    # 2. Handle simple braces {}
    open_braces = cleaned_latex.count('{')
    close_braces = cleaned_latex.count('}')
    if open_braces > close_braces:
        missing = open_braces - close_braces
        logs.append(f"Detected {missing} unclosed braces, attempting to close")
        cleaned_latex += '}' * missing
    elif close_braces > open_braces:
        extra = close_braces - open_braces
        logs.append(f"Detected {extra} extra closing braces, removing from end")
        for _ in range(min(extra, 5)):
            if cleaned_latex.endswith('}'):
                cleaned_latex = cleaned_latex[:-1]
                
    # 3. Handle simple brackets []
    open_brackets = cleaned_latex.count('[')
    close_brackets = cleaned_latex.count(']')
    if open_brackets > close_brackets:
        missing = open_brackets - close_brackets
        logs.append(f"Detected {missing} unclosed brackets, attempting to close")
        cleaned_latex += ']' * missing
    elif close_brackets > open_brackets:
        extra = close_brackets - open_brackets
        logs.append(f"Detected {extra} extra closing brackets, removing from end")
        for _ in range(min(extra, 5)):
            if cleaned_latex.endswith(']'):
                cleaned_latex = cleaned_latex[:-1]

    return cleaned_latex, logs
