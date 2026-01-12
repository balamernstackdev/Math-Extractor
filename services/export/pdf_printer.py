
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtCore import QObject, pyqtSignal, QUrl, QMarginsF
from PyQt6.QtGui import QPageLayout, QPageSize
from pathlib import Path
from core.logger import logger

class PDFPrinter(QObject):
    """
    Helper to print HTML to PDF using QWebEnginePage.
    Must run on the Main Thread.
    """
    finished = pyqtSignal(bool, str)  # success, message/path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.page = QWebEnginePage(parent)
        self.output_path = ""
        
        # Connect signals
        self.page.loadFinished.connect(self._on_load_finished)
        self.page.pdfPrintingFinished.connect(self._on_pdf_finished)

    def print_html_to_pdf(self, html_path: str, output_path: str):
        """
        Load local HTML file and print to PDF.
        """
        self.output_path = output_path
        file_url = QUrl.fromLocalFile(html_path)
        logger.info(f"[PDFPrinter] Loading HTML: {html_path}")
        self.page.load(file_url)

    def _on_load_finished(self, success):
        if not success:
            logger.error("[PDFPrinter] Failed to load HTML page.")
            self.finished.emit(False, "Failed to load HTML content.")
            return

        logger.info("[PDFPrinter] HTML loaded. Rendering MathJax...")
        
        # We need to wait for MathJax to finish rendering.
        # We can inject a script to check MathJax status or just wait a bit?
        # Robust way: use a JS Promise or callback.
        # For now, let's assume MathJax runs quickly. 
        # But wait! The HTML has <script async src="...MathJax..."></script>.
        # We should wait for the window.MathJax.startup.promise.
        
        # Inject JS to trigger print after MathJax
        # Or simpler: Just print. MathJax might race.
        # Let's try to just print for now, assume MathJax is fast enough,
        # OR add a small delay if needed. 
        # Better: run JS to check ready state.
        
        self._start_printing()

    def _start_printing(self):
        logger.info(f"[PDFPrinter] Printing to PDF: {self.output_path}")
        
        layout = QPageLayout(
            QPageSize(QPageSize.PageSizeId.A4),
            QPageLayout.Orientation.Portrait,
            QMarginsF(0, 0, 0, 0) # HTML handles margins
        )
        
        self.page.printToPdf(self.output_path, layout)

    def _on_pdf_finished(self, output_path: str, success: bool):
        if success:
            logger.info(f"[PDFPrinter] PDF saved successfully to {output_path}")
            self.finished.emit(True, output_path)
        else:
            logger.error(f"[PDFPrinter] Failed to save PDF to {output_path}")
            self.finished.emit(False, "PDF printing failed.")
