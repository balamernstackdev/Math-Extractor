"""
Development Hot-Reload Watcher
Automatically restarts the application when UI files change.
"""
import subprocess
import sys
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class AppReloader(FileSystemEventHandler):
    """Handles file changes and restarts the application."""
    
    def __init__(self, app_path: Path):
        self.app_path = app_path
        self.process = None
        self.restart_pending = False
        self.last_restart = 0
        self.debounce_seconds = 2  # Wait 2 seconds after change before restarting
        
    def start_app(self):
        """Start the application."""
        if self.process:
            print("\n🔄 Stopping previous instance...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        
        print(f"\n🚀 Starting application...")
        self.process = subprocess.Popen(
            [sys.executable, str(self.app_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        self.last_restart = time.time()
        
        # Print initial output in a separate thread
        import threading
        def print_output():
            for line in self.process.stdout:
                print(line, end='')
        
        thread = threading.Thread(target=print_output, daemon=True)
        thread.start()
    
    def on_modified(self, event):
        """Called when a file is modified."""
        if event.is_directory:
            return
        
        # Only watch UI and style files
        file_path = Path(event.src_path)
        if file_path.suffix in ['.py'] and any(part in file_path.parts for part in ['ui', 'services']):
            # Debounce: avoid multiple restarts for rapid saves
            if time.time() - self.last_restart < self.debounce_seconds:
                self.restart_pending = True
                return
            
            print(f"\n📝 Detected change in: {file_path.name}")
            self.restart_pending = False
            self.start_app()
    
    def check_pending_restart(self):
        """Check if there's a pending restart after debounce period."""
        if self.restart_pending and time.time() - self.last_restart >= self.debounce_seconds:
            print("\n📝 Processing pending restart...")
            self.restart_pending = False
            self.start_app()

def main():
    """Main entry point."""
    print("=" * 60)
    print("🔥 HOT-RELOAD DEVELOPMENT MODE")
    print("=" * 60)
    print("\nWatching for changes in:")
    print("  - ui/*.py")
    print("  - services/*.py")
    print("\nThe app will automatically restart when you save changes.")
    print("Press Ctrl+C to stop.\n")
    print("=" * 60)
    
    # Setup paths
    project_root = Path(__file__).parent
    app_path = project_root / "app.py"
    watch_dirs = [
        project_root / "ui",
        project_root / "services",
    ]
    
    # Create reloader
    reloader = AppReloader(app_path)
    
    # Start initial app instance
    reloader.start_app()
    
    # Setup file watcher
    observer = Observer()
    for watch_dir in watch_dirs:
        if watch_dir.exists():
            observer.schedule(reloader, str(watch_dir), recursive=True)
            print(f"👀 Watching: {watch_dir}")
    
    observer.start()
    
    try:
        while True:
            time.sleep(1)
            reloader.check_pending_restart()
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping watcher...")
        observer.stop()
        if reloader.process:
            reloader.process.terminate()
    
    observer.join()
    print("✅ Development server stopped.")

if __name__ == "__main__":
    main()
