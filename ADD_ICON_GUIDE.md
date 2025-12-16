# Adding Icon to Executable

## Quick Start

### Option 1: If you have a logo image (PNG, JPG, etc.)

1. **Place your logo image** in the project root (e.g., `logo.png`, `mathpix_logo.png`)

2. **Convert to .ico format:**
   ```bash
   python create_icon.py logo.png icon.ico
   ```

3. **Rebuild the executable:**
   ```bash
   python build_exe.py
   ```

The icon will now appear on your `MathpixClone.exe` file!

### Option 2: Create icon manually

1. **Use an online converter:**
   - Go to https://convertio.co/png-ico/ or https://www.icoconverter.com/
   - Upload your logo image
   - Download the .ico file
   - Save as `icon.ico` in project root

2. **Use image editing software:**
   - GIMP, Photoshop, or Paint.NET
   - Create a 256x256 or 512x512 image
   - Export as .ico format
   - Save as `icon.ico` in project root

3. **Rebuild the executable:**
   ```bash
   python build_exe.py
   ```

## Icon Requirements

- **Format**: `.ico` (Windows Icon format)
- **Recommended sizes**: 16x16, 32x32, 48x48, 64x64, 128x128, 256x256
- **Best size**: 256x256 or 512x512 (will be resized automatically)
- **Format**: PNG with transparency works best
- **File location**: Project root (same directory as `app.py`)

## Mathpix-Style Icon Design

Based on the Mathpix logo description:
- **Background**: Bright blue square with rounded corners
- **Foreground**: White stylized "m" character
- **Shadow**: Subtle dark shadow for depth

### Creating the Icon

1. **Design in image editor:**
   - Create 256x256 or 512x512 canvas
   - Blue background (#0078d4 or similar)
   - White "m" character in center
   - Add subtle shadow/depth

2. **Export as PNG** (with transparency if needed)

3. **Convert to .ico** using `create_icon.py`:
   ```bash
   python create_icon.py mathpix_logo.png icon.ico
   ```

## Verification

After building:
1. Check `dist\MathpixClone.exe`
2. The icon should appear in File Explorer
3. The icon should appear in the taskbar when running

## Troubleshooting

### Icon not showing
- **Check file path**: Icon must be in project root
- **Check file format**: Must be `.ico` format
- **Rebuild**: Delete `build/` and `dist/` folders, then rebuild
- **Check spec file**: Verify `icon='icon.ico'` in `MathpixClone.spec`

### Icon looks blurry
- Use higher resolution source image (512x512 or 1024x1024)
- The script creates multiple sizes automatically

### "PIL not found" error
- Install Pillow: `pip install Pillow`
- Required for `create_icon.py` script

## Current Configuration

The `MathpixClone.spec` file is configured to use:
- **Icon file**: `icon.ico` (in project root)
- **If icon not found**: Executable will use default Python icon

## Next Steps

1. Create or obtain your logo image
2. Convert to `.ico` format
3. Place `icon.ico` in project root
4. Rebuild executable
5. Verify icon appears on `.exe` file

