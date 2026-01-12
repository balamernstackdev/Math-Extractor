
import os

log_file = 'mathpix_clone.log'
if os.path.exists(log_file):
    with open(log_file, 'rb') as f:
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - 20000))
        lines = f.read().decode('utf-8', errors='ignore').splitlines()
        for line in lines:
            if "D_{\Sigma}" in line or "D_{\\Sigma}" in line or "PreviewPanel" in line or "StrictPipeline" in line:
                print(line)
else:
    print("Log file not found")
