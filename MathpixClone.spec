# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Mathpix Clone application.

This file provides more control over the build process than command-line arguments.
You can customize it to include additional files, exclude modules, etc.

Usage:
    pyinstaller MathpixClone.spec
"""

import sys
from pathlib import Path
import os

# PyInstaller hooks for collecting data files
from PyInstaller.utils.hooks import collect_data_files, collect_all

# Get project root - PyInstaller should be run from project root
# Use current working directory (where pyinstaller command is run from)
spec_root = Path.cwd()

# Verify we're in the right place - look for app.py
if not (spec_root / 'app.py').exists():
    # Try to find project root by looking for app.py in parent directories
    for parent in spec_root.parents:
        if (parent / 'app.py').exists():
            spec_root = parent
            break

# Print for debugging (will show in PyInstaller output)
print(f"[SPEC] Project root: {spec_root}")
print(f"[SPEC] Data exists: {(spec_root / 'data').exists()}")
print(f"[SPEC] App.py exists: {(spec_root / 'app.py').exists()}")

# Check for icon file
icon_path = spec_root / 'icon.ico'
if icon_path.exists():
    print(f"[SPEC] ✅ Icon found: {icon_path}")
else:
    print(f"[SPEC] ⚠️  Icon not found: {icon_path}")
    print(f"[SPEC]    To add an icon: Create icon.ico in project root or use create_icon.py")

# Collect pix2tex data files (models, configs, etc.)
pix2tex_datas = []
pix2tex_binaries = []
pix2tex_hiddenimports = []

try:
    pix2tex_info = collect_all('pix2tex')
    pix2tex_datas = pix2tex_info[0]  # Data files
    pix2tex_binaries = pix2tex_info[1]  # Binaries
    pix2tex_hiddenimports = pix2tex_info[2]  # Hidden imports
    print(f"[SPEC] Collected {len(pix2tex_datas)} pix2tex data files")
except Exception as e:
    print(f"[SPEC] Warning: Could not collect pix2tex data files: {e}")

# Collect QtWebEngine resources (CRITICAL for PreviewPanel)
qtwebengine_datas = []
qtwebengine_binaries = []
qtwebengine_hiddenimports = []
qtwebengine_datas = []
try:
    from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs, get_pyqt_qt_binaries
    # Collect QtWebEngine data files (translations, resources, etc.)
    qtwebengine_datas = collect_data_files('PyQt6.QtWebEngine', includes=['**/*'])
    # Also collect QtWebEngineCore resources
    qtwebengine_datas.extend(collect_data_files('PyQt6.QtWebEngineCore', includes=['**/*']))
    # Collect QtWebEngine binaries (DLLs)
    qtwebengine_binaries = collect_dynamic_libs('PyQt6.QtWebEngine')
    qtwebengine_binaries.extend(collect_dynamic_libs('PyQt6.QtWebEngineCore'))
    # CRITICAL: Collect ALL Qt DLLs (WebEngine depends on QtCore, QtGui, QtNetwork, QtQuick, etc.)
    qt_all_binaries = get_pyqt_qt_binaries('PyQt6')
    qtwebengine_binaries.extend(qt_all_binaries)
    # Collect QtWebEngine submodules
    qtwebengine_hiddenimports = collect_submodules('PyQt6.QtWebEngine')
    qtwebengine_hiddenimports.extend(collect_submodules('PyQt6.QtWebEngineCore'))
    print(f"[SPEC] Collected {len(qtwebengine_datas)} QtWebEngine resource files")
    print(f"[SPEC] Collected {len(qtwebengine_binaries)} Qt binaries (including WebEngine)")
    print(f"[SPEC] Collected {len(qtwebengine_hiddenimports)} QtWebEngine submodules")
except Exception as e:
    print(f"[SPEC] Warning: Could not collect QtWebEngine resources: {e}")
    # Try alternative method
    try:
        import PyQt6.QtWebEngine
        import PyQt6.QtWebEngineCore
        qtwebengine_path = Path(PyQt6.QtWebEngine.__file__).parent
        qtwebengine_core_path = Path(PyQt6.QtWebEngineCore.__file__).parent
        print(f"[SPEC] QtWebEngine path: {qtwebengine_path}")
        print(f"[SPEC] QtWebEngineCore path: {qtwebengine_core_path}")
        # Manually add common QtWebEngine submodules
        qtwebengine_hiddenimports = [
            'PyQt6.QtWebEngine',
            'PyQt6.QtWebEngineCore',
            'PyQt6.QtWebEngineWidgets',
            'PyQt6.QtWebEngineCore.QWebEngineUrlRequestInterceptor',
            'PyQt6.QtWebEngineCore.QWebEngineUrlSchemeHandler',
        ]
    except Exception as e2:
        print(f"[SPEC] Warning: Could not locate QtWebEngine paths: {e2}")
        # qtwebengine_hiddenimports already initialized as empty list above

# Also try to include pix2tex cache if it exists (models downloaded by user)
pix2tex_cache = Path(os.path.expanduser('~/.cache/pix2tex'))
if pix2tex_cache.exists():
    print(f"[SPEC] Found pix2tex cache at: {pix2tex_cache}")
    # Include cache directory
    for item in pix2tex_cache.rglob('*'):
        if item.is_file():
            rel_path = item.relative_to(pix2tex_cache.parent.parent)
            pix2tex_datas.append((str(item), str(rel_path.parent)))
            print(f"[SPEC] Including pix2tex cache file: {item.name}")

block_cipher = None

a = Analysis(
    ['app.py'],  # Main entry point
    pathex=[str(spec_root)],
    binaries=pix2tex_binaries + qtwebengine_binaries,  # Include pix2tex and QtWebEngine binaries
    datas=[
        # Use absolute paths - PyInstaller will copy these to the executable
        # Only include if they exist (data might be created at runtime)
        *([(str(spec_root / 'data'), 'data')] if (spec_root / 'data').exists() else []),
        *([(str(spec_root / 'utils' / 'entity_reference.json'), 'utils')] if (spec_root / 'utils' / 'entity_reference.json').exists() else []),
        # Optional offline MathJax bundle
        *([(str(spec_root / 'mathjax'), 'mathjax')] if (spec_root / 'mathjax').exists() else []),
        # Include pix2tex data files (models, configs)
        *pix2tex_datas,
        # Include QtWebEngine resources (CRITICAL for PreviewPanel)
        # Note: qtwebengine_datas already includes translations and resources via collect_data_files
        *qtwebengine_datas,
    ],
    hiddenimports=[
        # PyQt6 modules (CRITICAL: Include WebEngine for PreviewPanel)
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtWebEngineWidgets',  # REQUIRED for PreviewPanel MathML rendering
        'PyQt6.QtWebEngineCore',  # REQUIRED for WebEngine
        'PyQt6.QtWebEngine',  # REQUIRED for WebEngine resources
        # CRITICAL: WebEngine dependencies (required by WebEngine)
        'PyQt6.QtNetwork',  # REQUIRED by WebEngine
        'PyQt6.QtQuick',  # REQUIRED by WebEngineCore
        'PyQt6.QtQuickWidgets',  # REQUIRED by WebEngineWidgets
        # Include all QtWebEngine submodules (collected above)
        *qtwebengine_hiddenimports,
        
        # FastAPI and web (only if using API mode)
        'fastapi',
        'uvicorn',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.websockets',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.loops.asyncio',
        
        # OCR and ML
        'pix2tex',
        'pix2tex.cli',
        'pix2tex.model',
        'pix2tex.utils',
        'pix2text',
        'latex2mathml',  # LaTeX to MathML converter
        'latex2mathml.converter',  # Main converter module
        'latex2mathml.parser',  # Parser module
        'latex2mathml.symbols',  # Symbol definitions
        'latex2mathml.commands',  # Command definitions
        'latex2mathml.exceptions',  # Exception classes
        'latex2mathml.symbols_parser',  # Symbol parser
        'latex2mathml.tokenizer',  # Tokenizer
        'latex2mathml.walker',  # AST walker
        'pytesseract',
        # Include pix2tex hidden imports
        *pix2tex_hiddenimports,
        
        # MathML recovery modules (CRITICAL: Dynamic imports)
        'services.ocr.mathml_recovery_pro',
        'services.ocr.mathml_recovery',
        'services.ocr.mathml_recovery_pro_force',
        'services.ocr.dynamic_latex_reconstructor',
        'services.ocr.latex_to_mathml',
        'services.ocr.strict_pipeline',
        'services.ocr.openai_mathml_converter',
        'services.ocr.pipeline',
        'services.ocr.math_expression_pipeline',
        'services.ocr.image_to_latex',  # OCR service
        'services.ocr.ocr_mathml_cleaner',  # MathML cleaner
        'services.ocr.pix2tex_auto_fixer',  # Auto fixer
        
        # XML/HTML parsing (REQUIRED for latex2mathml and MathML processing)
        'xml.etree.ElementTree',
        'xml.etree.cElementTree',  # C implementation if available
        'html',
        'html.parser',
        'html.entities',
        
        # Image processing
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',  # Some image operations
        'cv2',
        'numpy',
        
        # ML frameworks (minimal - only what pix2tex needs)
        'torch',
        'torch.nn',
        'torch.nn.functional',
        'transformers',
        
        # OpenAI (optional)
        'openai',
        'httpx',  # Required by openai client
        
        # Other dependencies
        'pydantic',
        'pymupdf',  # PyMuPDF
        'fitz',  # PyMuPDF alias
    ],
    hookspath=([str(spec_root / 'hooks')] if (spec_root / 'hooks').exists() else []),  # Include custom hooks if directory exists
    hooksconfig={},
    runtime_hooks=([str(spec_root / 'hooks' / 'pyi_rth_pyqt6.py')] if (spec_root / 'hooks' / 'pyi_rth_pyqt6.py').exists() else []),
    excludes=[
        # Testing and development
        'matplotlib.tests',
        'matplotlib.testing',
        'numpy.tests',
        'scipy',
        'pytest',
        'pytest_*',
        'IPython',
        'jupyter',
        'notebook',
        'tkinter',
        'unittest',
        'doctest',
        
        # PyTorch unnecessary components (BIG SIZE SAVINGS)
        'torch.distributed',  # Distributed training - not needed
        'torch.multiprocessing',  # Multiprocessing - not needed
        'torch.onnx',  # ONNX export - not needed
        'torch.jit',  # JIT compilation - not needed
        'torch.autograd.profiler',  # Profiling - not needed
        'torch.backends.cudnn',  # CUDA - not needed for CPU
        'torch.backends.mkl',  # MKL - optional
        'torch.backends.mkldnn',  # MKLDNN - optional
        'torch.backends.openmp',  # OpenMP - optional
        'torch.backends.quantized',  # Quantization - not needed
        'torch.cuda',  # CUDA support - not needed for CPU
        'torch.testing',  # Testing - not needed
        'torch.utils.bottleneck',  # Profiling - not needed
        'torch.utils.tensorboard',  # TensorBoard - not needed
        'torch._dynamo',  # Dynamic compilation - not needed
        'torch._inductor',  # Inductor - not needed
        'torch._lazy',  # Lazy tensors - not needed
        'torch._numpy',  # NumPy compatibility - not needed
        'torch.ao',  # AO quantization - not needed
        
        # torchvision (NOT NEEDED for pix2tex - BIG SIZE SAVINGS ~100-200MB)
        'torchvision',
        'torchvision.*',
        
        # Transformers unnecessary components (be conservative - pix2tex might need some)
        'transformers.trainer',  # Training - not needed
        'transformers.training_args',  # Training - not needed
        'transformers.integrations.*',  # Integrations - not needed
        'transformers.commands.*',  # CLI commands - not needed
        'transformers.onnx.*',  # ONNX export - not needed
        'transformers.quantizers.*',  # Quantization - not needed
        'transformers.models.deprecated.*',  # Deprecated models
        'transformers.models.megatron.*',  # Megatron - not needed
        'transformers.models.granite.*',  # Granite - not needed
        'transformers.models.musicgen.*',  # MusicGen - not needed
        'transformers.models.wav2vec2.*',  # Audio models - not needed
        'transformers.models.mgp_str.*',  # MGP - not needed
        'transformers.models.realm.*',  # REALM - not needed
        
        # PyQt6 unnecessary modules (KEEP WebEngine and its dependencies - they're REQUIRED!)
        'PyQt6.QtOpenGL',
        'PyQt6.QtPrintSupport',
        # DO NOT EXCLUDE QtWebEngine or its dependencies - PreviewPanel needs them!
        # 'PyQt6.QtWebEngine',  # REQUIRED - DO NOT EXCLUDE
        # 'PyQt6.QtWebEngineWidgets',  # REQUIRED - DO NOT EXCLUDE
        # 'PyQt6.QtNetwork',  # REQUIRED by WebEngine - DO NOT EXCLUDE
        # 'PyQt6.QtQuick',  # REQUIRED by WebEngineCore - DO NOT EXCLUDE
        # 'PyQt6.QtQuickWidgets',  # REQUIRED by WebEngineWidgets - DO NOT EXCLUDE
        'PyQt6.QtWebSockets',
        'PyQt6.QtBluetooth',
        'PyQt6.QtNfc',
        'PyQt6.QtPositioning',
        'PyQt6.QtLocation',
        'PyQt6.QtSensors',
        'PyQt6.QtSerialPort',
        'PyQt6.QtSql',
        'PyQt6.QtSvg',
        'PyQt6.QtTest',
        'PyQt6.QtXml',
        'PyQt6.QtXmlPatterns',
        'PyQt6.QtDesigner',
        'PyQt6.QtHelp',
        'PyQt6.QtMultimedia',
        'PyQt6.QtMultimediaWidgets',
        'PyQt6.QtQml',
        'PyQt6.QtRemoteObjects',
        'PyQt6.QtScxml',
        'PyQt6.QtStateMachine',
        'PyQt6.QtTextToSpeech',
        'PyQt6.QtCharts',
        'PyQt6.QtDataVisualization',
        'PyQt6.Qt3DCore',
        'PyQt6.Qt3DRender',
        'PyQt6.Qt3DInput',
        'PyQt6.Qt3DLogic',
        'PyQt6.Qt3DAnimation',
        'PyQt6.Qt3DExtras',
        
        # Matplotlib unnecessary backends (keep only what's needed)
        'matplotlib.backends.backend_pdf',
        'matplotlib.backends.backend_ps',
        'matplotlib.backends.backend_svg',
        'matplotlib.backends.backend_template',
        'matplotlib.backends.backend_tkagg',
        'matplotlib.backends.backend_webagg',
        'matplotlib.backends.backend_wx',
        'matplotlib.backends.backend_wxagg',
        'matplotlib.backends.backend_gtk3agg',
        'matplotlib.backends.backend_gtk3cairo',
        'matplotlib.backends.backend_gtk4agg',
        'matplotlib.backends.backend_gtk4cairo',
        'matplotlib.backends.backend_qt5agg',
        'matplotlib.backends.backend_qt4agg',
        'matplotlib.backends.backend_cairo',
        'matplotlib.backends.backend_macosx',
        'matplotlib.backends.backend_nbagg',
        'matplotlib.backends.backend_pgf',
        'matplotlib.backends.backend_qt',
        'matplotlib.backends.qt_compat',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MathpixClone',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Use UPX compression (if available)
    upx_exclude=[
        'vcruntime140.dll',  # Don't compress Windows runtime DLLs
        'python*.dll',  # Don't compress Python DLLs
    ],
    runtime_tmpdir=None,
    console=False,  # No console window (GUI app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(spec_root / 'icon.ico') if (spec_root / 'icon.ico').exists() else None,  # Mathpix-style icon
)
