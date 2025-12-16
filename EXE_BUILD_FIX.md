# EXE Build Fix - Complete Solution

## Root Cause Analysis

The Windows .exe build was failing because:

1. **QtWebEngine was EXCLUDED** from the build, but PreviewPanel requires it for MathML rendering
2. **Missing hidden imports** for:
   - `latex2mathml` and its submodules
   - MathML recovery modules (dynamic imports)
   - XML/HTML parsing modules
   - `httpx` (required by OpenAI client)
3. **QtWebEngine resources not bundled** (DLLs, translations, etc.)
4. **MathJax loaded from CDN** - fails offline in EXE
5. **No runtime hooks** for proper path resolution in bundled environment

## Fixes Applied

### 1. Updated `MathpixClone.spec`

#### Added QtWebEngine to hidden imports:
```python
'PyQt6.QtWebEngineWidgets',  # REQUIRED for PreviewPanel MathML rendering
'PyQt6.QtWebEngineCore',  # REQUIRED for WebEngine
'PyQt6.QtWebEngine',  # REQUIRED for WebEngine resources
```

#### Removed QtWebEngine from excludes:
- Commented out exclusion of `PyQt6.QtWebEngine` and `PyQt6.QtWebEngineWidgets`

#### Added missing hidden imports:
- `latex2mathml.converter`, `latex2mathml.parser`, `latex2mathml.symbols`
- All MathML recovery modules (with full paths)
- `xml.etree.ElementTree`, `xml.etree.cElementTree`
- `html`, `html.parser`, `html.entities`
- `httpx` (for OpenAI client)

#### Added QtWebEngine resource collection:
- Collects QtWebEngine data files and binaries
- Includes QtWebEngineCore resources

### 2. Created Runtime Hook (`hooks/pyi_rth_pyqt6.py`)

Ensures proper path resolution in bundled executable:
- Sets `QTWEBENGINEPROCESS_PATH` environment variable
- Adds PyQt6 DLL paths to `PATH`
- Sets `QT_PLUGIN_PATH` for Qt plugins

### 3. Created QtWebEngine Hook (`hooks/hook-PyQt6.QtWebEngine.py`)

Collects all QtWebEngine resources:
- Data files from `PyQt6.QtWebEngine` and `PyQt6.QtWebEngineCore`
- Dynamic libraries (DLLs)
- Qt binaries required by WebEngine

### 4. Updated PreviewPanel (`ui/preview_panel.py`)

#### Offline MathJax Support:
- Detects if running in PyInstaller bundle (`sys.frozen`)
- Tries to load local MathJax from bundle (`mathjax/tex-mml-chtml.js`)
- Falls back to CDN if local not found (with warning)
- Applied to both `_render_mathml()` and `_render_tex()` methods

## Build Command

```bash
python build_exe.py
```

Or directly:
```bash
pyinstaller MathpixClone.spec --clean --noconfirm
```

## Verification Checklist

After building, verify:

- [ ] EXE launches without errors
- [ ] PreviewPanel renders MathML equations correctly
- [ ] MathML generation works (not falling back to `<mtext>`)
- [ ] OCR → LaTeX → MathML pipeline works
- [ ] ULTRA MathML recovery triggers correctly
- [ ] No "Rendering error" in PreviewPanel
- [ ] Works offline (no internet required)

## Optional: Bundle MathJax Locally

For true offline operation, you can bundle MathJax:

1. Download MathJax 3.x:
   ```bash
   npm install mathjax@3
   ```

2. Copy to project:
   ```bash
   mkdir -p mathjax
   cp -r node_modules/mathjax/es5 mathjax/
   ```

3. Update `MathpixClone.spec` to include MathJax:
   ```python
   datas=[
       ...
       *([(str(spec_root / 'mathjax'), 'mathjax')] if (spec_root / 'mathjax').exists() else []),
   ],
   ```

## Expected Results

- **MathML Generation**: Works correctly, no `<mtext>` fallbacks
- **PreviewPanel**: Renders equations correctly using QtWebEngine
- **Offline Operation**: Works without internet (if MathJax is bundled)
- **All Features**: OCR, LaTeX conversion, MathML recovery all functional

## Troubleshooting

If issues persist:

1. **Check build logs** for missing imports:
   ```bash
   pyinstaller MathpixClone.spec --log-level=DEBUG
   ```

2. **Verify QtWebEngine is bundled**:
   - Check `dist/MathpixClone/PyQt6/Qt6/bin/` for WebEngine DLLs
   - Check `dist/MathpixClone/PyQt6/QtWebEngine*` directories

3. **Test PreviewPanel in EXE**:
   - Launch EXE
   - Extract a formula
   - Check if MathML renders (not "Rendering error")

4. **Check console output** (if console=True in spec):
   - Look for import errors
   - Check for QtWebEngine initialization errors

## Files Modified

1. `MathpixClone.spec` - Complete rebuild with all fixes
2. `hooks/pyi_rth_pyqt6.py` - Runtime hook (NEW)
3. `hooks/hook-PyQt6.QtWebEngine.py` - QtWebEngine hook (NEW)
4. `ui/preview_panel.py` - Offline MathJax support

## Next Steps

1. Rebuild the EXE using the updated spec file
2. Test all features in the EXE
3. If MathJax CDN fails offline, bundle MathJax locally (see Optional section above)

