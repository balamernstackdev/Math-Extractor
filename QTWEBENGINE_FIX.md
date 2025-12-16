# QtWebEngine Initialization Fix

## Problem
The executable was showing this error:
```
QtWebEngine not available.
Error: QtWebEngineWidgets must be imported or Qt.AA_ShareOpenGLContexts must be set before a QCoreApplication instance is created
```

## Root Cause
QtWebEngine requires either:
1. `QtWebEngineWidgets` to be imported BEFORE any `QApplication` is created, OR
2. `Qt.AA_ShareOpenGLContexts` attribute to be set BEFORE any `QApplication` is created

The issue was that `QApplication` was being created in `app.py` (for IP check dialog) and `main_window.py` (for main UI) BEFORE WebEngine was properly initialized.

## Solution

### 1. Runtime Hook Fix (CRITICAL)
**File**: `hooks/pyi_rth_pyqt6.py`

Added attribute setting at the very top of the runtime hook, which runs BEFORE any application code:
```python
# CRITICAL: Set Qt attribute for WebEngine BEFORE any QApplication is created
try:
    from PyQt6.QtCore import QCoreApplication, Qt
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
except (ImportError, AttributeError):
    pass
```

This ensures the attribute is set before ANY QApplication instance is created.

### 2. Early Import in app.py
**File**: `app.py`

Added WebEngine import at the very top, before any Qt code:
```python
# CRITICAL: Import QtWebEngineWidgets BEFORE any QApplication is created
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
    from PyQt6.QtWebEngineCore import QWebEngineCore  # noqa: F401
except ImportError:
    pass
```

### 3. Attribute Setting Before QApplication Creation
**Files**: `app.py` and `ui/main_window.py`

Added attribute setting right before creating QApplication as a backup:
```python
# CRITICAL: Set attribute before creating QApplication
QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
app = QtWidgets.QApplication(sys.argv)
```

## Files Modified

1. **`hooks/pyi_rth_pyqt6.py`**
   - Added attribute setting at the top (runs first)
   - This is the PRIMARY fix

2. **`app.py`**
   - Added WebEngine import at top
   - Added attribute setting before QApplication creation in IP check

3. **`ui/main_window.py`**
   - Added attribute setting before QApplication creation in `run_qt_app()`

## Verification

After rebuilding the executable, the PreviewPanel should:
- ✅ Load QtWebEngine without errors
- ✅ Render MathML equations properly
- ✅ Display "Rendered Equation" section correctly

## Build Instructions

1. Rebuild the executable:
   ```bash
   python build_exe.py
   ```

2. Test the executable:
   - Launch the app
   - Upload a PDF or image
   - Check that the "Rendered Equation" section displays properly
   - Verify no WebEngine errors in the UI

## Why This Works

The runtime hook (`pyi_rth_pyqt6.py`) is executed by PyInstaller BEFORE any of your application code runs. By setting the attribute there, we ensure it's set before:
- Any imports that might create QApplication
- Any code in `app.py` that creates QApplication
- Any code in `main_window.py` that creates QApplication

This is the most reliable way to ensure WebEngine initialization works correctly in a PyInstaller bundle.
