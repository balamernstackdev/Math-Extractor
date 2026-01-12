"""
Diagnostic script to test OCR output and identify tokenizer issues.
Run this script with a test image to see what raw output pix2tex produces.
"""
import sys
import os
from pathlib import Path
from PIL import Image

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from services.ocr.image_to_latex import ImageToLatex

def test_ocr(image_path):
    """Test OCR on a single image and print diagnostic information."""
    print(f"Testing OCR on: {image_path}")
    print("=" * 80)
    
    # Initialize OCR
    ocr = ImageToLatex()
    
    # Check if math OCR is available
    if not ocr.has_math_ocr:
        print("ERROR: Math OCR (pix2tex) not available!")
        return
    
    print("✓ Math OCR initialized successfully")
    
    # Check tokenizer
    if hasattr(ocr.math_ocr, 'tokenizer'):
        tokenizer = ocr.math_ocr.tokenizer
        print(f"✓ Tokenizer loaded")
        
        # Get vocab info
        if hasattr(tokenizer, 'get_vocab'):
            vocab = tokenizer.get_vocab()
            print(f"  Vocab size: {len(vocab)}")
            
            # Show a sample of tokens
            sample_tokens = list(vocab.items())[:10]
            print(f"  Sample tokens: {sample_tokens}")
        
        # Try a simple encode/decode test
        try:
            test_text = "x^2"
            if hasattr(tokenizer, 'encode'):
                encoded = tokenizer.encode(test_text)
                print(f"  Encode test: '{test_text}' -> {encoded.ids if hasattr(encoded, 'ids') else encoded}")
                
                if hasattr(tokenizer, 'decode'):
                    if hasattr(encoded, 'ids'):
                        decoded = tokenizer.decode(encoded.ids)
                    else:
                        decoded = tokenizer.decode(encoded)
                    print(f"  Decode test: {encoded.ids if hasattr(encoded, 'ids') else encoded} -> '{decoded}'")
        except Exception as e:
            print(f"  ! Tokenizer encode/decode test failed: {e}")
    else:
        print("ERROR: Tokenizer not found in math_ocr!")
    
    print("\n" + "-" * 80)
    print("Running OCR...")
    print("-" * 80 + "\n")
    
    # Run OCR
    try:
        latex_output = ocr.image_to_latex(image_path)
        print(f"LaTeX Output:\n{latex_output}\n")
        print(f"Output length: {len(latex_output)}")
        print(f"Output type: {type(latex_output)}")
        
        # Check if output looks valid
        has_backslash = '\\' in latex_output
        has_braces = '{' in latex_output or '}' in latex_output
        has_math_symbols = any(c in latex_output for c in ['^', '_', '=', '+', '-'])
        
        print(f"\nValidity checks:")
        print(f"  Has LaTeX commands (\\): {has_backslash}")
        print(f"  Has braces: {has_braces}")
        print(f"  Has math symbols: {has_math_symbols}")
        
        if not (has_backslash or has_math_symbols):
            print("\n⚠ WARNING: Output doesn't look like valid LaTeX!")
            print("  This suggests tokenizer decoding might be producing garbage")
            
    except Exception as e:
        print(f"ERROR during OCR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_ocr_output.py <image_path>")
        print("\nExample:")
        print("  python test_ocr_output.py examples/equation.png")
        sys.exit(1)
    
    image_path = sys.argv[1]
    if not os.path.exists(image_path):
        print(f"ERROR: Image not found: {image_path}")
        sys.exit(1)
    
    test_ocr(image_path)
