"""
Build script to create executable (.exe) from the Mathpix Clone application.

Usage:
    python build_exe.py

This will create a standalone executable in the 'dist' folder.
"""

import os

# Disable albumentations update check which hangs the build
os.environ["NO_ALBUMENTATIONS_UPDATE"] = "1"

import PyInstaller.__main__
import sys
import time
from pathlib import Path

def kill_process_by_name(process_name):
    """Try to kill a process by name (Windows only)."""
    try:
        import subprocess
        # Use taskkill to terminate the process
        subprocess.run(['taskkill', '/F', '/IM', process_name], 
                      capture_output=True, check=False)
        return True
    except Exception:
        return False

def ensure_exe_not_locked(exe_path):
    """Ensure the executable file is not locked before building."""
    if not exe_path.exists():
        return True
    
    print(f"Checking if {exe_path.name} is locked...")
    
    # Try to delete the file to check if it's locked
    try:
        # Rename first (safer than delete)
        temp_name = exe_path.with_suffix('.exe.old')
        if temp_name.exists():
            try:
                temp_name.unlink()
            except Exception:
                pass
        
        exe_path.rename(temp_name)
        temp_name.rename(exe_path)  # Rename back
        print(f"[OK] {exe_path.name} is not locked")
        return True
    except PermissionError:
        print(f"[WARN] {exe_path.name} is locked. Attempting to unlock...")
        
        # Try to kill the process
        if kill_process_by_name('Math Extractor.exe'):
            print("   Killed running Math Extractor.exe process")
            time.sleep(1)  # Wait a moment for the process to fully terminate
        else:
            print("   No running Math Extractor.exe process found")
        
        # Try again after killing process
        try:
            temp_name = exe_path.with_suffix('.exe.old')
            if temp_name.exists():
                try:
                    temp_name.unlink()
                except Exception:
                    pass
            
            exe_path.rename(temp_name)
            temp_name.rename(exe_path)
            print(f"[OK] {exe_path.name} is now unlocked")
            return True
        except PermissionError:
            print(f"[ERROR] {exe_path.name} is still locked!")
            print("\nPlease:")
            print("  1. Close any running Math Extractor.exe instances")
            print("  2. Close File Explorer windows showing the 'dist' folder")
            print("  3. Wait a few seconds for antivirus to release the file")
            print("  4. Or manually delete the file and try again")
            return False

def clean_artifacts(project_root):
    """Aggressively clean build artifacts and caches."""
    print("[CLEAN] Cleaning build artifacts...")
    import shutil
    
    dirs_to_clean = [
        project_root / 'build',
        project_root / 'dist',
    ]
    
    for d in dirs_to_clean:
        if d.exists():
            try:
                shutil.rmtree(d)
                print(f"   Deleted {d}")
            except Exception as e:
                print(f"   [WARN] Could not delete {d}: {e}")

    # Clean pycache
    print("[CLEAN] Cleaning __pycache__...")
    for p in project_root.rglob('__pycache__'):
        try:
            shutil.rmtree(p)
        except Exception:
            pass
    print("[DONE] Cleanup complete")

def build_exe():
    """Build the executable using PyInstaller with optimized spec file."""
    
    # Get the project root directory
    project_root = Path(__file__).parent
    
    # Aggressive clean first
    clean_artifacts(project_root)
    
    # Use the spec file for better control and size optimization
    # The spec file includes all exclusions and optimizations
    spec_file = project_root / 'MathpixClone.spec'
    
    if not spec_file.exists():
        print(f"[ERROR] Spec file not found: {spec_file}")
        print("Please ensure MathpixClone.spec exists in the project root")
        sys.exit(1)
    
    # Check if exe is locked before building
    # OneDir mode: dist/Math Extractor/Math Extractor.exe
    exe_path = project_root / 'dist' / 'Math Extractor' / 'Math Extractor.exe'
    if exe_path.exists():
        if not ensure_exe_not_locked(exe_path):
            print("\n" + "=" * 80)
            print("[ERROR] Cannot proceed with build - executable is locked")
            print("=" * 80)
            sys.exit(1)
    
    # PyInstaller arguments - use spec file
    args = [
        str(spec_file),  # Use spec file for optimized build
        '--clean',  # Clean build directories
        '--noconfirm',  # Overwrite output without asking
    ]
    
    print("=" * 80)
    print("Building Mathpix Clone Executable (Folder Mode)")
    print("=" * 80)
    print(f"Project root: {project_root}")
    print(f"Output will be in: {project_root / 'dist' / 'Math Extractor'}")
    print("=" * 80)
    
    try:
        PyInstaller.__main__.run(args)
        
        # DISABLED: Pandas is required by pix2tex at runtime
        # Previously this removed pandas to save space, but it breaks the application
        # # FORCE REMOVE PANDAS (Fixes ImportError: pytz/dateutil and saves 60MB)
        # # PyInstaller includes it despite 'excludes' because pytesseract imports it inside try/except.
        # # By deleting it, we force the ImportError which pytesseract handles gracefully.
        # pandas_dir = project_root / 'dist' / 'Math Extractor' / '_internal' / 'pandas'
        # if pandas_dir.exists():
        #     print(f"[OPTIMIZE] Removing pandas to fix dependencies and save space: {pandas_dir}")
        #     import shutil
        #     try:
        #         shutil.rmtree(pandas_dir)
        #         print("   [OK] Pandas removed.")
        #     except Exception as e:
        #         print(f"   [WARN] Failed to remove pandas: {e}")
        
        print("\n" + "=" * 80)
        print("[SUCCESS] Build completed successfully!")
        print(f"Executable location: {exe_path}")
        print("=" * 80)
    except PermissionError as e:
        print("\n" + "=" * 80)
        print(f"[ERROR] Build failed: Permission denied")
        print(f"Error: {e}")
        print("\nSolution:")
        print("  1. Close any running Math Extractor.exe instances")
        print("  2. Close File Explorer windows showing the 'dist' folder")
        print("  3. Wait a few seconds and try again")
        print("  4. Or manually delete dist/Math Extractor.exe and rebuild")
        print("=" * 80)
        sys.exit(1)
    except Exception as e:
        print("\n" + "=" * 80)
        print(f"[ERROR] Build failed: {e}")
        print("=" * 80)
        sys.exit(1)

    # Copy to installer/app
    # Copy to installer/app
    installer_app_dir = project_root / 'installer' / 'app'
    
    # Create directory if it doesn't exist
    if not installer_app_dir.exists():
        try:
            installer_app_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created installer directory: {installer_app_dir}")
        except Exception as e:
            print(f"[WARN] Failed to create installer directory: {e}")

    if installer_app_dir.exists():
        print(f"\nUpdating installer directory: {installer_app_dir}")
        try:
            import shutil
            # Remove everything except deps
            for item in installer_app_dir.iterdir():
                if item.name != 'deps':
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
            
            # Copy new build files
            build_output = project_root / 'dist' / 'Math Extractor'
            if build_output.exists():
                for item in build_output.iterdir():
                    if item.is_dir():
                        shutil.copytree(item, installer_app_dir / item.name)
                    else:
                        shutil.copy2(item, installer_app_dir)
                print("[SUCCESS] Installer directory updated successfully!")
            else:
                print("[WARN] Build output not found, cannot update installer dir.")
        except Exception as e:
            print(f"[WARN] Failed to update installer directory: {e}")


if __name__ == "__main__":
    build_exe()

