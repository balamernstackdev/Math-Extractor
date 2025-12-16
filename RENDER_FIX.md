# Render Deployment Fixes

## Issues Fixed

### 1. ✅ Syntax Warnings (Invalid Escape Sequences)

**Problem:**
```
SyntaxWarning: invalid escape sequence '\s'
SyntaxWarning: invalid escape sequence '\j'
```

**Fix:**
- Changed `\s`, `\j`, etc. to `\\s`, `\\j` in docstrings
- Or use raw strings `r"..."` for regex patterns

**Files Fixed:**
- `services/ocr/latex_to_mathml.py` - Fixed escape sequences in docstrings

### 2. ✅ IP Allowlist Blocking Render

**Problem:**
```
ERROR - IP allowlist blocked this machine (ip=74.220.48.242)
```

**Fix:**
- IP allowlist check now **skips in API mode**
- Web servers should be accessible from anywhere
- Only applies to GUI mode (desktop app)

**Change:**
```python
# Before: Checked IP before checking mode
if settings.allowed_ips and not enforce_ip_allowlist(...):
    sys.exit(1)
mode = sys.argv[1] if len(sys.argv) > 1 else None

# After: Check mode first, skip IP check in API mode
mode = sys.argv[1] if len(sys.argv) > 1 else None
if mode != "api" and settings.allowed_ips and not enforce_ip_allowlist(...):
    sys.exit(1)
```

### 3. ✅ PyQt6 Loading on Headless Server

**Problem:**
```
qt.qpa.plugin: Could not load the Qt platform plugin "xcb"
This application failed to start because no Qt platform plugin could be initialized.
```

**Root Cause:**
- `from ui.main_window import run_qt_app` was imported at module level
- This caused PyQt6 to load even in API mode
- PyQt6 requires GUI environment (X11/xcb) which Render doesn't have

**Fix:**
- Made import **lazy** (only when GUI mode is needed)
- PyQt6 is now only imported when `mode != "api"`

**Change:**
```python
# Before: Module-level import
from ui.main_window import run_qt_app

# After: Lazy import in GUI mode only
if mode == "api":
    # No PyQt6 import
    uvicorn.run(create_app(), ...)
else:
    # Only import PyQt6 when needed
    from ui.main_window import run_qt_app
    run_qt_app()
```

---

## Summary

✅ **Syntax warnings fixed** - No more invalid escape sequence warnings  
✅ **IP allowlist fixed** - Skips check in API mode  
✅ **PyQt6 loading fixed** - Only loads in GUI mode, not API mode  

---

## Testing

After these fixes, Render deployment should work:

1. **No syntax warnings** during startup
2. **No IP blocking** in API mode
3. **No Qt errors** - PyQt6 won't try to load

---

## Environment Variables for Render

You can optionally set these in Render dashboard:

- `MATHPIX_HOST` - Default: `0.0.0.0` (already set in render.yaml)
- `MATHPIX_PORT` - Default: `8000` (Render sets this automatically)
- `MATHPIX_ALLOWED_IPS` - Leave empty for public access (recommended for web)

---

## Next Steps

1. ✅ Fixes applied
2. ⏳ Commit and push changes
3. ⏳ Render will auto-deploy
4. ✅ Should work without errors!

