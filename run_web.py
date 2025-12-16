# """Quick launcher for web versions of MathPix Clone."""
# from __future__ import annotations

# import sys

# def main() -> None:
#     """Launch web version based on argument."""
#     if len(sys.argv) > 1 and sys.argv[1] == "streamlit":
#         # Launch Streamlit web app
#         try:
#             import streamlit.web.cli as stcli
#             sys.argv = ["streamlit", "run", "web_app.py", "--server.port=8501"]
#             stcli.main()
#         except ImportError:
#             print("❌ Streamlit not installed. Run: pip install streamlit")
#             sys.exit(1)
#     else:
#         # Launch FastAPI web app
#         from app import create_app, settings
#         import uvicorn
#         from core.logger import init_logging, ensure_directories
#         from utils.file_utils import ensure_directories as ensure_dirs
        
#         init_logging()
#         ensure_dirs()
#         app = create_app()
#         print(f"🚀 Starting FastAPI server at http://{settings.host}:{settings.port}")
#         print(f"📝 Web interface: http://{settings.host}:{settings.port}")
#         uvicorn.run(app, host=settings.host, port=settings.port)

# if __name__ == "__main__":
#     main()

"""Quick launcher for web versions of MathPix Clone."""
from __future__ import annotations
import sys
import os

def main() -> None:
    PORT = int(os.environ.get("PORT", 8000))

    if len(sys.argv) > 1 and sys.argv[1] == "streamlit":
        # Launch Streamlit web app (Render-safe)
        try:
            import streamlit.web.cli as stcli
            sys.argv = [
                "streamlit",
                "run",
                "web_app.py",
                "--server.address=0.0.0.0",
                f"--server.port={PORT}",
            ]
            stcli.main()
        except ImportError:
            print("❌ Streamlit not installed. Run: pip install streamlit")
            sys.exit(1)
    else:
        # Launch FastAPI web app (Render-safe)
        from app import create_app
        import uvicorn
        from core.logger import init_logging
        from utils.file_utils import ensure_directories

        init_logging()
        ensure_directories()

        app = create_app()

        print(f"🚀 Starting FastAPI server on 0.0.0.0:{PORT}")
        uvicorn.run(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
