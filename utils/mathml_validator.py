"""Validate and diagnose MathML structure issues."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Optional, List, Tuple


def validate_mathml(mathml: str) -> Tuple[bool, List[str]]:
    """
    Validate MathML structure and return issues found.
    
    Args:
        mathml: MathML string to validate
    
    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []
    
    if not mathml or not mathml.strip():
        return False, ["MathML is empty"]
    
    # Check for basic MathML structure
    if '<math' not in mathml:
        issues.append("Missing <math> root element")
        return False, issues
    
    try:
        # Try to parse as XML
        root = ET.fromstring(mathml)
        
        # Check namespace
        if root.tag != '{http://www.w3.org/1998/Math/MathML}math' and not root.tag.startswith('math'):
            issues.append(f"Invalid root element: {root.tag}")
        
        # Check for common structural issues
        _check_structural_issues(root, issues)
        
        return len(issues) == 0, issues
        
    except ET.ParseError as e:
        issues.append(f"XML parse error: {str(e)}")
        return False, issues
    except Exception as e:
        issues.append(f"Validation error: {str(e)}")
        return False, issues


def _check_structural_issues(element: ET.Element, issues: List[str], depth: int = 0) -> None:
    """Recursively check for structural issues in MathML."""
    if depth > 20:  # Prevent infinite recursion
        return
    
    tag = element.tag.split('}')[-1] if '}' in element.tag else element.tag
    
    # Check for common issues
    if tag == 'mo':
        text = (element.text or '').strip()
        # Check for suspicious operators
        if text in [']', '[', '(', ')'] and not element.get('stretchy'):
            # These should usually be stretchy
            pass  # Not necessarily an issue
    
    # Check for missing text in elements that should have content
    if tag in ['mi', 'mn', 'mo', 'mtext']:
        if not element.text and not list(element):
            issues.append(f"Empty {tag} element at depth {depth}")
    
    # Recursively check children
    for child in element:
        _check_structural_issues(child, issues, depth + 1)


def diagnose_corrupted_mathml(mathml: str) -> dict:
    """
    Diagnose issues with corrupted MathML.
    
    Returns a dictionary with diagnosis information.
    """
    diagnosis = {
        'is_valid': False,
        'issues': [],
        'suggestions': [],
        'structure_summary': {}
    }
    
    is_valid, issues = validate_mathml(mathml)
    diagnosis['is_valid'] = is_valid
    diagnosis['issues'] = issues
    
    if not is_valid:
        # Analyze the structure
        try:
            root = ET.fromstring(mathml)
            diagnosis['structure_summary'] = _analyze_structure(root)
            
            # Generate suggestions
            if 'Y_i]' in mathml or 'Y_j]' in mathml:
                diagnosis['suggestions'].append(
                    "Missing opening bracket '[' - check if LaTeX had corrupted brackets"
                )
            if 'D_Ohigl' in mathml or 'gigl' in mathml.lower():
                diagnosis['suggestions'].append(
                    "Subscripts appear corrupted - original LaTeX may have had OCR errors"
                )
            if 't_z()' in mathml or 't_Z()' in mathml:
                diagnosis['suggestions'].append(
                    "Subscript structure corrupted - check LaTeX input for proper subscript syntax"
                )
        except:
            pass
    
    return diagnosis


def _analyze_structure(element: ET.Element, depth: int = 0) -> dict:
    """Analyze MathML structure."""
    summary = {
        'tag': element.tag.split('}')[-1] if '}' in element.tag else element.tag,
        'text': (element.text or '').strip(),
        'children': []
    }
    
    for child in element:
        if depth < 5:  # Limit depth for summary
            summary['children'].append(_analyze_structure(child, depth + 1))
    
    return summary


def suggest_latex_fix(mathml: str) -> Optional[str]:
    """
    Suggest what the original LaTeX might have been based on corrupted MathML.
    
    This is a heuristic approach - not always accurate.
    """
    # Look for patterns that suggest what the LaTeX should be
    if 'Y_i]' in mathml or 'Y_j]' in mathml:
        # Likely should be Y_j[t] or Y_i[t]
        if 'sum' in mathml.lower() or '∑' in mathml:
            return r"Y_j[t] = \sum_{i \in \mathcal{I}(j)} h_{i,j}[t] X_i[t] + Z_j[t]"
        else:
            return r"Y_j[t] = ..."  # Incomplete suggestion
    
    return None

