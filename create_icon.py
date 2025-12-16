"""
Helper script to create an .ico file from an image for the executable icon.

Usage:
    python create_icon.py <input_image> [output_icon]

Examples:
    python create_icon.py logo.png
    python create_icon.py logo.png icon.ico
    python create_icon.py mathpix_logo.png MathpixClone.ico
"""

import sys
from pathlib import Path
from PIL import Image

def create_icon(input_path: str, output_path: str = "icon.ico") -> None:
    """Convert an image to .ico format with multiple sizes."""
    
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"❌ Error: Input file not found: {input_path}")
        sys.exit(1)
    
    try:
        # Open the image
        img = Image.open(input_path)
        print(f"✅ Loaded image: {input_path} ({img.size[0]}x{img.size[1]})")
        
        # Create icon with multiple sizes (Windows requires multiple sizes)
        # Common sizes: 16x16, 32x32, 48x48, 64x64, 128x128, 256x256
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        
        # Resize image for each size (high quality)
        icon_images = []
        for size in sizes:
            resized = img.resize(size, Image.Resampling.LANCZOS)
            icon_images.append(resized)
            print(f"  Created {size[0]}x{size[1]} version")
        
        # Save as .ico file with all sizes
        # Use the largest image and specify all sizes
        icon_images[-1].save(  # Use the largest (256x256)
            output_path,
            format='ICO',
            sizes=[(img.size[0], img.size[1]) for img in icon_images]
        )
        
        print(f"✅ Icon created successfully: {output_path}")
        print(f"   File size: {Path(output_path).stat().st_size / 1024:.2f} KB")
        
    except Exception as e:
        print(f"❌ Error creating icon: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n❌ Error: Please provide an input image file")
        print("Usage: python create_icon.py <input_image> [output_icon]")
        sys.exit(1)
    
    input_image = sys.argv[1]
    output_icon = sys.argv[2] if len(sys.argv) > 2 else "icon.ico"
    
    create_icon(input_image, output_icon)

