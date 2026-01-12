
import sys
import os
from pathlib import Path
from core.logger import logger

def get_resource_path(relative_path: str) -> str:
    """
    Get the absolute path to a resource, works for dev and for PyInstaller.
    
    Args:
        relative_path: Path relative to the project root (e.g., "mathjax/tex-mml-svg.js")
    
    Returns:
        Absolute path to the resource.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
            logger.debug(f"[ResourceUtils] Running in frozen mode, base_path: {base_path}")
        else:
            # In dev, use the project root
            # This file is in utils/, so project root is one level up
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            # logger.debug(f"[ResourceUtils] Running in dev mode, base_path: {base_path}")

        path = os.path.join(base_path, relative_path)
        
        # Normalize path separators
        return os.path.normpath(path)
        
    except Exception as e:
        logger.error(f"[ResourceUtils] Failed to resolve path for {relative_path}: {e}")
        return relative_path

def get_mathjax_path() -> str:
    """Helper to find MathJax specific script."""
    # List of possible locations relative to root
    possible_paths = [
        "mathjax/tex-mml-svg.js",
        "mathjax/es5/tex-mml-svg.js",
        "mathjax/tex-mml-chtml.js",
        "mathjax/es5/tex-mml-chtml.js"
    ]
    
    for p in possible_paths:
        full_path = get_resource_path(p)
        if os.path.exists(full_path):
            return full_path
            
    # Fallback to CDN if allowed, or just return the primary local path even if missing (to let it fail specifically)
    return get_resource_path("mathjax/tex-mml-svg.js")
