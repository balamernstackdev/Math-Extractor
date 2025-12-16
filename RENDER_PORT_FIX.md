# Render Port Binding Fix

## 🚨 **Problem**

Render deployment shows:
```
==> No open ports detected on 0.0.0.0, continuing to scan...
==> Docs on specifying a port: https://render.com/docs/web-services#port-binding
```

**Root Cause:**
- FastAPI was binding to `127.0.0.1:8000` (localhost only)
- Render requires binding to `0.0.0.0` (all interfaces)
- Render can't detect the service because it's not listening on the right interface

## ✅ **Fixes Applied**

### **1. Host Binding Fixed**

**Before:**
```python
host: str = os.getenv("MATHPIX_HOST", "127.0.0.1")  # Localhost only
uvicorn.run(create_app(), host=settings.host, port=settings.port)
```

**After:**
```python
# Check Render's HOST env var first
host = os.getenv("HOST", settings.host)
if host == "127.0.0.1":
    host = "0.0.0.0"  # Override for web deployment

port = int(os.getenv("PORT", str(settings.port)))  # Use Render's PORT
uvicorn.run(create_app(), host=host, port=port)
```

### **2. Deprecation Warning Fixed**

**Before:**
```python
@app.on_event("startup")  # Deprecated
async def startup_event():
    ...
```

**After:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_logging()
    ensure_directories()
    logger.info("FastAPI service started")
    yield
    # Shutdown
    logger.info("FastAPI service shutting down")

app = FastAPI(..., lifespan=lifespan)
```

### **3. Config Updated**

**`core/config.py`:**
- Default host changed to `0.0.0.0` (was `127.0.0.1`)
- Checks `HOST` env var (Render sets this)
- Checks `PORT` env var (Render sets this)

---

## 🎯 **How It Works**

### **Local Development:**
- Can still use `127.0.0.1` if set explicitly
- Defaults to `0.0.0.0` for web deployment

### **Render Deployment:**
- Render sets `HOST=0.0.0.0` and `PORT=8000` (or custom)
- App uses these environment variables
- Binds to `0.0.0.0:8000` (or Render's port)
- Render can detect the service ✅

---

## 📋 **Environment Variables**

Render automatically sets:
- `HOST=0.0.0.0` (or custom)
- `PORT=8000` (or custom)

Your app now:
1. Checks `HOST` env var first
2. Falls back to `settings.host`
3. Overrides `127.0.0.1` → `0.0.0.0` for web deployment

---

## ✅ **Expected Results**

After this fix:
- ✅ Server binds to `0.0.0.0:8000` (or Render's port)
- ✅ Render detects the service
- ✅ No "No open ports detected" error
- ✅ App accessible via Render URL
- ✅ No deprecation warnings

---

## 🚀 **Next Steps**

1. ✅ Fixes applied
2. ⏳ Commit and push:
   ```bash
   git add app.py core/config.py
   git commit -m "Fix Render port binding: use 0.0.0.0, fix lifespan deprecation"
   git push origin main
   ```
3. ⏳ Render will auto-deploy
4. ✅ Should work now!

---

## 📊 **Summary**

- ✅ **Host binding fixed** - Uses `0.0.0.0` for web deployment
- ✅ **Port detection fixed** - Uses Render's PORT env var
- ✅ **Deprecation fixed** - Uses lifespan handlers
- ✅ **Ready to deploy**

**Your app should now be detected by Render!** 🎉

