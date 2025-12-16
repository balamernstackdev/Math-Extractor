"""Snips page showing cropped formulas."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from PyQt6 import QtCore, QtGui, QtWidgets


class SnipsPage(QtWidgets.QScrollArea):
    """Display saved snips and allow copy/insert."""

    insert_requested = QtCore.pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWidgetResizable(True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)

        self._cards: list[QtWidgets.QWidget] = []
        self._columns = 2  # default columns; simple grid to use available width

        container = QtWidgets.QWidget()
        self.layout = QtWidgets.QGridLayout(container)
        self.layout.setContentsMargins(12, 12, 12, 12)
        self.layout.setHorizontalSpacing(12)
        self.layout.setVerticalSpacing(12)
        self.setWidget(container)

    def add_snip(self, record: Dict[str, object]) -> None:
        """Add a snip widget from record data."""
        widget = QtWidgets.QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: #16181d;
                border: 1px solid #242832;
                border-radius: 8px;
            }
        """)
        vbox = QtWidgets.QVBoxLayout(widget)
        vbox.setContentsMargins(10, 10, 10, 10)
        vbox.setSpacing(8)
        widget.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Maximum)
        widget.setMinimumWidth(320)

        img_label = QtWidgets.QLabel()
        pixmap = QtGui.QPixmap(str(Path(record["image"])))
        img_label.setPixmap(pixmap.scaledToWidth(280, QtCore.Qt.TransformationMode.SmoothTransformation))
        img_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(img_label)

        latex = str(record.get("latex", ""))
        mathml = str(record.get("mathml", ""))

        latex_label = QtWidgets.QLabel(latex)
        latex_label.setWordWrap(True)
        latex_label.setStyleSheet("color: #dfe3ec;")
        vbox.addWidget(latex_label)

        btns = QtWidgets.QHBoxLayout()
        btns.setSpacing(6)
        copy_latex_btn = QtWidgets.QPushButton("Copy LaTeX")
        copy_mathml_btn = QtWidgets.QPushButton("Copy MathML")
        insert_btn = QtWidgets.QPushButton("Insert")
        delete_btn = QtWidgets.QPushButton("Delete")
        for btn in (copy_latex_btn, copy_mathml_btn, insert_btn, delete_btn):
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        btns.addWidget(copy_latex_btn)
        btns.addWidget(copy_mathml_btn)
        btns.addWidget(insert_btn)
        btns.addWidget(delete_btn)
        vbox.addLayout(btns)

        copy_latex_btn.clicked.connect(lambda: self._copy_with_feedback(copy_latex_btn, latex, "LaTeX copied"))
        copy_mathml_btn.clicked.connect(lambda: self._copy_with_feedback(copy_mathml_btn, mathml or latex, "MathML copied"))
        insert_btn.clicked.connect(lambda: self.insert_requested.emit(latex))
        delete_btn.clicked.connect(lambda: self._remove_snip(widget))

        self._cards.append(widget)
        self._reflow_cards()

    def _remove_snip(self, widget: QtWidgets.QWidget) -> None:
        """Remove a snip card from the list."""
        if widget in self._cards:
            self._cards.remove(widget)
        widget.setParent(None)
        self._reflow_cards()

    def _reflow_cards(self) -> None:
        """Lay out cards in a simple grid to use horizontal space."""
        # Clear current items from layout
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        # Add back in grid
        for idx, card in enumerate(self._cards):
            row = idx // self._columns
            col = idx % self._columns
            self.layout.addWidget(card, row, col, alignment=QtCore.Qt.AlignmentFlag.AlignTop)
            self.layout.setRowStretch(row, 0)

        # Add a stretch at the bottom to keep cards pinned to the top
        self.layout.setRowStretch((len(self._cards) // self._columns) + 1, 1)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        """Adjust columns based on available width."""
        super().resizeEvent(event)
        width = event.size().width()
        # Choose columns based on width thresholds
        if width > 900:
            columns = 3
        elif width > 640:
            columns = 2
        else:
            columns = 1
        if columns != self._columns:
            self._columns = columns
            self._reflow_cards()

    def _copy_with_feedback(self, sender: QtWidgets.QWidget, text: str, message: str) -> None:
        """Copy to clipboard and show a quick tooltip-style confirmation."""
        QtWidgets.QApplication.clipboard().setText(text)
        # Show tooltip near the sender button
        global_pos = sender.mapToGlobal(sender.rect().center())
        QtWidgets.QToolTip.showText(global_pos, message, sender)

