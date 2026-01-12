import os
from pathlib import Path

def get_dir_size(path):
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += get_dir_size(entry.path)
    except Exception:
        pass
    return total

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"

def main():
    dist_dir = Path("dist/Math Extractor/_internal")
    if not dist_dir.exists():
        print("dist/Math Extractor/_internal not found")
        # Try base dir
        dist_dir = Path("dist/Math Extractor")
        return

    print(f"Analyzing {dist_dir}...\n")
    
    items = []
    for item in dist_dir.iterdir():
        if item.is_file():
            size = item.stat().st_size
            items.append((item.name, size, "FILE"))
        elif item.is_dir():
            size = get_dir_size(item)
            items.append((item.name, size, "DIR"))
    
    # Sort by size
    items.sort(key=lambda x: x[1], reverse=True)
    
    for name, size, type_ in items[:20]:
        print(f"{type_:4} {name:30} : {format_size(size)}")

if __name__ == "__main__":
    main()
