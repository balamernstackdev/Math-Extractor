"""
Test gatekeeper pipeline with PRE-OPENAI and AST-level validation.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.ocr.strict_pipeline import (
    StrictMathpixPipeline,
    pre_openai_regex_corruption_checker,
    validate_mathml_ast_rules,
    validate_latex_ast_rules
)

def test_gatekeeper():
    """Test gatekeeper pipeline."""
    
    print("=" * 80)
    print("GATEKEEPER PIPELINE TEST")
    print("=" * 80)
    
    # Test 1: Pre-OpenAI checker
    print("\nTest 1: PRE-OPENAI regex corruption checker")
    test_latex = "e_q u_i v s_u m"
    is_corrupt, patterns = pre_openai_regex_corruption_checker(test_latex)
    print(f"  Input: {test_latex}")
    print(f"  CORRUPTED: {is_corrupt}")
    print(f"  Patterns: {patterns[:3]}")
    
    # Test 2: LaTeX AST rules
    print("\nTest 2: LaTeX AST-level checker")
    is_valid, violations = validate_latex_ast_rules(test_latex)
    print(f"  AST Valid: {is_valid}")
    print(f"  Violations: {violations[:3] if violations else []}")
    
    # Test 3: MathML AST rules
    print("\nTest 3: MathML AST-level checker")
    test_mathml = '<math><msub><mi>e</mi><mi>q</mi></msub></math>'
    is_valid_ml, violations_ml = validate_mathml_ast_rules(test_mathml)
    print(f"  Input: {test_mathml[:50]}...")
    print(f"  AST Valid: {is_valid_ml}")
    print(f"  Violations: {violations_ml[:3] if violations_ml else []}")
    
    # Test 4: Full pipeline with corrupted input
    print("\nTest 4: Full pipeline with corrupted input")
    pipeline = StrictMathpixPipeline()
    result = pipeline.process_latex("e_q u_i v s_u m")
    print(f"  Valid: {result['is_valid']}")
    print(f"  Corruption detected: {len(result['corruption_detected'])} violations")
    print(f"  Used AI: {result['used_ai']}")
    
    print("\n" + "=" * 80)
    print("Gatekeeper test completed")
    print("=" * 80)

if __name__ == "__main__":
    test_gatekeeper()

