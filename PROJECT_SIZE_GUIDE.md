# Project Size Reduction Guide

## 🔍 **Why Is Your Project So Large?**

Your Python project can be large due to several factors:

### **Common Large Items:**

1. **ML Models & Dependencies** (~500MB - 2GB)
   - PyTorch (torch) - ~500MB-1GB
   - Transformers library - ~200-500MB
   - pix2tex models - ~50-200MB
   - CUDA libraries (if installed)

2. **Build Artifacts** (~200-500MB)
   - `build/` - PyInstaller temporary files
   - `dist/` - Built executable
   - `__pycache__/` - Python bytecode cache

3. **User Data** (Variable)
   - `data/uploads/` - Uploaded images (195 PNG files found!)
   - `data/mathml/` - Generated MathML files
   - Log files

4. **Framework Dependencies** (~100-300MB)
   - PyQt6 + QtWebEngine - ~200MB
   - NumPy, OpenCV, PIL - ~50-100MB
   - FastAPI, Uvicorn - ~20-30MB

5. **Virtual Environment** (~500MB - 2GB)
   - `.venv/` or `venv/` - All installed packages

---

## 📊 **Size Breakdown**

### **Typical Sizes:**

| Component | Size | Can Remove? |
|-----------|------|-------------|
| **Virtual Environment** | 500MB - 2GB | ✅ Yes (use .gitignore) |
| **Build Artifacts** | 200-500MB | ✅ Yes (use .gitignore) |
| **User Data** | Variable | ✅ Yes (use .gitignore) |
| **PyTorch** | 500MB-1GB | ⚠️ Only if not needed |
| **Transformers** | 200-500MB | ⚠️ Only if not needed |
| **PyQt6** | 100-200MB | ❌ No (needed for GUI) |
| **Source Code** | 5-10MB | ❌ No (needed) |

---

## 🎯 **Quick Fixes to Reduce Size**

### **1. Update .gitignore (CRITICAL!)**

Add these to `.gitignore` to exclude large files from Git:

```gitignore
# Python virtual environment
.venv/
venv/
env/
ENV/

# Python cache
__pycache__/
*.pyc
*.pyo
*.pyd
.Python

# Build artifacts
build/
dist/
*.spec.bak
*.egg-info/

# User data (should not be in repo)
data/uploads/
data/mathml/
*.log
*.log.*

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# ML Models (if downloaded)
*.pth
*.pt
*.onnx
*.h5
models/
checkpoints/

# Large test files
tests/*.pdf
tests/*.png
tests/*.jpg
```

### **2. Clean Build Artifacts**

```bash
# Remove build directory
rmdir /s /q build

# Remove dist directory (keep if you need the exe)
rmdir /s /q dist

# Clean Python cache
python -m py_compile --clean .
# Or manually:
for /r %i in (__pycache__) do @if exist "%i" rd /s /q "%i"
```

### **3. Clean User Data**

```bash
# Remove uploaded images (keep structure)
del /s /q data\uploads\*.png

# Remove old logs
del /s /q *.log.*
```

### **4. Use Lightweight Requirements for Development**

Create `requirements-dev.txt` with only essential packages:

```txt
# Core dependencies only
fastapi
uvicorn
PyQt6
pillow
opencv-python
latex2mathml
python-dotenv
```

Install ML packages only when needed:
```bash
pip install pix2tex torch transformers
```

---

## 🚀 **Reduce Executable Size**

### **Current EXE Size: ~300-500MB**

To reduce EXE size:

1. **Exclude Unused PyTorch Modules** (Already done in spec)
   - torchvision
   - torch.cuda
   - torch.distributed

2. **Exclude Unused Transformers Models**
   - Audio models
   - Large language models not used by pix2tex

3. **Use CPU-only PyTorch**
   ```bash
   pip uninstall torch
   pip install torch --index-url https://download.pytorch.org/whl/cpu
   ```
   This saves ~200-300MB!

4. **Exclude FastAPI if not using API mode**
   - Only needed for `python app.py api`
   - Can save ~20-30MB

---

## 📁 **Project Structure Optimization**

### **What Should Be in Git:**

✅ **Include:**
- Source code (`.py` files)
- Configuration files
- `requirements.txt`
- `README.md`
- Documentation

❌ **Exclude:**
- Virtual environments
- Build artifacts
- User data
- Log files
- Large test files

---

## 🔧 **Commands to Check Size**

### **Windows PowerShell:**

```powershell
# Check total project size
Get-ChildItem -Recurse -File | Measure-Object -Property Length -Sum

# Check size by directory
Get-ChildItem -Directory | ForEach-Object {
    $size = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | 
             Measure-Object -Property Length -Sum).Sum
    [PSCustomObject]@{
        Directory = $_.Name
        'Size(MB)' = [math]::Round($size/1MB, 2)
    }
} | Sort-Object 'Size(MB)' -Descending

# Find largest files
Get-ChildItem -Recurse -File | 
    Sort-Object Length -Descending | 
    Select-Object -First 10 Name, @{Name='Size(MB)';Expression={[math]::Round($_.Length/1MB, 2)}}
```

### **Find Large Files:**

```powershell
# Files larger than 10MB
Get-ChildItem -Recurse -File | Where-Object {$_.Length -gt 10MB} | 
    Select-Object FullName, @{Name='Size(MB)';Expression={[math]::Round($_.Length/1MB, 2)}}
```

---

## 📋 **Recommended .gitignore**

Update your `.gitignore` with this complete version:

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
*.egg-info/
dist/
build/
*.egg

# Virtual Environment
venv/
env/
ENV/
.venv/

# IDE
.vscode/
.idea/
*.swp
*.swo
*.sublime-project
*.sublime-workspace

# OS
.DS_Store
Thumbs.db
desktop.ini

# Project specific
data/uploads/
data/mathml/
*.log
*.log.*

# Build artifacts
build/
dist/
*.spec.bak

# ML Models (if downloaded separately)
*.pth
*.pt
*.onnx
*.h5
models/
checkpoints/
.cache/

# Test files (large)
tests/*.pdf
tests/*.png
tests/*.jpg
tests/*.jpeg

# Temporary files
*.tmp
*.temp
*.bak
```

---

## 🎯 **Action Plan**

### **Immediate Actions (Reduce Git Repo Size):**

1. ✅ Update `.gitignore` (see above)
2. ✅ Remove large files from Git history:
   ```bash
   git rm -r --cached build/
   git rm -r --cached dist/
   git rm -r --cached data/uploads/
   git rm -r --cached __pycache__/
   git commit -m "Remove large files from Git"
   ```
3. ✅ Clean local files:
   ```bash
   rmdir /s /q build
   rmdir /s /q __pycache__
   ```

### **Long-term Optimizations:**

1. Use CPU-only PyTorch for smaller EXE
2. Exclude unused dependencies
3. Clean user data regularly
4. Use separate requirements files for dev/prod

---

## 📊 **Expected Results**

### **Before:**
- Project folder: 2-5GB
- Git repo: 500MB-2GB
- EXE: 300-500MB

### **After:**
- Project folder: 500MB-1GB (after cleaning)
- Git repo: 10-50MB (only source code)
- EXE: 200-400MB (with optimizations)

---

## ⚠️ **Important Notes**

1. **Don't delete virtual environment** - You need it for development
2. **Don't delete source code** - Obviously needed
3. **Do delete build artifacts** - Can be regenerated
4. **Do exclude user data** - Should not be in repo
5. **Do use .gitignore** - Prevents committing large files

---

## 🔍 **Check Current Size**

Run this to see what's taking up space:

```powershell
cd mathpix_clone
Get-ChildItem -Directory | ForEach-Object {
    $size = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | 
             Measure-Object -Property Length -Sum).Sum
    [PSCustomObject]@{
        Directory = $_.Name
        'Size(MB)' = [math]::Round($size/1MB, 2)
    }
} | Sort-Object 'Size(MB)' -Descending | Format-Table -AutoSize
```

This will show you exactly which directories are largest!

