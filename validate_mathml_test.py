#!/usr/bin/env python3
"""
Validate MathML using the strict pipeline validation functions.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from services.ocr.strict_pipeline import (
    validate_mathml_strict,
    validate_mathml_ast_rules,
    is_corrupted_mathml,
    mathml_has_spelled_words
)

def validate_mathml(mathml: str) -> None:
    """Validate MathML and print detailed results."""
    print("=" * 80)
    print("MATHML VALIDATION REPORT")
    print("=" * 80)
    print()
    
    # Decode the MathML for readability
    decoded = mathml.replace('&#x0003D;', '=').replace('&#x0007B;', '{').replace('&#x00028;', '(')
    decoded = decoded.replace('&#x0002C;', ',').replace('&#x00029;', ')').replace('&#x02208;', '∈')
    decoded = decoded.replace('&#x0211D;', 'ℝ').replace('&#x0002B;', '+').replace('&#x02264;', '≤')
    decoded = decoded.replace('&#x0007D;', '}')
    
    print("INPUT MathML (decoded entities for readability):")
    print("-" * 80)
    print(decoded)
    print()
    
    # Run all validation checks
    print("VALIDATION CHECKS:")
    print("-" * 80)
    
    # 1. Strict validation
    is_valid, violations = validate_mathml_strict(mathml)
    print(f"1. Strict Validation: {'✅ PASSED' if is_valid else '❌ FAILED'}")
    if violations:
        print(f"   Violations ({len(violations)}):")
        for v in violations:
            print(f"     - {v}")
    print()
    
    # 2. AST validation
    is_ast_valid, ast_violations = validate_mathml_ast_rules(mathml)
    print(f"2. AST Validation: {'✅ PASSED' if is_ast_valid else '❌ FAILED'}")
    if ast_violations:
        print(f"   Violations ({len(ast_violations)}):")
        for v in ast_violations:
            print(f"     - {v}")
    print()
    
    # 3. Corruption check
    is_corrupted = is_corrupted_mathml(mathml)
    print(f"3. Corruption Check: {'✅ CLEAN' if not is_corrupted else '❌ CORRUPTED'}")
    print()
    
    # 4. Spelled words check
    has_spelled, spelled_violations = mathml_has_spelled_words(mathml)
    print(f"4. Spelled Words Check: {'✅ CLEAN' if not has_spelled else '❌ HAS SPELLED WORDS'}")
    if spelled_violations:
        print(f"   Violations ({len(spelled_violations)}):")
        for v in spelled_violations:
            print(f"     - {v}")
    print()
    
    # Overall result
    print("=" * 80)
    overall_valid = is_valid and is_ast_valid and not is_corrupted and not has_spelled
    print(f"OVERALL RESULT: {'✅ VALID' if overall_valid else '❌ INVALID'}")
    print("=" * 80)
    
    # Mathematical interpretation
    print()
    print("MATHEMATICAL INTERPRETATION:")
    print("-" * 80)
    print("D = {(D₁, D₂) ∈ ℝ²⁺ : D₁ + D₂ ≤ 1}")
    print()
    print("This represents:")
    print("- D: A set (bold)")
    print("- (D₁, D₂): Ordered pair")
    print("- ∈ ℝ²⁺: Element of positive real numbers squared")
    print("- D₁ + D₂ ≤ 1: Constraint (sum less than or equal to 1)")
    print()
    
    return overall_valid

if __name__ == "__main__":
    mathml = """<math xmlns="http://www.w3.org/1998/Math/MathML" display="block"><mrow><mrow><mi mathvariant="bold">D</mi></mrow><mo>&#x0003D;</mo><mo stretchy="false">&#x0007B;</mo><mo stretchy="false">&#x00028;</mo><msub><mi>D</mi><mrow><mn>1</mn></mrow></msub><mo>&#x0002C;</mo><msub><mi>D</mi><mrow><mn>2</mn></mrow></msub><mo stretchy="false">&#x00029;</mo><mo>&#x02208;</mo><msubsup><mi>&#x0211D;</mi><mrow><mo>&#x0002B;</mo></mrow><mrow><mn>2</mn></mrow></msubsup><mi>:</mi><msub><mi>D</mi><mrow><mn>1</mn></mrow></msub><mo>&#x0002B;</mo><msub><mi>D</mi><mrow><mn>2</mn></mrow></msub><mo>&#x02264;</mo><mn>1</mn><mo stretchy="false">&#x0007D;</mo></mrow></math>"""
    
    is_valid = validate_mathml(mathml)
    sys.exit(0 if is_valid else 1)

