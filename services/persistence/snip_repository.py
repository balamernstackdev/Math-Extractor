"""
SnipRepository.py
Persistence layer for Mathpix Clone Snips.
Stores snips in a JSON Lines (.jsonl) file for robustness and append-only performance.
"""
from __future__ import annotations
import json
import uuid
import time
from pathlib import Path
from typing import List, Dict, Optional
from core.logger import logger
from core.config import settings

class SnipRepository:
    """Manages storage and retrieval of saved math snips."""
    
    def __init__(self, storage_dir: Optional[Path] = None):
        """
        Initialize repository.
        Args:
            storage_dir: Directory to store snips.jsonl. Defaults to settings.user_data_dir.
        """
        if storage_dir:
            self.storage_dir = storage_dir
        elif hasattr(settings, 'data_dir'):
            self.storage_dir = settings.data_dir
        else:
            # Fallback for dev/testing
            self.storage_dir = Path("data")
            
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.storage_dir / "snips.jsonl"
        self._cache: List[Dict] = []
        self._loaded = False
        
    def _load(self):
        """Load all snips from disk into cache."""
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
                            logger.error(f"[SnipRepository] Corrupt line skipped in {self.db_path}")
        except Exception as e:
            logger.error(f"[SnipRepository] Failed to load DB: {e}")
            
        # Sort by timestamp desc (newest first)
        self._cache.sort(key=lambda x: x.get('created_at', 0), reverse=True)
        self._loaded = True
        logger.info(f"[SnipRepository] Loaded {len(self._cache)} snips")

    def get_all(self) -> List[Dict]:
        """Get all snips (newest first)."""
        if not self._loaded:
            self._load()
        return self._cache

    def add(self, latex: str, mathml: str, image_path: Optional[str] = None, tags: List[str] = None) -> Dict:
        """
        Save a new snip.
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
            "tags": tags or [],
            "status": "success" # Default
        }
        
        # Append to file
        try:
            with open(self.db_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record) + "\n")
            
            # Update cache (prepend to keep sorted)
            self._cache.insert(0, record)
            logger.info(f"[SnipRepository] Saved snip {record['id']}")
            return record
        except Exception as e:
            logger.error(f"[SnipRepository] Save failed: {e}")
            raise IOError(f"Could not save snip: {e}")

    def delete(self, snip_id: str) -> bool:
        """Delete a snip by ID (expensive: rewrites file)."""
        if not self._loaded:
            self._load()
            
        initial_len = len(self._cache)
        self._cache = [s for s in self._cache if s['id'] != snip_id]
        
        if len(self._cache) == initial_len:
            return False # Not found
            
        # Rewrite file
        try:
            with open(self.db_path, 'w', encoding='utf-8') as f:
                for record in sorted(self._cache, key=lambda x: x['created_at']): # Write oldest first
                    f.write(json.dumps(record) + "\n")
            
            # Re-sort cache for UI
            self._cache.sort(key=lambda x: x.get('created_at', 0), reverse=True)
            logger.info(f"[SnipRepository] Deleted snip {snip_id}")
            return True
        except Exception as e:
            logger.error(f"[SnipRepository] Delete failed: {e}")
            return False
