"""
Export Worker
Background thread for running intensive file conversions.
"""
from PyQt6 import QtCore
from pathlib import Path
from services.export.html_exporter import PDFToHTMLConverter
from core.logger import logger

class HTMLConversionWorker(QtCore.QThread):
    finished = QtCore.pyqtSignal(bool, str) # success, message/path
    progress = QtCore.pyqtSignal(str)
    
    def __init__(self, pdf_path: str, output_path: str):
        super().__init__()
        self.pdf_path = pdf_path
        self.output_path = output_path
        
    def run(self):
        try:
            self.progress.emit("Initializing converter...")
            converter = PDFToHTMLConverter(self.pdf_path)
            
            self.progress.emit("Processing pages (this may take a while)...")
            html_content = converter.convert(progress_callback=self.progress.emit)
            
            self.progress.emit("Saving file...")
            with open(self.output_path, "w", encoding="utf-8") as f:
                f.write(html_content)
                
            self.finished.emit(True, self.output_path)
            
        except Exception as e:
            logger.exception("HTML Conversion failed")
            self.finished.emit(False, str(e))
