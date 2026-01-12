"""
Batch Image Processing Queue
Allows users to process multiple images in sequence with queue management.
"""

from PyQt6 import QtCore, QtGui, QtWidgets
from pathlib import Path
from ui.styles import Theme

class BatchQueueItem(QtWidgets.QWidget):
    """Visual representation of a single item in the batch queue."""
    
    removed = QtCore.pyqtSignal(str) # Emits item_id
    
    def __init__(self, item_id: str, file_path: str, parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self.file_path = file_path
        self._build_ui()
        
    def _build_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        
        # Container style
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
            }}
        """)
        
        # 1. Icon/Thumbnail (Placeholder)
        icon_label = QtWidgets.QLabel("📄")
        icon_label.setStyleSheet("font-size: 16px; background: transparent; border: none;")
        layout.addWidget(icon_label)
        
        # 2. Filename & Status
        info_layout = QtWidgets.QVBoxLayout()
        info_layout.setSpacing(2)
        
        name_label = QtWidgets.QLabel(Path(self.file_path).name)
        name_label.setStyleSheet(f"font-weight: 600; color: {Theme.TEXT_PRIMARY}; background: transparent; border: none;")
        info_layout.addWidget(name_label)
        
        self.status_label = QtWidgets.QLabel("Pending")
        self.status_label.setStyleSheet(f"font-size: 11px; color: {Theme.TEXT_TERTIARY}; background: transparent; border: none;")
        info_layout.addWidget(self.status_label)
        
        layout.addLayout(info_layout, stretch=1)
        
        # 3. Progress Bar (Small)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 0) # Undefined/Loading by default
        self.progress.setFixedHeight(4)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: {Theme.BACKGROUND};
                border-radius: 2px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: {Theme.ACCENT};
                border-radius: 2px;
            }}
        """)
        self.progress.hide() # Hidden until active
        layout.addWidget(self.progress)
        self.progress.setFixedWidth(60)

        # 4. Remove Button
        self.remove_btn = QtWidgets.QPushButton("✕")
        self.remove_btn.setFixedSize(20, 20)
        self.remove_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.remove_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Theme.TEXT_TERTIARY};
                border: none;
                font-weight: bold;
                padding: 0;
            }}
            QPushButton:hover {{
                color: {Theme.ERROR};
                background: {Theme.SURFACE_HOVER};
            }}
        """)
        self.remove_btn.clicked.connect(lambda: self.removed.emit(self.item_id))
        layout.addWidget(self.remove_btn)

    def set_status(self, status: str, state: str = "pending"):
        """
        Update status text and visual state.
        state options: 'pending', 'processing', 'completed', 'failed'
        """
        self.status_label.setText(status)
        
        if state == "processing":
            self.progress.show()
            self.status_label.setStyleSheet(f"font-size: 11px; color: {Theme.ACCENT}; background: transparent; border: none;")
        elif state == "completed":
            self.progress.hide()
            self.status_label.setStyleSheet(f"font-size: 11px; color: {Theme.SUCCESS}; background: transparent; border: none;")
            # Change icon/remove button to Check
            self.remove_btn.hide()
        elif state == "failed":
            self.progress.hide()
            self.status_label.setStyleSheet(f"font-size: 11px; color: {Theme.ERROR}; background: transparent; border: none;")
        else:
            self.progress.hide()


class BatchQueuePanel(QtWidgets.QWidget):
    """
    Side panel for managing the batch processing queue.
    """
    
    # Signals
    items_added = QtCore.pyqtSignal(list) # List of paths
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = {} # id -> widget
        self.queue = [] # list of ids
        self._build_ui()
        self.setAcceptDrops(True)

    def _build_ui(self):
        self.setFixedWidth(280) # Fixed sidebar width
        self.setStyleSheet(f"background-color: {Theme.SIDEBAR}; border-left: 1px solid {Theme.BORDER};")
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header
        header = QtWidgets.QLabel("Queue")
        header.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {Theme.TEXT_SECONDARY}; text-transform: uppercase; letter-spacing: 1px;")
        layout.addWidget(header)
        
        # Stats
        self.stats_label = QtWidgets.QLabel("0 items pending")
        self.stats_label.setStyleSheet(f"color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
        layout.addWidget(self.stats_label)
        
        # Scroll Area for Items
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")
        
        self.content_widget = QtWidgets.QWidget()
        self.items_layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.items_layout.setSpacing(8)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.addStretch() # Push items up
        
        scroll.setWidget(self.content_widget)
        layout.addWidget(scroll)
        
        # Drop Zone Hint
        self.drop_hint = QtWidgets.QLabel("Drop images here\nto add to queue")
        self.drop_hint.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.drop_hint.setStyleSheet(f"""
            border: 2px dashed {Theme.BORDER};
            border-radius: 8px;
            color: {Theme.TEXT_TERTIARY};
            padding: 20px;
            font-size: 12px;
        """)
        layout.addWidget(self.drop_hint)
        
        # Bottom Actions
        action_layout = QtWidgets.QHBoxLayout()
        clear_btn = QtWidgets.QPushButton("Clear All")
        clear_btn.setStyleSheet(f"""
            background: transparent; 
            border: 1px solid {Theme.BORDER}; 
            color: {Theme.TEXT_SECONDARY};
            font-size: 11px;
        """)
        clear_btn.clicked.connect(self.clear_queue)
        action_layout.addWidget(clear_btn)
        layout.addLayout(action_layout)

    def add_files(self, file_paths: list[str]):
        """Add files to the visual queue."""
        import uuid
        
        added_ids = []
        for path in file_paths:
            if not Path(path).exists():
                continue
                
            item_id = str(uuid.uuid4())
            item_widget = BatchQueueItem(item_id, path)
            item_widget.removed.connect(self.remove_item)
            
            # Insert before the stretch (last item)
            count = self.items_layout.count()
            self.items_layout.insertWidget(count - 1, item_widget)
            
            self.items[item_id] = item_widget
            self.queue.append(item_id)
            added_ids.append(item_id)
            
        self._update_stats()
        
        # Hide drop hint if items exist
        if self.queue:
            self.drop_hint.hide()

    def remove_item(self, item_id: str):
        """Remove an item from the queue."""
        if item_id in self.items:
            widget = self.items.pop(item_id)
            widget.deleteLater()
            if item_id in self.queue:
                self.queue.remove(item_id)
            self._update_stats()
            
            # Show hint if empty
            if not self.queue:
                self.drop_hint.show()

    def clear_queue(self):
        """Clear all items."""
        for item_id in list(self.items.keys()):
            self.remove_item(item_id)

    def update_item_status(self, item_id: str, status: str, state: str):
        """Update the UI status of a specific item."""
        if item_id in self.items:
            self.items[item_id].set_status(status, state)

    def _update_stats(self):
        count = len(self.queue)
        self.stats_label.setText(f"{count} items in queue")
    
    def get_next_pending(self) -> tuple[str, str] | None:
        """Get the item_id and file_path of the next pending item."""
        # This is a simple FIFO queue
        # We need to track 'pending' state. 
        # For simplicity, we can assume the queue is processed in order
        # But workers might pick items?
        # Let's iterate widget status. Not ideal but robust.
        # Better: keep a list of 'processed_ids' or just iterate visual queue
        
        for item_id in self.queue:
            widget = self.items[item_id]
            # Check if status text is "Pending" (fragile string check but effective here)
            if widget.status_label.text() == "Pending":
                return item_id, widget.file_path
        return None

    # Drag & Drop Support
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        paths = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if Path(path).suffix.lower() in ['.png', '.jpg', '.jpeg', '.bmp']:
                paths.append(path)
        
        if paths:
            self.add_files(paths)
            self.items_added.emit(paths)
