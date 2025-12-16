"""Bounding box utilities for PDF page overlays."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class BoundingBox:
    """Represents a detected formula bounding box."""

    x: int
    y: int
    w: int
    h: int
    id: str

    def to_dict(self) -> dict[str, int | str]:
        """Serialize bounding box to dictionary."""
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h, "id": self.id}


def normalize_boxes(boxes: List[BoundingBox]) -> List[BoundingBox]:
    """Ensure bounding boxes have positive width/height."""
    normalized: List[BoundingBox] = []
    for box in boxes:
        w = abs(box.w)
        h = abs(box.h)
        normalized.append(BoundingBox(box.x, box.y, w, h, box.id))
    return normalized

