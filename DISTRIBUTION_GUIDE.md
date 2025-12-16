# Distribution Guide - Using MathpixClone.exe on Other Systems

## ✅ What Works Out of the Box

After building the executable, you can:

1. **Copy `MathpixClone.exe` to ANY Windows 10/11 computer**
2. **Run it directly** - No Python installation needed
3. **All core features work**:
   - ✅ PDF loading and viewing
   - ✅ Image OCR (pix2tex for math formulas)
   - ✅ LaTeX to MathML conversion
   - ✅ MathML export
   - ✅ UI (PyQt6 interface)
   - ✅ Settings and configuration
   - ✅ Notes and snippets

## 📋 System Requirements

### Minimum Requirements:
- **Windows 10 or Windows 11** (64-bit)
- **4 GB RAM** (8 GB recommended)
- **500 MB free disk space** (for executable + data)
- **No Python installation required!**
- **No dependencies to install!**

### Optional (for better OCR):
- **Tesseract OCR** (optional, for text fallback)
  - Only needed if pix2tex fails
  - Can be installed separately if needed
  - Not required for math OCR (pix2tex handles that)

## 🚀 How to Distribute

### Method 1: Single File (Easiest)
1. Build the executable: `python build_exe.py`
2. Copy `dist\MathpixClone.exe` to a USB drive or share it
3. On the target computer, just double-click to run!

### Method 2: Folder Distribution (Faster Startup)
If you want faster startup times:
1. Build with `--onedir` instead of `--onefile`
2. Copy the entire `dist\MathpixClone\` folder
3. Run `MathpixClone.exe` from that folder

## ⚠️ Important Notes

### What's Included:
- ✅ Python interpreter
- ✅ All Python libraries (PyQt6, FastAPI, etc.)
- ✅ ML models (pix2tex models)
- ✅ All dependencies
- ✅ Data directory structure

### What Might Need Setup:

1. **Tesseract OCR** (Optional - only for text fallback):
   - If you want text OCR as fallback
   - Users can install Tesseract separately
   - Or configure path in Settings if already installed
   - **Not required** - pix2tex handles math OCR

2. **OpenAI API Key** (Optional - for AI features):
   - If using OpenAI for LaTeX repair
   - Users need to add their API key in Settings
   - Works without it (uses deterministic conversion)

3. **Data Directory**:
   - Created automatically on first run
   - Stores uploads, notes, settings
   - Located in user's app data folder

## 🎯 Features That Work

### ✅ Fully Functional:
- PDF loading and rendering
- Math formula OCR (pix2tex)
- LaTeX to MathML conversion
- MathML export
- Image processing
- UI interface
- Settings management
- Notes and snippets

### ⚙️ Configurable:
- Tesseract path (if installed)
- OpenAI API key (if using AI features)
- Output directories
- UI preferences

## 📦 Distribution Checklist

Before distributing:

- [ ] Test the executable on a clean Windows system (without Python)
- [ ] Verify all features work
- [ ] Check file size (should be 200-500 MB)
- [ ] Create a README with basic instructions
- [ ] Optionally create an installer (using Inno Setup or NSIS)

## 🔧 Troubleshooting on Target Systems

### Issue: "Missing DLL" errors
**Solution**: Install Visual C++ Redistributable:
- Download from Microsoft
- Install vcredist_x64.exe

### Issue: Slow startup
**Solution**: Normal for first run (extraction takes time)
- Subsequent runs are faster
- Consider using `--onedir` build for faster startup

### Issue: OCR not working
**Solution**: 
- Check if pix2tex models loaded (check logs)
- Models are included in executable, should work automatically

### Issue: Can't save files
**Solution**: 
- Check write permissions
- App creates data directory automatically
- May need admin rights for some locations

## 💡 Best Practices

1. **Test First**: Always test on a clean system before distributing
2. **Include README**: Provide basic usage instructions
3. **Version Info**: Consider adding version number to executable
4. **Updates**: Users can replace the .exe file to update
5. **Portable Mode**: Executable is portable - can run from USB drive

## 🎉 Summary

**YES!** The executable is **fully portable** and **self-contained**:

- ✅ Works on any Windows 10/11 system
- ✅ No installation required
- ✅ All features included
- ✅ No dependencies needed
- ✅ Just copy and run!

The executable includes everything needed to run the application, making it perfect for distribution to other systems!

