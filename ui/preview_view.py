"""
Preview View Component
Combines PDF Viewer (Source) and Preview Panel (Result) in a split view.
"""

from PyQt6 import QtCore, QtGui, QtWidgets
from ui.preview_panel import PreviewPanel
from ui.pdf_viewer import PDFViewer
from ui.styles import Theme

from ui.sidebar_thumbnails import ThumbnailSidebar

class PreviewView(QtWidgets.QWidget):
    """
    Split view: Thumbnails (Left) | PDF Source (Center) | Result (Right).
    """
    
    upload_requested = QtCore.pyqtSignal()
    
    def __init__(self, pdf_viewer: PDFViewer, preview_panel: PreviewPanel, parent=None):
        super().__init__(parent)
        self.pdf_viewer = pdf_viewer
        self.preview_panel = preview_panel
        self.thumbnail_sidebar = ThumbnailSidebar()
        
        # Connect Navigation
        self.thumbnail_sidebar.page_selected.connect(self.pdf_viewer.scroll_to_page)
        
        self._build_ui()
        
    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Toolbar (Zoom, Fit, Page Nav)
        self.toolbar = self._create_toolbar()
        layout.addWidget(self.toolbar)
        
        # Splitter
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(1)
        self.splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {Theme.BORDER};
            }}
            QSplitter::handle:hover {{
                background: {Theme.ACCENT};
            }}
        """)
        
        # Left: Thumbnails (DISABLED PER USER REQUEST)
        # self.splitter.addWidget(self.thumbnail_sidebar)
        
        # Center: PDF Container
        pdf_container = QtWidgets.QWidget()
        pdf_layout = QtWidgets.QVBoxLayout(pdf_container)
        pdf_layout.setContentsMargins(0, 0, 0, 0)
        pdf_layout.addWidget(self.pdf_viewer)
        self.splitter.addWidget(pdf_container)
        
        # Right: Inspector (Preview)
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidget(self.preview_panel)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff) # Vertical only
        self.splitter.addWidget(scroll_area)
        
        # 2-Pane sizing: [Fluid Canvas, Fluid Inspector]
        self.splitter.setCollapsible(0, False)
        self.splitter.setStretchFactor(0, 3) # Canvas
        self.splitter.setStretchFactor(1, 2) # Inspector
        
        self.splitter.setSizes([900, 700])
        
        layout.addWidget(self.splitter)
        
    def _create_toolbar(self):
        """Create a minimal toolbar for PDF controls."""
        toolbar = QtWidgets.QFrame()
        toolbar.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.BACKGROUND};
                border-bottom: 1px solid {Theme.BORDER};
            }}
            QPushButton {{
                background-color: {Theme.ACCENT};
                color: {Theme.ACCENT_TEXT};
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Theme.ACCENT_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {Theme.ACCENT_PRESSED};
            }}
        """)
        toolbar.setFixedHeight(56)
        
        layout = QtWidgets.QHBoxLayout(toolbar)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)
        
        # Upload PDF button
        upload_btn = QtWidgets.QPushButton("📄 Upload PDF")
        upload_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        upload_btn.clicked.connect(self.upload_requested.emit)
        layout.addWidget(upload_btn)
        
        # Zoom Out
        zoom_out = QtWidgets.QPushButton("🔍 Zoom Out")
        zoom_out.setToolTip("Zoom Out")
        zoom_out.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        zoom_out.clicked.connect(lambda: self.pdf_viewer.scale(0.9, 0.9))
        layout.addWidget(zoom_out)
        
        # Fit to Screen
        fit_btn = QtWidgets.QPushButton("⬜ Fit to Screen")
        fit_btn.setToolTip("Fit Page to Screen")
        fit_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        fit_btn.clicked.connect(lambda: self.pdf_viewer.resetTransform()) 
        layout.addWidget(fit_btn)
        
        # Zoom In
        zoom_in = QtWidgets.QPushButton("🔍 Zoom In")
        zoom_in.setToolTip("Zoom In")
        zoom_in.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        zoom_in.clicked.connect(lambda: self.pdf_viewer.scale(1.1, 1.1))
        layout.addWidget(zoom_in)
        
        layout.addStretch()
        
        return toolbar
