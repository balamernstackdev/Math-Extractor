import os

root_dir = r"d:\test-r&d\mathpix_clone"
target = "OCRWorker"

print(f"Searching for {target} in {root_dir}...")

for dirpath, dirnames, filenames in os.walk(root_dir):
    if "node_modules" in dirpath or ".venv" in dirpath or ".git" in dirpath:
        continue
    for filename in filenames:
        if filename.endswith(".py"):
            filepath = os.path.join(dirpath, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    for i, line in enumerate(lines):
                        if target in line:
                            print(f"{filepath}:{i+1}: {line.strip()}")
            except Exception as e:
                print(f"Error reading {filepath}: {e}")
