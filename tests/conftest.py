"""Pytest configuration for tests."""
from __future__ import annotations

import sys
from pathlib import Path

# Add the parent directory (mathpix_clone) to the Python path
# This allows imports like "from services.ocr..." to work
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

