"""Layout detection for mathematical equations.

This module identifies bounding boxes and structural elements in equation images.
It will eventually replace the monolithic LaTeX-first approach with region-wise
detection that preserves spatial relationships.
"""
from __future__ import annotations

import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple
from pathlib import Path
from core.logger import logger


@dataclass
class Region:
    """A detected region in the equation image."""
    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    region_type: str  # 'symbol', 'subscript', 'superscript', 'fraction', 'matrix', 'operator'
    confidence: float = 1.0
    
    @property
    def center_x(self) -> float:
        return self.bbox[0] + self.bbox[2] / 2
    
    @property
    def center_y(self) -> float:
        return self.bbox[1] + self.bbox[3] / 2
    
    def __repr__(self) -> str:
        return f"Region(type={self.region_type!r}, bbox={self.bbox}, conf={self.confidence:.2f})"


class LayoutDetector:
    """Detect spatial layout and structural elements in equation images.
    
    This is a Phase 1 implementation that provides basic bounding box detection.
    Future enhancements will include:
    - Grid detection for matrices
    - Fraction bar detection
    - Horizontal alignment detection
    - Connected component analysis
    """
    
    def __init__(self):
        self.min_region_area = 10  # Minimum pixel area to consider a valid region
        self.max_region_area = 50000  # Maximum area (filter out noise)
    
    def detect(self, image_path: str | Path) -> List[Region]:
        """Detect regions in the equation image.
        
        Args:
            image_path: Path to the cropped equation image
            
        Returns:
            List of detected regions with bounding boxes and type hints
        """
        try:
            # Load image
            img = cv2.imread(str(image_path))
            if img is None:
                logger.error(f"[LayoutDetector] Failed to load image: {image_path}")
                return []
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Apply adaptive thresholding to handle varying lighting
            binary = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY_INV, 11, 2
            )
            
            # Find connected components
            num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
                binary, connectivity=8
            )
            
            regions = []
            
            # Process each component (skip background at index 0)
            for i in range(1, num_labels):
                x, y, w, h, area = stats[i]
                
                # Filter out too small or too large regions
                if area < self.min_region_area or area > self.max_region_area:
                    continue
                
                # Heuristic type classification based on size and position
                # This is a placeholder - will be replaced with proper classification
                region_type = self._classify_region_type(x, y, w, h, img.shape)
                
                regions.append(Region(
                    bbox=(x, y, w, h),
                    region_type=region_type,
                    confidence=0.8  # Placeholder confidence
                ))
            
            # Sort regions left-to-right, top-to-bottom for logical ordering
            regions = sorted(regions, key=lambda r: (r.center_y, r.center_x))
            
            logger.info(f"[LayoutDetector] Detected {len(regions)} regions in {image_path}")
            return regions
            
        except Exception as e:
            logger.error(f"[LayoutDetector] Error during detection: {e}")
            return []
    
    def _classify_region_type(self, x: int, y: int, w: int, h: int, 
                              img_shape: Tuple[int, int, int]) -> str:
        """Classify region type based on geometric heuristics.
        
        This is a placeholder implementation. Future versions will use:
        - Machine learning classifiers
        - Spatial relationship graphs
        - Pattern matching (e.g., fraction bars, matrix grids)
        """
        img_height, img_width = img_shape[:2]
        
        # Vertical position relative to image
        vertical_position = y / img_height
        
        # Aspect ratio
        aspect_ratio = w / h if h > 0 else 1.0
        
        # Simple heuristics (to be replaced with proper classification)
        if aspect_ratio > 3.0:
            # Very wide - likely a horizontal line (fraction bar, underline)
            return 'operator'
        elif vertical_position < 0.3:
            # Upper region - likely superscript
            return 'superscript'
        elif vertical_position > 0.7:
            # Lower region - likely subscript
            return 'subscript'
        else:
            # Middle region - likely main symbol
            return 'symbol'
    
    def detect_grid(self, regions: List[Region]) -> List[List[Region]]:
        """Detect grid structure (for matrices, aligned equations).
        
        Args:
            regions: List of detected regions
            
        Returns:
            2D list of regions organized by row and column
        """
        # Placeholder for matrix detection
        # Future implementation will cluster regions by row/column alignment
        return [regions]  # Return single row for now
