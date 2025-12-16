"""
Build script to create executable (.exe) from the Mathpix Clone application.

Usage:
    python build_exe.py

This will create a standalone executable in the 'dist' folder.
"""

import PyInstaller.__main__
import sys
from pathlib import Path

def build_exe():
    """Build the executable using PyInstaller with optimized spec file."""
    
    # Get the project root directory
    project_root = Path(__file__).parent
    
    # Use the spec file for better control and size optimization
    # The spec file includes all exclusions and optimizations
    spec_file = project_root / 'MathpixClone.spec'
    
    if not spec_file.exists():
        print(f"❌ Spec file not found: {spec_file}")
        print("Please ensure MathpixClone.spec exists in the project root")
        sys.exit(1)
    
    # PyInstaller arguments - use spec file
    args = [
        str(spec_file),  # Use spec file for optimized build
        '--clean',  # Clean build directories
        '--noconfirm',  # Overwrite output without asking
    ]
    
    print("=" * 80)
    print("Building Mathpix Clone Executable")
    print("=" * 80)
    print(f"Project root: {project_root}")
    print(f"Output will be in: {project_root / 'dist'}")
    print("=" * 80)
    
    try:
        PyInstaller.__main__.run(args)
        print("\n" + "=" * 80)
        print("✅ Build completed successfully!")
        print(f"Executable location: {project_root / 'dist' / 'MathpixClone.exe'}")
        print("=" * 80)
    except Exception as e:
        print("\n" + "=" * 80)
        print(f"❌ Build failed: {e}")
        print("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    build_exe()

