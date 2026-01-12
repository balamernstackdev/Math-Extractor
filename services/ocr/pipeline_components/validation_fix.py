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
    lefts = len(re.findall(r'\\left', latex))
    rights = len(re.findall(r'\\right', latex))
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
