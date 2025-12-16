# Quick Build Guide - Create .exe File

## Step 1: Install PyInstaller
```bash
pip install pyinstaller
```

## Step 2: Build the Executable

### Simple Method (Recommended):
```bash
python build_exe.py
```

### Alternative Method:
```bash
pyinstaller MathpixClone.spec
```

## Step 3: Find Your Executable

After building, your executable will be in:
```
dist/MathpixClone.exe
```

## That's It! 🎉

You can now:
- Copy `MathpixClone.exe` to any Windows computer
- Run it without installing Python or any dependencies
- Share it with others

## File Size Warning

The executable will be **large** (100-500 MB) because it includes:
- Python interpreter
- All libraries (PyQt6, FastAPI, pix2tex, etc.)
- ML models

This is normal for Python applications with ML dependencies.

## Troubleshooting

If you get errors, see `BUILD_EXE_INSTRUCTIONS.md` for detailed troubleshooting.

