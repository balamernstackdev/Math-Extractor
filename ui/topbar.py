"""Top bar for global actions."""
from __future__ import annotations

from PyQt6 import QtCore, QtWidgets


class TopBar(QtWidgets.QFrame):
    """Top bar with save and status actions."""

    save_notes = QtCore.pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        layout = QtWidgets.QHBoxLayout(self)
        self.save_btn = QtWidgets.QPushButton("Save Notes")
        layout.addWidget(self.save_btn)
        layout.addStretch()
        self.save_btn.clicked.connect(self.save_notes.emit)

