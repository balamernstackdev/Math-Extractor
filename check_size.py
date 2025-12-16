"""Simple script to check project directory sizes."""
import os
from pathlib import Path
from collections import defaultdict

def get_dir_size(path: Path) -> int:
    """Get total size of directory in bytes."""
    total = 0
    try:
        for entry in path.rglob('*'):
            if entry.is_file():
                total += entry.stat().st_size
    except (PermissionError, OSError):
        pass
    return total

def format_size(size_bytes: int) -> str:
    """Format bytes to human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def main():
    """Check sizes of main directories."""
    project_root = Path(__file__).parent
    
    print("=" * 80)
    print("Project Size Analysis")
    print("=" * 80)
    print(f"Project root: {project_root}")
    print()
    
    # Check main directories
    dirs_to_check = [
        'build',
        'dist',
        'data',
        'venv',
        '.venv',
        'env',
        '__pycache__',
        'tests',
        'examples',
    ]
    
    sizes = {}
    total_size = 0
    
    for dir_name in dirs_to_check:
        dir_path = project_root / dir_name
        if dir_path.exists():
            size = get_dir_size(dir_path)
            sizes[dir_name] = size
            total_size += size
            print(f"{dir_name:20s}: {format_size(size)}")
    
    # Check for other large directories
    print()
    print("Other directories:")
    for item in project_root.iterdir():
        if item.is_dir() and item.name not in dirs_to_check and not item.name.startswith('.'):
            size = get_dir_size(item)
            if size > 1_000_000:  # Show if > 1MB
                sizes[item.name] = size
                total_size += size
                print(f"{item.name:20s}: {format_size(size)}")
    
    print()
    print("=" * 80)
    print(f"Total checked: {format_size(total_size)}")
    print()
    print("Top 5 largest directories:")
    sorted_sizes = sorted(sizes.items(), key=lambda x: x[1], reverse=True)
    for name, size in sorted_sizes[:5]:
        print(f"  {name:20s}: {format_size(size)}")
    print("=" * 80)
    
    # Recommendations
    print()
    print("Recommendations:")
    if 'build' in sizes:
        print("  ✅ Delete 'build/' directory (can be regenerated)")
    if 'dist' in sizes:
        print("  ⚠️  'dist/' contains your EXE - keep if needed")
    if 'venv' in sizes or '.venv' in sizes:
        print("  ✅ Add 'venv/' to .gitignore (should not be in Git)")
    if 'data' in sizes:
        print("  ✅ Add 'data/uploads/' to .gitignore (user data)")
    if '__pycache__' in sizes:
        print("  ✅ Delete '__pycache__/' directories (can be regenerated)")

if __name__ == "__main__":
    main()

