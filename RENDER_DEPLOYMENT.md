# Deploy to Render.com - Complete Guide

## ✅ Yes, You Can Deploy to Render!

Your app is **already configured** for web deployment. The FastAPI mode is completely separate from the EXE build.

---

## 🎯 **Will It Affect EXE Build?**

### ❌ **NO - Zero Impact!**

The two modes are **completely independent**:

1. **EXE Build** (`python app.py` or no args)
   - Uses PyQt6 GUI
   - Creates desktop application
   - Requires Windows build environment
   - **Not affected by Render deployment**

2. **Web Deployment** (`python app.py api`)
   - Uses FastAPI web server
   - Runs on Render cloud
   - **Not affected by EXE build**

**They share the same codebase but run in different modes!**

---

## 🚀 **Quick Deployment Steps**

### Step 1: Create `render.yaml` (Already Created ✅)

The file `render.yaml` is already in your project root with the correct configuration.

### Step 2: Push to GitHub

```bash
# If not already a git repo
git init
git add .
git commit -m "Initial commit"

# Add your GitHub remote
git remote add origin https://github.com/YOUR_USERNAME/mathpix-clone.git
git push -u origin main
```

### Step 3: Deploy on Render

1. **Sign up**: Go to [render.com](https://render.com) and sign up (free)

2. **Connect GitHub**:
   - Click "New" → "Web Service"
   - Connect your GitHub account
   - Select your repository

3. **Configure Service**:
   - **Name**: `mathpix-clone` (or any name)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py api`
   - Render will auto-detect `render.yaml` if present

4. **Deploy**:
   - Click "Create Web Service"
   - Render will build and deploy automatically
   - Wait 5-10 minutes for first deployment

5. **Access Your App**:
   - Your app will be live at: `https://mathpix-clone.onrender.com`
   - (URL will be your service name)

---

## 📋 **What Render Needs**

### Required Files (Already Present ✅)

1. ✅ `app.py` - Main application file
2. ✅ `requirements.txt` - Python dependencies
3. ✅ `render.yaml` - Deployment configuration (just created)

### How It Works

When Render runs `python app.py api`:
- Your app checks `sys.argv[1] == "api"`
- It starts FastAPI server instead of PyQt6 GUI
- FastAPI runs on port 8000 (Render sets PORT env var)
- Web interface is accessible via browser

---

## 🔧 **Configuration Details**

### Environment Variables

Render automatically sets:
- `PORT` - Port number (usually 8000)
- `HOST` - Should be `0.0.0.0` for Render

### Optional Settings

If you need IP restrictions, add to Render dashboard:
- `MATHPIX_ALLOWED_IPS` - Comma-separated IPs (leave empty for public access)

---

## ⚠️ **Important Notes**

### 1. PyQt6 Not Needed for Web Mode

When running `python app.py api`:
- PyQt6 is **NOT imported** (only when GUI mode runs)
- No Qt DLLs needed
- Much smaller and faster startup
- **This is why it doesn't affect EXE build**

### 2. Render Free Tier Limitations

- ⚠️ **Spins down after 15 minutes of inactivity**
- ⚠️ **Takes ~30 seconds to wake up** (first request after sleep)
- ⚠️ **Limited resources** (512MB RAM, shared CPU)
- ✅ **Completely free**
- ✅ **Auto-deploys on git push**

### 3. Dependencies

Make sure `requirements.txt` includes:
- `fastapi`
- `uvicorn`
- All OCR/ML dependencies
- **NOT PyQt6** (not needed for web mode)

---

## 🧪 **Test Locally First**

Before deploying, test web mode locally:

```bash
# Test FastAPI mode
python app.py api

# Should see:
# INFO: Starting FastAPI server at 0.0.0.0:8000
# INFO: Uvicorn running on http://0.0.0.0:8000

# Open browser: http://localhost:8000
```

If this works locally, it will work on Render!

---

## 📊 **Deployment Comparison**

| Aspect | EXE Build | Render Deployment |
|--------|-----------|-------------------|
| **Command** | `python app.py` | `python app.py api` |
| **UI** | PyQt6 Desktop | FastAPI Web |
| **Dependencies** | PyQt6 + All | FastAPI + All (no PyQt6) |
| **Platform** | Windows only | Any device with browser |
| **Offline** | ✅ Yes | ❌ No (needs internet) |
| **Affects Other** | ❌ No | ❌ No |

---

## 🎯 **Best Practice**

### Deploy Both!

1. **EXE**: For users who want desktop app (offline, native)
2. **Web**: For users who want browser access (any device, no install)

**They complement each other perfectly!**

---

## 🔍 **Troubleshooting**

### Build Fails on Render

**Check:**
1. `requirements.txt` has all dependencies
2. Python version matches (check `runtime.txt` if needed)
3. Build logs in Render dashboard

### App Doesn't Start

**Check:**
1. Start command is correct: `python app.py api`
2. Port is set correctly (Render auto-sets PORT env var)
3. Logs in Render dashboard for errors

### Slow First Request

**Normal!** Render free tier spins down after inactivity. First request after sleep takes ~30 seconds to wake up.

---

## 📝 **Next Steps**

1. ✅ `render.yaml` is created
2. ⏳ Push code to GitHub
3. ⏳ Deploy on Render.com
4. ⏳ Test web interface
5. ✅ Continue building EXE (no conflicts!)

---

## 🎉 **Summary**

- ✅ **Can deploy to Render**: Yes!
- ✅ **Affects EXE build**: No, completely separate
- ✅ **Already configured**: Just need to deploy
- ✅ **Both can coexist**: Deploy web AND build EXE

**You're all set!** 🚀

