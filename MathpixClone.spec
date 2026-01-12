# -*- mode: python ; coding: utf-8 -*-

"""
PyInstaller spec for Mathpix Clone
STABLE CONFIGURATION

Verified for:
- Python 3.11.x
- PyInstaller 6.x
- PyQt6 6.7.x + QtWebEngine
- pix2tex / torch (CPU)
"""

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_all, collect_dynamic_libs
import sys
import os
from unittest.mock import MagicMock

# FIX: Mock optional dependencies to prevent "No module named" errors 
# during submodule collection
import types

# Create simple module mocks
mamba_ssm_mock = types.ModuleType("mamba_ssm")
numba_mock = types.ModuleType("numba")

sys.modules["mamba_ssm"] = mamba_ssm_mock
sys.modules["numba"] = numba_mock

block_cipher = None

# =====================================================
# PROJECT ROOT
# =====================================================
spec_root = Path.cwd()

# =====================================================
# GLOBAL COLLECTORS (MUST BE DEFINED FIRST)
# =====================================================
datas = []
binaries = []
hiddenimports = []

# FIX: Explicitly bundle icon for runtime use
if (spec_root / "icon.ico").exists():
    datas.append(("icon.ico", "."))

# =====================================================
# POPPLER (PDF → IMAGE)
# =====================================================
poppler_dir = spec_root / "poppler" / "bin"
if poppler_dir.exists():
    datas.append((str(poppler_dir), "poppler/bin"))

# =====================================================
# MATHJAX (OFFLINE PREVIEW)
# =====================================================
mathjax_dir = spec_root / "mathjax"
if mathjax_dir.exists():
    datas.append((str(mathjax_dir), "mathjax"))

# =====================================================
# PIX2TEX DATA (MODELS / CONFIG)
# =====================================================
try:
    datas += collect_data_files("pix2tex", includes=["**/*"])
except Exception:
    pass

# Explicitly bundle valid model files we found
if (spec_root / "pix2tex_model").exists():
    datas.append(("pix2tex_model", "pix2tex_model"))

# =====================================================
# PANDAS (Required by pix2tex)
# =====================================================
# NOTE: Pandas collection is now handled by hooks/hook-pandas.py  
# to avoid numba warnings during submodule collection
# try:
#     # Use granular collection to avoid recursive 'collect_all' warnings (e.g. numba)
#     # Collect submodules (Python code), data files, and binaries separately
#     pandas_submodules = collect_submodules('pandas')
#     # Filter out numba-dependent submodules
#     pandas_submodules = [m for m in pandas_submodules if '_numba' not in m]
#     hiddenimports += pandas_submodules
#     datas += collect_data_files('pandas', include_py_files=False)
#     binaries += collect_dynamic_libs('pandas')
# except Exception:
#     pass


# =====================================================
# QT / WEBENGINE (CRITICAL)
# =====================================================
hiddenimports += [
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.QtNetwork",
    "PyQt6.QtPrintSupport",
    "PyQt6.QtWebChannel",
    "PyQt6.QtQuick",
    "PyQt6.QtQuickWidgets",
    "PyQt6.QtWebEngine",
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebEngineWidgets",
    
    
    # Force include UI modules
    "ui",
]

# Aggressively collect all UI submodules
hiddenimports += collect_submodules("ui")

hiddenimports += collect_submodules("PyQt6.QtWebEngineCore")
hiddenimports += collect_submodules("PyQt6.QtWebEngineWidgets")
hiddenimports += collect_submodules("timm")
# Filter out kernels to avoid warnings about optional dependencies
transformers_mods = collect_submodules("transformers")
hiddenimports += [m for m in transformers_mods if "kernels" not in m]
hiddenimports += collect_submodules("x_transformers")
hiddenimports += collect_submodules("albumentations")
hiddenimports += collect_submodules("services.ocr.pipeline_components")

# =====================================================
# OCR / ML / MATH
# =====================================================
hiddenimports += [
    "pix2tex",
    "pix2tex.model",
    "pix2tex.utils",
    "pix2tex.model",
    "pix2tex.utils",
    # CRITICAL: Dynamic imports for MathML conversion pipeline
    "services.ocr.latex_parser",
    "services.ocr.ast_to_mathml",
    "services.ocr.pipeline_components",
    # CRITICAL: Tokenizers library for force-reload fix
    "tokenizers",
    "tokenizers.implementations",
    "tokenizers.models",
    "tokenizers.decoders",
    "tokenizers.normalizers",
    "tokenizers.pre_tokenizers",
    "tokenizers.processors",
    "latex2mathml",
    "latex2mathml.converter",
    "latex2mathml.commands",
    "latex2mathml.exceptions",
    "pytesseract",
    "fitz",
    "pymupdf",
    # CRITICAL: Missing dependencies for pix2tex
    "tokenizers",
    "transformers",
    "huggingface_hub",
    "yaml",
    "packaging",
    # MISSING DEPS THAT CAUSE RUNTIME CRASHES or GARBAGE OUTPUT
    "x_transformers",  # CRITICAL for pix2tex model architecture
    "albumentations",  # CRITICAL for image preprocessing
    "albumentations.augmentations",
    "albumentations.augmentations.geometric",
    "albumentations.augmentations.transforms",
    "timm", 
    "einops",
    "pandas",  # Required by pix2tex
    "pandas._libs",
    "pandas._libs.pandas_parser",
    "pandas._libs.tslib",
    "pandas._libs.skiplist",
    "pandas._libs.arrays",
    "pandas._libs.interval",
    "pandas._libs.hashing",
    "chardet",
    "charset_normalizer",
    # FIX: Explicitly include opencv
    "cv2", 
    "dotenv",

    # FIX: Explicitly include Qt modules
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtWebEngineCore",
    # CRITICAL FIX FOR MATHML CRASH
    "lxml",
    "lxml.etree",
    "lxml._elementpath",
    "defusedxml",
    "torchvision",
    "pytz",
    "dateutil",
    "PIL",
    "PIL.Image",
    "PIL.ImageOps",
]

# CRITICAL: Copy metadata for version checks (transformers checks tokenizers version)
from PyInstaller.utils.hooks import copy_metadata
datas += copy_metadata('tokenizers')
datas += copy_metadata('transformers')
datas += copy_metadata('timm')
datas += copy_metadata('packaging')

# =====================================================
# EXCLUDES (SPEED + SIZE OPTIMIZATION)
# =====================================================
excludes = [
    # Test / dev
    "expecttest",
    "pytest",
    "IPython",
    "jupyter",
    "tkinter",

    # Vision (huge)
    # NOTE: pix2tex might need torchvision. 
    # Enable torchvision since we need it for pix2tex transforms
    # "torchvision",

    # Project garbage
    "tests",
    "docs",
    "examples",

    # Web frameworks (not needed for desktop app)
    "streamlit",
    "fastapi",
    "uvicorn",
    "starlette",
    "tornado",
    "fsspec",
    "s3fs",

    # Data Science / Plotting (heavy, likely unused by core OCR)
    "matplotlib",
    "seaborn",
    "bokeh",
    "plotly",
    "pydeck",
    "altair",
    # Unused heavy libraries
    # "pandas",
    
    # Dev / Misc
    "lib2to3",
    "pkg_resources",  # careful, but often huge
    
    # Fix runtime extraction error
    "bidi",
    "algorithm",
    
    # NLTK is unused and causes issues
    "nltk",

    # Heavy Vision/ML transient deps
    "paddle",
    "paddlepaddle",
    "paddlex",
    "pyarrow",
    "datasets",
    
    # Unused PyQt6 modules (save ~200MB)
    "PyQt6.QtQuick",
    "PyQt6.QtQml",
    "PyQt6.QtSql",
    "PyQt6.QtSvg",
    "PyQt6.QtXml",
    "PyQt6.QtMultimedia",
    "PyQt6.QtBluetooth",
    "PyQt6.QtNfc",
    "PyQt6.QtPositioning",
    "PyQt6.QtRemoteObjects",
    "PyQt6.QtSensors",
    "PyQt6.QtSerialPort",
    "PyQt6.QtTest",
    
    # Optional deps causing warnings
    "numba",  # Optional performance optimization - removed pandas.core._numba to let hook collect it
    "transformers.kernels.falcon_mamba",
    "transformers.kernels",  # Excludes all kernel implementations (falcon_mamba, etc.)
    "mamba_ssm",
]


# =====================================================
# ANALYSIS
# =====================================================
a = Analysis(
    ["app.py"],
    pathex=[str(spec_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(spec_root / "hooks")] if (spec_root / "hooks").exists() else [],
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

# =====================================================
# PYZ
# =====================================================
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# =====================================================
# EXE
# =====================================================
# Icon selection
icon_path = spec_root / "icon.ico"
if icon_path.exists():
    selected_icon = str(icon_path)
else:
    selected_icon = None

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Math Extractor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=selected_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Math Extractor',
)
