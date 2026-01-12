"""
Equation Cache for Performance Optimization

Caches processed equation results to avoid re-processing identical formulas.
Uses SHA256 hash of image data as cache key with LRU eviction.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Optional, TypedDict
from collections import OrderedDict

from core.config import settings
from core.logger import logger


class CachedEquation(TypedDict):
    """Cached equation result."""
    latex: str
    mathml: str
    is_valid: bool
    timestamp: float
    hash: str
    corruption_score: Optional[float]


class EquationCache:
    """LRU cache for processed equations."""
    
    def __init__(self, max_size: int = 100):
        """
        Initialize equation cache.
        
        Args:
            max_size: Maximum number of cached equations (LRU eviction)
        """
        self.max_size = max_size
        self._cache: OrderedDict[str, CachedEquation] = OrderedDict()
        self._cache_file = settings.cache_dir / "equation_cache.json"
        self._load_cache()
        
    def _compute_hash(self, image_path: str | Path) -> str:
        """
        Compute fast BLAKE2b hash of image file.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Hexadecimal hash string
        """
        try:
            with open(image_path, 'rb') as f:
                # BLAKE2b is significantly faster than SHA256 for large files
                content = f.read()
                file_hash = hashlib.blake2b(content, digest_size=20).hexdigest()
            return file_hash
        except Exception as e:
            logger.warning(f"[EquationCache] Failed to hash image {image_path}: {e}")
            return ""
    
    def get(self, image_path: str | Path) -> Optional[CachedEquation]:
        """
        Retrieve cached equation result.
        
        Args:
            image_path: Path to cropped equation image
            
        Returns:
            Cached result if found, None otherwise
        """
        img_hash = self._compute_hash(image_path)
        if not img_hash:
            return None
            
        if img_hash in self._cache:
            # Move to end (most recently used)
            self._cache.move_to_end(img_hash)
            cached = self._cache[img_hash]
            # Ensure backward compatibility for entries without corruption_score
            if "corruption_score" not in cached:
                cached["corruption_score"] = 0.0
            logger.info(f"[EquationCache] Cache HIT for {Path(image_path).name}")
            return cached
        
        logger.debug(f"[EquationCache] Cache MISS for {Path(image_path).name}")
        return None
    
    def put(self, image_path: str | Path, latex: str, mathml: str, is_valid: bool, corruption_score: float = 0.0) -> None:
        """
        Store equation result in cache.
        
        Args:
            image_path: Path to cropped equation image
            latex: Processed LaTeX
            mathml: Generated MathML
            is_valid: Whether result passed validation
        """
        img_hash = self._compute_hash(image_path)
        if not img_hash:
            return
        
        # Add to cache
        self._cache[img_hash] = CachedEquation(
            latex=latex,
            mathml=mathml,
            is_valid=is_valid,
            timestamp=time.time(),
            hash=img_hash,
            corruption_score=corruption_score
        )
        
        # Move to end (most recently used)
        self._cache.move_to_end(img_hash)
        
        # Evict oldest if exceeds max size
        if len(self._cache) > self.max_size:
            oldest_key = next(iter(self._cache))
            evicted = self._cache.pop(oldest_key)
            logger.debug(f"[EquationCache] Evicted old entry (hash: {evicted['hash'][:8]})")
        
        logger.info(f"[EquationCache] Cached equation for {Path(image_path).name} (total: {len(self._cache)})")
        
        # Persist to disk
        self._save_cache()
    
    def _load_cache(self) -> None:
        """Load cache from disk (cross-session persistence)."""
        if not self._cache_file.exists():
            logger.debug("[EquationCache] No cache file found, starting fresh")
            return
        
        try:
            with open(self._cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Load entries sorted by timestamp (oldest first for LRU)
            entries = sorted(data.items(), key=lambda x: x[1].get('timestamp', 0))
            
            for img_hash, cached_eq in entries:
                self._cache[img_hash] = cached_eq
            
            logger.info(f"[EquationCache] Loaded {len(self._cache)} cached equations from disk")
            
        except Exception as e:
            logger.warning(f"[EquationCache] Failed to load cache: {e}")
            self._cache.clear()
    
    def _save_cache(self) -> None:
        """Persist cache to disk."""
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self._cache_file, 'w', encoding='utf-8') as f:
                json.dump(dict(self._cache), f, indent=2)
            
            logger.debug(f"[EquationCache] Saved {len(self._cache)} entries to disk")
            
        except Exception as e:
            logger.warning(f"[EquationCache] Failed to save cache: {e}")
    
    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        if self._cache_file.exists():
            self._cache_file.unlink()
        logger.info("[EquationCache] Cache cleared")
    
    def stats(self) -> dict:
        """Get cache statistics."""
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "utilization": f"{len(self._cache) / self.max_size * 100:.1f}%"
        }


# Global singleton instance
_cache_instance: Optional[EquationCache] = None


def get_equation_cache() -> EquationCache:
    """Get global equation cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = EquationCache()
    return _cache_instance
