"""Application entry point for Mathpix-style clone using FastAPI and PyQt6."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import tempfile
from pathlib import Path

# NOTE: Do NOT import QtWebEngine here at module level!
# The runtime hook (pyi_rth_pyqt6.py) will set PATH and initialize Qt properly.
# Module-level imports happen before PATH is set, causing DLL resolution failures.

import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from core.config import settings
from core.logger import init_logging, logger
from services.pdf_loader.pdf_reader import PDFReader
from services.pdf_loader.pdf_renderer import PDFRenderer
from services.ocr.formula_detector import FormulaDetector
from services.ocr.image_to_latex import ImageToLatex
from services.ocr.latex_to_mathml import LatexToMathML
from services.exporters.xml_writer import XMLWriter
# Import run_qt_app lazily - only when GUI mode is needed (not in API mode)
# This prevents PyQt6 from loading on headless servers
from utils.file_utils import ensure_directories
from utils.image_utils import crop_image
from utils.ip_guard import enforce_ip_allowlist


def create_app() -> FastAPI:
    """Create FastAPI app with basic health and upload routes."""
    app = FastAPI(title="MathML Extractor", version="0.1.0")

    pdf_reader = PDFReader()
    pdf_renderer = PDFRenderer()
    detector = FormulaDetector()
    latex_ocr = ImageToLatex()
    latex_mathml = LatexToMathML()
    xml_writer = XMLWriter()

    @app.on_event("startup")
    async def startup_event() -> None:
        init_logging()
        ensure_directories()
        logger.info("FastAPI service started")

    @app.get("/", response_class=HTMLResponse)
    async def root() -> str:
        """Serve simple HTML frontend."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>MathML Extractor - Web</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background: #1e1e1e; color: white; }
                h1 { color: #0078d4; }
                .upload-area { border: 2px dashed #0078d4; padding: 40px; text-align: center; border-radius: 8px; margin: 20px 0; }
                button { background: #0078d4; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
                button:hover { background: #106ebe; }
                #results { margin-top: 20px; }
                .formula { background: #2b2b2b; padding: 15px; margin: 10px 0; border-radius: 4px; }
                code { background: #1e1e1e; padding: 5px; border-radius: 3px; display: block; margin: 10px 0; }
            </style>
        </head>
        <body>
            <h1>📐 MathPix Clone - Web Edition</h1>
            <p>Upload PDFs or images to extract mathematical formulas</p>
            
            <div class="upload-area">
                <input type="file" id="fileInput" accept=".pdf,.png,.jpg,.jpeg" />
                <br><br>
                <button onclick="uploadFile()">Upload & Process</button>
            </div>
            
            <div id="results"></div>
            
            <script>
                async function uploadFile() {
                    const fileInput = document.getElementById('fileInput');
                    const file = fileInput.files[0];
                    if (!file) {
                        alert('Please select a file');
                        return;
                    }
                    
                    const formData = new FormData();
                    formData.append('file', file);
                    
                    const resultsDiv = document.getElementById('results');
                    resultsDiv.innerHTML = '<p>Processing...</p>';
                    
                    try {
                        const response = await fetch('/upload', {
                            method: 'POST',
                            body: formData
                        });
                        const data = await response.json();
                        
                        if (data.status === 'success') {
                            let html = '<h2>Results:</h2>';
                            data.formulas.forEach((f, idx) => {
                                html += `
                                    <div class="formula">
                                        <h3>Formula ${idx + 1}</h3>
                                        <p><strong>LaTeX:</strong></p>
                                        <code>${f.latex || 'N/A'}</code>
                                        <p><strong>MathML:</strong></p>
                                        <code>${f.mathml || 'N/A'}</code>
                                    </div>
                                `;
                            });
                            resultsDiv.innerHTML = html;
                        } else {
                            resultsDiv.innerHTML = `<p style="color: red;">Error: ${data.message}</p>`;
                        }
                    } catch (error) {
                        resultsDiv.innerHTML = `<p style="color: red;">Error: ${error.message}</p>`;
                    }
                }
            </script>
        </body>
        </html>
        """

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/upload")
    async def upload_file(file: UploadFile = File(...)) -> JSONResponse:
        """Handle file upload and process."""
        try:
            # Save uploaded file temporarily
            suffix = Path(file.filename).suffix if file.filename else ".pdf"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                content = await file.read()
                tmp_file.write(content)
                tmp_path = Path(tmp_file.name)
            
            formulas = []
            
            if file.content_type == "application/pdf":
                # Process PDF
                pages = pdf_reader.read_pdf(tmp_path)
                images = pdf_renderer.render_pages(pages)
                
                for img_path in images:
                    bboxes = detector.detect_formulas(img_path)
                    for bbox in bboxes:
                        # Extract LaTeX and MathML
                        try:
                            crop_path = crop_image(img_path, bbox)
                            latex = latex_ocr.image_to_latex(crop_path)
                            mathml = latex_mathml.convert(latex) if latex else ""
                            formulas.append({
                                "latex": latex or "",
                                "mathml": mathml or "",
                                "bbox": bbox
                            })
                        except Exception as e:
                            logger.warning(f"Failed to extract formula: {e}")
            else:
                # Process image
                bboxes = detector.detect_formulas(tmp_path)
                for bbox in bboxes:
                    try:
                        crop_path = crop_image(tmp_path, bbox)
                        latex = latex_ocr.image_to_latex(crop_path)
                        mathml = latex_mathml.convert(latex) if latex else ""
                        formulas.append({
                            "latex": latex or "",
                            "mathml": mathml or "",
                            "bbox": bbox
                        })
                    except Exception as e:
                        logger.warning(f"Failed to extract formula: {e}")
            
            # Cleanup
            if tmp_path.exists():
                tmp_path.unlink()
            
            return JSONResponse({
                "status": "success",
                "formulas": formulas,
                "count": len(formulas)
            })
        
        except Exception as exc:  # noqa: BLE001
            logger.exception("Upload processing failed: %s", exc)
            return JSONResponse(
                {"status": "error", "message": str(exc)},
                status_code=500
            )

    @app.post("/process_pdf")
    async def process_pdf(path: str) -> dict[str, str | list[dict[str, float | str]]]:
        """Process a PDF path through render and detection pipeline."""
        try:
            pages = pdf_reader.read_pdf(path)
            images = pdf_renderer.render_pages(pages)
            results: list[dict[str, float | str]] = []
            for img_path in images:
                bboxes = detector.detect_formulas(img_path)
                for bbox in bboxes:
                    bbox["page_image"] = str(img_path)
                results.extend(bboxes)
            xml_writer.write_document(results)
            return {"status": "processed", "bounding_boxes": results}
        except Exception as exc:  # noqa: BLE001
            logger.exception("Processing failed: %s", exc)
            return {"status": "error", "message": str(exc)}

    @app.post("/ocr_region")
    async def ocr_region(image_path: str) -> dict[str, str]:
        """OCR a cropped region to LaTeX and MathML."""
        try:
            latex = latex_ocr.image_to_latex(image_path)
            mathml = latex_mathml.convert(latex)
            return {"latex": latex, "mathml": mathml}
        except Exception as exc:  # noqa: BLE001
            logger.exception("OCR failed: %s", exc)
            return {"status": "error", "message": str(exc)}

    return app


def main() -> None:
    """Entry point for CLI; starts FastAPI or PyQt based on args."""
    init_logging()
    ensure_directories()
    
    # Check mode first - IP allowlist only applies to GUI mode
    mode: Optional[str] = sys.argv[1] if len(sys.argv) > 1 else None
    
    # IP allowlist check - skip in API mode (web servers should be accessible)
    # Also skip if MATHPIX_ALLOWED_IPS is not set (allow all)
    if mode != "api" and settings.allowed_ips and not enforce_ip_allowlist(set(settings.allowed_ips)):
        # User-friendly dialog when blocked (GUI mode only)
        try:
            from PyQt6 import QtWidgets, QtCore
            
            # CRITICAL: Set attribute before creating QApplication
            QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
            
            app = QtWidgets.QApplication(sys.argv)
            QtWidgets.QMessageBox.critical(
                None,
                "Access denied",
                "This machine's public IP is not in MATHPIX_ALLOWED_IPS.\n\n"
                "Set the environment variable MATHPIX_ALLOWED_IPS to a comma-separated list "
                "of allowed IPs and restart the application."
            )
        except Exception:
            logger.error(
                "Access denied: this IP is not in MATHPIX_ALLOWED_IPS. "
                "Update the allowlist and rebuild/restart."
            )
        sys.exit(1)
    
    if mode == "api":
        logger.info("Starting FastAPI server at %s:%s", settings.host, settings.port)
        # API mode - no PyQt6 needed, skip IP check
        uvicorn.run(create_app(), host=settings.host, port=settings.port)
    else:
        logger.info("Starting PyQt6 UI")
        # Lazy import - only load PyQt6 when GUI mode is needed
        from ui.main_window import run_qt_app
        run_qt_app()


if __name__ == "__main__":
    main()

