"""
Test script for MANDATORY Pipeline with ZERO tolerance.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.ocr.strict_pipeline import (
    StrictMathpixPipeline,
    detect_latex_corruption,
    validate_mathml_strict,
    is_corrupted_mathml
)

def test_mandatory_pipeline():
    """Test the mandatory pipeline."""
    
    print("=" * 80)
    print("MANDATORY PIPELINE TEST")
    print("=" * 80)
    
    # Test 1: Clean LaTeX (no corruption)
    print("\nTest 1: Clean LaTeX (no corruption expected)")
    test_latex = r"Y_j[t] \equiv \sum_{i \in \mathbb{Z}(j)} h_{i,j}[t] X_i[t] + Z_j[t]"
    print(f"Input: {test_latex}")
    
    pipeline = StrictMathpixPipeline()
    result = pipeline.process_latex(test_latex)
    
    print(f"Valid: {result['is_valid']}")
    print(f"Used AI: {result['used_ai']}")
    print(f"Corruption detected: {result['corruption_detected']}")
    print(f"MathML length: {len(result['mathml'])}")
    
    # Test 2: Corrupted LaTeX (should trigger mandatory OpenAI)
    print("\n" + "=" * 80)
    print("Test 2: Corrupted LaTeX (should trigger MANDATORY OpenAI)")
    corrupted_latex = r"e_{q}u_{i}v s_{u}m_{i} m_{a}t_{h}b_{b}Z"
    print(f"Input: {corrupted_latex}")
    
    is_corrupt, patterns = detect_latex_corruption(corrupted_latex)
    print(f"Corruption detected: {is_corrupt}")
    print(f"Patterns: {patterns}")
    
    # Test 3: MathML validation
    print("\n" + "=" * 80)
    print("Test 3: MathML Validation")
    
    # Corrupted MathML
    bad_mathml = '<math><msub><mi>l</mi><mi>e</mi></msub></math>'
    is_corrupt_ml = is_corrupted_mathml(bad_mathml)
    print(f"Bad MathML (<msub><mi>l</mi>): is_corrupted={is_corrupt_ml}")
    
    is_valid, violations = validate_mathml_strict(bad_mathml)
    print(f"Validation: is_valid={is_valid}, violations={violations}")
    
    # Good MathML
    good_mathml = '<math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mo>&#x2261;</mo></mrow></math>'
    is_valid2, violations2 = validate_mathml_strict(good_mathml)
    print(f"Good MathML: is_valid={is_valid2}, violations={violations2}")
    
    print("\n" + "=" * 80)
    print("All tests completed")
    print("=" * 80)

if __name__ == "__main__":
    test_mandatory_pipeline()

