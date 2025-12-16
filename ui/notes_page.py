"""Notes page allowing text and formula insertion."""
from __future__ import annotations

from pathlib import Path

from PyQt6 import QtWidgets

from core.config import settings


class NotesPage(QtWidgets.QFrame):
    """Notes editor with formula insertion."""

    def __init__(self) -> None:
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        self.editor = QtWidgets.QTextEdit()
        self.save_path = settings.notes_dir / "notes.md"
        layout.addWidget(self.editor)

    def insert_formula(self, latex: str) -> None:
        """Insert LaTeX text into editor."""
        cursor = self.editor.textCursor()
        cursor.insertText(latex + " ")

    def save_notes(self) -> Path:
        """Save notes to disk."""
        text = self.editor.toPlainText()
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        self.save_path.write_text(text, encoding="utf-8")
        return self.save_path

