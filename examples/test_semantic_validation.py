"""
Test semantic validation - REQUIRED TEST CASE.

Input (OCR): Y_j[t] s_u_m i∈Z(j) h_{i,j}[t] X_i[t] + Z_j[t]

Expected Output:
- LaTeX: Y_j[t] = \sum_{i \in \mathbb{Z}(j)} h_{i,j}[t] X_i[t] + Z_j[t]
- MathML: Proper semantic MathML with <mo>∑</mo>, <mi mathvariant="double-struck">Z</mi>
- Human-readable: Plain text equation
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.ocr.strict_pipeline import StrictMathpixPipeline

def test_semantic_validation():
    """Test semantic validation with REQUIRED TEST CASE."""
    
    print("=" * 80)
    print("SEMANTIC VALIDATION TEST - REQUIRED TEST CASE")
    print("=" * 80)
    
    pipeline = StrictMathpixPipeline()
    
    # REQUIRED TEST CASE
    print("\nREQUIRED TEST CASE:")
    print("Input (OCR): Y_j[t] s_u_m i∈Z(j) h_{i,j}[t] X_i[t] + Z_j[t]")
    
    result = pipeline.process_latex('Y_j[t] s_u_m i∈Z(j) h_{i,j}[t] X_i[t] + Z_j[t]')
    
    print(f"\n✓ Valid: {result['is_valid']}")
    print(f"✓ Corruption detected: {len(result['corruption_detected'])} violations")
    print(f"✓ Used AI: {result['used_ai']}")
    
    print(f"\n✓ Clean LaTeX:")
    print(f"  {result['clean_latex']}")
    
    print(f"\n✓ MathML (first 200 chars):")
    mathml_preview = result['mathml'][:200] if result['mathml'] else "N/A"
    print(f"  {mathml_preview}...")
    
    # Check for semantic correctness
    print(f"\n✓ Semantic checks:")
    has_sum = '\\sum' in result['clean_latex'] or '∑' in result['mathml'] or '&#x2211;' in result['mathml']
    has_equiv = '=' in result['clean_latex'] or '<mo>=</mo>' in result['mathml'] or '<mo>&#x0003D;</mo>' in result['mathml']
    has_mathbb = '\\mathbb{Z}' in result['clean_latex'] or 'mathvariant="double-struck"' in result['mathml']
    has_mo_sum = '<mo>' in result['mathml'] and ('∑' in result['mathml'] or '&#x2211;' in result['mathml'])
    no_spelled_words = 's_u_m' not in result['clean_latex'] and '<msub><mi>s</mi><mi>u</mi>' not in result['mathml']
    
    print(f"  Has \\sum: {has_sum}")
    print(f"  Has =: {has_equiv}")
    print(f"  Has \\mathbb{{Z}}: {has_mathbb}")
    print(f"  Has <mo>∑</mo>: {has_mo_sum}")
    print(f"  No spelled words: {no_spelled_words}")
    
    print(f"\n✓ Human-readable:")
    print(f"  {result['human_readable']}")
    
    if result['corruption_detected']:
        print(f"\n⚠ Corruption detected: {result['corruption_detected'][:3]}")
    
    print("\n" + "=" * 80)
    print("Semantic validation test completed")
    print("=" * 80)

if __name__ == "__main__":
    test_semantic_validation()

