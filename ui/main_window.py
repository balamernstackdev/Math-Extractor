"""Main PyQt6 window for Mathpix clone."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List

# Import logger early for use in WebEngine initialization
from core.logger import logger

# CRITICAL: Do NOT import Qt at module level in EXE mode!
# The runtime hook (pyi_rth_pyqt6.py) sets up DLL paths FIRST.
# Module-level imports happen during import, which can be before PATH is fully set.
# We'll import Qt inside functions instead.

# In EXE mode, just set environment variables (don't import Qt yet)
if getattr(sys, 'frozen', False):
    import os
    base_path = Path(sys._MEIPASS)
    
    # Set QtWebEngine process path (no import needed)
    webengine_process = base_path / 'PyQt6' / 'Qt6' / 'bin' / 'QtWebEngineProcess.exe'
    if webengine_process.exists():
        os.environ['QTWEBENGINEPROCESS_PATH'] = str(webengine_process)
        logger.info(f"[MainWindow] Set QTWEBENGINEPROCESS_PATH: {webengine_process}")
    else:
        logger.warning(f"[MainWindow] QtWebEngineProcess.exe not found at: {webengine_process}")
    
    # Add PyQt6 bin to DLL directory (Windows Python 3.8+)
    pyqt6_bin = base_path / 'PyQt6' / 'Qt6' / 'bin'
    if pyqt6_bin.exists():
        try:
            os.add_dll_directory(str(pyqt6_bin))
            logger.info(f"[MainWindow] Added PyQt6 bin to DLL directory: {pyqt6_bin}")
        except (AttributeError, OSError):
            # Fallback to PATH for older Python or if add_dll_directory fails
            current_path = os.environ.get('PATH', '')
            os.environ['PATH'] = str(pyqt6_bin) + os.pathsep + current_path
            logger.info(f"[MainWindow] Added PyQt6 bin to PATH: {pyqt6_bin}")

# Now import Qt - PATH/DLL directory should be set by runtime hook
from PyQt6 import QtCore, QtGui, QtWidgets

# CRITICAL: Do NOT import QtWebEngineWidgets at module level in EXE mode!
# The import happens too early and can cause "cannot import type" errors.
# PreviewPanel will import it lazily when needed, after QApplication is created.
# This ensures all Qt DLLs are fully loaded before WebEngine tries to import.
from services.ocr.formula_detector import FormulaDetector
from services.ocr.image_to_latex import ImageToLatex
from services.ocr.latex_to_mathml import LatexToMathML
from services.ocr.word_detector import WordDetector
from services.pdf_loader.pdf_reader import PDFReader
from services.pdf_loader.pdf_renderer import PDFRenderer
from services.exporters.xml_writer import XMLWriter
from services.exporters.asciimath_converter import AsciiMathConverter
from services.exporters.table_exporter import TableExporter
from services.exporters.markdown_exporter import MarkdownExporter
from ui.bounding_overlay import BoundingOverlay
from ui.enhanced_sidebar import EnhancedSidebar
from ui.dashboard_view import DashboardView
from ui.upload_view import UploadView
from ui.preview_view import PreviewView
from ui.history_view import HistoryView
from ui.notes_page import NotesPage
from ui.pdfs_panel import PDFsPanel
from ui.pdf_viewer import PDFViewer
from ui.preview_panel import PreviewPanel
from ui.formula_list_panel import FormulaListPanel
from ui.settings_dialog import SettingsDialog
from ui.snips_page import SnipsPage
from ui.styles import Theme
from utils.file_utils import ensure_directories
from utils.image_utils import crop_image
from services.ocr.strict_pipeline import StrictMathpixPipeline
from services.persistence.snip_repository import SnipRepository
from services.persistence.history_repository import HistoryRepository
from services.ocr.ocr_worker import OCRWorker


# ============================================================================
# PDF PROCESSING WORKER THREAD
# ============================================================================

# ============================================================================
# PDF PROCESSING WORKER THREAD (PRIORITY QUEUE BASED)
# ============================================================================
from queue import PriorityQueue
import time

class PDFProcessingWorker(QtCore.QThread):
    """
    Background worker for PDF processing with PRIORITY QUEUE support.
    Allows prioritizing visible pages over sequential ones.
    """
    
    # Signals
    status_update = QtCore.pyqtSignal(str)
    page_rendered = QtCore.pyqtSignal(int, Path)
    formula_detected = QtCore.pyqtSignal(int, list)
    finished_success = QtCore.pyqtSignal(dict)
    finished_error = QtCore.pyqtSignal(str)
    
    def __init__(self, pdf_path: str, pdf_reader, pdf_renderer, detector, latex_ocr, latex_mathml):
        super().__init__()
        self.pdf_path = pdf_path
        self.detector = detector
        self._cancelled = False
        
        # Priority Queue: (priority, page_num)
        # Priority 0 = Highest (Visible), 10 = High (Next), 100 = Normal (Sequential)
        self.queue = PriorityQueue()
        self.processed_pages = set()
        self.total_pages = 0
        
    def cancel(self):
        """Cancel the processing."""
        self._cancelled = True
        
    def prioritize_page(self, page_num: int):
        """Bump a page to the top of the queue if not already processed."""
        if page_num not in self.processed_pages:
            # Add with highest priority (0).
            # Duplicate entries are fine; we check processed_pages before working.
            self.queue.put((0, page_num))
            logger.info(f"[Worker] Prioritized page {page_num}")

    def _get_poppler_path(self) -> str | None:
        """Resolve Poppler path (supports PyInstaller EXE)."""
        import sys
        if getattr(sys, "frozen", False):
            poppler = Path(sys._MEIPASS) / "poppler" / "bin"
            if poppler.exists():
                return str(poppler)
        
        from core.config import settings
        if settings.poppler_path:
            return str(settings.poppler_path)
        return None

    def run(self):
        """Execute PDF processing using Priority Queue."""
        from core.config import settings
        import fitz  # PyMuPDF
        
        try:
            doc = fitz.open(self.pdf_path)
            self.total_pages = len(doc)
            
            # 1. Populate Queue with sequential pages (Priority 100)
            for i in range(1, self.total_pages + 1):
                self.queue.put((100, i))
                
            self.status_update.emit(f"🔄 Queued {self.total_pages} pages...")
            
            while not self.queue.empty():
                if self._cancelled:
                    break
                    
                # Get next page (lowest priority number = first)
                priority, page_num = self.queue.get()
                
                if page_num in self.processed_pages:
                    continue
                
                # --- PROCESS PAGE ---
                try:
                    # A. Render Page
                    img_path = settings.uploads_dir / f"page_{page_num}.png"
                    img_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Use PyMuPDF for speed
                    page = doc.load_page(page_num - 1)
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    pix.save(str(img_path))
                    
                    self.page_rendered.emit(page_num, img_path)
                    
                    # B. Detect Formulas
                    if self._cancelled: break
                    
                    # Only update status if it's a high priority task to avoid spamming
                    if priority < 50:
                        self.status_update.emit(f"🔍 Detecting formulas on page {page_num}...")
                    
                    formulas = self.detector.detect_formulas(img_path)
                    if formulas:
                        self.formula_detected.emit(page_num, formulas)
                        
                    self.processed_pages.add(page_num)
                    
                    # Tiny sleep to allow UI to breathe
                    time.sleep(0.01)
                    
                except Exception as e:
                    logger.error(f"Failed to process page {page_num}: {e}")
            
            doc.close()
            
            if not self._cancelled:
                self.finished_success.emit({})
                self.status_update.emit("✅ PDF processing complete")
            
        except Exception as exc:
            logger.exception("PDF Worker crashed: %s", exc)
            self.finished_error.emit(str(exc))

from ui.batch_queue_panel import BatchQueuePanel

class MainWindow(QtWidgets.QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()


        ensure_directories()
        self.setWindowTitle("MathML Extractor")
        self.resize(1600, 900)
        
        # Set Application Icon
        # Set Application Icon
        icon_name = "icon.ico"
        if getattr(sys, 'frozen', False):
            # In EXE, look in _MEIPASS
            icon_path = Path(sys._MEIPASS) / icon_name
        else:
            # In Dev, look in root
            icon_path = Path(__file__).parent.parent / icon_name

        if icon_path.exists():
           self.setWindowIcon(QtGui.QIcon(str(icon_path)))
        
        # Apply Global Theme
        self.setStyleSheet(Theme.get_qss())

        self.pdf_reader = PDFReader()
        self.pdf_renderer = PDFRenderer()
        self.detector = FormulaDetector()
        self.word_detector = WordDetector()
        self.latex_ocr = ImageToLatex()
        self.latex_mathml = LatexToMathML()
        self.xml_writer = XMLWriter()
        self.asciimath_converter = AsciiMathConverter()
        self.table_exporter = TableExporter()
        self.markdown_exporter = MarkdownExporter()
        self.snip_repo = SnipRepository() # Persistence
        self.history_repo = HistoryRepository() # History log
        self._ocr_workers = [] # Track active OCR workers
        self.show_word_boxes = False
        
        # Recent files storage
        self.settings = QtCore.QSettings("MathpixClone", "App")
        self.recent_files = self._load_recent_files()

        self.sidebar = EnhancedSidebar()
        self.pdfs_panel = PDFsPanel()
        
        # PRE-WARM OCR (Asynchronous)
        QtCore.QTimer.singleShot(100, self._warm_up_ocr)
        self.pdfs_panel.hide() # Hidden by default
        self.pdf_viewer = PDFViewer()
        self.preview_panel = PreviewPanel()
        self.formula_list_panel = FormulaListPanel()
        
        # Batch Queue
        self.batch_queue = BatchQueuePanel()
        self.batch_queue.items_added.connect(self._handle_batch_added)
        self.batch_queue.hide() # Toggleable
        
        # --- Views ---
        self.dashboard_view = DashboardView()
        self.upload_view = UploadView()
        self.preview_view = PreviewView(self.pdf_viewer, self.preview_panel)
        self.snips_page = SnipsPage()
        self.history_view = HistoryView()
        # Notes as a hidden logic component for now, or unified with Snips
        self.notes_page = NotesPage() 

        # --- Overlay ---
        self.overlay = BoundingOverlay(self.pdf_viewer.scene)
        self._last_selected_region: dict | None = None
        
        # --- State ---
        self.current_pdf_path: str | None = None
        self.current_page_images: List[Path] = []
        self.extracted_formulas: dict[int, List[dict]] = {}
        self.pdf_worker: PDFProcessingWorker | None = None
        self._processing_pages: dict[int, Path] = {}

        self._init_layout()
        self._connect_signals()
        
        # Start at Home
        self.sidebar.set_active_nav("home")
        # Load recent data into dashboard and sidebar
        recent_pdfs = [p for p in self.recent_files if Path(p).exists() and Path(p).suffix.lower() == ".pdf"]
        self.sidebar.load_pdf_list(recent_pdfs)
        self.dashboard_view.update_recent_pdfs(recent_pdfs)
        
        self._load_saved_snips() # Load persisted snips
        self._load_history()     # Load persisted history
        
        # Update dashboard with real snips
        self.dashboard_view.update_recent_snips(self.snip_repo.get_all())

    def _init_layout(self):
        """Initialize the split layout: Sidebar | Content | BatchQueue (Right)."""
        central = QtWidgets.QWidget()
        main_layout = QtWidgets.QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 1. Sidebar (Left)
        main_layout.addWidget(self.sidebar)
        
        # 2. View Stack (Center)
        self.view_stack = QtWidgets.QStackedWidget()
        
        # Map views to indices
        # 0: Dashboard (Home)
        self.view_stack.addWidget(self.dashboard_view)
        # 1: Upload (Files)
        self.view_stack.addWidget(self.upload_view)
        # 2: Notes
        self.view_stack.addWidget(self.notes_page)
        # 3: PDFs/Preview
        self.view_stack.addWidget(self.preview_view)
        # 4: Snips
        self.view_stack.addWidget(self.snips_page)
        # 5: History
        self.view_stack.addWidget(self.history_view)
        
        main_layout.addWidget(self.view_stack, stretch=1)
        
        # 3. Batch Queue (Right - Toggleable)
        main_layout.addWidget(self.batch_queue)
        
        self.setCentralWidget(central)
        
        # Drag & Drop support for main window
        self.setAcceptDrops(True)

        self._active_batch_workers = []
        self.MAX_BATCH_WORKERS = 2

    def _handle_batch_added(self, items: list):
        """Handle items added to batch queue."""
        self.batch_queue.show()
        self._process_batch_queue()

    def _process_batch_queue(self):
        """Process next pending item in queue."""
        # 1. Check worker capacity
        if len(self._active_batch_workers) >= self.MAX_BATCH_WORKERS:
            return

        # 2. Get next pending item
        next_item = self.batch_queue.get_next_pending()
        if not next_item:
            return # No more pending items

        item_id, file_path = next_item
        logger.info(f"[Batch] Starting processing for {Path(file_path).name} (ID: {item_id})")

        # 3. Update UI status
        self.batch_queue.update_item_status(item_id, "Processing...", "processing")

        # 4. Start Worker
        worker = OCRWorker(file_path, self.latex_ocr, self.latex_mathml)
        
        # Connect signals
        worker.result_ready.connect(lambda p, l, m, v, c, a: self._on_batch_item_finished(item_id, p, l, m, v, c))
        worker.error_occurred.connect(lambda e, p: self._on_batch_item_error(item_id, e))
        
        # Track worker
        self._active_batch_workers.append(worker)
        # Remove from active list when finished (regardless of success/error)
        worker.finished.connect(lambda: self._on_batch_worker_cleanup(worker))
        
        worker.start()
        
        # 5. Recursively try to start more workers if capacity allows
        self._process_batch_queue()

    def _on_batch_item_finished(self, item_id: str, path: str, latex: str, mathml: str, is_valid: bool, confidence: float):
        """Handle successful batch item processing."""
        logger.info(f"[Batch] Item finished: {item_id}")
        self.batch_queue.update_item_status(item_id, "Completed", "completed")
        
        # Auto-save to History
        self.history_repo.add(latex, mathml, is_valid, path)
        self._load_history() # Refresh UI
        
    def _on_batch_item_error(self, item_id: str, error_msg: str):
        """Handle failed batch item."""
        logger.warning(f"[Batch] Item failed: {item_id} - {error_msg}")
        self.batch_queue.update_item_status(item_id, "Failed", "failed")

    def _on_batch_worker_cleanup(self, worker):
        """Clean up worker and trigger next item."""
        if worker in self._active_batch_workers:
            self._active_batch_workers.remove(worker)
        
        # Trigger next processing cycle
        self._process_batch_queue()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()
            
    def dropEvent(self, event):
        urls = event.mimeData().urls()
        paths = [url.toLocalFile() for url in urls if Path(url.toLocalFile()).suffix.lower() in ['.pdf', '.png', '.jpg', '.jpeg']]
        
        if not paths:
            return

        # Case 1: Single PDF -> Open as usual
        if len(paths) == 1 and Path(paths[0]).suffix.lower() == '.pdf':
            self.load_pdf_and_preview(paths[0])
            return
            
        # Case 2: Multiple Images -> Add to Batch Queue
        images = [p for p in paths if Path(p).suffix.lower() in ['.png', '.jpg', '.jpeg']]
        
        if len(images) > 1:
            self.batch_queue.add_files(images)
            self.batch_queue.show()
            self._process_batch_queue()
        elif len(images) == 1:
            # Check if we should add to queue (e.g. if queue is already open/processing)
            if self.batch_queue.isVisible() and self.batch_queue.queue:
                self.batch_queue.add_files(images)
            else:
                # Direct simple OCR for single image
                self.load_image_direct(images[0])

    def load_image_direct(self, image_path: str):
        """Load a single image directly for OCR."""
        self.sidebar.set_active_nav("pdfs")
        self.view_stack.setCurrentIndex(3)
        self.preview_panel.show_loading("Processing image...")
        self.preview_panel._show_image_preview(image_path)
        
        # Start OCR
        worker = OCRWorker(image_path, self.latex_ocr, self.latex_mathml)
        worker.result_ready.connect(self.preview_panel.update_preview)
        
        # Connect History Save
        worker.result_ready.connect(self._save_to_history_on_complete)
        
        worker.start()
        # Keep reference
        self._ocr_workers.append(worker)
        worker.finished.connect(lambda: self._ocr_workers.remove(worker) if worker in self._ocr_workers else None)

    def _connect_signals(self) -> None:
        # Navigation
        self.sidebar.navigation_changed.connect(self._handle_navigation)
        
        # Upload from sidebar
        self.sidebar.upload_requested.connect(self.load_pdf_and_preview)
        self.sidebar.pdf_selected.connect(self._on_pdf_selected)
        
        # Upload from view
        self.upload_view.file_selected.connect(self.load_pdf_and_preview)
        
        # Dashboard upload cards
        self.dashboard_view.upload_pdf_clicked.connect(self._open_file_dialog)
        self.dashboard_view.upload_note_clicked.connect(self._open_file_dialog)
        self.dashboard_view.upload_snip_clicked.connect(self._open_file_dialog)
        
        # Preview view upload
        # Preview view upload
        # (This was duplicated below, removed here)

        
        # Dashboard interactions
        self.dashboard_view.equation_selected.connect(self._on_dashboard_equation_selected)
        self.history_view.equation_selected.connect(self._on_dashboard_equation_selected)
        
        # Overlay / Snip
        self.overlay.selection_started.connect(lambda: self.preview_panel.show_loading("Selecting region..."))
        self.overlay.region_selected.connect(self.ocr_region)
        self.overlay.region_updated.connect(self.ocr_region)
        self.overlay.formula_selected.connect(self._on_formula_clicked)
        self.overlay.show_context_menu.connect(self.pdf_viewer.show_context_menu)
        self.pdf_viewer.status_message.connect(self.sidebar.set_status)
        
        # Preview Panel interactions
        self.preview_panel.copy_mathml_requested.connect(self._copy_to_clipboard)
        self.preview_panel.copy_tsv_requested.connect(self._handle_copy_tsv)
        self.preview_panel.copy_asciimath_requested.connect(self._handle_copy_asciimath)
        self.preview_panel.export_requested.connect(self._export_mathml)
        self.preview_panel.save_snip_requested.connect(self._on_save_snip_requested)
        
        # Snips
        self.snips_page.insert_requested.connect(self.notes_page.insert_formula)
        self.snips_page.snip_deleted.connect(self._on_snip_deleted)
        self.snips_page.export_requested.connect(self._on_batch_export)
        
        # PDF Viewer Actions
        self.pdf_viewer.action_requested.connect(self._handle_viewer_action)
        self.pdf_viewer.visible_pages_changed.connect(self._on_visible_pages_changed)
        
        # Preview View actions
        self.preview_view.upload_requested.connect(self._open_file_dialog)
        
        # Settings button
        self.sidebar.settings_btn.clicked.connect(self._open_settings)

    def _on_visible_pages_changed(self, visible_pages: list):
        """Handle scroll events: prioritize processing of visible pages."""
        if self.pdf_worker and self.pdf_worker.isRunning():
            for page_num in visible_pages:
                self.pdf_worker.prioritize_page(page_num)

    def _handle_navigation(self, view_id: str):
        """Switch views based on sidebar selection."""
        if view_id == "settings":
            self._open_settings()
            return
        
        view_map = {
            "home": 0,      # Dashboard
            "files": 1,     # Upload
            "notes": 2,     # Notes editor
            "pdfs": 3,      # Preview
            "snips": 4,     # Snips grid
            "history": 5    # History list (moved to 6)
        }
        
        if view_id in view_map:
            self.view_stack.setCurrentIndex(view_map[view_id])

    def load_pdf_and_preview(self, path: str):
        """Load a PDF and switch to Preview view."""
        self.load_pdf(path)
        self.sidebar.set_active_nav("pdfs")
        self._handle_navigation("pdfs")
    
    def _on_pdf_selected(self, path: str) -> None:
        """Handle PDF selection from sidebar - switch to PDFs view and load."""
        self.view_stack.setCurrentIndex(3)  # Switch to Preview view (index 3 now)
        self.sidebar.set_active_nav("pdfs")
        self.load_pdf(path)
    
    def _open_file_dialog(self):
        """Open file dialog for PDF upload from dashboard."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select PDF", "", "PDF Files (*.pdf)"
        )
        if path:
            self.load_pdf_and_preview(path)
    
    def _populate_dashboard_samples(self):
        """Add sample equations to dashboard for testing."""
        from datetime import datetime, timedelta
        
        sample_equations = [
            {
                'mathml': '<math><mrow><mi>x</mi><mo>=</mo><mfrac><mrow><mo>−</mo><mi>b</mi><mo>±</mo><msqrt><mrow><msup><mi>b</mi><mn>2</mn></msup><mo>−</mo><mn>4</mn><mi>a</mi><mi>c</mi></mrow></msqrt></mrow><mrow><mn>2</mn><mi>a</mi></mrow></mfrac></mrow></math>',
                'latex': r'x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}',
                'is_valid': True,
                'has_warnings': False,
                'equation_type': 'single-line',
                'timestamp': datetime.now() - timedelta(minutes=5),
                'is_starred': True
            },
            {
                'mathml': '<math><mtable columnalign="right left"><mtr><mtd><mi>x</mi></mtd><mtd><mo>=</mo><mi>a</mi></mtd></mtr><mtr><mtd><mi>y</mi></mtd><mtd><mo>=</mo><mi>b</mi></mtd></mtr></mtable></math>',
                'latex': r'x = a \\\\ y = b',
                'is_valid': True,
                'has_warnings': False,
                'equation_type': 'align',
                'timestamp': datetime.now() - timedelta(minutes=10),
                'is_starred': False
            },
            {
                'mathml': '<math><mrow><mi>E</mi><mo>=</mo><mi>m</mi><msup><mi>c</mi><mn>2</mn></msup></mrow></math>',
                'latex': r'E = mc^2',
                'is_valid': True,
                'has_warnings': False,
                'equation_type': 'single-line',
                'timestamp': datetime.now() - timedelta(hours=2),
                'is_starred': True
            },
            {
                'mathml': '<math><mrow><munderover><mo>∑</mo><mrow><mi>i</mi><mo>=</mo><mn>1</mn></mrow><mi>n</mi></munderover><msub><mi>x</mi><mi>i</mi></msub></mrow></math>',
                'latex': r'\\sum_{i=1}^{n} x_i',
                'is_valid': False,
                'has_warnings': False,
                'equation_type': 'single-line',
                'timestamp': datetime.now() - timedelta(days=1),
                'is_starred': False
            }
        ]
        
        self.dashboard_view.set_equations(sample_equations)
        self.history_view.set_equations(sample_equations)
        
        # Populate Snips (needs slight mapping)
        # Mock image for snips
        import shutil
        mock_img = self.settings.fileName() + "_mock.png" # Just a placeholder
        
        for eq in sample_equations:
            record = {
                "id": f"snip_{eq['timestamp']}",
                "latex": eq['latex'],
                "mathml": eq['mathml'],
                "image": "assets/icon.ico",  # Placeholder if actual crop not available
            }
            # Only add if image exists, or handle graceful fallback in snips_page
            # Ideally create a dummy image or check if we have one
            # For now, let's skip populating snips with dummy data that might crash due to missing image
            pass
    

    
    def _on_dashboard_equation_selected(self, equation_data: dict):
        """Handle equation selection from dashboard."""
        # TODO: Open equation in preview panel or new view
        logger.info(f"Dashboard equation selected: {equation_data.get('equation_type', 'unknown')}")
        
        # For now, just switch to preview view
        self.view_stack.setCurrentIndex(3)  # Preview view (index 3 now)
        
        # Update preview panel with the equation
        self.preview_panel.update_preview(
            image_path=equation_data.get('image_path'),
            latex=equation_data.get('latex', ''),
            mathml=equation_data.get('mathml', ''),
            is_valid=equation_data.get('is_valid', False)
        )





    def load_pdf(self, path: str) -> None:
        """Load and render PDF asynchronously."""
        # Check if already loaded to prevent redundant rendering
        if self.current_pdf_path and str(Path(self.current_pdf_path).resolve()) == str(Path(path).resolve()):
            logger.info("PDF %s already loaded, skipping reload", path)
            self.sidebar.set_status(f"✅ Ready: {Path(path).name}")
            return

        # Cancel any existing worker
        if self.pdf_worker and self.pdf_worker.isRunning():
            self.pdf_worker.cancel()
            self.pdf_worker.wait(1000)  # Wait up to 1 second
        
        try:
            self.current_pdf_path = path
            self.current_page_images = []
            self.extracted_formulas = {}
            self._processing_pages = {}
            
            # Clear PDF viewer and formula panel
            self.pdf_viewer.clear_pages()
            self.preview_view.thumbnail_sidebar.clear()
            self.preview_panel.clear_all()

            
            # Create and start worker thread
            self.pdf_worker = PDFProcessingWorker(
                path,
                self.pdf_reader,
                self.pdf_renderer,
                self.detector,
                self.latex_ocr,
                self.latex_mathml
            )
            
            # Connect signals
            self.pdf_worker.status_update.connect(self.sidebar.set_status)
            self.pdf_worker.page_rendered.connect(self._on_page_rendered)
            self.pdf_worker.formula_detected.connect(self._on_formulas_detected)
            self.pdf_worker.finished_success.connect(self._on_pdf_processing_finished)
            self.pdf_worker.finished_error.connect(self._on_pdf_processing_error)
            
            # Start processing in background
            self.pdf_worker.start()
            
            # Add to recent files
            self._add_recent_file(path, "pdf")
            
            # Update Dashboard and Sidebar
            self.sidebar._add_pdf_to_list(path)
            recent_pdfs = [p for p in self.recent_files if Path(p).exists() and Path(p).suffix.lower() == ".pdf"]
            self.dashboard_view.update_recent_pdfs(recent_pdfs)
            
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to start PDF loading: %s", exc)
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to load PDF:\n{exc}")
            self.sidebar.set_status(f"❌ Load failed: {Path(path).name}")
    
    def _on_page_rendered(self, page_num: int, image_path: Path):
        """Handle page rendered signal - add to viewer immediately."""
        self._processing_pages[page_num] = image_path
        self.current_page_images.append(image_path)
        
        # Add page to viewer immediately (incremental loading)
        self.pdf_viewer.add_page(image_path)
        self.preview_view.thumbnail_sidebar.add_page(page_num - 1)
        self.preview_view.thumbnail_sidebar.set_page_status(page_num - 1, 'processing')
        
        # Update overlay paths
        self._update_overlay_image_paths()
    
    def _on_formulas_detected(self, page_num: int, formulas: list):
        """Handle formulas detected signal - draw boxes immediately."""
        image_path = self._processing_pages.get(page_num)
        if image_path:
            # Find the corresponding pixmap item
            pixmap_item = None
            for item in self.pdf_viewer._page_items:
                if item.data(0) == str(image_path):
                    pixmap_item = item
                    break
            
            if pixmap_item:
                self.overlay.draw_formula_boxes(image_path, formulas, pixmap_item)
                
            # Update sidebar status
            self.preview_view.thumbnail_sidebar.set_page_status(page_num - 1, 'done')
    
    def _on_formula_extracted(self, page_num: int, formula_idx: int, formula_data: dict):
        """Handle formula extracted signal - update formulas dict."""
        if page_num not in self.extracted_formulas:
            self.extracted_formulas[page_num] = []
        # Ensure list is long enough
        while len(self.extracted_formulas[page_num]) <= formula_idx:
            self.extracted_formulas[page_num].append({})
        self.extracted_formulas[page_num][formula_idx] = formula_data
        
        # Update sidebar incrementally
        self._update_formulas_display()
    
    def _on_pdf_processing_finished(self, extracted_formulas: dict):
        """Handle PDF processing finished successfully."""
        self.extracted_formulas = extracted_formulas
        self._update_formulas_display()
        self.sidebar.set_status(f"✅ Loaded {Path(self.current_pdf_path).name if self.current_pdf_path else 'PDF'}")
        logger.info("PDF processing completed successfully")
    
    def _on_pdf_processing_error(self, error_msg: str):
        """Handle PDF processing error."""
        logger.error("PDF processing error: %s", error_msg)
        QtWidgets.QMessageBox.warning(self, "PDF Processing Error", f"An error occurred while processing the PDF:\n{error_msg}")
        self.sidebar.set_status(f"❌ Processing failed: {error_msg}")

    def detect_current_page(self) -> None:
        """Detect formulas on the currently visible page."""
        if not self.current_page_images:
            QtWidgets.QMessageBox.warning(self, "No PDF", "Please upload a PDF first.")
            return

        idx = self.pdf_viewer.get_active_page_index()
        
        # Get path directly from viewer to ensure sync
        image_path = self.pdf_viewer.get_page_image_path(idx)
        if not image_path:
             self.sidebar.set_status("⚠ Could not determine page image")
             return

        # Ensure we are passing Path objects
        image_path = Path(image_path)
        
        if not image_path.exists():
            self.sidebar.set_status(f"❌ Image file missing on disk: {image_path.name}")
            QtWidgets.QMessageBox.warning(self, "File Missing", f"The image for page {idx+1} could not be found.\nPlease reload the PDF.")
            return

        self.sidebar.set_status(f"🔍 Scanning page {idx+1}...")
        # Run detection incrementally on this single page
        # We assume the user wants to ADD these results, or update them.
        # Since we key by page number, it will overwrite the page's entry but keep others.
        self.run_detection([image_path], clear_existing=False)
        self.sidebar.set_status(f"✅ Scanned page {idx+1}")

    def run_detection(self, images: List[Path], clear_existing: bool = True) -> None:
        """Detect formulas only and automatically extract MathML for each."""
        if clear_existing:
            self.extracted_formulas = {}
            self.formula_list_panel.clear_formulas()
        
        # Initialize pipeline once if possible, or per run
        pipeline = StrictMathpixPipeline()
        total_formulas = 0
        
        for page_num, image_path in enumerate(images, start=1):
            # If incremental, key by actual page number if possible, but images list implies sequence.
            # However, if we pass a single image, "page_num" here might be 1 but it corresponds to actual page X.
            # We need to map back to actual page number if possible.
            # Strategy: pass a list of tuples (page_num, image_path) instead of just images?
            # Or simplified: if we are scanning specific pages, we assume the caller handles logic.
            # Let's rely on finding the item in viewer to get the REAL page number.
            
            # Find the corresponding pixmap item for this image
            pixmap_item = None
            actual_page_num = page_num # default
            
            for item in self.pdf_viewer._page_items:
                if item.data(0) == str(image_path):
                    pixmap_item = item
                    actual_page_num = item.data(1) # get stored page num
                    break
            
            # Use actual_page_num for storage
            page_key = actual_page_num
            
            if not image_path.exists():
                logger.error("Image file not found for page %d: %s", actual_page_num, image_path)
                self.sidebar.set_status(f"❌ Failed to find image for page {actual_page_num}")
                continue
            
            # Detect formulas only (skip word detection)
            try:
                formulas = self.detector.detect_formulas(image_path)
                # Filter formulas to only include reasonable-sized ones
                filtered_formulas = []
                for formula in formulas:
                    w, h = formula["w"], formula["h"]
                    # Filter: reasonable size, not too small
                    if w * h > 200 and w > 30 and h > 10:
                        filtered_formulas.append(formula)
                
                if filtered_formulas and pixmap_item:
                    # Draw formula boxes on the PDF
                    self.overlay.draw_formula_boxes(image_path, filtered_formulas, pixmap_item)
                    logger.info("Detected %d formulas on page %d", len(filtered_formulas), actual_page_num)
                    
                    # Automatically extract MathML for each formula
                    page_formulas = []
                    for idx, formula in enumerate(filtered_formulas):
                        self.sidebar.set_status(f"📝 Extracting formula {idx+1}/{len(filtered_formulas)} from page {actual_page_num}...")
                        QtWidgets.QApplication.processEvents()
                        
                        try:
                            # Crop and extract
                            crop_path = crop_image(image_path, formula)  # type: ignore[arg-type]
                            latex = self.latex_ocr.image_to_latex(crop_path)
                            
                            # Use Strict Pipeline for robust conversion (matches Mathpix quality)
                            result = pipeline.process_latex(latex)
                            
                            # Use clean LaTeX and verified MathML from pipeline
                            final_latex = result.clean_latex if result.success else latex
                            final_mathml = result.clean_mathml if result.success else ""
                            is_valid = result.success
                            
                            # Log validation issues if any
                            if not result.success:
                                logger.warning("Pipeline validation failed for formula %d: %s", idx+1, result.error_message)

                            is_multiline = r"\\" in final_latex
                            
                            # Check for OCR failure
                            if latex == r"\text{OCR failed}" or latex == r"\text{No text detected}":
                                final_latex = ""
                                final_mathml = ""
                                is_valid = False

                            page_formulas.append({
                                "bbox": formula,
                                "latex": final_latex,
                                "mathml": final_mathml,
                                "image_path": str(image_path),
                                "crop_path": str(crop_path),
                                "formula_id": f"page{actual_page_num}_formula{idx+1}",
                                "page": actual_page_num,
                                "multiline": is_multiline,
                                "is_valid": is_valid
                            })
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("Failed to extract formula %d on page %d: %s", idx+1, actual_page_num, exc)
                            # Still add it with empty values
                            page_formulas.append({
                                "bbox": formula,
                                "latex": "",
                                "mathml": "",
                                "image_path": str(image_path),
                                "crop_path": "",
                                "formula_id": f"page{actual_page_num}_formula{idx+1}",
                                "page": actual_page_num,
                                "multiline": False,
                                "is_valid": False
                            })
                    
                    self.extracted_formulas[actual_page_num] = page_formulas
                    total_formulas += len(page_formulas)
                    
                    # Add to formula card panel (append if incremental)
                    self.formula_list_panel.add_formulas(page_formulas)
                    
            except Exception as exc:  # noqa: BLE001
                logger.warning("Formula detection failed for page %d: %s", actual_page_num, exc)
                self.extracted_formulas[actual_page_num] = []
        
        # Update status and display formulas (even if empty)
        if total_formulas > 0:
            self.sidebar.set_status(f"✅ Extracted {total_formulas} formulas from {len(images)} pages")
        else:
            self.sidebar.set_status("⚠ No formulas detected")
        
        # Always update sidebar to show formulas (or empty state)
        pass

    def _handle_viewer_action(self, action: str, data: dict) -> None:
        """Handle actions from PDF Viewer context menu (Copy LaTeX, etc.)."""
        image_path = Path(data.get("image_path", ""))
        bbox = data.get("bbox", {})
        
        if not image_path.exists() or not bbox:
            return

        # Common OCR processing
        if action.startswith("copy_"):
            try:
                self.sidebar.set_status("🔄 Processing for copy...")
                QtWidgets.QApplication.processEvents()
                
                crop_path = crop_image(image_path, bbox)
                latex = self.latex_ocr.image_to_latex(crop_path)
                
                # Strict pipeline for better quality
                from services.ocr.strict_pipeline import StrictMathpixPipeline
                pipeline = StrictMathpixPipeline()
                result = pipeline.process_latex(latex)
                
                clean_latex = result.get("clean_latex", latex)
                mathml = result.get("mathml", "")
                
                text_to_copy = ""
                if action == "copy_latex":
                    text_to_copy = clean_latex
                elif action == "copy_mathml":
                    text_to_copy = mathml
                elif action == "copy_asciimath":
                    text_to_copy = self.asciimath_converter.convert(clean_latex)
                    self.sidebar.set_status("✅ Copied ASCHII") # Keeping it short
                
                if text_to_copy:
                    self._copy_to_clipboard(text_to_copy)
                    self.sidebar.set_status(f"✅ Copied {action.replace('copy_', '').upper()}")
                else:
                    self.sidebar.set_status("⚠ Copy failed - no text")
                    
            except Exception as exc:
                logger.exception("Action %s failed: %s", action, exc)
                self.sidebar.set_status("❌ Action failed")
    
    def _handle_copy_tsv(self, latex: str) -> None:
        """Convert LaTeX table to TSV and copy to clipboard."""
        try:
            tsv = self.table_exporter.to_tsv(latex)
            if tsv:
                self._copy_to_clipboard(tsv)
                self.sidebar.set_status("✅ Table copied as TSV (Excel-ready)")
            else:
                # Fallback to normal copy if not a valid table structure
                self._copy_to_clipboard(latex)
                self.sidebar.set_status("ℹ Copied raw LaTeX (No tabular structure found)")
        except Exception as e:
            logger.error(f"TSV copy failed: {e}")
            self.sidebar.set_status("❌ TSV Copy failed")

    def _handle_copy_asciimath(self, latex: str) -> None:
        """Convert LaTeX to AsciiMath and copy to clipboard."""
        try:
            asciimath = self.asciimath_converter.convert(latex)
            self._copy_to_clipboard(asciimath)
            self.sidebar.set_status("✅ Copied as AsciiMath")
        except Exception as e:
            logger.error(f"AsciiMath copy failed: {e}")
            self.sidebar.set_status("❌ AsciiMath Copy failed")

    def _update_formulas_display(self) -> None:
        """Update the formula list panel with all extracted formulas."""
        pass

    def _on_batch_export(self) -> None:
        """Handle batch export of all snips to Markdown."""
        snips = self.snip_repo.get_all()
        if not snips:
            QtWidgets.QMessageBox.information(self, "Export", "No snips to export.")
            return
            
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Snips to Markdown", "math_snips_export.md", "Markdown Files (*.md)"
        )
        
        if file_path:
            success = self.markdown_exporter.export(snips, Path(file_path))
            if success:
                self.sidebar.set_status(f"✅ Exported {len(snips)} snips to Markdown")
                QtWidgets.QMessageBox.information(self, "Export Success", f"Successfully exported {len(snips)} snips.")
            else:
                self.sidebar.set_status("❌ Export failed")
                QtWidgets.QMessageBox.critical(self, "Export Failed", "Failed to export snips.")

    def _on_formula_list_selection(self, formula_data: dict):
        """Handle selection from formula list."""
        latex = formula_data.get('latex', '')
        mathml = formula_data.get('mathml', '')
        crop_path = formula_data.get('crop_path', '')
        image_path = formula_data.get('image_path', '')
        is_valid = formula_data.get('is_valid', False)
        
        # Switch to detail view
        self.preview_view.show_preview()
        
        # Update preview panel
        self.preview_panel.update_preview(latex, mathml, is_valid=is_valid, image_path=crop_path or image_path)
        
        # Highlight in PDF
        if 'page' in formula_data:
             page_idx = int(formula_data['page']) - 1
             # Ensure visible
             # self.pdf_viewer.scroll_to_page(page_idx) # If such method exists
             pass
    
    def _on_formula_card_selected(self, formula_data: dict):
        """Handle formula card selection - update preview panel."""
        latex = formula_data.get('latex', '')
        mathml = formula_data.get('mathml', '')
        crop_path = formula_data.get('crop_path', '')
        is_valid = formula_data.get('is_valid', False)
        
        # Update preview panel
        self.preview_panel.update_preview(latex, mathml, is_valid=is_valid, image_path=crop_path)
        
        # Log selection
        formula_id = formula_data.get('formula_id', 'unknown')
        page = formula_data.get('page', '?')
        logger.info(f"Formula card selected: {formula_id} from page {page}")


    def _on_formula_clicked(self, image_path: Path, formula_data: dict) -> None:
        """Handle formula clicked on PDF overlay."""
        # Detect-only creates bboxes without latex. Trigger OCR if needed.
        latex = formula_data.get("latex")
        
        if not latex:
            # Run OCR on this specific region
            self.ocr_region(image_path, formula_data)
        else:
            # If we had latex (e.g. from cache or full OCR run), show it
            mathml = formula_data.get("mathml", "")
            crop_path = formula_data.get("crop_path", str(image_path)) # fallback
            self.preview_panel.update_preview(latex, mathml, is_valid=True, image_path=str(crop_path))


    # ============================================================================
    # ASYNC OCR PROCESSING
    # ============================================================================

    def ocr_region(self, image_path: Path, region_rect: dict) -> None:
        """Process a specific region of an image."""
        try:
            # Initialize _ocr_workers if not already done
            if not hasattr(self, '_ocr_workers'):
                self._ocr_workers = []

            # PREDICTIVE CANCELLATION: Cancel pending OCR tasks for the same panel
            if self._ocr_workers:
                logger.info(f"[MainWindow] Cancelling {len(self._ocr_workers)} pending OCR workers...")
                for old_worker in self._ocr_workers:
                    if old_worker.isRunning():
                        old_worker.requestInterruption()

            # 1. Update Preview to loading state
            self.sidebar.set_active_nav("pdfs")
            self._handle_navigation("pdfs")
            self.preview_panel.show_loading("Refining Selection...")
            
            # 2. Crop the image region
            crop_path = crop_image(image_path, region_rect)  # type: ignore[arg-type]
            if not crop_path:
                raise ValueError("Failed to crop image region")
                
            self.preview_panel._show_image_preview(str(crop_path))
            
            # 3. Determine modes
            is_handwriting = False
            is_table = False
            
            if hasattr(self.preview_panel, 'handwriting_mode_cb') and self.preview_panel.handwriting_mode_cb.isChecked():
                is_handwriting = True
                logger.info("[MainWindow] Scribble Mode active for this region")
            
            if hasattr(self.preview_panel, 'table_mode_cb') and self.preview_panel.table_mode_cb.isChecked():
                is_table = True
                logger.info("[MainWindow] Table Mode active for this region")

            # 4. Create and start worker
            worker = OCRWorker(str(crop_path), self.latex_ocr, StrictMathpixPipeline(), 
                               handwriting_mode=is_handwriting, 
                               table_mode=is_table)
            worker.partial_result_ready.connect(self._on_partial_ocr_result)
            worker.status_update.connect(self._on_ocr_status_update)
            worker.result_ready.connect(self._on_ocr_result)
            worker.error_occurred.connect(self._on_ocr_error)
            worker.finished.connect(lambda: self._cleanup_worker(worker))
            
            self._ocr_workers.append(worker)
            worker.start()
            
            logger.info(f"[MainWindow] Started background OCR worker for {crop_path.name}")
            
        except Exception as e:
            logger.exception(f"Failed to start OCR: {e}")
            self.sidebar.set_status(f"❌ Error: {str(e)[:50]}")
            # Ensure correct argument types for update_preview
            self.preview_panel.update_preview(r"\text{Initialization failed}", "", False, 0.0)


    def _on_ocr_result(self, image_path: str, latex: str, mathml: str, is_valid: bool, confidence: float = 0.0, ast_node=None):
        """Handle successful OCR/Pipeline result from worker."""
        try:
            self.sidebar.set_status("✅ Equation processed", mode="success")
            
            # Update Preview Panel with confidence AND AST
            # Correct signature: latex, mathml, is_valid, confidence, image_path, ast_data
            self.preview_panel.update_preview(latex, mathml, is_valid, confidence, image_path=image_path, ast_data=ast_node)
            
            # PERSIST IMAGE for history (temp to permanent)
            permanent_image = self._persist_image(image_path, "history_images")
            
            # Add to History Repository
            self.history_repo.add(
                latex=latex,
                mathml=mathml,
                image_path=permanent_image,
                is_valid=is_valid
            )
            

            # Update history view if visible
            if hasattr(self, 'history_view'):
                self.history_view.set_equations(self.history_repo.get_all())
            
        except Exception as e:
            logger.exception(f"Error handling OCR result: {e}")

    def _on_ocr_error(self, message: str, image_path: str = ""):
        """Handle OCR/Pipeline error from worker."""
        self.sidebar.set_status(f"❌ Processing failed: {message}", mode="error")
        # Update preview panel with error state
        self.preview_panel.update_preview(rf"\text{{Error: {message}}}", "", is_valid=False, image_path=None)
        logger.error(f"[MainWindow] OCR Worker error for {image_path}: {message}")

    def _on_partial_ocr_result(self, image_path: str, raw_latex: str):
        """Handle intermediate (fast) OCR results for instant feedback."""
        logger.info(f"[MainWindow] Progressive OCR: Received raw LaTeX ({len(raw_latex)} chars)")
            # Update UI immediately with raw LaTeX while refinement continues
        self.preview_panel.update_partial_preview(image_path, raw_latex)

    def _on_ocr_status_update(self, message: str):
        """Update sidebar status with progressive worker messages."""
        self.sidebar.set_status(f"🔄 {message}", mode="working")

    def _cleanup_worker(self, worker):
        """Remove finished worker from tracking list."""
        if hasattr(self, '_ocr_workers') and worker in self._ocr_workers:
            self._ocr_workers.remove(worker)
            logger.debug(f"[MainWindow] Cleaned up OCR worker. Active workers: {len(self._ocr_workers)}")

    def _warm_up_ocr(self):
        """Invoke OCR warm-up in a background thread."""
        logger.info("[MainWindow] Initiating background OCR warm-up...")
        import threading
        # We use a simple thread here because it's a one-off startup task
        # and doesn't need complex signal handling
        thread = threading.Thread(target=self.latex_ocr.warm_up, daemon=True)
        thread.start()

    # Legacy views removed (Home, Files)


    def _handle_navigation(self, nav_name: str) -> None:
        """Handle navigation changes."""
        logger.info("Navigation changed to: %s", nav_name)
        view_map = {
            "home": 0,
            "files": 1,
            "notes": 2,
            "pdfs": 3,
            "snips": 4,
        }
        index = view_map.get(nav_name)
        if index is not None:
            self.view_stack.setCurrentIndex(index)

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy text to clipboard."""
        QtWidgets.QApplication.clipboard().setText(text)
        # Lightweight feedback via tooltip near cursor
        cursor_pos = QtGui.QCursor.pos()
        QtWidgets.QToolTip.showText(cursor_pos, "Copied to clipboard", self)
    
    def _on_formula_clicked(self, image_path: Path, bbox: dict) -> None:
        """Handle formula click - process it immediately."""
        logger.info("Formula clicked: %s", image_path.name)
        self.ocr_region(image_path, bbox)
    
    def _on_formula_selected(self, formula_data: dict) -> None:
        """Handle formula selection from sidebar - show in preview panel."""
        crop_path = formula_data.get("crop_path", "")
        latex = formula_data.get("latex", "")
        mathml = formula_data.get("mathml", "")
        
        if crop_path and Path(crop_path).exists():
            self.preview_panel.update_preview(latex, mathml, image_path=crop_path)
            self.sidebar.set_status(f"✅ Showing formula from page")
        else:
            # If crop doesn't exist, try to create it
            image_path = formula_data.get("image_path", "")
            bbox = formula_data.get("bbox", {})
            if image_path and bbox:
                try:
                    crop_path = crop_image(Path(image_path), bbox)  # type: ignore[arg-type]
                    self.preview_panel.update_preview(latex, mathml, image_path=str(crop_path))
                    self.sidebar.set_status(f"✅ Showing formula")
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to crop formula: %s", exc)
                    self.sidebar.set_status("⚠ Failed to show formula")
    

    

    


    def _update_overlay_image_paths(self) -> None:
        """Update overlay with image paths from PDF viewer items."""
        self.overlay.image_paths.clear()
        for item in self.pdf_viewer._page_items:
            image_path_str = item.data(0)
            if image_path_str:
                self.overlay.image_paths[item] = Path(image_path_str)

    def _toggle_word_boxes(self, checked: bool) -> None:
        """Toggle word bounding boxes visibility."""
        self.show_word_boxes = checked
        self.toggle_boxes_btn.setText("👁️ Hide Words" if checked else "👁️ Show Words")
        
        # Redraw boxes with new visibility setting
        if self.current_page_images:
            for image_path in self.current_page_images:
                try:
                    words = self.word_detector.detect_words(image_path, min_confidence=30.0)
                    boxes = [
                        {
                            "x": word["x"],
                            "y": word["y"],
                            "w": word["w"],
                            "h": word["h"],
                            "id": f"word_{idx}",
                            "text": word["text"],
                            "confidence": word["confidence"],
                        }
                        for idx, word in enumerate(words)
                    ]
                    self.overlay.draw_boxes(image_path, boxes, show_boxes=self.show_word_boxes)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to toggle word boxes: %s", exc)

    def _load_recent_files(self) -> list:
        """Load recent files from QSettings."""
        recent = self.settings.value("recent_files", [])
        if recent is None:
            return []
        # Ensure it's a list
        if isinstance(recent, str):
            return [recent] if recent else []
        return recent if isinstance(recent, list) else []
    
    def _add_recent_file(self, path: str, file_type: str = "pdf") -> None:
        """Add a file to recent files list."""
        # Load current recent files
        recent = self._load_recent_files()
        
        # Remove if already exists (to move to top)
        if path in recent:
            recent.remove(path)
        
        # Add to beginning
        recent.insert(0, path)
        
        # Keep only last 10
        recent = recent[:10]
        
        # Save back to settings
        self.settings.setValue("recent_files", recent)
        logger.info(f"Added {file_type} to recent files: {path}")

    def _open_settings(self) -> None:
        """Open settings dialog."""
        dialog = SettingsDialog(self)
        if dialog.exec():
            # Reinitialize OCR services with new Tesseract path
            from services.ocr.image_to_latex import ImageToLatex
            from services.ocr.word_detector import WordDetector
            self.latex_ocr = ImageToLatex()
            self.word_detector = WordDetector()
            logger.info("Tesseract path updated, OCR services reinitialized")
    def _persist_image(self, source_path: str, subfolder: str = "images") -> str:
        """Copy a temporary image to permanent storage."""
        if not source_path:
            return ""
        
        try:
            from pathlib import Path
            import shutil
            src = Path(source_path)
            if not src.exists():
                logger.warning(f"[MainWindow] Source image not found for persistence: {source_path}")
                return source_path
                
            dest_dir = self.snip_repo.storage_dir / subfolder
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            # Use original filename
            dest_path = dest_dir / src.name
            
            # Copy file
            shutil.copy2(src, dest_path)
            logger.debug(f"[MainWindow] Persisted image: {src.name} -> {subfolder}")
            return str(dest_path)
        except Exception as e:
            logger.error(f"[MainWindow] Image persistence failed: {e}")
            return source_path

    def _fit_pdf_to_window(self) -> None:
        """Fit PDF pages to window width while maintaining aspect ratio."""
        if self.pdf_viewer.scene and self.pdf_viewer.scene.items():
            # Fit to width only, not height - so pages are readable
            items_rect = self.pdf_viewer.scene.itemsBoundingRect()
            viewport_width = self.pdf_viewer.viewport().width()
            
            if viewport_width > 0 and items_rect.width() > 0:
                # Calculate scale to fit width
                scale = (viewport_width - 40) / items_rect.width()
                self.pdf_viewer.resetTransform()
                self.pdf_viewer.scale(scale, scale)
                # Center vertically on first page
                self.pdf_viewer.ensureVisible(0, 0, 10, 10)

    def _export_mathml(self, mathml: str) -> None:
        """Export MathML to file (Word or XML)."""
        if not mathml:
            QtWidgets.QMessageBox.warning(self, "Export Error", "No content to export.")
            return

        try:
            # 1. Ask user for destination
            from datetime import datetime
            default_name = f"equation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            path_str, filter_used = QtWidgets.QFileDialog.getSaveFileName(
                self, 
                "Export Equation", 
                str(Path.home() / "Documents" / default_name),
                "MS Word Document (*.doc);;MathML XML (*.xml)"
            )
            
            if not path_str:
                return # Canceled
                
            path = Path(path_str)
            
            # 2. Export based on selection
            if filter_used.startswith("MS Word"):
                # Enforce .doc extension for our HTML-based trick
                if path.suffix.lower() not in ['.doc', '.docx']:
                    path = path.with_suffix('.doc')
                    
                from services.exporters.word_exporter import WordExporter
                exporter = WordExporter()
                out_path = exporter.export_to_word(mathml, path)
                msg = f"Word document saved to:\n{out_path}\n\nTip: Open this file with MS Word."
                
            else:
                # Default to XML
                if path.suffix.lower() != '.xml':
                    path = path.with_suffix('.xml')
                    
                # Standard write
                path.write_text(mathml, encoding="utf-8")
                out_path = path
                msg = f"MathML saved to:\n{out_path}"

            QtWidgets.QMessageBox.information(self, "Export Successful", msg)
            
        except Exception as exc:  # noqa: BLE001
            logger.exception("Export failed: %s", exc)
            QtWidgets.QMessageBox.critical(self, "Export Error", f"Failed to export:\n{exc}")

    def _on_dashboard_equation_selected(self, data: dict) -> None:
        """Handle selection from dashboard or history."""
        if data.get("type") == "pdf_jump":
            path = data.get("path")
            if path:
                self.load_pdf_and_preview(path)
            return

        # Regular equation selection
        latex = data.get('latex', '')
        mathml = data.get('mathml', '')
        # Handle both 'image' (snip repo) and 'image_path' (ocr_region/history)
        image_path = data.get('image') or data.get('image_path', '')
        is_valid = data.get('is_valid', True)
        confidence = data.get('confidence', 1.0) # Default to 100% if not stored
        
        # Switch to Preview view
        self.view_stack.setCurrentIndex(3)
        self.sidebar.set_active_nav("pdfs")
        
        # Update preview panel
        self.preview_panel.update_preview(
            latex=latex, 
            mathml=mathml, 
            is_valid=is_valid, 
            confidence=confidence, 
            image_path=str(image_path) if image_path else None
        )

    def _load_saved_snips(self):
        """Load snips from repository into UI."""
        try:
            snips = self.snip_repo.get_all()
            logger.info(f"Loading {len(snips)} saved snips")
            for snip in snips:
                self.snips_page.add_snip(snip)
        except Exception as e:
            logger.error(f"Failed to load saved snips: {e}")

    def _load_history(self):
        """Load history from repository into UI."""
        try:
            items = self.history_repo.get_all()
            logger.info(f"Loading {len(items)} history items")
            self.history_view.set_equations(items)
        except Exception as e:
            logger.error(f"Failed to load history: {e}")

    def _on_save_snip_requested(self, snip_data: dict) -> None:
        """Handle request to save a new snip."""
        logger.info("[MainWindow] Saving new snip: %s...", snip_data.get("latex", "")[:20])
        try:
            # PERSIST IMAGE for snip (move from temp to permanent)
            temp_image = snip_data.get("image") or snip_data.get("image_path")
            permanent_image = self._persist_image(temp_image, "snip_images")
            
            # 1. Save to repository (persistence)
            saved_record = self.snip_repo.add(
                latex=snip_data.get("latex", ""),
                mathml=snip_data.get("mathml", ""),
                image_path=permanent_image
            )
            
            # 2. Add to UI
            self.snips_page.add_snip(saved_record)
            
            # 3. Update dashboard
            self.dashboard_view.update_recent_snips(self.snip_repo.get_all())
            
            self.sidebar.set_status("✅ Snip Saved")
        except Exception as e:
            logger.error("Failed to save snip: %s", e)
            QtWidgets.QMessageBox.warning(self, "Save Error", f"Could not save snip: {e}")

    def _on_snip_deleted(self, snip_id: str) -> None:
        """Handle request to delete a snip from persistence."""
        logger.info(f"[MainWindow] Deleting snip from repo: {snip_id}")
        try:
            success = self.snip_repo.delete(snip_id)
            if success:
                self.sidebar.set_status("🗑️ Snip Deleted")
                # Update dashboard
                self.dashboard_view.update_recent_snips(self.snip_repo.get_all())
            else:
                logger.warning(f"Could not delete snip {snip_id} from repository (not found?)")
        except Exception as e:
            logger.error(f"Failed to delete snip: {e}")
            self.sidebar.set_status("❌ Delete Failed")

    # ============================================================================
    # NEW FUNCTIONALITY
    # ============================================================================

    # Legacy logic removed


    def _cleanup_worker(self, worker):
        """Cleanup finished worker to prevent memory leaks."""
        if hasattr(self, '_ocr_workers') and worker in self._ocr_workers:
            self._ocr_workers.remove(worker)
            worker.deleteLater()
            logger.debug(f"[MainWindow] Cleaned up worker. Remaining active: {len(self._ocr_workers)}")

def run_qt_app() -> None:
    """Launch the PyQt application."""
    # CRITICAL: Set attribute before creating QApplication for WebEngine
    # (Runtime hook should have set this, but set it here as backup)
    try:
        QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    except Exception as e:
        logger.warning(f"Could not set AA_ShareOpenGLContexts: {e}")
    
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

