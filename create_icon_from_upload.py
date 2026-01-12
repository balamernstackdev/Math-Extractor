
from PIL import Image
import os

# Source path (uploaded artifact)
source_path = "d:/test-r&d/mathpix_clone/ui/Pandiyan Heart Centre VC.png"
dest_path = "d:/test-r&d/mathpix_clone/icon.ico"

if not os.path.exists(source_path):
    print(f"Error: Source image not found at {source_path}")
    exit(1)

try:
    img = Image.open(source_path)
    # Save as ICO with multiple sizes for best scaling in Windows
    img.save(dest_path, format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print(f"Successfully created icon.ico at {dest_path}")
except Exception as e:
    print(f"Error converting image: {e}")
    exit(1)
