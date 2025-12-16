# Fixing Formula Extraction in Executable

## Problem
After building the executable (.exe), formula extraction is not working:
- OCR produces corrupted LaTeX
- MathML shows "No MathML available"
- Rendered equation is corrupted

## Root Cause
**pix2tex models are not included in the executable** or **cannot be found at runtime**.

pix2tex downloads models to `~/.cache/pix2tex` on first use. When running as an executable:
1. Models might not be bundled
2. Path resolution might fail
3. Cache directory might not be accessible

## Solution Applied

### 1. Updated `MathpixClone.spec`
- Added `collect_all('pix2tex')` to collect pix2tex data files
- Included pix2tex cache directory if it exists
- Added pix2tex hidden imports
- Created custom hook for pix2tex

### 2. Created Custom Hook (`hooks/hook-pix2tex.py`)
- Collects pix2tex data files automatically
- Includes model files from cache if available

### 3. Updated `image_to_latex.py`
- Added path resolution for PyInstaller executables
- Handles `sys._MEIPASS` (temporary extraction directory)
- Sets environment variables for pix2tex cache
- Better error logging

## How to Fix

### Step 1: Download Models First (Before Building)
Run the application normally (not as executable) to download pix2tex models:
```bash
python app.py
# Select a formula region - this will download models to ~/.cache/pix2tex
```

### Step 2: Rebuild Executable
```bash
python build_exe.py
```

The build will now include:
- pix2tex Python modules
- pix2tex data files
- Downloaded models from cache (if available)

### Step 3: Test the Executable
1. Run `dist\MathpixClone.exe`
2. Upload a PDF
3. Select a formula region
4. Check if OCR works correctly

## Alternative: Bundle Models Manually

If models are still not found, you can manually copy them:

1. **Find models:**
   ```bash
   # Windows
   dir %USERPROFILE%\.cache\pix2tex
   
   # Linux/Mac
   ls ~/.cache/pix2tex
   ```

2. **Copy to project:**
   ```bash
   # Create models directory in project
   mkdir -p models/pix2tex
   
   # Copy models
   cp -r ~/.cache/pix2tex/* models/pix2tex/
   ```

3. **Update spec file** to include models:
   ```python
   datas=[
       *([(str(spec_root / 'models' / 'pix2tex'), '.cache/pix2tex')] 
         if (spec_root / 'models' / 'pix2tex').exists() else []),
   ]
   ```

## Troubleshooting

### Issue: "pix2tex not available" error
**Solution:** Ensure pix2tex is installed before building:
```bash
pip install pix2tex[api]
```

### Issue: Models still not found
**Solution:** Check logs for pix2tex initialization errors:
- Look for `[pix2tex]` log messages
- Check if cache directory is accessible
- Verify models are included in build

### Issue: Corrupted LaTeX output
**Solution:** This might be a different issue:
- Check if pix2tex is actually running (look for "Using pix2tex for math OCR" in logs)
- Verify image quality (pix2tex needs clear images)
- Check if strict pipeline is processing LaTeX correctly

## Verification

After rebuilding, check:
1. ✅ Executable size includes models (~800MB+)
2. ✅ Logs show "Math OCR (pix2tex) initialized successfully"
3. ✅ Formula extraction produces valid LaTeX
4. ✅ MathML is generated correctly

## Notes

- **First run**: Models might need to be downloaded on first use (if not bundled)
- **Cache location**: Models are stored in user's cache directory
- **Size impact**: Including models increases executable size by ~50-100MB
- **Performance**: Models are loaded once at startup

