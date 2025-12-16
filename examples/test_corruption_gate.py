"""
Test corruption gate - Regex + AST checks BEFORE OpenAI.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.ocr.strict_pipeline import StrictMathpixPipeline

def test_corruption_gate():
    """Test corruption gate blocks corruption before OpenAI."""
    
    print("=" * 80)
    print("CORRUPTION GATE TEST")
    print("=" * 80)
    
    pipeline = StrictMathpixPipeline()
    
    # Test 1: Corrupted input (should trigger gate)
    print("\nTest 1: Corrupted input (e_q u_i v s_u m)")
    result1 = pipeline.process_latex('e_q u_i v s_u m')
    print(f"  Valid: {result1['is_valid']}")
    print(f"  Corruption detected: {len(result1['corruption_detected'])} violations")
    print(f"  Used AI: {result1['used_ai']}")
    print(f"  Stage failed: {result1.get('stage_failed', 'None')}")
    if result1['corruption_detected']:
        print(f"  Violations: {result1['corruption_detected'][:3]}")
    
    # Test 2: Valid input (should pass gate)
    print("\nTest 2: Valid input")
    result2 = pipeline.process_latex('Y_j[t] \\equiv \\sum_{i \\in \\mathbb{Z}(j)} h_{i,j}[t] X_i[t] + Z_j[t]')
    print(f"  Valid: {result2['is_valid']}")
    print(f"  Corruption detected: {len(result2['corruption_detected'])} violations")
    print(f"  Used AI: {result2['used_ai']}")
    
    print("\n" + "=" * 80)
    print("Corruption gate test completed")
    print("=" * 80)

if __name__ == "__main__":
    test_corruption_gate()

