"""
Test production-grade MathOCR pipeline.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.ocr.strict_pipeline import StrictMathpixPipeline

def test_production_grade():
    """Test production-grade pipeline."""
    
    print("=" * 80)
    print("PRODUCTION-GRADE MATHOCR PIPELINE TEST")
    print("=" * 80)
    
    pipeline = StrictMathpixPipeline()
    result = pipeline.process_latex(r"Y_j[t] \equiv \sum_{i \in \mathbb{Z}(j)} h_{i,j}[t] X_i[t] + Z_j[t]")
    
    print("\n✓ Production-grade pipeline test:")
    print(f"  Valid: {result['is_valid']}")
    print(f"  Clean LaTeX: {result['clean_latex'][:60]}...")
    print(f"  Human-readable: {result['human_readable'][:60]}...")
    print(f"  Corruption detected: {len(result['corruption_detected'])} violations")
    print(f"  MathML length: {len(result['mathml'])}")
    print(f"  Used AI: {result['used_ai']}")
    
    print("\n" + "=" * 80)
    print("Test completed")
    print("=" * 80)

if __name__ == "__main__":
    test_production_grade()

