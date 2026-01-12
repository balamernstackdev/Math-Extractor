from PyQt6 import QtCore, QtGui, QtWidgets
from ui.styles import Theme

class ThumbnailSidebar(QtWidgets.QWidget):
    """
    Left-hand sidebar showing page thumbnails and processing status.
    """
    
    page_selected = QtCore.pyqtSignal(int) # Emits page_num (0-indexed)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220) # Fixed width for sidebar
        self.setStyleSheet(f"background-color: {Theme.SIDEBAR}; border-right: 1px solid {Theme.BORDER};")
        self._build_ui()
        self.thumbnails = {} # Map page_num -> Widget

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = QtWidgets.QFrame()
        header.setFixedHeight(40)
        header.setStyleSheet(f"border-bottom: 1px solid {Theme.BORDER}; background: {Theme.SIDEBAR};")
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(12, 0, 12, 0)
        
        title = QtWidgets.QLabel("PAGES")
        title.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;")
        header_layout.addWidget(title)
        
        layout.addWidget(header)
        
        # Scroll Area for Thumbnails
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("background: transparent;")
        
        self.content_widget = QtWidgets.QWidget()
        self.content_layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content_layout.setSpacing(12)
        self.content_layout.addStretch() # Push items up
        
        self.scroll_area.setWidget(self.content_widget)
        layout.addWidget(self.scroll_area)
        
    def add_page(self, page_num: int):
        """Add a thumbnail placeholder for a page."""
        # Insert before the stretch (last item)
        container = QtWidgets.QWidget()
        container.setFixedHeight(140)
        container.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        
        # Click handler
        container.mousePressEvent = lambda e: self.page_selected.emit(page_num)
        
        vbox = QtWidgets.QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(4)
        
        # Thumbnail Visual (Placeholder)
        thumb_frame = QtWidgets.QFrame()
        thumb_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
            }}
            QFrame:hover {{
                border-color: {Theme.ACCENT};
            }}
        """)
        vbox.addWidget(thumb_frame)
        
        # Page Label
        label = QtWidgets.QLabel(f"Page {page_num + 1}")
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 11px;")
        vbox.addWidget(label)
        
        # Store ref
        self.thumbnails[page_num] = container
        
        # Add to layout (before stretch)
        count = self.content_layout.count()
        self.content_layout.insertWidget(count - 1, container)
        
    def set_page_status(self, page_num: int, status: str):
        """
        Update the status indicator for a page.
        status: 'pending', 'processing', 'done', 'error'
        """
        if page_num not in self.thumbnails:
            return
            
        container = self.thumbnails[page_num]
        frame = container.findChild(QtWidgets.QFrame)
        label = container.findChild(QtWidgets.QLabel)
        
        if status == 'processing':
            frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {Theme.SURFACE};
                    border: 2px solid {Theme.ACCENT};
                    border-radius: 4px;
                }}
            """)
            label.setText(f"Page {page_num + 1} • ...")
            label.setStyleSheet(f"color: {Theme.ACCENT}; font-size: 11px; font-weight: bold;")
            
        elif status == 'done':
            frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {Theme.SURFACE};
                    border: 1px solid {Theme.SUCCESS};
                    border-radius: 4px;
                }}
            """)
            label.setText(f"Page {page_num + 1} • ✓")
            label.setStyleSheet(f"color: {Theme.SUCCESS}; font-size: 11px;")
            
        elif status == 'error':
            frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {Theme.SURFACE};
                    border: 1px solid {Theme.ERROR};
                    border-radius: 4px;
                }}
            """)
            label.setText(f"Page {page_num + 1} • ⚠")
            label.setStyleSheet(f"color: {Theme.ERROR}; font-size: 11px;")
            
        else: # pending or normal
            frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {Theme.SURFACE};
                    border: 1px solid {Theme.BORDER};
                    border-radius: 4px;
                }}
                QFrame:hover {{
                    border-color: {Theme.ACCENT};
                }}
            """)
            label.setText(f"Page {page_num + 1}")
            label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 11px;")

    def clear(self):
        """Remove all thumbnails."""
        # Remove all widgets except the stretch
        while self.content_layout.count() > 1:
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.thumbnails.clear()
