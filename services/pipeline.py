from ocr_cleaner import clean_ocr_text
from structure_rebuilder import rebuild_math_structure
from latex_normalizer import normalize_latex

def process_math_ocr(raw_text: str) -> str:
    print("\n[STEP 1] Raw OCR Input:", raw_text)

    cleaned = clean_ocr_text(raw_text)
    print("\n[STEP 2] Cleaned OCR:", cleaned)

    rebuilt = rebuild_math_structure(cleaned)
    print("\n[STEP 3] Rebuilt Structure:", rebuilt)

    latex = normalize_latex(rebuilt)
    print("\n[STEP 4] Normalized LaTeX:", latex)

