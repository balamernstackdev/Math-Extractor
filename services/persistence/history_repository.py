"""
HistoryRepository.py
Persistence layer for Mathpix Clone Extraction History.
Automatically logs every successful extraction.
"""
from __future__ import annotations
import json
import uuid
import time
from pathlib import Path
from typing import List, Dict, Optional
from core.logger import logger
from core.config import settings

class HistoryRepository:
    """Manages storage and retrieval of extraction history."""
    
    def __init__(self, storage_dir: Optional[Path] = None):
        """
        Initialize repository.
        Args:
            storage_dir: Directory to store history.jsonl. Defaults to settings.user_data_dir.
        """
        if storage_dir:
            self.storage_dir = storage_dir
        else:
            self.storage_dir = settings.data_dir
            
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.storage_dir / "history.jsonl"
        self._cache: List[Dict] = []
        self._loaded = False
        
    def _load(self):
        """Load all history from disk into cache."""
        self._cache = []
        if not self.db_path.exists():
            self._loaded = True
            return

        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            self._cache.append(json.loads(line))
                        except json.JSONDecodeError:
                            logger.error(f"[HistoryRepository] Corrupt line skipped in {self.db_path}")
        except Exception as e:
            logger.error(f"[HistoryRepository] Failed to load DB: {e}")
            
        # Sort by timestamp desc (newest first)
        self._cache.sort(key=lambda x: x.get('created_at', 0), reverse=True)
        self._loaded = True
        logger.info(f"[HistoryRepository] Loaded {len(self._cache)} items")

    def get_all(self) -> List[Dict]:
        """Get all history (newest first)."""
        if not self._loaded:
            self._load()
        return self._cache

    def add(self, latex: str, mathml: str, image_path: Optional[str] = None, is_valid: bool = True) -> Dict:
        """
        Log a new extraction to history.
        Returns the created record.
        """
        if not self._loaded:
            self._load()
            
        record = {
            "id": str(uuid.uuid4()),
            "created_at": time.time(),
            "latex": latex.strip(),
            "mathml": mathml.strip(),
            "image": str(image_path) if image_path else None,
            "is_valid": is_valid
        }
        
        # Append to file
        try:
            with open(self.db_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record) + "\n")
            
            # Update cache (prepend to keep sorted)
            self._cache.insert(0, record)
            
            # Limit cache size to 500 for history (optional but healthy)
            if len(self._cache) > 500:
                self._cache = self._cache[:500]
                
            logger.info(f"[HistoryRepository] Logged extraction {record['id']}")
            return record
        except Exception as e:
            logger.error(f"[HistoryRepository] Logging failed: {e}")
            return record # Return record anyway so UI can use it temporarily

    def clear(self):
        """Clear all history."""
        self._cache = []
        try:
            if self.db_path.exists():
                self.db_path.unlink()
            self._loaded = True
        except Exception as e:
            logger.error(f"[HistoryRepository] Clear failed: {e}")
