import ast
import os
from pathlib import Path

imports = set()

for py in Path(".").rglob("*.py"):
    if any(x in str(py) for x in [".venv", "build", "dist", "__pycache__"]):
        continue
    try:
        tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    imports.add(n.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
    except Exception:
        pass

with open("requirements.txt", "w", encoding="utf-8") as f:
    for pkg in sorted(imports):
        f.write(pkg + "\n")

print("requirements.txt generated safely")
