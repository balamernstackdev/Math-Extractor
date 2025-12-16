"""Configuration management for Mathpix clone."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

# PyInstaller support: detect if running as executable
def _get_base_dir() -> Path:
    """Get base directory, handling both development and PyInstaller executable."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller executable
        # Use user's app data directory for data storage
        if sys.platform == 'win32':
            appdata = os.getenv('APPDATA', os.path.expanduser('~'))
            base_dir = Path(appdata) / 'MathpixClone'
        else:
            # Linux/Mac
            base_dir = Path.home() / '.mathpix_clone'
        return base_dir
    else:
        # Running as script - use project root
        return Path(__file__).resolve().parents[1]

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    # Load .env file from project root (only in development, not in exe)
    if not getattr(sys, 'frozen', False):
        env_path = _get_base_dir() / ".env"
        if env_path.exists():
            load_dotenv(env_path)
except ImportError:
    # python-dotenv not installed, skip .env loading
    pass    

def _find_poppler_path() -> Path | None:
    """Auto-detect Poppler installation path on Windows."""
    # Check environment variable first
    if env_path := os.getenv("POPPLER_PATH"):
        path = Path(env_path)
        if path.exists() and (path / "pdftoppm.exe").exists():
            return path
    
    # Check common Windows installation locations
    local_appdata = os.getenv("LOCALAPPDATA")
    if local_appdata:
        # WinGet installation path
        winget_path = Path(local_appdata) / "Microsoft" / "WinGet" / "Packages"
        if winget_path.exists():
            for poppler_dir in winget_path.glob("*poppler*"):
                # Search for poppler-*/Library/bin pattern
                for match in poppler_dir.glob("poppler-*/Library/bin"):
                    if (match / "pdftoppm.exe").exists():
                        return match
    
    # Check Program Files
    for program_files in [os.getenv("ProgramFiles"), os.getenv("ProgramFiles(x86)")]:
        if program_files:
            poppler_path = Path(program_files) / "poppler" / "Library" / "bin"
            if poppler_path.exists() and (poppler_path / "pdftoppm.exe").exists():
                return poppler_path
    
    return None


def _find_tesseract_path() -> str | None:
    """Auto-detect Tesseract OCR installation path on Windows."""
    # Check environment variable first
    if env_path := os.getenv("TESSERACT_CMD"):
        if Path(env_path).exists():
            return env_path
    
    # Check common Windows installation locations
    for program_files in [os.getenv("ProgramFiles"), os.getenv("ProgramFiles(x86)")]:
        if program_files:
            # Common Tesseract installation paths
            tesseract_paths = [
                Path(program_files) / "Tesseract-OCR" / "tesseract.exe",
                Path(program_files) / "Tesseract" / "tesseract.exe",
            ]
            for tesseract_path in tesseract_paths:
                if tesseract_path.exists():
                    return str(tesseract_path)
    
    # Check if tesseract is in PATH
    import shutil
    tesseract_cmd = shutil.which("tesseract")
    if tesseract_cmd:
        return tesseract_cmd
    
    return None


def _load_tesseract_from_config() -> str | None:
    """Load Tesseract path from saved config file."""
    base_dir = _get_base_dir()
    config_file = base_dir / "data" / "config.json"
    if config_file.exists():
        try:
            import json
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                tesseract_path = config.get("tesseract_path")
                if tesseract_path and Path(tesseract_path).exists():
                    return tesseract_path
        except Exception:  # noqa: BLE001
            pass
    return None


@dataclass
class Settings:
    """Application settings."""

    base_dir: Path = _get_base_dir()
    data_dir: Path = base_dir / "data"
    uploads_dir: Path = data_dir / "uploads"
    snips_dir: Path = data_dir / "snips"
    notes_dir: Path = data_dir / "notes"
    host: str = os.getenv("MATHPIX_HOST", "127.0.0.1")
    port: int = int(os.getenv("MATHPIX_PORT", "8000"))
    log_level: str = os.getenv("MATHPIX_LOG_LEVEL", "INFO")
    allowed_ips: set[str] = frozenset(
        ip.strip()
        for ip in os.getenv("MATHPIX_ALLOWED_IPS", "").split(",")
        if ip.strip()
    )
    tesseract_cmd: str | None = (
        os.getenv("TESSERACT_CMD") 
        or _load_tesseract_from_config() 
        or _find_tesseract_path()
    )
    poppler_path: Path | None = _find_poppler_path()
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")    
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")    
    use_openai_fallback: bool = os.getenv("USE_OPENAI_FALLBACK", "false").lower() == "true"


settings = Settings()

