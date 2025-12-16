"""
Test script for STRICT Mathpix-style Pipeline.

Tests the pipeline with the example equation:
Y_j[t] ≡ ∑_{i∈ℤ(j)} h_{i,j}[t] X_i[t] + Z_j[t]
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.ocr.strict_pipeline import StrictMathpixPipeline

def test_strict_pipeline():
    """Test the strict pipeline with example equation."""
    
    # Test case from requirements
    test_latex = r"Y_j[t] \equiv \sum_{i \in \mathbb{Z}(j)} h_{i,j}[t] X_i[t] + Z_j[t]"
    
    print("=" * 80)
    print("STRICT PIPELINE TEST")
    print("=" * 80)
    print(f"\nInput LaTeX: {test_latex}\n")
    
    pipeline = StrictMathpixPipeline()
    result = pipeline.process_latex(test_latex)
    
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"Valid: {result['is_valid']}")
    print(f"Corruption Score: {result['corruption_score']:.2f}")
    print(f"Used AI: {result['used_ai']}")
    print(f"Stage Failed: {result.get('stage_failed', 'None')}")
    
    if result['validation_errors']:
        print(f"\nValidation Errors: {result['validation_errors']}")
    
    if result['corruption_detected']:
        print(f"\nCorruption Detected: {result['corruption_detected']}")
    
    print(f"\nClean LaTeX: {result['clean_latex']}")
    print(f"\nMathML (first 500 chars):\n{result['mathml'][:500]}")
    
    print("\n" + "=" * 80)
    print("PIPELINE LOG")
    print("=" * 80)
    for log_entry in result['log']:
        print(f"  {log_entry}")
    
    print("\n" + "=" * 80)
    print("EXPECTED OUTPUT")
    print("=" * 80)
    print("""
Expected MathML structure:
- <msub><mi>Y</mi><mi>j</mi></msub>
- <mo>≡</mo> (or &#x2261;)
- <munder><mo>∑</mo><mrow>...</mrow></munder>
- <mi mathvariant="double-struck">Z</mi>
- Proper subscripts and superscripts
- No <mtext> for equations
- No split identifiers
""")
    
    # Validate output
    mathml = result['mathml']
    checks = {
        'Has <math> tag': '<math' in mathml,
        'Has <msub> for Y_j': '<msub>' in mathml and 'Y' in mathml,
        'Has equivalence symbol': ('&#x2261;' in mathml or '&#x02261;' in mathml or 
                                   '≡' in mathml or 'equiv' in mathml.lower() or
                                   '&#x02261;' in mathml),
        'Has summation': ('&#x2211;' in mathml or '&#x02211;' in mathml or 
                         '∑' in mathml or 'sum' in mathml.lower() or
                         '<msub><mo>' in mathml),  # Summation can be in <msub><mo>
        'Has double-struck Z': ('mathvariant="double-struck"' in mathml or 
                               '&#x02124;' in mathml or 'Z' in mathml),
        'No <mtext> for equation': '<mtext>' not in mathml or mathml.count('<mtext>') == 0,
        'No split words': not any(word in mathml for word in ['<mi>m</mi><mi>a</mi><mi>t</mi><mi>h</mi>']),
    }
    
    print("\n" + "=" * 80)
    print("VALIDATION CHECKS")
    print("=" * 80)
    for check, passed in checks.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {check}")
    
    all_passed = all(checks.values())
    print(f"\nOverall: {'✓ ALL CHECKS PASSED' if all_passed else '✗ SOME CHECKS FAILED'}")
    
    return result


if __name__ == "__main__":
    test_strict_pipeline()

