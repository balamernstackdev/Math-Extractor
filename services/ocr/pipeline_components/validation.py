
import re
import xml.etree.ElementTree as ET
from typing import Tuple, List
from core.logger import logger

def validate_latex_ast_rules(latex: str) -> Tuple[bool, List[str]]:
    """
    AST-LEVEL CHECKER for LaTeX (REQUIRED).
    
    LaTeX AST Rules - Reject if:
    - Operator nodes represented as identifiers
    - Subscripts contain >1 alphabetic token
    - Command tokens fragmented into letters
    
    Returns: (is_valid, list_of_violations)
    """
    if not latex:
        return True, []
    
    violations = []
    
    # Check: Operator nodes represented as identifiers
    # Pattern: operators written as plain text (not commands)
    operator_as_identifier = [
        (r'(?<!\\)\b(equiv|sum|min|max|log|sin|cos|in|notin)\b(?!\s*\{)', 'AST VIOLATION: operator represented as identifier'),
    ]
    
    for pattern, violation in operator_as_identifier:
        if re.search(pattern, latex, re.IGNORECASE):
            violations.append(violation)
    
    # Check: Subscripts contain >1 alphabetic token
    # Pattern: _{word} where word is multi-letter (not single identifier)
    multi_letter_subscript = r'_\s*\{([a-zA-Z]{2,})\}'
    matches = re.findall(multi_letter_subscript, latex)
    for match in matches:
        # Allow common math identifiers (but not words)
        if match.lower() not in ['in', 'eq', 'ne', 'le', 'ge']:
            violations.append(f'AST VIOLATION: subscript contains >1 alphabetic token: {match}')
    
    # Check: Command tokens fragmented into letters
    # Pattern: letter-by-letter subscripts that form commands
    fragmented_commands = [
        (r'([a-z])_\{([a-z])\}([a-z])_\{([a-z])\}([a-z])', 'AST VIOLATION: command token fragmented into letters'),
    ]
    
    for pattern, violation in fragmented_commands:
        if re.search(pattern, latex, re.IGNORECASE):
            violations.append(violation)
    
    return len(violations) == 0, violations


def validate_mathml_strict(mathml: str) -> Tuple[bool, List[str]]:
    """
    MANDATORY: Strict MathML validation with ZERO tolerance.
    
    Returns: (is_valid, list_of_violations)
    """
    if not mathml or not mathml.strip():
        return False, ['Empty MathML']
    
    violations = []
    
    # Structural check via XML parsing
    try:
        root = ET.fromstring(mathml)
        tag_name = root.tag.split('}')[-1] if '}' in root.tag else root.tag
        if tag_name != 'math':
            violations.append(f"BLOCKER: Invalid root element. Expected <math>, got <{tag_name}> (Incorrect root element)")
    except ET.ParseError as e:
        msg = f"BLOCKER: Invalid MathML XML structure - {e}"
        # Test compliance: if it looks like it's missing <math> or has raw ASCII
        if "math" not in mathml:
            msg += " (missing <math> root)"
        if "<=" in mathml or "!=" in mathml:
            msg += " (Found unescaped ASCII operators, use Unicode equivalents)"
        violations.append(msg)
        return False, violations

    # Rule: Empty tokens
    for node in root.iter():
        tag = node.tag.split('}')[-1]
        if tag in {'mi', 'mo', 'mn'}:
            if not (node.text and node.text.strip()) and len(node) == 0:
                violations.append(f"INVALID: Empty mathematical token <{tag}>")

    # Rule: Missing namespace
    if 'xmlns="http://www.w3.org/1998/Math/MathML"' not in mathml:
        violations.append("INVALID: Missing MathML namespace declaration")
        
    # Rule: LaTeX commands in MathML
    if re.search(r'\\(?:frac|sqrt|left|right|begin|end)', mathml):
        violations.append("INVALID: LaTeX commands found in MathML text nodes")
        
    # Rule: Operators in <mi>
    op_ok, op_violations = validate_operators_in_mathml(mathml)
    if not op_ok:
        violations.extend(op_violations)
        
    # Gatekeeper: JS and LLM noise
    gatekeeper_patterns = [
        (r'\[object Object\]', 'GATEKEEPER VIOLATION: JavaScript object leak detected'),
        (r'\\begin\{array\}', 'GATEKEEPER VIOLATION: LaTeX array environment in text node'),
    ]
    for pattern, violation in gatekeeper_patterns:
        if re.search(pattern, mathml):
            violations.append(violation)

    # Rule 1: Spelling words via msub (STRICTLY FORBIDDEN)
    repeated_subscript_words = [
        (r'(?:<msub><mi>e</mi><mi>q</mi></msub>.*?<msub><mi>u</mi><mi>i</mi></msub>.*?<mi>v</mi>)|(?:<msub><mi>e</mi><mi>q</mi></msub>.*?<mi>u</mi>.*?<msub><mi>i</mi><mi>v</mi></msub>)', 'STRICTLY FORBIDDEN: "equiv" spelled via repeated single-letter <msub> chains (e_q u_i v)'),
        (r'<msub><mi>s</mi><mi>u</mi></msub>.*?<mi>m</mi>', 'STRICTLY FORBIDDEN: "sum" spelled via repeated single-letter <msub> chains (s_u m)'),
        (r'<msub><mi>m</mi><mi>a</mi></msub>.*?<msub><mi>t</mi><mi>h</mi></msub>.*?<msub><mi>b</mi><mi>b</mi></msub>', 'STRICTLY FORBIDDEN: "mathbb" spelled via repeated single-letter <msub> chains (m_a t_h b_b)'),
        # Generic multi-subscript rule removed to prevent false positives on valid sequences like variables with indices
    ]
    
    for pattern, violation in repeated_subscript_words:
        if re.search(pattern, mathml, re.IGNORECASE):
            violations.append(violation)
            
    # Display check
    display_match = re.search(r'display=["\']([^"\']+)["\']', mathml)
    if display_match:
        display_value = display_match.group(1)
        if display_value not in ['block', 'inline']:
            violations.append(f'INVALID: display attribute must be "block" or "inline", not "{display_value}"')
    
    return len(violations) == 0, violations


def validate_multiline_mathml(mathml: str) -> Tuple[bool, List[str]]:
    """
    Validate MathML table structure for multi-line equations.
    """
    if not mathml or not mathml.strip():
        return True, []
    
    violations = []
    
    if '<mtable' not in mathml:
        return True, []
    
    try:
        root = ET.fromstring(mathml)
    except ET.ParseError as e:
        violations.append(f"BLOCKER: Invalid XML structure - {e}")
        return False, violations
    
    tables = (root.findall('.//{http://www.w3.org/1998/Math/MathML}mtable') or 
              root.findall('.//mtable'))
    
    if not tables:
        violations.append("ERROR: Found <mtable tag but not valid XML element")
        return False, violations
    
    for table_idx, table in enumerate(tables):
        rows = (table.findall('{http://www.w3.org/1998/Math/MathML}mtr') or 
                table.findall('mtr'))
        
        if len(rows) < 1:
            violations.append(f"ERROR: Table {table_idx+1} has no rows (<mtr>)")
            continue
        
        for row_idx, row in enumerate(rows):
            cells = (row.findall('{http://www.w3.org/1998/Math/MathML}mtd') or 
                     row.findall('mtd'))
            
            if len(cells) < 1:
                violations.append(f"ERROR: Table {table_idx+1}, Row {row_idx+1} has no cells (<mtd>)")
        
        cell_counts = []
        for row in rows:
            cells = (row.findall('{http://www.w3.org/1998/Math/MathML}mtd') or 
                     row.findall('mtd'))
            cell_counts.append(len(cells))
        
        if len(set(cell_counts)) > 1:
            violations.append(f"WARNING: Table {table_idx+1} has inconsistent column counts: {cell_counts}.")
        
        for row_idx, row in enumerate(rows):
            cells = (row.findall('{http://www.w3.org/1998/Math/MathML}mtd') or 
                     row.findall('mtd'))
            all_empty = True
            for cell in cells:
                if (cell.text and cell.text.strip()) or len(list(cell)) > 0:
                    all_empty = False
                    break
            if all_empty:
                violations.append(f"WARNING: Table {table_idx+1}, Row {row_idx+1} is completely empty")
        
        for child in table:
            tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if tag_name not in ['mtr', 'mlabeledtr']:
                violations.append(f"ERROR: Table {table_idx+1} has invalid direct child <{tag_name}>.")
    
    is_valid = len([v for v in violations if 'BLOCKER' in v or 'ERROR' in v]) == 0
    return is_valid, violations


def is_llm_generated_mathml(mathml: str) -> Tuple[bool, List[str]]:
    """
    GATEKEEPER RULE: Detect if MathML was generated by an LLM.
    """
    if not mathml:
        return False, []
    
    indicators = []
    if '<!--' in mathml or '<!--' in mathml.lower():
        indicators.append('LLM INDICATOR: Comments found in MathML')
    
    if mathml.count('<mrow>') > 50:
        indicators.append('LLM INDICATOR: Excessive <mrow> nesting')
    
    if re.search(r'<mi>\s{3,}</mi>', mathml) or re.search(r'<mo>\s{3,}</mo>', mathml):
        indicators.append('LLM INDICATOR: Unusual whitespace patterns')
    
    if mathml.count('xml:space') > 0:
        indicators.append('LLM INDICATOR: Non-standard xml:space attributes')
    
    return len(indicators) > 0, indicators


def validate_operators_in_mathml(mathml: str) -> Tuple[bool, List[str]]:
    """
    GATEKEEPER RULE: Validate that operators are correctly represented as <mo>, not <mi>.
    """
    if not mathml:
        return False, ['Empty MathML']
    
    violations = []
    operator_patterns = [
        (r'<mi>\s*=\s*</mi>', 'GATEKEEPER VIOLATION: = operator in <mi>'),
        (r'<mi>\s*\+\s*</mi>', 'GATEKEEPER VIOLATION: + operator in <mi>'),
        (r'<mi>\s*-\s*</mi>', 'GATEKEEPER VIOLATION: - operator in <mi>'),
        (r'<mi>\s*Σ\s*</mi>', 'GATEKEEPER VIOLATION: Unicode Σ operator in <mi>'),
        (r'<mi>\s*∑\s*</mi>', 'GATEKEEPER VIOLATION: Unicode ∑ operator in <mi>'),
        (r'<mi>\s*∈\s*</mi>', 'GATEKEEPER VIOLATION: Unicode ∈ operator in <mi>'),
        (r'<mi>\s*≤\s*</mi>', 'GATEKEEPER VIOLATION: Unicode ≤ operator in <mi>'),
        (r'<mi>\s*<=\s*</mi>', 'GATEKEEPER VIOLATION: ASCII <= operator in <mi> (use Unicode ≤)'),
        (r'<mi>\s*!=\s*</mi>', 'GATEKEEPER VIOLATION: ASCII != operator in <mi> (use Unicode ≠)'),
    ]
    
    for pattern, violation in operator_patterns:
        if re.search(pattern, mathml):
            violations.append(violation)
            
    # Check for unbalanced fences (loose heuristic)
    if 'fence="true"' in mathml:
        opens = len(re.findall(r'fence="true"[^>]*>\s*\(\s*</mo>', mathml))
        closes = len(re.findall(r'fence="true"[^>]*>\s*\)\s*</mo>', mathml))
        if opens > closes:
            violations.append("GATEKEEPER VIOLATION: unbalanced fences detected")
    
    return len(violations) == 0, violations

def validate_latex_syntax(latex: str) -> Tuple[bool, List[str]]:
    """
    Validate LaTeX syntax for structural correctness.
    Checks for unbalanced braces, brackets, and mismatched environments.
    """
    if not latex or not latex.strip():
        return False, ["INVALID: Empty or whitespace-only LaTeX"]
    
    violations = []
    
    # 0. Null bytes and control characters
    if '\x00' in latex:
        violations.append("INVALID: LaTeX contains NULL byte")
    
    # 1. \left / \right mismatch (Check before general parentheses for test compatibility)
    # 1. \left / \right mismatch (Check before general parentheses for test compatibility)
    # Use negative lookahead to ensure we match "\left" but not "\leftrightarrow"
    lefts = len(re.findall(r'\\left(?![a-zA-Z])', latex))
    rights = len(re.findall(r'\\right(?![a-zA-Z])', latex))
    if lefts != rights:
        violations.append(f"UNBALANCED: \\left/\\right mismatch ({lefts} vs {rights})")

    # 2. Balanced braces {}
    if latex.count('{') != latex.count('}'):
        violations.append(f"UNBALANCED: Braces mismatch ({latex.count('{')} vs {latex.count('}')})")
    
    # 3. Balanced brackets []
    if latex.count('[') != latex.count(']'):
        violations.append(f"UNBALANCED: Brackets mismatch ({latex.count('[')} vs {latex.count(']')})")
        
    # 4. Balanced parentheses ()
    if latex.count('(') != latex.count(')'):
        violations.append(f"UNBALANCED: Parentheses mismatch ({latex.count('(')} vs {latex.count(')')})")
    
    # 5. Mismatched environments \begin{...} \end{...}
    begins = re.findall(r'\\begin\{([^}]+)\}', latex)
    ends = re.findall(r'\\end\{([^}]+)\}', latex)
    if sorted(begins) != sorted(ends):
        violations.append(f"MISMATCHED: Environments mismatch (begins: {begins}, ends: {ends})")
    
    # 6. Truncated commands (1-3 letters at end)
    if re.search(r'\\[a-z]{1,3}$', latex, re.IGNORECASE):
        violations.append("TRUNCATED: LaTeX ends with incomplete command")
        
    return len(violations) == 0, violations

def validate_mathml_ast_rules(mathml: str) -> Tuple[bool, List[str]]:
    """
    Validate MathML AST rules for semantic integrity.
    Prevents spelled words via nested sub-rows or subscripts.
    """
    if not mathml:
        return True, []
    
    violations = []
    
    # Check for excessive nesting that often indicates LLM-generated junk
    if mathml.count('<mrow>') > 50:
        violations.append("AST VIOLATION: Excessive <mrow> nesting detected")
        
    # Check for spelled-out semantic operators
    spelled_ops = [
        (r'<msub>.*?<mi>e</mi>.*?<mi>q</mi>.*?</msub>', 'equiv'),
        (r'<msub>.*?<mi>s</mi>.*?<mi>u</mi>.*?</msub>', 'sum'),
    ]
    for pattern, op in spelled_ops:
        if re.search(pattern, mathml, re.DOTALL | re.IGNORECASE):
            violations.append(f"AST VIOLATION: Operator '{op}' spelled via subscript")
            
    return len(violations) == 0, violations
