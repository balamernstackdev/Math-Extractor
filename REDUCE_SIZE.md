# Reducing Executable Size

## Current Size: ~800MB
## Target Size: ~300-400MB (50% reduction)

## Optimizations Applied

### 1. Excluded torchvision (~100-200MB saved)
- **torchvision** is NOT needed for pix2tex
- Only needed for computer vision tasks
- This is the biggest single win

### 2. Excluded PyTorch CUDA/Distributed (~50-100MB saved)
- **torch.cuda** - CUDA support (not needed for CPU)
- **torch.distributed** - Distributed training
- **torch.onnx** - ONNX export
- **torch.jit** - JIT compilation
- **torch._dynamo** - Dynamic compilation
- **torch._inductor** - Inductor backend

### 3. Excluded Unnecessary Transformers Models (~50-100MB saved)
- Deprecated models
- Audio models (wav2vec2, musicgen)
- Large language models not used by pix2tex
- Training utilities
- ONNX export tools

### 4. Excluded Unnecessary PyQt6 Modules (~20-30MB saved)
- WebEngine, Bluetooth, NFC, etc.
- 3D graphics, Charts, DataVisualization
- Multimedia, Network, QML

### 5. Excluded Matplotlib Backends (~10-20MB saved)
- GTK, WX, Tkinter backends
- PDF, PS, SVG backends (if not needed)
- Keep only essential backends

### 6. Excluded Test/Development Files (~10-20MB saved)
- pytest, unittest, doctest
- IPython, Jupyter
- Test files from numpy, matplotlib

## Additional Optimizations (If Still Too Large)

### Option 1: Use --onedir instead of --onefile
- Creates a folder with multiple files
- Faster startup (no extraction)
- Slightly larger total size but better performance

### Option 2: Exclude FastAPI/Uvicorn (if not using API mode)
- Only needed if running `python app.py api`
- Can save ~20-30MB

### Option 3: Use UPX Compression
- Already enabled in spec file
- Can reduce size by 20-30%
- May cause antivirus false positives

### Option 4: Exclude More Transformers Models
- Be careful - pix2tex might need some
- Test thoroughly after excluding

### Option 5: Use PyTorch CPU-only Build
- Install: `pip install torch --index-url https://download.pytorch.org/whl/cpu`
- Smaller than CUDA-enabled builds
- Only works for CPU inference

## Expected Results

After these optimizations:
- **Before**: ~800MB
- **After**: ~300-400MB
- **Reduction**: ~50% smaller

## Testing After Optimization

1. **Test OCR functionality** - Ensure pix2tex still works
2. **Test LaTeX conversion** - Ensure latex2mathml works
3. **Test UI** - Ensure PyQt6 interface works
4. **Test API mode** (if using) - Ensure FastAPI works

## If Build Fails

If you get "ModuleNotFoundError" after optimization:

1. Check which module is missing
2. Add it back to `hiddenimports` in `MathpixClone.spec`
3. Rebuild

## Build Command

```bash
python build_exe.py
```

Or directly:
```bash
pyinstaller MathpixClone.spec
```

