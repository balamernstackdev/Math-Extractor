"""Glyph classification for mathematical symbols.

This module classifies image regions into mathematical symbols/tokens.
It will eventually use a trained CNN or ONNX model to recognize individual glyphs.
"""
from __future__ import annotations

import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple
from pathlib import Path
from core.logger import logger
from .layout_detector import Region


@dataclass
class Token:
    """A recognized mathematical token/glyph."""
    glyph: str  # The recognized symbol (e.g., 'α', '∑', '\in', '2')
    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    confidence: float = 1.0
    region_type: str = 'symbol'  # From layout detector
    
    @property
    def center_x(self) -> float:
        return self.bbox[0] + self.bbox[2] / 2
    
    @property
    def center_y(self) -> float:
        return self.bbox[1] + self.bbox[3] / 2
    
    def __repr__(self) -> str:
        return f"Token(glyph={self.glyph!r}, type={self.region_type}, conf={self.confidence:.2f})"


class GlyphClassifier:
    """Classify image regions into mathematical glyphs/symbols.
    
    This is a Phase 1 stub implementation that will eventually:
    - Load a trained ONNX model
    - Perform CNN-based glyph recognition
    - Handle multi-character operators
    - Recognize handwritten symbols
    
    For now, it returns placeholder tokens to enable pipeline testing.
    """
    
    def __init__(self, model_path: str | Path | None = None):
        """Initialize the glyph classifier.
        
        Args:
            model_path: Optional path to an ONNX model file
        """
        self.model_path = model_path
        self.model = None  # Placeholder for future ONNX model
        self.input_shape = (1, 32, 32)
        
        # Placeholder: Common mathematical symbols for stub recognition
        self.symbol_set = [
            '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
            'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm',
            'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
            'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M',
            'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
            '+', '-', '=', '×', '÷', '∈', '∑', '∏', '∫', '√',
            'α', 'β', 'γ', 'δ', 'θ', 'λ', 'μ', 'π', 'σ', 'ω',
        ]
        
        if model_path and Path(model_path).exists():
            self._load_model(str(model_path))
            
    def _load_model(self, model_path: str):
        """Load ONNX model with performance optimizations."""
        try:
            import onnxruntime as ort
            
            # Create session options
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            sess_options.intra_op_num_threads = 1  # Avoid oversubscription
            
            self.model = ort.InferenceSession(model_path, sess_options)
            logger.info(f"[GlyphClassifier] Loaded ONNX model from {model_path} (optimized)")
            
            # Get input shape
            if self.model:
                self.input_name = self.model.get_inputs()[0].name
                self.input_shape = self.model.get_inputs()[0].shape
            
        except Exception as e:
            logger.error(f"[GlyphClassifier] Failed to load ONNX model: {e}")
            self.model = None

    def _classify_region(self, region_img: np.ndarray) -> Tuple[str, float]:
        """Classify a single region image.
        
        Strategy:
        1. Try ONNX model if available.
        2. Fallback to Tesseract if enabled.
        3. Fallback to stub.
        """
        # 1. ONNX Inference
        if self.model:
            try:
                # Preprocess
                processed_img = self._preprocess_for_onnx(region_img)
                
                # Inference
                outputs = self.model.run(None, {self.input_name: processed_img})
                
                # Postprocess (assuming softmax output)
                # TODO: implementations need a label map. 
                # For now, this is a structure block waiting for the map.
                # label_index = np.argmax(outputs[0])
                # glyph = self.label_map[label_index]
                # return glyph, float(np.max(outputs[0]))
                pass # Continue to callback until label map is ready
            except Exception as e:
                logger.warning(f"[GlyphClassifier] ONNX inference failed: {e}")
        
        # 2. Tesseract OCR (Existing hybrid logic)
        try:
            # Attempt to use Tesseract for symbol recognition
            import pytesseract
            from core.config import settings
            
            # Configure Tesseract path if available
            if settings.tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
            
            # Preprocess the region for better OCR
            gray = cv2.cvtColor(region_img, cv2.COLOR_BGR2GRAY) if len(region_img.shape) == 3 else region_img
            
            # Apply thresholding to enhance contrast
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Resize small regions for better recognition
            h, w = binary.shape
            if h < 20 or w < 20:
                scale = max(20 / h, 20 / w)
                new_w, new_h = int(w * scale), int(h * scale)
                binary = cv2.resize(binary, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
            
            # Use Tesseract with single character mode (PSM 10)
            config = '--psm 10 -c tessedit_char_whitelist=0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+-=<>()[]{}.,;:|'
            
            # Get OCR result
            text = pytesseract.image_to_string(binary, config=config).strip()
            
            confidence = 0.85 if text else 0.3
            
            if not text:
                return 'x', 0.3
            
            glyph = text[0]
            # logger.debug(f"[GlyphClassifier] Recognized: '{glyph}' (conf={confidence:.2f})")
            return glyph, confidence
            
        except ImportError:
            logger.warning("[GlyphClassifier] Tesseract not available, using stub")
            return 'x', 0.5
        except Exception as e:
            logger.warning(f"[GlyphClassifier] OCR failed: {e}, using stub")
            return 'x', 0.3

    def _preprocess_for_onnx(self, img: np.ndarray) -> np.ndarray:
        """Prepare image for ONNX model."""
        # Resize to input shape (e.g., 32x32)
        target_h, target_w = self.input_shape[2], self.input_shape[3] # Assuming NCHW
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        resized = cv2.resize(gray, (target_w, target_h))
        
        # Normalize 0-1
        normalized = resized.astype(np.float32) / 255.0
        
        # Add dimensions: (1, 1, H, W)
        return np.expand_dims(np.expand_dims(normalized, axis=0), axis=0)

    
    def classify_regions(self, image_path: str | Path, regions: List[Region]) -> List[Token]:
        """Classify a list of regions into tokens (Parallelized).
        
        Args:
            image_path: Path to the original full-page image
            regions: List of detected regions
            
        Returns:
            List of classified Tokens
        """
        if not regions:
            return []
            
        try:
            image = cv2.imread(str(image_path))
            if image is None:
                raise ValueError(f"Could not load image: {image_path}")
                
            tokens = []
            
            # Prepare region images (must be done in main thread to avoid OpenCV threading issues)
            region_images = []
            region_data = [] # Store metadata to reconstruct tokens
            
            for region in regions:
                x, y, w, h = region.bbox
                if w <= 0 or h <= 0:
                    continue
                
                # Extract region image
                roi = image[y:y+h, x:x+w]
                region_images.append(roi)
                region_data.append(region)
            
            # Run classification in parallel
            from concurrent.futures import ThreadPoolExecutor
            import os
            
            # Determine worker count (IO bound vs CPU bound depending on Tesseract/ONNX)
            max_workers = min(os.cpu_count() or 4, 8)
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                results = list(executor.map(self._classify_region, region_images))
            
            # Reconstruct tokens
            for (glyph, confidence), region in zip(results, region_data):
                tokens.append(Token(
                    glyph=glyph, 
                    bbox=region.bbox, 
                    confidence=confidence, 
                    region_type=region.region_type
                ))
                
            return tokens
            
        except Exception as e:
            logger.error(f"[GlyphClassifier] Error during classification: {e}")
            return []

    def classify_single(self, image_path: str | Path) -> List[Token]:
        """Convenience method to detect layout and classify in one step.
        
        Args:
            image_path: Path to equation image
            
        Returns:
            List of classified tokens
        """
        from .layout_detector import LayoutDetector
        
        detector = LayoutDetector()
        regions = detector.detect(image_path)
        return self.classify_regions(image_path, regions)
