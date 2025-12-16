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

# Try to import WebEngine (but don't fail if it doesn't work)
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
    logger.info("[MainWindow] QtWebEngineWidgets imported successfully")
except ImportError as e:
    logger.warning(f"[MainWindow] QtWebEngineWidgets not available: {e}. PreviewPanel will use fallback.")
except Exception as e:
    logger.warning(f"[MainWindow] Error importing QtWebEngineWidgets: {e}. PreviewPanel will use fallback.")
from services.ocr.formula_detector import FormulaDetector
from services.ocr.image_to_latex import ImageToLatex
from services.ocr.latex_to_mathml import LatexToMathML
from services.ocr.word_detector import WordDetector
from services.pdf_loader.pdf_reader import PDFReader
from services.pdf_loader.pdf_renderer import PDFRenderer
from services.exporters.xml_writer import XMLWriter
from ui.bounding_overlay import BoundingOverlay
from ui.enhanced_sidebar import EnhancedSidebar
from ui.notes_page import NotesPage
from ui.pdf_viewer import PDFViewer
from ui.preview_panel import PreviewPanel
from ui.settings_dialog import SettingsDialog
from ui.snips_page import SnipsPage
from ui.topbar import TopBar
from utils.file_utils import ensure_directories
from utils.image_utils import crop_image


class MainWindow(QtWidgets.QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        ensure_directories()
        self.setWindowTitle("Mathpix Clone")
        self.resize(1600, 900)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a1a;
            }
        """)

        self.pdf_reader = PDFReader()
        self.pdf_renderer = PDFRenderer()
        self.detector = FormulaDetector()
        self.word_detector = WordDetector()
        self.latex_ocr = ImageToLatex()
        self.latex_mathml = LatexToMathML()
        self.xml_writer = XMLWriter()
        self.show_word_boxes = False  # Toggle for showing word boxes

        # UI Components
        self.sidebar = EnhancedSidebar()
        self.pdf_viewer = PDFViewer()
        self.preview_panel = PreviewPanel()
        self.snips_page = SnipsPage()
        self.notes_page = NotesPage()
        self.overlay = BoundingOverlay(self.pdf_viewer.scene)
        self._last_selected_region: dict | None = None  # Store last selected region for download
        
        # Current PDF tracking
        self.current_pdf_path: str | None = None
        self.current_page_images: List[Path] = []
        # Store extracted formulas page-wise: {page_num: [{"bbox": {...}, "latex": "...", "mathml": "...", "image_path": "..."}, ...]}
        self.extracted_formulas: dict[int, List[dict]] = {}

        # Create stacked widget for view switching
        self.view_stack = QtWidgets.QStackedWidget()
        
        # Create different views
        self.home_view = self._create_home_view()
        self.files_view = self._create_files_view()
        self.notes_view_widget = QtWidgets.QWidget()
        notes_layout = QtWidgets.QVBoxLayout(self.notes_view_widget)
        notes_layout.addWidget(self.notes_page)
        
        # PDFs view (main PDF viewer with toolbar)
        pdfs_view = QtWidgets.QWidget()
        pdfs_main_layout = QtWidgets.QVBoxLayout(pdfs_view)
        pdfs_main_layout.setContentsMargins(0, 0, 0, 0)
        pdfs_main_layout.setSpacing(0)
        
        # Toolbar for PDFs view - Modern design
        pdfs_toolbar = QtWidgets.QFrame()
        pdfs_toolbar.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border-bottom: 1px solid #2d2d2d;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
                border: none;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #3a3a3a;
                color: #888;
            }
            QPushButton:checked {
                background-color: #005a9e;
            }
        """)
        toolbar_layout = QtWidgets.QHBoxLayout(pdfs_toolbar)
        toolbar_layout.setContentsMargins(16, 10, 16, 10)
        toolbar_layout.setSpacing(12)
        toolbar_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter)
        
        upload_toolbar_btn = QtWidgets.QPushButton("📄 Upload PDF")
        upload_toolbar_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        upload_toolbar_btn.setFixedHeight(44)
        upload_toolbar_btn.setMinimumWidth(140)
        upload_toolbar_btn.clicked.connect(lambda: self.sidebar.upload_btn.click())
        toolbar_layout.addWidget(upload_toolbar_btn)
        
        # Separator
        separator1 = QtWidgets.QFrame()
        separator1.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        separator1.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        separator1.setStyleSheet("color: #3a3a3a;")
        toolbar_layout.addWidget(separator1)
        
        # Zoom controls with proper icons
        from PyQt6.QtGui import QIcon, QFont, QPixmap, QPainter
        from PyQt6.QtWidgets import QStyle
        from PyQt6.QtCore import Qt
        
        # Create zoom out icon (minus sign)
        zoom_out_pixmap = QPixmap(20, 20)
        zoom_out_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(zoom_out_pixmap)
        painter.setPen(Qt.GlobalColor.white)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawLine(5, 10, 15, 10)
        painter.end()
        zoom_out_btn = QtWidgets.QPushButton("Zoom Out")
        zoom_out_btn.setIcon(QIcon(zoom_out_pixmap))
        zoom_out_btn.setToolTip("Zoom Out")
        zoom_out_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        zoom_out_btn.setFixedHeight(44)
        zoom_out_btn.setMinimumWidth(110)
        zoom_out_btn.setIconSize(QtCore.QSize(20, 20))
        zoom_out_btn.clicked.connect(lambda: self.pdf_viewer.scale(0.8, 0.8))
        toolbar_layout.addWidget(zoom_out_btn)
        
        # Fit to Window button with icon
        zoom_fit_btn = QtWidgets.QPushButton("Fit to Screen")
        zoom_fit_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogListView)
        zoom_fit_btn.setIcon(zoom_fit_icon)
        zoom_fit_btn.setToolTip("Fit to Window")
        zoom_fit_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        zoom_fit_btn.setFixedHeight(44)
        zoom_fit_btn.setMinimumWidth(130)
        zoom_fit_btn.setIconSize(QtCore.QSize(16, 16))
        zoom_fit_btn.clicked.connect(self._fit_pdf_to_window)
        toolbar_layout.addWidget(zoom_fit_btn)
        
        # Create zoom in icon (plus sign)
        zoom_in_pixmap = QPixmap(20, 20)
        zoom_in_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(zoom_in_pixmap)
        painter.setPen(Qt.GlobalColor.white)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawLine(10, 5, 10, 15)  # Vertical line
        painter.drawLine(5, 10, 15, 10)  # Horizontal line
        painter.end()
        zoom_in_btn = QtWidgets.QPushButton("Zoom In")
        zoom_in_btn.setIcon(QIcon(zoom_in_pixmap))
        zoom_in_btn.setToolTip("Zoom In")
        zoom_in_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        zoom_in_btn.setFixedHeight(44)
        zoom_in_btn.setMinimumWidth(110)
        zoom_in_btn.setIconSize(QtCore.QSize(20, 20))
        zoom_in_btn.clicked.connect(lambda: self.pdf_viewer.scale(1.2, 1.2))
        toolbar_layout.addWidget(zoom_in_btn)
        
        # Separator
        separator2 = QtWidgets.QFrame()
        separator2.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        separator2.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        separator2.setStyleSheet("color: #3a3a3a;")
        toolbar_layout.addWidget(separator2)
        
        toolbar_layout.addStretch()
        
        pdfs_main_layout.addWidget(pdfs_toolbar)
        
        # PDF viewer and preview
        pdfs_content_layout = QtWidgets.QHBoxLayout()
        pdfs_content_layout.setContentsMargins(0, 0, 0, 0)
        pdfs_content_layout.addWidget(self.pdf_viewer, stretch=1)
        pdfs_content_layout.addWidget(self.preview_panel, stretch=0)
        pdfs_main_layout.addLayout(pdfs_content_layout, stretch=1)
        
        # Snips view
        snips_view = QtWidgets.QWidget()
        snips_layout = QtWidgets.QVBoxLayout(snips_view)
        snips_layout.addWidget(self.snips_page)
        
        # Add views to stack
        self.view_stack.addWidget(self.home_view)  # 0 - Home
        self.view_stack.addWidget(self.files_view)  # 1 - Files
        self.view_stack.addWidget(self.notes_view_widget)  # 2 - Notes
        self.view_stack.addWidget(pdfs_view)  # 3 - PDFs
        self.view_stack.addWidget(snips_view)  # 4 - Snips
        
        # Main layout
        central = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Left sidebar
        layout.addWidget(self.sidebar, stretch=0)
        
        # Center: Stacked views
        layout.addWidget(self.view_stack, stretch=1)
        
        self.setCentralWidget(central)

        # Start with Home view and highlight Home in sidebar
        self.view_stack.setCurrentIndex(0)
        self.sidebar.set_active_nav("home")

        self._connect_signals()

    def _connect_signals(self) -> None:
        # Sidebar signals
        self.sidebar.upload_requested.connect(self.load_pdf)
        self.sidebar.pdf_selected.connect(self._on_pdf_selected)
        self.sidebar.navigation_changed.connect(self._handle_navigation)
        self.sidebar.settings_btn.clicked.connect(self._open_settings)
        self.sidebar.formula_selected.connect(self._on_formula_selected)
        
        # Overlay signals
        self.overlay.region_selected.connect(self.ocr_region)
        self.overlay.formula_selected.connect(self._on_formula_clicked)
        self.overlay.show_context_menu.connect(self._show_formula_context_menu)
        
        # PDF viewer context menu for downloading selected regions
        self.pdf_viewer.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.pdf_viewer.customContextMenuRequested.connect(self._show_pdf_viewer_context_menu)
        
        # Preview panel signals
        self.preview_panel.copy_mathml_requested.connect(self._copy_to_clipboard)
        self.preview_panel.export_requested.connect(self._export_mathml)
        
        # Snips and notes
        self.snips_page.insert_requested.connect(self.notes_page.insert_formula)

    def _on_pdf_selected(self, path: str) -> None:
        """Handle PDF selection from sidebar - switch to PDFs view and load."""
        self.view_stack.setCurrentIndex(3)  # Switch to PDFs view
        self.sidebar.set_active_nav("pdfs")
        self.sidebar.set_selected_pdf(path)  # Highlight selected PDF in list
        self.load_pdf(path)

    def load_pdf(self, path: str) -> None:
        """Load and render PDF."""
        try:
            self.sidebar.set_status(f"⏳ Loading {Path(path).name}...")
            QtWidgets.QApplication.processEvents()  # Update UI
            self.current_pdf_path = path
            pages = self.pdf_reader.read_pdf(path)
            self.sidebar.set_status(f"🔄 Rendering pages...")
            QtWidgets.QApplication.processEvents()
            images = self.pdf_renderer.render_pages(pages)
            if images:
                self.current_page_images = images
                self.pdf_viewer.load_pages(images)
                # Store image paths in overlay for coordinate conversion
                self._update_overlay_image_paths()
                self.sidebar.set_status(f"🔍 Detecting formulas...")
                QtWidgets.QApplication.processEvents()
                self.run_detection(images)
                # Add to sidebar list if not already there
                self.sidebar._add_pdf_to_list(path)
                self.sidebar.set_selected_pdf(path)  # Highlight the loaded PDF
                self.sidebar.set_status(f"✅ Loaded {Path(path).name}")
            else:
                self.sidebar.set_status("❌ No images rendered")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to load PDF: %s", exc)
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to load PDF:\n{exc}")
            self.sidebar.set_status(f"❌ Load failed: {Path(path).name}")

    def run_detection(self, images: List[Path]) -> None:
        """Detect formulas only and automatically extract MathML for each."""
        self.extracted_formulas = {}  # Clear previous extractions
        total_formulas = 0
        
        for page_num, image_path in enumerate(images, start=1):
            # Find the corresponding pixmap item for this image
            pixmap_item = None
            for item in self.pdf_viewer._page_items:
                if item.data(0) == str(image_path):
                    pixmap_item = item
                    break
            
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
                    logger.info("Detected %d formulas on page %d", len(filtered_formulas), page_num)
                    
                    # Automatically extract MathML for each formula
                    page_formulas = []
                    for idx, formula in enumerate(filtered_formulas):
                        self.sidebar.set_status(f"📝 Extracting formula {idx+1}/{len(filtered_formulas)} from page {page_num}...")
                        QtWidgets.QApplication.processEvents()
                        
                        try:
                            # Crop and extract
                            crop_path = crop_image(image_path, formula)  # type: ignore[arg-type]
                            latex = self.latex_ocr.image_to_latex(crop_path)
                            mathml = self.latex_mathml.convert(latex) if latex and latex.strip() and latex != r"\text{OCR failed}" and latex != r"\text{No text detected}" else ""
                            
                            page_formulas.append({
                                "bbox": formula,
                                "latex": latex if latex else "",
                                "mathml": mathml if mathml else "",
                                "image_path": str(image_path),
                                "crop_path": str(crop_path),
                                "formula_id": f"page{page_num}_formula{idx+1}"
                            })
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("Failed to extract formula %d on page %d: %s", idx+1, page_num, exc)
                            # Still add it with empty values
                            page_formulas.append({
                                "bbox": formula,
                                "latex": "",
                                "mathml": "",
                                "image_path": str(image_path),
                                "crop_path": "",
                                "formula_id": f"page{page_num}_formula{idx+1}"
                            })
                    
                    self.extracted_formulas[page_num] = page_formulas
                    total_formulas += len(page_formulas)
                    
            except Exception as exc:  # noqa: BLE001
                logger.warning("Formula detection failed for page %d: %s", page_num, exc)
                self.extracted_formulas[page_num] = []
        
        # Update status and display formulas (even if empty)
        if total_formulas > 0:
            self.sidebar.set_status(f"✅ Extracted {total_formulas} formulas from {len(images)} pages")
        else:
            self.sidebar.set_status("⚠ No formulas detected")
        
        # Always update sidebar to show formulas (or empty state)
        self._update_formulas_display()
    
    def _update_formulas_display(self) -> None:
        """Update the sidebar to display extracted formulas page-wise."""
        self.sidebar.update_formulas_display(self.extracted_formulas)
        logger.info("Extracted formulas: %d pages", len(self.extracted_formulas))
        for page_num, formulas in self.extracted_formulas.items():
            logger.info("Page %d: %d formulas", page_num, len(formulas))

    def ocr_region(self, image_path: Path, bbox: dict[str, int | str]) -> None:
        """Crop region, OCR, convert, and add to snips."""
        try:
            self.sidebar.set_status("🔄 Processing selection...")
            QtWidgets.QApplication.processEvents()
            
            # Validate bbox
            if bbox.get("w", 0) < 5 or bbox.get("h", 0) < 5:
                self.sidebar.set_status("⚠ Selection too small")
                return
            
            crop_path = crop_image(image_path, bbox)  # type: ignore[arg-type]
            
            # Store crop path and bbox for potential download
            self._last_selected_region = {"crop_path": crop_path, "bbox": bbox, "image_path": image_path}
            
            self.sidebar.set_status("📝 Extracting text...")
            QtWidgets.QApplication.processEvents()
            
            latex = self.latex_ocr.image_to_latex(crop_path)
            
            # Check if we got a meaningful result
            if not latex or latex.strip() == "" or latex == r"\text{OCR failed}" or latex == r"\text{No text detected}":
                # Show the debug image path if available
                debug_path = crop_path.parent / f"{crop_path.stem}_debug_original.png"
                debug_msg = ""
                if debug_path.exists():
                    debug_msg = f"\n\nDebug image saved to:\n{debug_path}\n\nPlease check if the crop region is correct."
                
                self.sidebar.set_status("⚠ OCR failed - Tesseract couldn't read formula")
                error_latex = r"\text{OCR failed - Tesseract cannot read mathematical formulas well. Try selecting a clearer region or use a specialized math OCR service.}"
                error_mathml = '<math xmlns="http://www.w3.org/1998/Math/MathML"><mtext>OCR failed - Tesseract cannot read mathematical formulas well</mtext></math>'
                self.preview_panel.update_preview(str(crop_path), error_latex, error_mathml)
                
                # Show helpful message
                QtWidgets.QMessageBox.information(
                    self, 
                    "OCR Limitation", 
                    f"Tesseract OCR is designed for regular text, not mathematical formulas.\n\n"
                    f"It cannot reliably read complex formulas with:\n"
                    f"- Subscripts and superscripts\n"
                    f"- Greek letters\n"
                    f"- Special mathematical symbols\n\n"
                    f"For better results, consider:\n"
                    f"1. Using a specialized math OCR service (like Mathpix API)\n"
                    f"2. Manually typing the LaTeX\n"
                    f"3. Selecting simpler, clearer formula regions{debug_msg}"
                )
                return
            
            self.sidebar.set_status("🔢 Processing equation...")
            QtWidgets.QApplication.processEvents()
            
            # Process through strict pipeline to get clean MathML (handles LaTeX → MathML conversion)
            from services.ocr.strict_pipeline import StrictMathpixPipeline
            from core.logger import logger
            
            pipeline = StrictMathpixPipeline()
            # Log the exact LaTeX being passed to strict pipeline (for debugging corruption)
            logger.info("[MAIN] Processing LaTeX through strict pipeline: %s", latex[:100])
            logger.debug("[MAIN] Full LaTeX being processed: %s", latex)
            result = pipeline.process_latex(latex)
            
            # Log pipeline results for debugging
            pipeline_log = result.get("log", [])
            if pipeline_log:
                logger.info("[MAIN] Strict pipeline log (last 5 lines): %s", "\n".join(pipeline_log[-5:]))
            
            # Use pipeline results
            clean_latex = result.get("clean_latex", latex)  # Use original if no clean version
            mathml = result.get("mathml", "")
            is_valid = result.get("is_valid", False)
            
            logger.info("[MAIN] Strict pipeline result: is_valid=%s, clean_latex length=%d, mathml length=%d", 
                       is_valid, len(clean_latex), len(mathml))
            
            # If pipeline didn't produce valid MathML, log warning but don't fallback to direct conversion
            # (direct conversion might produce corrupted MathML)
            if not mathml or not is_valid:
                logger.warning("[MAIN] Strict pipeline did not produce valid MathML - corruption may be present")
                if result.get("validation_errors"):
                    logger.warning("[MAIN] Validation errors: %s", result.get("validation_errors")[:3])
                # Don't use direct conversion - it might produce corrupted MathML
                # mathml = self.latex_mathml.convert(latex)
            
            # Update preview panel with clean LaTeX and MathML
            # Pass validation status so PreviewPanel trusts pipeline's validation
            self.preview_panel.update_preview(str(crop_path), clean_latex, mathml, is_valid=is_valid)
            
            record = {
                "id": bbox.get("id", "eq"),
                "latex": clean_latex,  # Use clean LaTeX from pipeline
                "mathml": mathml,
                "x": bbox["x"],
                "y": bbox["y"],
                "w": bbox["w"],
                "h": bbox["h"],
                "image": str(crop_path),
            }
            self.snips_page.add_snip(record)
            self.notes_page.insert_formula(clean_latex)  # Use clean LaTeX
            self.sidebar.set_status("✅ Selection processed")
        except Exception as exc:  # noqa: BLE001
            # Best-effort: never block the user; show whatever we could extract
            from core.logger import logger
            logger.exception("OCR region failed: %s", exc)
            error_msg = str(exc)
            # Build a minimal fallback so preview still shows something
            fallback_latex = latex if "latex" in locals() else r"\text{No text}"
            fallback_mathml = f'<math xmlns="http://www.w3.org/1998/Math/MathML"><mtext>{fallback_latex}</mtext></math>'
            self.preview_panel.update_preview(str(crop_path) if "crop_path" in locals() else None, fallback_latex, fallback_mathml)
            # Non-blocking status update
            self.sidebar.set_status("⚠ Processed with fallback (MathML best-effort)")
            # Optionally surface a gentle message without stopping flow
            logger.warning("MathML best-effort fallback used: %s", error_msg)

    def _create_home_view(self) -> QtWidgets.QWidget:
        """Create a Mathpix-inspired home/dashboard view."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(32, 24, 32, 32)
        layout.setSpacing(18)

        # Hero text
        title = QtWidgets.QLabel("Welcome back")
        title.setStyleSheet("font-size: 28px; font-weight: 700; color: #f3f4f6;")
        subtitle = QtWidgets.QLabel("Upload PDFs, notes, or snips to start extracting MathML.")
        subtitle.setStyleSheet("font-size: 15px; color: #cdd2dc;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Search bar (visual only)
        search_box = QtWidgets.QLineEdit()
        search_box.setPlaceholderText("Search your content")
        search_box.setClearButtonEnabled(True)
        search_box.setFixedHeight(40)
        search_box.setStyleSheet("""
            QLineEdit {
                background: #12141a;
                border: 1px solid #242832;
                border-radius: 8px;
                color: #e9ecf2;
                padding-left: 12px;
            }
            QLineEdit:focus { border: 1px solid #3a82f7; }
        """)
        layout.addWidget(search_box)

        # Source chips
        chips = QtWidgets.QHBoxLayout()
        chips.setSpacing(10)
        def chip(text: str, checked: bool = False) -> QtWidgets.QPushButton:
            b = QtWidgets.QPushButton(text)
            b.setCheckable(True)
            b.setChecked(checked)
            b.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet("""
                QPushButton {
                    background: #12141a;
                    color: #dfe3ec;
                    border: 1px solid #242832;
                    border-radius: 16px;
                    padding: 8px 14px;
                }
                QPushButton:checked {
                    background: #1f6feb;
                    border: 1px solid #1f6feb;
                    color: #ffffff;
                }
            """)
            return b
        chips.addWidget(chip("All", True))
        chips.addWidget(chip("Notes"))
        chips.addWidget(chip("PDFs"))
        chips.addWidget(chip("Snips"))
        chips.addStretch()
        layout.addLayout(chips)

        # Upload cards row
        cards = QtWidgets.QHBoxLayout()
        cards.setSpacing(14)
        def card(title_text: str, subtitle_text: str, color: str) -> QtWidgets.QFrame:
            frame = QtWidgets.QFrame()
            frame.setStyleSheet(f"""
                QFrame {{
                    background: #0f1116;
                    border: 1px solid #1e222d;
                    border-radius: 12px;
                }}
                QLabel {{ color: #dfe3ec; }}
            """)
            v = QtWidgets.QVBoxLayout(frame)
            v.setContentsMargins(14, 12, 14, 12)
            v.setSpacing(6)
            title_lbl = QtWidgets.QLabel(title_text)
            title_lbl.setStyleSheet("font-size: 16px; font-weight: 700;")
            title_lbl.setWordWrap(True)
            subtitle_lbl = QtWidgets.QLabel(subtitle_text)
            subtitle_lbl.setStyleSheet("font-size: 13px; color: #aab2c2;")
            subtitle_lbl.setWordWrap(True)
            btn = QtWidgets.QPushButton(f"Upload {title_text}")
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {color};
                    color: #ffffff;
                    border: none;
                    border-radius: 8px;
                    padding: 10px 14px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {color};
                    opacity: 0.9;
                }}
            """)
            if title_text.lower() == "pdf":
                btn.clicked.connect(lambda: self.sidebar.upload_btn.click())
            v.addWidget(title_lbl)
            v.addWidget(subtitle_lbl)
            v.addStretch()
            v.addWidget(btn)
            return frame

        cards.addWidget(card("PDF", "Upload PDFs to extract formulas, LaTeX, and MathML.", "#1f6feb"))
        cards.addWidget(card("Note", "Keep quick notes alongside your extractions.", "#7b7df3"))
        cards.addWidget(card("Snip", "Save cropped formulas for reuse and copying.", "#2ca66f"))
        cards.addStretch()
        layout.addLayout(cards)

        # Drag/drop area
        drop = QtWidgets.QFrame()
        drop.setFixedHeight(160)
        drop.setStyleSheet("""
            QFrame {
                border: 1px dashed #2f3542;
                border-radius: 12px;
                background: #0f1116;
            }
        """)
        drop_layout = QtWidgets.QVBoxLayout(drop)
        drop_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        drop_label = QtWidgets.QLabel("Paste or drag & drop a file here")
        drop_label.setStyleSheet("color: #dfe3ec; font-size: 14px;")
        drop_sub = QtWidgets.QLabel("Supported: PDF, PNG, JPG, MD (drag & drop UI only; processing via uploads)")
        drop_sub.setStyleSheet("color: #9aa3b5; font-size: 12px;")
        drop_layout.addWidget(drop_label)
        drop_layout.addWidget(drop_sub)
        layout.addWidget(drop)

        # Recent placeholder
        recent_title = QtWidgets.QLabel("Recent")
        recent_title.setStyleSheet("font-size: 16px; font-weight: 600; color: #dfe3ec;")
        layout.addWidget(recent_title)
        recent_placeholder = QtWidgets.QLabel("No recent items yet. Upload a PDF or snip to see it here.")
        recent_placeholder.setStyleSheet("color: #9aa3b5; font-size: 13px;")
        layout.addWidget(recent_placeholder)

        layout.addStretch()
        return widget

    def _create_files_view(self) -> QtWidgets.QWidget:
        """Create the files view."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QtWidgets.QLabel("Files")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: white;")
        layout.addWidget(title)
        
        info = QtWidgets.QLabel("Your uploaded PDFs will appear here. Click 'PDFs' in the sidebar to view them.")
        info.setStyleSheet("font-size: 14px; color: #aaa; padding: 10px;")
        layout.addWidget(info)
        
        layout.addStretch()
        return widget

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
            self.preview_panel.update_preview(crop_path, latex, mathml)
            self.sidebar.set_status(f"✅ Showing formula from page")
        else:
            # If crop doesn't exist, try to create it
            image_path = formula_data.get("image_path", "")
            bbox = formula_data.get("bbox", {})
            if image_path and bbox:
                try:
                    crop_path = crop_image(Path(image_path), bbox)  # type: ignore[arg-type]
                    self.preview_panel.update_preview(str(crop_path), latex, mathml)
                    self.sidebar.set_status(f"✅ Showing formula")
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to crop formula: %s", exc)
                    self.sidebar.set_status("⚠ Failed to show formula")
    
    def _show_formula_context_menu(self, image_path: Path, bbox: dict, screen_pos: QtCore.QPoint) -> None:
        """Show context menu for formula (like Mathpix)."""
        # Process the formula first to get LaTeX and MathML
        try:
            crop_path = crop_image(image_path, bbox)  # type: ignore[arg-type]
            latex = self.latex_ocr.image_to_latex(crop_path)
            mathml = self.latex_mathml.convert(latex)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to process formula for context menu: %s", exc)
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to process formula:\n{exc}")
            return
        
        # Create context menu
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #3c3c3c;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 30px 8px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0078d4;
            }
        """)
        
        # COPY action
        copy_action = menu.addAction("📋 COPY")
        copy_action.triggered.connect(lambda: self._copy_to_clipboard(latex))
        
        # LaTeX action
        latex_action = menu.addAction("\\{} LaTeX")
        latex_action.triggered.connect(lambda: self._copy_to_clipboard(latex))
        
        # MathML action
        mathml_action = menu.addAction("<ml> MathML")
        mathml_action.triggered.connect(lambda: self._copy_to_clipboard(mathml))
        
        menu.addSeparator()
        
        # DOWNLOAD section header
        download_menu = menu.addMenu("⬇️ DOWNLOAD")
        
        # Download LaTeX/MathML
        download_formula_action = download_menu.addAction("📄 Formula (LaTeX/MathML)")
        download_formula_action.triggered.connect(lambda: self._export_formula(latex, mathml))
        
        # Download Image (like Mathpix)
        download_image_action = download_menu.addAction("🖼️ Image")
        download_image_action.triggered.connect(lambda: self._download_image(crop_path, bbox))
        
        # Image action (show in preview)
        image_action = menu.addAction("🖼️ Image")
        image_action.triggered.connect(lambda: self._preview_formula(crop_path, latex, mathml))
        
        # Show menu at cursor position
        menu.exec(screen_pos)
    
    def _export_formula(self, latex: str, mathml: str) -> None:
        """Export formula to file (used by context menu)."""
        # Use existing export method
        self._export_mathml(latex, mathml)
    
    def _preview_formula(self, crop_path: Path, latex: str, mathml: str) -> None:
        """Show formula in preview panel."""
        self.preview_panel.update_preview(str(crop_path), latex, mathml)
    
    def _download_image(self, crop_path: Path, bbox: dict) -> None:
        """Download cropped image to user-selected location (like Mathpix)."""
        from PyQt6.QtWidgets import QFileDialog
        import shutil
        
        # Suggest filename based on bbox and page
        suggested_name = f"diagram_{bbox.get('id', 'region')}.png"
        
        # Open file save dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Image",
            suggested_name,
            "PNG Images (*.png);;JPEG Images (*.jpg);;All Files (*.*)"
        )
        
        if file_path:
            try:
                shutil.copy2(crop_path, file_path)
                logger.info("Downloaded image to: %s", file_path)
                self.sidebar.set_status(f"✅ Image saved to {Path(file_path).name}")
            except Exception as exc:
                logger.exception("Failed to download image: %s", exc)
                QtWidgets.QMessageBox.warning(
                    self,
                    "Download Failed",
                    f"Failed to save image:\n{exc}"
                )
    
    def _show_pdf_viewer_context_menu(self, pos: QtCore.QPoint) -> None:
        """Show context menu when right-clicking on PDF viewer (for downloading selected regions/diagrams)."""
        # Check if there's a recently selected region
        if not self._last_selected_region:
            return
        
        crop_path = self._last_selected_region.get("crop_path")
        bbox = self._last_selected_region.get("bbox")
        
        if not crop_path or not bbox:
            return
        
        # Create context menu
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #3c3c3c;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 30px 8px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0078d4;
            }
        """)
        
        # DOWNLOAD section
        download_menu = menu.addMenu("⬇️ DOWNLOAD")
        download_image_action = download_menu.addAction("🖼️ Image")
        download_image_action.triggered.connect(lambda: self._download_image(crop_path, bbox))
        
        # Show menu at cursor position
        global_pos = self.pdf_viewer.mapToGlobal(pos)
        menu.exec(global_pos)

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
        """Export MathML to file."""
        from services.exporters.mathml_writer import MathMLWriter
        writer = MathMLWriter()
        try:
            path = writer.write_mathml(mathml)
            QtWidgets.QMessageBox.information(self, "Exported", f"MathML exported to:\n{path}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Export failed: %s", exc)
            QtWidgets.QMessageBox.critical(self, "Export Error", f"Failed to export:\n{exc}")


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

