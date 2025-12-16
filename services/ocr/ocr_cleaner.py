import re
import unicodedata

INVALID_CHARS = r"[¥€¢©®™ºª×¿¡§¶•°«»“”‘’–—…·•‚„`´∆≈≠∞√∂]"

def clean_ocr_text(text: str) -> str:
    # Normalize unicode
    text = unicodedata.normalize("NFKD", text)

    # Remove invalid characters
    text = re.sub(INVALID_CHARS, "", text)

    # Remove duplicate operators
    text = text.replace("++", "+")
    text = text.replace("--", "-")

    # Remove random spaces between numbers/letters
    text = re.sub(r"(?<=\d)\s+(?=\d)", "", text)
    text = re.sub(r"\s+", " ", text)

    # Fix e-1 → e^{-1}
    text = re.sub(r"e-1\b", r"e^{-1}", text)

    # Fix yos → y_{o}s
    text = re.sub(r"yos", r"y_{o}s", text)

    # Fix r( ( to r(
    text = text.replace("r( (", "r(")

    return text.strip()
