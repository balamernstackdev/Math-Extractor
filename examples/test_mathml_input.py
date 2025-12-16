"""Test MathML input processing with corrupted MathML."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from services.ocr.strict_pipeline import StrictMathpixPipeline

# Corrupted MathML from user
corrupted_mathml = '''<math xmlns="http://www.w3.org/1998/Math/MathML" display="inline"><mrow><msub><mi>Y</mi><mrow><mi>j</mi></mrow></msub><mo stretchy="false">[</mo><mi>t</mi><mo stretchy="false">]</mo><msub><mi>e</mi><mrow><mi>q</mi></mrow></msub><msub><mi>u</mi><mrow><mi>i</mi></mrow></msub><msub><mi>v</mi><mrow><mi>u</mi></mrow></msub><msub><mi>m</mi><mrow><msub><mi>i</mi><mrow><mi>n</mi></mrow></msub><mi>a</mi><mi>t</mi><mi>h</mi><msub><mi>b</mi><mrow><mi>b</mi></mrow></msub><mi>Z</mi><mo stretchy="false">&#x00028;</mo><mi>j</mi><mo stretchy="false">&#x00029;</mo></mrow></msub><msub><mi>h</mi><mrow><mi>i</mi><mo>&#x0002C;</mo><mi>j</mi></mrow></msub><mo stretchy="false">[</mo><mi>t</mi><mo stretchy="false">]</mo><msub><mi>X</mi><mrow><mi>i</mi></mrow></msub><mo stretchy="false">[</mo><mi>t</mi><mo stretchy="false">]</mo><mo>&#x0002B;</mo><msub><mi>m</mi><mrow><mi>a</mi><mi>t</mi><mi>h</mi><msub><mi>b</mi><mrow><mi>b</mi></mrow></msub><msub><mi>Z</mi><mrow><mi>j</mi></mrow></msub><mo stretchy="false">[</mo><mi>t</mi><mo stretchy="false">]</mo></mrow></msub></mrow></math>'''

if __name__ == "__main__":
    print("=" * 80)
    print("TEST: Processing corrupted MathML input")
    print("=" * 80)
    print(f"\nInput MathML (corrupted):")
    print(corrupted_mathml[:200] + "...")
    
    pipeline = StrictMathpixPipeline()
    result = pipeline.process_mathml(corrupted_mathml)
    
    print(f"\n{'='*80}")
    print("RESULTS:")
    print(f"{'='*80}")
    print(f"Is valid: {result['is_valid']}")
    print(f"Used AI: {result['used_ai']}")
    print(f"Corruption detected: {len(result['corruption_detected'])} patterns")
    
    if result['clean_latex']:
        print(f"\nClean LaTeX:")
        print(f"  {result['clean_latex']}")
    else:
        print("\nClean LaTeX: (empty)")
    
    if result['mathml']:
        print(f"\nClean MathML (length: {len(result['mathml'])}):")
        print(f"  {result['mathml'][:200]}...")
        # Check for corruption patterns
        has_equiv = '<mo>&#x2261;</mo>' in result['mathml'] or '<mo>≡</mo>' in result['mathml'] or '&#x2261;' in result['mathml']
        has_sum = '<mo>&#x2211;</mo>' in result['mathml'] or '<mo>∑</mo>' in result['mathml'] or '&#x2211;' in result['mathml']
        has_double_struck = 'mathvariant="double-struck"' in result['mathml']
        has_equals = '<mo>=</mo>' in result['mathml'] or '=</mo>' in result['mathml']
        
        print(f"\nMathML Validation:")
        print(f"  Has <mo>≡</mo> (equiv): {has_equiv}")
        print(f"  Has <mo>∑</mo> (sum): {has_sum}")
        print(f"  Has mathvariant=\"double-struck\": {has_double_struck}")
        print(f"  Has <mo>=</mo>: {has_equals}")
    else:
        print("\nClean MathML: (empty - rejected)")
    
    if result['human_readable']:
        print(f"\nHuman-readable:")
        print(f"  {result['human_readable']}")
    
    if result['validation_errors']:
        print(f"\nValidation errors:")
        for error in result['validation_errors'][:5]:
            print(f"  - {error}")
    
    if result['corruption_detected']:
        print(f"\nCorruption detected:")
        for corruption in result['corruption_detected'][:5]:
            print(f"  - {corruption}")

