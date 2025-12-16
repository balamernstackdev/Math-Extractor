"""
Test semantic correctness - STRICTLY FORBIDDEN patterns.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.ocr.strict_pipeline import StrictMathpixPipeline

def test_semantic_correctness():
    """Test semantic correctness pipeline."""
    
    print("=" * 80)
    print("SEMANTIC CORRECTNESS TEST")
    print("=" * 80)
    
    pipeline = StrictMathpixPipeline()
    
    # Test 1: Valid input
    print("\nTest 1: Valid semantic input")
    result1 = pipeline.process_latex('Y_j[t] \\equiv \\sum_{i \\in \\mathbb{Z}(j)} h_{i,j}[t] X_i[t] + Z_j[t]')
    print(f"  Valid: {result1['is_valid']}")
    print(f"  Clean LaTeX: {result1['clean_latex'][:60]}...")
    print(f"  Human-readable: {result1['human_readable'][:60]}...")
    print(f"  Corruption: {len(result1['corruption_detected'])} violations")
    
    # Test 2: Corrupted input (spelled operators)
    print("\nTest 2: Corrupted input (spelled operators)")
    result2 = pipeline.process_latex('e_q u_i v s_u m')
    print(f"  Valid: {result2['is_valid']}")
    print(f"  Corruption: {len(result2['corruption_detected'])} violations")
    print(f"  Used AI: {result2['used_ai']}")
    if result2['corruption_detected']:
        print(f"  Violations: {result2['corruption_detected'][:3]}")
    
    print("\n" + "=" * 80)
    print("Semantic correctness test completed")
    print("=" * 80)

if __name__ == "__main__":
    test_semantic_correctness()

