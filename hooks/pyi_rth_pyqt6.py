"""
PyInstaller runtime hook for PyQt6.
Ensures proper path resolution in bundled executable.

CRITICAL: This hook runs BEFORE any application code, so we can set
Qt attributes here before QApplication is created.

IMPORTANT: We must set up PATH and DLL resolution BEFORE importing Qt,
otherwise Qt modules won't be able to find their dependencies.
"""
import sys
import os
from pathlib import Path

# Fix for PyInstaller bundled executable
if getattr(sys, 'frozen', False):
    # Running in PyInstaller bundle
    base_path = Path(sys._MEIPASS)
    
    # CRITICAL: Set up DLL directories FIRST, before any Qt imports
    # PyInstaller may place DLLs in multiple locations:
    # 1. PyQt6/Qt6/bin/ (standard location)
    # 2. Root of _MEIPASS (where PyInstaller places collected binaries)
    # 3. PyQt6/ (where PyQt6 modules are)
    
    dll_paths_to_add = []
    
    # Standard PyQt6 bin directory
    pyqt6_bin = base_path / 'PyQt6' / 'Qt6' / 'bin'
    if pyqt6_bin.exists():
        dll_paths_to_add.append(pyqt6_bin)
    
    # Root of _MEIPASS (PyInstaller places collected binaries here)
    if base_path.exists():
        dll_paths_to_add.append(base_path)
    
    # PyQt6 root (modules are here, DLLs might be too)
    pyqt6_root = base_path / 'PyQt6'
    if pyqt6_root.exists():
        dll_paths_to_add.append(pyqt6_root)
    
    # Add all found DLL directories
    path_added = False
    for dll_path in dll_paths_to_add:
        if dll_path.exists():
            # Use os.add_dll_directory() for Windows (Python 3.8+)
            # This is more reliable than PATH for DLL resolution
            try:
                os.add_dll_directory(str(dll_path))
                path_added = True
                try:
                    if hasattr(sys, 'stderr'):
                        print(f"[RUNTIME_HOOK] Added DLL directory: {dll_path}", file=sys.stderr)
                except Exception:
                    pass
            except AttributeError:
                # Python < 3.8, fall back to PATH
                current_path = os.environ.get('PATH', '')
                os.environ['PATH'] = str(dll_path) + os.pathsep + current_path
                path_added = True
            except OSError:
                # Directory doesn't exist or can't be added, skip
                pass
            
            # Also add to PATH as backup (some DLLs might use PATH)
            current_path = os.environ.get('PATH', '')
            if str(dll_path) not in current_path:
                os.environ['PATH'] = str(dll_path) + os.pathsep + current_path
                path_added = True
    
    if not path_added:
        try:
            if hasattr(sys, 'stderr'):
                print(f"[RUNTIME_HOOK] WARNING: No DLL directories found! Checked: {dll_paths_to_add}", file=sys.stderr)
        except Exception:
            pass
    
    # Ensure Qt can find plugins
    qt_plugin_path = base_path / 'PyQt6' / 'Qt6' / 'plugins'
    if qt_plugin_path.exists():
        os.environ.setdefault('QT_PLUGIN_PATH', str(qt_plugin_path))
    
    # Ensure QtWebEngine can find its resources
    # Try multiple possible paths for QtWebEngineProcess
    possible_paths = [
        base_path / 'PyQt6' / 'Qt6' / 'bin' / 'QtWebEngineProcess.exe',
        base_path / 'PyQt6' / 'Qt6' / 'libexec' / 'QtWebEngineProcess.exe',
        base_path / 'QtWebEngineProcess.exe',
    ]
    
    qtwep_found = False
    for qtwep_path in possible_paths:
        if qtwep_path.exists():
            os.environ.setdefault('QTWEBENGINEPROCESS_PATH', str(qtwep_path))
            qtwep_found = True
            try:
                if hasattr(sys, 'stderr'):
                    print(f"[RUNTIME_HOOK] Found QtWebEngineProcess: {qtwep_path}", file=sys.stderr)
            except Exception:
                pass
            break
    
    if not qtwep_found:
        # Not found in standard paths - will be handled by app.py/main_window.py
        # Don't try to import QtWebEngineCore here as it requires DLLs to be loaded
        try:
            if hasattr(sys, 'stderr'):
                print("[RUNTIME_HOOK] Warning: QtWebEngineProcess.exe not found in standard paths", file=sys.stderr)
        except Exception:
            pass
    
    # Log that we're setting up DLL paths
    try:
        if hasattr(sys, 'stderr'):
            print(f"[RUNTIME_HOOK] Setting up Qt DLL paths. Base: {base_path}", file=sys.stderr)
            print(f"[RUNTIME_HOOK] Added {len(dll_paths_to_add)} DLL directories to search path", file=sys.stderr)
            for dll_path in dll_paths_to_add:
                if dll_path.exists():
                    # Check if Qt DLLs exist
                    qt_dlls = list(dll_path.glob('Qt6*.dll'))
                    if qt_dlls:
                        print(f"[RUNTIME_HOOK] Found {len(qt_dlls)} Qt DLLs in: {dll_path}", file=sys.stderr)
    except Exception:
        pass
    
    # NOW we can safely import Qt and set attributes
    # DLL directories are set, DLLs should be resolvable
    try:
        # Import QtCore first to ensure DLLs load
        # This is the critical test - if this fails, DLLs aren't found
        from PyQt6 import QtCore
        # Verify we can access Qt types
        if hasattr(QtCore, 'Qt') and hasattr(QtCore.Qt, 'ApplicationAttribute'):
            # Set the attribute that allows WebEngine to work
            # This must be done before QApplication is created
            QtCore.QCoreApplication.setAttribute(
                QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts, 
                True
            )
            # Log success
            try:
                if hasattr(sys, 'stderr'):
                    print("[RUNTIME_HOOK] ✅ Successfully imported QtCore and set AA_ShareOpenGLContexts", file=sys.stderr)
            except Exception:
                pass
        else:
            # Qt structure not as expected
            try:
                if hasattr(sys, 'stderr'):
                    print("[RUNTIME_HOOK] ⚠️  Warning: Qt structure unexpected", file=sys.stderr)
            except Exception:
                pass
    except ImportError as e:
        # Qt not available - this is CRITICAL
        try:
            if hasattr(sys, 'stderr'):
                print(f"[RUNTIME_HOOK] ❌ CRITICAL ERROR: Cannot import QtCore: {e}", file=sys.stderr)
                print(f"[RUNTIME_HOOK] Checked DLL directories: {dll_paths_to_add}", file=sys.stderr)
                # List what DLLs we found
                for dll_path in dll_paths_to_add:
                    if dll_path.exists():
                        qt_dlls = list(dll_path.glob('Qt6*.dll'))
                        if qt_dlls:
                            print(f"[RUNTIME_HOOK] Found DLLs in {dll_path}: {[d.name for d in qt_dlls[:5]]}", file=sys.stderr)
        except Exception:
            pass
    except Exception as e:
        # Any other error - log it
        try:
            if hasattr(sys, 'stderr'):
                print(f"[RUNTIME_HOOK] ❌ ERROR: Failed to set Qt attribute: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
        except Exception:
            pass

