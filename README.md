# Mathpix Clone (Python)
    
Mathpix-style desktop application combining FastAPI backend and PyQt6 UI. Supports PDF ingestion, page rendering, formula detection, OCR to LaTeX, conversion to MathML, XML export, snips library, and notes editor.

## Features
- PDF upload, rendering to PNG
- Bounding box detection (OpenCV contours)
- Manual region selection overlay
- OCR with Tesseract to LaTeX (configurable path)
- LaTeX to MathML conversion
- XML export of equations + bounding boxes
- Snips page with cropped formulas
- Notes page with formula insertion
- FastAPI endpoints for automation

## Setup
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

Install Tesseract (Windows) and set `TESSERACT_CMD` to the executable path if needed.

## Run
- Desktop UI: `python app.py`
- API server: `python app.py api` (served on 127.0.0.1:8000 by default)

## Tests
```bash
pytest
```

## Project Structure
See the `mathpix_clone/` tree for services, UI components, and utils. Data directories (`data/uploads`, `data/snips`, `data/notes`) are created on first run.

