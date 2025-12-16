# Remove Large Files from Git

## 🚨 **Problem**

Your Git repository is **904 MB** because large files are already committed:
- `.venv/` - 1.68 GB (virtual environment)
- `dist/` - 748 MB (built executable)
- `data/` - 58 MB (user data)

Even though `.gitignore` is updated, **Git still tracks these files** because they were committed before.

## ✅ **Solution: Remove from Git (Keep Local Files)**

### **Step 1: Remove from Git Tracking**

```bash
# Remove .venv from Git (keeps local files)
git rm -r --cached .venv

# Remove dist from Git (keeps local files)
git rm -r --cached dist

# Remove data/uploads and data/mathml from Git
git rm -r --cached data/uploads
git rm -r --cached data/mathml

# Remove build directory if it exists
git rm -r --cached build

# Remove __pycache__ directories
git rm -r --cached **/__pycache__

# Remove log files
git rm --cached *.log
git rm --cached *.log.*
```

### **Step 2: Commit the Removal**

```bash
git commit -m "Remove large files from Git (venv, dist, user data)"
```

### **Step 3: Push to GitHub**

```bash
git push origin main
```

**Note:** The first push after removal will still be large because Git needs to remove the files from history. Subsequent pushes will be much smaller.

---

## 🔧 **Alternative: Clean Git History (Advanced)**

If you want to completely remove these files from Git history (makes repo smaller):

### **Option 1: Use git-filter-repo (Recommended)**

```bash
# Install git-filter-repo
pip install git-filter-repo

# Remove .venv from entire history
git filter-repo --path .venv --invert-paths

# Remove dist from entire history
git filter-repo --path dist --invert-paths

# Remove data/uploads from entire history
git filter-repo --path data/uploads --invert-paths
```

**⚠️ Warning:** This rewrites Git history. You'll need to force push:
```bash
git push origin main --force
```

### **Option 2: Use BFG Repo-Cleaner**

```bash
# Download BFG: https://rtyley.github.io/bfg-repo-cleaner/
java -jar bfg.jar --delete-folders .venv dist
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

---

## 📋 **Quick Fix (Recommended)**

Run these commands to remove large files:

```bash
# Remove from Git tracking (keeps local files)
git rm -r --cached .venv dist build data/uploads data/mathml

# Remove any log files
git rm --cached *.log 2>nul
git rm --cached *.log.* 2>nul

# Commit
git commit -m "Remove large files: venv, dist, build, user data"

# Push (will be large this time, but future pushes will be small)
git push origin main
```

---

## ✅ **Verify .gitignore is Working**

After removing files, verify they won't be added again:

```bash
# Check .gitignore
cat .gitignore

# Try to add a file in .venv (should be ignored)
git add .venv/test.txt
git status  # Should show nothing
```

---

## 📊 **Expected Results**

### **Before:**
- Git repo: ~900 MB
- Push size: ~900 MB

### **After:**
- Git repo: ~10-50 MB (only source code)
- Push size: ~900 MB (first time, to remove files)
- Future pushes: ~1-5 MB (only code changes)

---

## 🎯 **What Should Be in Git**

✅ **Include:**
- Source code (`.py` files)
- Configuration files
- `requirements.txt`
- `README.md`
- Documentation (`.md` files)
- Small test files

❌ **Exclude:**
- `.venv/` - Virtual environment
- `dist/` - Built executables
- `build/` - Build artifacts
- `data/uploads/` - User uploaded files
- `data/mathml/` - Generated files
- `__pycache__/` - Python cache
- `*.log` - Log files

---

## ⚠️ **Important Notes**

1. **`git rm --cached`** removes files from Git but **keeps them locally**
2. **First push after removal** will still be large (Git needs to remove them)
3. **Future pushes** will be much smaller
4. **Team members** will need to pull and may see conflicts - coordinate if working in team

---

## 🚀 **Quick Command**

Copy and paste this entire block:

```bash
git rm -r --cached .venv dist build data/uploads data/mathml
git rm --cached *.log 2>nul
git commit -m "Remove large files from Git repository"
git push origin main
```

This will:
1. Remove large files from Git tracking
2. Commit the changes
3. Push to GitHub (large this time, but necessary)

