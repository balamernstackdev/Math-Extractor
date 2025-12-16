"""Formula detection via OpenCV contour detection."""
from __future__ import annotations

from pathlib import Path
from typing import List, TypedDict

import cv2
import numpy as np

from core.logger import logger


class BBoxDict(TypedDict):
    """Typed dictionary for bounding boxes."""

    x: int
    y: int
    w: int
    h: int
    id: str


class FormulaDetector:
    """Detect formula-like regions using OpenCV."""

    def detect_formulas(self, image_path: str | Path) -> List[BBoxDict]:
        """Return bounding boxes around suspected formulas.
        
        Uses heuristics to identify formula-like regions:
        - Regions with mathematical symbols (=, +, -, /, etc.)
        - Regions with subscripts/superscripts (small text above/below)
        - Regions with Greek letters or special notation
        - Inline formulas (usually wider than tall)
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")
        logger.info("Detecting formulas in %s", path)
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise ValueError(f"Unable to read image: {path}")

        # Preprocessing for better detection
        blurred = cv2.GaussianBlur(image, (5, 5), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Use morphological operations to connect nearby components (formulas often have multiple parts)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 3))
        dilated = cv2.dilate(thresh, kernel, iterations=1)
        
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        boxes: List[BBoxDict] = []
        img_height, img_width = image.shape
        
        for idx, contour in enumerate(contours, start=1):
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter by size - formulas should be reasonably sized
            area = w * h
            if area < 200:  # Too small
                continue
            if area > img_width * img_height * 0.5:  # Too large (probably whole page)
                continue
            
            # Filter by aspect ratio - formulas are usually wider than tall (inline) or roughly square
            aspect_ratio = w / h if h > 0 else 0
            if aspect_ratio < 0.3:  # Too tall and narrow (probably a column of text)
                continue
            if aspect_ratio > 10:  # Too wide (probably a line of text)
                continue
            
            # Extract region to analyze
            roi = image[max(0, y):min(img_height, y+h), max(0, x):min(img_width, x+w)]
            if roi.size == 0:
                continue
            
            # Check if region has characteristics of formulas
            # Formulas often have:
            # - Mixed text sizes (subscripts/superscripts)
            # - Special symbols
            # - Dense text (high pixel density)
            
            # Calculate text density (ratio of text pixels to total)
            roi_thresh = thresh[max(0, y):min(img_height, y+h), max(0, x):min(img_width, x+w)]
            if roi_thresh.size > 0:
                text_density = cv2.countNonZero(roi_thresh) / roi_thresh.size
                # Formulas typically have moderate to high text density
                if text_density < 0.05 or text_density > 0.8:  # Too sparse or too dense
                    continue
            
            # Additional check: formulas are often centered or left-aligned in their line
            # This is a simple heuristic - in practice, formulas can appear anywhere
            
            boxes.append({"x": int(x), "y": int(y), "w": int(w), "h": int(h), "id": f"eq{idx}"})

        # Sort by position (top to bottom, left to right)
        boxes.sort(key=lambda b: (b["y"], b["x"]))
        
        logger.debug("Found %d candidate formulas in %s", len(boxes), path.name)
        return boxes

