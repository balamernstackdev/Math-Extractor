"""Sidebar with actions."""
from __future__ import annotations

from PyQt6 import QtCore, QtWidgets


class Sidebar(QtWidgets.QFrame):
    """Left sidebar providing upload controls."""

    upload_requested = QtCore.pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setFixedWidth(200)
        layout = QtWidgets.QVBoxLayout(self)
        self.upload_btn = QtWidgets.QPushButton("Upload PDF")
        layout.addWidget(self.upload_btn)
        layout.addStretch()
        self.upload_btn.clicked.connect(self._on_upload)

    def _on_upload(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select PDF", "", "PDF Files (*.pdf)"
        )
        if path:
            self.upload_requested.emit(path)

