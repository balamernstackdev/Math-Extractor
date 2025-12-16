# Building Executable (.exe) for Mathpix Clone

This guide explains how to create a standalone Windows executable (.exe) file from the Mathpix Clone application.

## Prerequisites

1. **Python 3.8+** installed on your system
2. **All dependencies** installed (from `requirements.txt`)
3. **PyInstaller** installed:
   ```bash
   pip install pyinstaller
   ```

## Quick Start

### Option 1: Using the Build Script (Recommended)

1. Open a terminal/command prompt in the project directory
2. Run:
   ```bash
   python build_exe.py
   ```

3. The executable will be created in the `dist` folder:
   ```
   dist/MathpixClone.exe
   ```

### Option 2: Using PyInstaller Directly

1. Open a terminal/command prompt in the project directory
2. Run:
   ```bash
   pyinstaller MathpixClone.spec
   ```

3. The executable will be created in the `dist` folder

### Option 3: Using Command Line (Simple)

```bash
pyinstaller --name=MathpixClone --onefile --windowed --add-data="data;data" app.py
```

## Important Notes

### File Size
The executable will be **large** (100-500 MB) because it includes:
- Python interpreter
- All dependencies (PyQt6, FastAPI, pix2tex, etc.)
- ML models (if pix2tex includes them)
- All required libraries

### First Run
The first time you run the executable, it may take a few seconds to extract and start.

### Data Files
The executable includes the `data` directory, so all your uploads, notes, and settings will be preserved.

### Dependencies
Make sure all dependencies are installed before building:
```bash
pip install -r requirements.txt
pip install pyinstaller
```

## Troubleshooting

### Issue: "Module not found" errors
**Solution**: Add the missing module to `hiddenimports` in `MathpixClone.spec` or use `--hidden-import` flag.

### Issue: Large file size
**Solution**: 
- Use `--exclude-module` to exclude unused modules
- Consider using `--onedir` instead of `--onefile` (creates a folder with multiple files)

### Issue: Missing data files
**Solution**: Add them to the `datas` list in `MathpixClone.spec`:
```python
datas=[
    ('data', 'data'),
    ('path/to/file', 'destination'),
],
```

### Issue: ML models not loading
**Solution**: 
- Ensure pix2tex models are included using `--collect-all=pix2tex`
- Check if models need to be downloaded separately

### Issue: Slow startup
**Solution**: 
- Use `--onedir` instead of `--onefile` (faster startup, but multiple files)
- The first run is always slower due to extraction

## Distribution

### Single File Distribution
The `--onefile` option creates a single `.exe` file that you can distribute. Users can run it directly without installing Python.

### Folder Distribution (Alternative)
If you prefer a folder with multiple files (faster startup):
```bash
pyinstaller --name=MathpixClone --onedir --windowed --add-data="data;data" app.py
```

This creates a `dist/MathpixClone/` folder with:
- `MathpixClone.exe` (main executable)
- Supporting DLLs and libraries
- Data files

### Adding an Icon
1. Create or download an `.ico` file
2. Update `MathpixClone.spec`:
   ```python
   icon='icon.ico'
   ```
3. Or use command line:
   ```bash
   --icon=icon.ico
   ```

## Testing the Executable

1. Navigate to the `dist` folder
2. Run `MathpixClone.exe`
3. Test all features:
   - PDF loading
   - Image OCR
   - LaTeX conversion
   - MathML export
   - Settings

## System Requirements

The executable will work on:
- **Windows 10/11** (64-bit)
- Systems without Python installed
- Systems without any dependencies installed

**Note**: The executable is platform-specific. You need to build it on Windows to create a Windows `.exe` file.

## Advanced Options

### Reduce File Size
```bash
pyinstaller --name=MathpixClone --onefile --windowed \
  --exclude-module=matplotlib.tests \
  --exclude-module=numpy.tests \
  --exclude-module=pytest \
  --add-data="data;data" \
  app.py
```

### Include Console for Debugging
Remove `--windowed` or set `console=True` in the spec file to see console output for debugging.

### Custom Version Info
Create a `version_info.txt` file and use:
```bash
--version-file=version_info.txt
```

## Support

If you encounter issues:
1. Check PyInstaller documentation: https://pyinstaller.org/
2. Review the build output for warnings
3. Test with `--onedir` first (easier to debug)
4. Check if all dependencies are properly included

