"""
PyInstaller hook for pix2tex to ensure models are accessible in executable.
"""
from PyInstaller.utils.hooks import collect_data_files, collect_all
import os
from pathlib import Path

# Collect all pix2tex data files
datas, binaries, hiddenimports = collect_all('pix2tex')

# Also try to find and include pix2tex cache (models)
pix2tex_cache = Path(os.path.expanduser('~/.cache/pix2tex'))
if pix2tex_cache.exists():
    for model_file in pix2tex_cache.rglob('*'):
        if model_file.is_file():
            # Include in datas with relative path
            rel_path = model_file.relative_to(pix2tex_cache.parent.parent)
            datas.append((str(model_file), str(rel_path.parent)))

