"""Word detection using Tesseract OCR."""
from __future__ import annotations

from pathlib import Path
from typing import List, TypedDict

from PIL import Image
import pytesseract

from core.config import settings
from core.logger import logger


class WordBBox(TypedDict):
    """Typed dictionary for word bounding boxes with text."""
    x: int
    y: int
    w: int
    h: int
    text: str
    confidence: float


class WordDetector:
    """Detect words using Tesseract OCR."""

    def __init__(self) -> None:
        """Initialize Tesseract."""
        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        else:
            import shutil
            tesseract_path = shutil.which("tesseract")
            if tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = tesseract_path

    def detect_words(self, image_path: str | Path, min_confidence: float = 0.0) -> List[WordBBox]:
        """Detect words in image using Tesseract OCR."""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")
        
        try:
            pytesseract.get_tesseract_version()
        except Exception as exc:
            logger.warning("Tesseract not available for word detection: %s", exc)
            return []
        
        logger.info("Detecting words in %s", path)
        # Load image as PIL Image (pytesseract requires PIL Image)
        try:
            image = Image.open(path)
        except Exception as exc:
            raise ValueError(f"Could not open image: {path}") from exc
        
        # Get word-level data from Tesseract
        try:
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        except Exception as exc:
            logger.exception("Tesseract word detection failed: %s", exc)
            return []
        
        words: List[WordBBox] = []
        n_boxes = len(data['text'])
        
        for i in range(n_boxes):
            text = data['text'][i].strip()
            conf = float(data['conf'][i])
            
            # Filter out empty text and low confidence
            if not text or conf < min_confidence:
                continue
            
            x = int(data['left'][i])
            y = int(data['top'][i])
            w = int(data['width'][i])
            h = int(data['height'][i])
            
            # Filter out very small boxes (likely noise)
            if w < 5 or h < 5:
                continue
            
            words.append({
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "text": text,
                "confidence": conf,
            })
        
        logger.debug("Found %d words with confidence >= %.1f", len(words), min_confidence)
        return words

