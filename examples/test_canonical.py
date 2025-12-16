"""Test canonical example from requirements."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from services.ocr.strict_pipeline import StrictMathpixPipeline

# Canonical test case from requirements
canonical_input = r"f_r a_c 1 n s_u_m t=0 n-1 [ r_v^(t)(y_0,...,y_{t-1}) ]^2 \le P"

expected_latex = r"\frac{1}{n}\sum_{t=0}^{n-1}\left[r_v^{(t)}(y_0,\dots,y_{t-1})\right]^2 \le P"

if __name__ == "__main__":
    print("=" * 80)
    print("CANONICAL TEST (MUST PASS)")
    print("=" * 80)
    print("\nOCR Input:")
    print(f"  {canonical_input}")
    print("\nExpected LaTeX:")
    print(f"  {expected_latex}")
    
    pipeline = StrictMathpixPipeline()
    result = pipeline.process_latex(canonical_input)
    
    print(f"\n{'='*80}")
    print("RESULTS:")
    print(f"{'='*80}")
    print(f"Is valid: {result['is_valid']}")
    print(f"Used AI: {result['used_ai']}")
    
    if result['clean_latex']:
        print(f"\nClean LaTeX:")
        print(f"  {result['clean_latex']}")
        
        # Check for required elements
        has_frac = '\\frac' in result['clean_latex']
        has_sum = '\\sum' in result['clean_latex']
        has_left = '\\left' in result['clean_latex']
        has_right = '\\right' in result['clean_latex']
        has_le = '\\le' in result['clean_latex'] or '≤' in result['clean_latex']
        no_corrupted = not any([
            'f_r' in result['clean_latex'],
            's_u' in result['clean_latex'],
            'e_q' in result['clean_latex'],
            'l_e' in result['clean_latex'],
            'r_i' in result['clean_latex'],
            'm_a' in result['clean_latex'],
            'b_f' in result['clean_latex'],
        ])
        
        print(f"\nLaTeX Validation:")
        print(f"  Has \\frac: {has_frac}")
        print(f"  Has \\sum: {has_sum}")
        print(f"  Has \\left: {has_left}")
        print(f"  Has \\right: {has_right}")
        print(f"  Has \\le: {has_le}")
        print(f"  No corrupted patterns: {no_corrupted}")
        
        # Check if matches expected (allowing for minor variations)
        matches_expected = (
            has_frac and has_sum and has_left and has_right and has_le and no_corrupted
        )
        print(f"\n  ✅ PASS" if matches_expected else f"\n  ❌ FAIL")
    else:
        print("\nClean LaTeX: (empty)")
    
    if result['mathml']:
        print(f"\nClean MathML (length: {len(result['mathml'])}):")
        print(f"  {result['mathml'][:300]}...")
        
        # Check for required MathML elements
        has_math_tag = '<math' in result['mathml']
        has_display_block = 'display="block"' in result['mathml']
        has_mfrac = '<mfrac>' in result['mathml']
        has_munderover = '<munderover>' in result['mathml'] or '<munder>' in result['mathml']
        has_mo_sum = '&#x2211;' in result['mathml'] or '∑' in result['mathml']
        has_mo_le = '&#x2264;' in result['mathml'] or '≤' in result['mathml']
        no_corrupted_mathml = not any([
            '<msub><mi>f</mi>' in result['mathml'],
            '<msub><mi>s</mi>' in result['mathml'],
            '<msub><mi>e</mi>' in result['mathml'],
        ])
        
        print(f"\nMathML Validation:")
        print(f"  Has <math> tag: {has_math_tag}")
        print(f"  Has display=\"block\": {has_display_block}")
        print(f"  Has <mfrac>: {has_mfrac}")
        print(f"  Has <munderover>/<munder>: {has_munderover}")
        print(f"  Has <mo>∑</mo>: {has_mo_sum}")
        print(f"  Has <mo>≤</mo>: {has_mo_le}")
        print(f"  No corrupted patterns: {no_corrupted_mathml}")
        
        mathml_valid = (
            has_math_tag and has_display_block and has_mfrac and 
            has_munderover and has_mo_sum and has_mo_le and no_corrupted_mathml
        )
        print(f"\n  ✅ PASS" if mathml_valid else f"\n  ❌ FAIL")
    else:
        print("\nClean MathML: (empty - rejected)")
    
    if result['human_readable']:
        print(f"\nHuman-readable:")
        print(f"  {result['human_readable']}")
    
    if result['corruption_detected']:
        print(f"\nCorruption detected:")
        for corruption in result['corruption_detected'][:5]:
            print(f"  - {corruption}")

