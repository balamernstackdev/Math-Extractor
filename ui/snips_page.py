"""Snips page showing cropped formulas."""
from __future__ import annotations

from pathlib import Path
from typing import Dict
from datetime import datetime

from PyQt6 import QtCore, QtGui, QtWidgets
from ui.styles import Theme
from core.logger import logger


class SnipsPage(QtWidgets.QWidget):
    """Display saved snips and allow copy/insert."""

    insert_requested = QtCore.pyqtSignal(str)
    snip_deleted = QtCore.pyqtSignal(str) # Emits the ID to be deleted from persistence
    export_requested = QtCore.pyqtSignal() # Request batch export

    def __init__(self) -> None:
        super().__init__()
        self.setStyleSheet(f"background-color: {Theme.BACKGROUND};")
        
        # Main Layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Scroll Area
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("background: transparent;")
        
        container = QtWidgets.QWidget()
        self.container_layout = QtWidgets.QVBoxLayout(container)
        self.container_layout.setContentsMargins(32, 32, 32, 32)
        self.container_layout.setSpacing(24)
        
        # Header + Search
        header_container = QtWidgets.QWidget()
        header_layout = QtWidgets.QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title_box = QtWidgets.QVBoxLayout()
        header = QtWidgets.QLabel("Snips")
        header.setStyleSheet(f"font-size: 28px; font-weight: 700; color: {Theme.TEXT_PRIMARY};")
        sub = QtWidgets.QLabel("Your collection of captured equations.")
        sub.setStyleSheet(f"font-size: 14px; color: {Theme.TEXT_SECONDARY};")
        title_box.addWidget(header)
        title_box.addWidget(sub)
        
        header_layout.addLayout(title_box)
        header_layout.addStretch()
        
        # Search Bar
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search equations...")
        self.search_input.setFixedWidth(300)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 8px;
                padding: 8px 12px;
                color: {Theme.TEXT_PRIMARY};
            }}
            QLineEdit:focus {{
                border: 1px solid {Theme.ACCENT};
            }}
        """)
        # Export All Button
        self.export_btn = QtWidgets.QPushButton("📤 Export All")
        self.export_btn.setFixedSize(120, 36)
        self.export_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.export_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.ACCENT};
                color: white;
                border-radius: 8px;
                font-weight: 600;
                font-size: 13px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {Theme.ACCENT_HOVER};
            }}
        """)
        self.export_btn.clicked.connect(self.export_requested.emit)
        header_layout.addWidget(self.export_btn)
        
        header_layout.addWidget(self.search_input)
        
        self.container_layout.addWidget(header_container)
        
        # Grid area
        self.grid_widget = QtWidgets.QWidget()
        self.grid_layout = QtWidgets.QGridLayout(self.grid_widget)
        self.grid_layout.setHorizontalSpacing(16)
        self.grid_layout.setVerticalSpacing(16)
        self.container_layout.addWidget(self.grid_widget)
        
        self.container_layout.addStretch()
        
        self.scroll_area.setWidget(container)
        layout.addWidget(self.scroll_area)
        
        self._cards: list[QtWidgets.QWidget] = []
        self._all_records: list[Dict[str, object]] = [] # Store records for filtering
        self._columns = 2
        
        # Connect search
        self.search_input.textChanged.connect(self.filter_snips)

    def add_snip(self, record: Dict[str, object], reflow: bool = True) -> None:
        """Add a snip record and its widget."""
        self._all_records.append(record)
        self._create_card_for_record(record, reflow)

    def _create_card_for_record(self, record: Dict[str, object], reflow: bool = True) -> None:
        """Create a snip widget and add it to the display list."""
        widget = QtWidgets.QFrame()
        widget.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 12px;
            }}
            QFrame:hover {{
                border-color: {Theme.ACCENT};
                background-color: {Theme.SURFACE_HOVER};
            }}
        """)
        
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        widget.setFixedHeight(140)
        
        # 1. Thumbnail
        img_label = QtWidgets.QLabel()
        img_label.setFixedSize(108, 108)
        img_label.setStyleSheet(f"background: {Theme.BACKGROUND}; border-radius: 8px; border: 1px solid {Theme.BORDER};")
        img_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        if "image" in record and record["image"] and Path(str(record["image"])).exists():
            pixmap = QtGui.QPixmap(str(record["image"]))
            img_label.setPixmap(pixmap.scaled(100, 100, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation))
        else:
            img_label.setText("No Image")
        layout.addWidget(img_label)
        
        # 2. Content
        content = QtWidgets.QWidget()
        content.setStyleSheet("border: none; background: transparent;")
        c_layout = QtWidgets.QVBoxLayout(content)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(4)
        
        latex = str(record.get("latex", ""))
        short_latex = (latex[:75] + '...') if len(latex) > 75 else latex
        latex_label = QtWidgets.QLabel(short_latex)
        latex_label.setWordWrap(True)
        latex_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-family: {Theme.FONT_FAMILY}; font-size: 14px;")
        c_layout.addWidget(latex_label)
        
        # Add MathML preview (hidden or truncated if needed, but per request UI alignment is key)
        # keeping just latex preview for visual identification is fine.
        
        ts = record.get("created_at", 0)
        if ts:
            dt_str = datetime.fromtimestamp(float(ts)).strftime("%b %d, %H:%M")
            time_label = QtWidgets.QLabel(dt_str)
            time_label.setStyleSheet(f"color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
            c_layout.addWidget(time_label)
        c_layout.addStretch()
        
        # Actions
        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(8)
        btn_style = f"QPushButton {{ background-color: {Theme.BACKGROUND}; color: {Theme.TEXT_SECONDARY}; border: 1px solid {Theme.BORDER}; border-radius: 6px; padding: 4px 12px; font-size: 12px; }} QPushButton:hover {{ background-color: {Theme.SURFACE_HOVER}; color: {Theme.TEXT_PRIMARY}; }}"
        
        # "Copy MathML" -> Standard MathML
        copy_mathml_btn = QtWidgets.QPushButton("Copy MathML")
        copy_mathml_btn.setStyleSheet(btn_style)
        
        # "Copy MML Code" -> MML code with prefix (if distinct) or just MML
        # User asked for "MML code". Assuming this means the namespaced version if available, or just distinct button.
        copy_mml_btn = QtWidgets.QPushButton("Copy MML Code")
        copy_mml_btn.setStyleSheet(btn_style)
        delete_btn = QtWidgets.QPushButton("🗑️")
        delete_btn.setFixedSize(28, 28)
        delete_btn.setStyleSheet(btn_style)
        
        actions.addWidget(copy_mathml_btn)
        actions.addWidget(copy_mml_btn)
        actions.addWidget(delete_btn)
        actions.addStretch()
        c_layout.addLayout(actions)
        layout.addWidget(content)

        # Wire signals
        # MathML: just the clean mathml
        mathml_content = str(record.get("mathml", "") or "")
        copy_mathml_btn.clicked.connect(lambda: self._copy_with_feedback(copy_mathml_btn, mathml_content, "MathML Copied!"))
        
        # MML Code: For now, we can reuse the mathml or generate the namespaced version if stored.
        # If 'mml' is not stored separately, we might need to rely on the standard mathml or re-generate.
        # Assuming for now we just want a second button acting on the same content or specifically labeled MML.
        # If the user specifically meant the "mml:" prefixed version created in preview_panel, we might not have it here unless persisted.
        # Let's assume standard MathML for both unless distinct data exists.
        copy_mml_btn.clicked.connect(lambda: self._copy_with_feedback(copy_mml_btn, mathml_content, "MML Code Copied!"))
        
        snip_id = str(record.get("id", ""))
        delete_btn.clicked.connect(lambda: self._remove_snip(widget, snip_id))

        self._cards.append(widget)
        if reflow:
            self._reflow_cards()

    def filter_snips(self, query: str) -> None:
        """Filter visible snips based on LaTeX content."""
        query = query.lower().strip()
        
        # Clear layout
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        
        # Clear cards list for reflow
        self._cards = []
        
        # Re-create cards for filtered records
        for record in self._all_records:
            latex = str(record.get("latex", "")).lower()
            if not query or query in latex:
                self._create_card_for_record(record, reflow=False)
        
        self._reflow_cards()

    def _remove_snip(self, widget: QtWidgets.QWidget, snip_id: str) -> None:
        """Remove a snip card from the list and notify for persistence."""
        # Also remove from all_records
        self._all_records = [r for r in self._all_records if str(r.get("id")) != snip_id]
        
        if widget in self._cards:
            self._cards.remove(widget)
        widget.setParent(None)
        self._reflow_cards()
        
        if snip_id:
            logger.info(f"[SnipsPage] Requesting deletion of snip: {snip_id}")
            self.snip_deleted.emit(snip_id)

    def _reflow_cards(self) -> None:
        """Lay out cards in a responsive grid."""
        # Clear layout
        for i in reversed(range(self.grid_layout.count())):
             self.grid_layout.itemAt(i).widget().setParent(None)
                
        # Reflow
        for idx, card in enumerate(self._cards):
            row = idx // self._columns
            col = idx % self._columns
            self.grid_layout.addWidget(card, row, col)
            
    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        """Responsive column adjustment."""
        width = event.size().width()
        if width > 1100:
            self._columns = 3
        elif width > 700:
            self._columns = 2
        else:
            self._columns = 1
        self._reflow_cards()
        super().resizeEvent(event)

    def _copy_with_feedback(self, sender: QtWidgets.QWidget, text: str, message: str) -> None:
        """Copy text to clipboard with tooltip feedback."""
        QtWidgets.QApplication.clipboard().setText(text)
        global_pos = sender.mapToGlobal(QtCore.QPoint(0, 0))
        QtWidgets.QToolTip.showText(global_pos, message, sender)
