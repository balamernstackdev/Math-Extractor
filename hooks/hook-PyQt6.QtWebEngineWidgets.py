# # """
# # PyInstaller hook for PyQt6.QtWebEngine
# # Ensures all QtWebEngine resources are bundled.

# # CRITICAL: This hook is essential for PreviewPanel MathML rendering.
# # Without it, the WebEngine widget will fail to load.
# # """
# # from PyInstaller.utils.hooks import (
# #     collect_data_files, 
# #     collect_dynamic_libs, 
# #     get_pyqt_qt_binaries,
# #     collect_submodules
# # )

# # # Collect QtWebEngine data files (translations, resources, etc.)
# # datas = collect_data_files('PyQt6.QtWebEngine', includes=['**/*'])
# # datas.extend(collect_data_files('PyQt6.QtWebEngineCore', includes=['**/*']))

# # # Collect QtWebEngine binaries (DLLs)
# # binaries = collect_dynamic_libs('PyQt6.QtWebEngine')
# # binaries.extend(collect_dynamic_libs('PyQt6.QtWebEngineCore'))

# # # Collect Qt binaries (WebEngine depends on these)
# # qt_binaries = get_pyqt_qt_binaries('PyQt6')
# # binaries.extend(qt_binaries)

# # # Collect QtWebEngine submodules (ensure all are included)
# # hiddenimports = collect_submodules('PyQt6.QtWebEngine')
# # hiddenimports.extend(collect_submodules('PyQt6.QtWebEngineCore'))

# # # Add critical WebEngine submodules explicitly
# # critical_imports = [
# #     'PyQt6.QtWebEngine',
# #     'PyQt6.QtWebEngineCore',
# #     'PyQt6.QtWebEngineWidgets',
# #     'PyQt6.QtWebEngineCore.QWebEngineUrlRequestInterceptor',
# #     'PyQt6.QtWebEngineCore.QWebEngineUrlSchemeHandler',
# #     'PyQt6.QtWebEngineCore.QWebEngineSettings',
# #     'PyQt6.QtWebEngineCore.QWebEngineProfile',
# #     'PyQt6.QtWebEngineCore.QWebEnginePage',
# #     'PyQt6.QtWebEngineWidgets.QWebEngineView',
# # ]

# # for imp in critical_imports:
# #     if imp not in hiddenimports:
# #         hiddenimports.append(imp)

# """
# PyInstaller hook for PyQt6 QtWebEngine (PyQt6 6.x)

# This hook ensures QtWebEngine widgets work correctly
# inside a PyInstaller-built executable.

# Compatible with:
# - Python 3.11
# - PyInstaller 6.x
# - PyQt6 / PyQt6-WebEngine 6.7.x
# """

# from PyInstaller.utils.hooks import (
#     collect_data_files,
#     collect_dynamic_libs,
#     collect_submodules,
# )

# # ------------------------------------------------------------
# # DATA FILES
# # ------------------------------------------------------------
# # Collect QtWebEngineCore resources (translations, resources)
# datas = []
# datas += collect_data_files(
#     'PyQt6.QtWebEngineCore',
#     includes=['**/*'],
# )

# # ------------------------------------------------------------
# # BINARIES (DLLs)
# # ------------------------------------------------------------
# binaries = []
# binaries += collect_dynamic_libs('PyQt6.QtWebEngineCore')
# binaries += collect_dynamic_libs('PyQt6.QtWebEngineWidgets')

# # ------------------------------------------------------------
# # HIDDEN IMPORTS (CRITICAL)
# # ------------------------------------------------------------
# hiddenimports = []

# # Core WebEngine modules
# hiddenimports += collect_submodules('PyQt6.QtWebEngineCore')
# hiddenimports += collect_submodules('PyQt6.QtWebEngineWidgets')

# # Explicit imports required at runtime
# hiddenimports += [
#     'PyQt6.QtWebEngineCore',
#     'PyQt6.QtWebEngineWidgets',
#     'PyQt6.QtWebEngineWidgets.QWebEngineView',
#     'PyQt6.QtWebEngineCore.QWebEnginePage',
#     'PyQt6.QtWebEngineCore.QWebEngineProfile',
#     'PyQt6.QtWebEngineCore.QWebEngineSettings',
#     'PyQt6.QtWebEngineCore.QWebEngineUrlSchemeHandler',
#     'PyQt6.QtWebEngineCore.QWebEngineUrlRequestInterceptor',
#     'PyQt6.QtWebChannel',
# ]


"""
PyInstaller hook for PyQt6 QtWebEngine

Compatible with:
- Python 3.11
- PyInstaller 6.x
- PyQt6 / PyQt6-WebEngine 6.7.x
"""

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

# ------------------------------------------------------------
# DATA FILES (Qt resources, translations)
# ------------------------------------------------------------
datas = []
datas += collect_data_files(
    'PyQt6.QtWebEngineCore',
    includes=['**/*'],
)

# ------------------------------------------------------------
# BINARIES (DLLs)
# ------------------------------------------------------------
binaries = []
binaries += collect_dynamic_libs('PyQt6.QtWebEngineCore')
binaries += collect_dynamic_libs('PyQt6.QtWebEngineWidgets')

# ------------------------------------------------------------
# HIDDEN IMPORTS (MODULES ONLY)
# ------------------------------------------------------------
hiddenimports = [
    'PyQt6.QtWebEngine',
    'PyQt6.QtWebEngineCore',
    'PyQt6.QtWebEngineWidgets',
    'PyQt6.QtWebChannel',
    'PyQt6.QtNetwork',
    'PyQt6.QtPrintSupport',
    'PyQt6.QtQuick',
    'PyQt6.QtQuickWidgets',
]

# Ensure all WebEngine submodules are included
hiddenimports += collect_submodules('PyQt6.QtWebEngineCore')
hiddenimports += collect_submodules('PyQt6.QtWebEngineWidgets')
