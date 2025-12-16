"""
Test REQUIRED OUTPUT FORMAT - All three outputs must be present.

REQUIRED TEST CASE:
Input: Y_j[t] s_u_m i∈Z(j) h_{i,j}[t] X_i[t] + Z_j[t]

Expected:
1. Clean LaTeX: Y_j[t] = \sum_{i \in \mathbb{Z}(j)} h_{i,j}[t] X_i[t] + Z_j[t]
2. Clean MathML: <math xmlns="..." display="block">...</math>
3. Human-readable: Plain English equation
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.ocr.strict_pipeline import StrictMathpixPipeline

def test_required_format():
    """Test REQUIRED OUTPUT FORMAT."""
    
    print("=" * 80)
    print("REQUIRED OUTPUT FORMAT TEST")
    print("=" * 80)
    
    pipeline = StrictMathpixPipeline()
    
    # REQUIRED TEST CASE
    print("\nREQUIRED TEST CASE:")
    print("Input (OCR): Y_j[t] s_u_m i in Z(j) h_{i,j}[t] X_i[t] + Z_j[t]")
    
    result = pipeline.process_latex('Y_j[t] s_u_m i∈Z(j) h_{i,j}[t] X_i[t] + Z_j[t]')
    
    print(f"\n[OK] Valid: {result['is_valid']}")
    print(f"[OK] Used AI: {result['used_ai']}")
    
    # 1. Clean LaTeX
    print(f"\n1. CLEAN LATEX:")
    print(f"   {result['clean_latex']}")
    
    # Check for required elements
    clean_latex_str = result['clean_latex'] or ''
    has_sum = '\\sum' in clean_latex_str
    has_equals = '=' in clean_latex_str
    has_mathbb = '\\mathbb{Z}' in clean_latex_str
    has_in = '\\in' in clean_latex_str
    
    print(f"   [OK] Has \\sum: {has_sum}")
    print(f"   [OK] Has =: {has_equals}")
    print(f"   [OK] Has \\mathbb{{Z}}: {has_mathbb}")
    print(f"   [OK] Has \\in: {has_in}")
    
    # 2. Clean MathML
    print(f"\n2. CLEAN MATHML:")
    mathml_str = str(result.get('mathml', '') or '')
    if mathml_str:
        # Check for required format
        has_math_tag = '<math' in mathml_str
        has_xmlns = 'xmlns="http://www.w3.org/1998/Math/MathML"' in mathml_str
        has_display_block = 'display="block"' in mathml_str
        has_mo_sum = '<mo>' in mathml_str and ('&#x2211;' in mathml_str or '&#x02211;' in mathml_str or '&#x2211;' in mathml_str)
        has_mo_equals = '<mo>=</mo>' in mathml_str or '<mo>&#x0003D;</mo>' in mathml_str or '<mo>&#x003D;</mo>' in mathml_str or '=</mo>' in mathml_str
        has_double_struck = 'mathvariant="double-struck"' in mathml_str
        
        print(f"   {mathml_str[:150]}...")
        print(f"   [OK] Has <math> tag: {has_math_tag}")
        print(f"   [OK] Has xmlns: {has_xmlns}")
        print(f"   [OK] Has display=\"block\": {has_display_block}")
        print(f"   [OK] Has <mo>SUM</mo>: {has_mo_sum}")
        print(f"   [OK] Has <mo>=</mo>: {has_mo_equals}")
        print(f"   [OK] Has mathvariant=\"double-struck\": {has_double_struck}")
    else:
        print("   [FAIL] MathML is empty!")
    
    # 3. Human-readable
    print(f"\n3. HUMAN-READABLE EQUATION:")
    print(f"   {result['human_readable']}")
    
    # Final validation
    print(f"\n{'='*80}")
    print("FINAL VALIDATION:")
    all_present = (
        result['clean_latex'] and 
        result['mathml'] and 
        result['human_readable']
    )
    print(f"[OK] All three outputs present: {all_present}")
    
    if not all_present:
        print("[FAIL] FAILED: Missing required outputs")
    else:
        print("[PASS] PASSED: All required outputs present")
    
    print("=" * 80)

if __name__ == "__main__":
    test_required_format()

