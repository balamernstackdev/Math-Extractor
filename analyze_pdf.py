
import os
import re

pdf_path = r"d:\test-r&d\mathpix_clone\tests\1300000044.pdf"

try:
    # Try pypdf first if available
    from pypdf import PdfReader
    print(f"Analyzing {pdf_path}...")
    reader = PdfReader(pdf_path)
    text = ""
    # Read first 5 pages and some random middle pages
    pages_indices = list(range(min(5, len(reader.pages))))
    if len(reader.pages) > 10:
        pages_indices.extend([len(reader.pages)//2, len(reader.pages)-1])
    
    print(f"Reading {len(pages_indices)} pages out of {len(reader.pages)}...")
    
    math_keywords = {
        "Calculus": ["integral", "derivative", "limit", "continuous", "differential"],
        "Linear Algebra": ["matrix", "vector", "eigenvalue", "determinant", "basis"],
        "Statistics": ["probability", "distribution", "variance", "mean", "stochastic", "SNR"],
        "Topology": ["manifold", "compact", "homeomorphism", "open set"],
        "Abstract Algebra": ["group", "ring", "field", "isomorphism"],
        "Common": ["theorem", "lemma", "proof", "definition", "equation"]
    }
    
    found_keywords = {}
    
    for i in pages_indices:
        page_text = reader.pages[i].extract_text()
        text += page_text + "\n"
        
        # Check for keywords
        for category, words in math_keywords.items():
            for word in words:
                if word.lower() in page_text.lower():
                    found_keywords.setdefault(category, set()).add(word)

    print("\n--- Domain Analysis ---")
    for cat, words in found_keywords.items():
        print(f"{cat}: {', '.join(words)}")
        
    # Check for specific symbol patterns in text (rough heuristic)
    if "∑" in text or "sum" in text.lower(): print("Contains Summation")
    if "∫" in text or "integral" in text.lower(): print("Contains Integrals")
    if "[" in text and "]" in text and ("matrix" in text.lower() or "vector" in text.lower()): print("Contains Matrices/Vectors")
    
except ImportError:
    print("pypdf not installed. Trying raw string search on binary (limited)...")
    try:
        with open(pdf_path, 'rb') as f:
            content = f.read()
            # Look for common markers
            if b'/Filter' in content: print("PDF seems valid")
            if b'matrix' in content.lower(): print("May contain Matrices")
            if b'integral' in content.lower(): print("May contain Integrals")
    except Exception as e:
        print(f"Error reading file: {e}")
except Exception as e:
    print(f"Analysis failed: {e}")
