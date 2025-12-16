"""Image helper utilities."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image

from core.logger import logger


def load_image(path: Path) -> Optional[np.ndarray]:
    """Load image using PIL and convert to numpy array."""
    try:
        with Image.open(path) as img:
            return np.array(img)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to load image %s: %s", path, exc)
        return None


def crop_image(image_path: Path, bbox: dict[str, int]) -> Path:
    """Crop an image using bounding box and save to snips directory."""
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Cannot open image: {image_path}")
    
    x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
    
    # Validate and clamp coordinates
    img_height, img_width = image.shape[:2]
    x = max(0, min(x, img_width - 1))
    y = max(0, min(y, img_height - 1))
    w = min(w, img_width - x)
    h = min(h, img_height - y)
    
    # Ensure minimum size
    if w < 5 or h < 5:
        logger.warning("Crop region too small: %dx%d at (%d,%d) for image %dx%d", 
                      w, h, x, y, img_width, img_height)
        raise ValueError(f"Crop region too small: {w}x{h}")
    
    logger.info("Cropping image: %s at (%d,%d) size %dx%d (image: %dx%d)", 
               image_path.name, x, y, w, h, img_width, img_height)
    
    crop = image[y : y + h, x : x + w]
    
    if crop.size == 0:
        raise ValueError(f"Empty crop result: {w}x{h} at ({x},{y})")
    
    out_path = image_path.parent / f"{image_path.stem}_{bbox.get('id', 'crop')}.png"
    cv2.imwrite(str(out_path), crop)
    logger.info("Saved crop to %s (size: %dx%d)", out_path, crop.shape[1], crop.shape[0])
    return out_path

