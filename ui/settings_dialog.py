"""Settings dialog for configuring Tesseract and other options."""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6 import QtCore, QtWidgets

from core.config import settings
from core.logger import logger


class SettingsDialog(QtWidgets.QDialog):
    """Dialog for application settings."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
            }
            QLabel {
                color: white;
            }
            QLineEdit {
                background-color: #3c3c3c;
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:disabled {
                background-color: #3c3c3c;
                color: #888;
            }
        """)
        
        self.config_file = settings.data_dir / "config.json"
        # Load current Tesseract path from settings
        self.saved_tesseract_path = settings.tesseract_cmd or ""
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QtWidgets.QLabel("Settings")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        layout.addWidget(title)
        
        # Tesseract OCR Section
        tesseract_group = QtWidgets.QFrame()
        tesseract_layout = QtWidgets.QVBoxLayout(tesseract_group)
        tesseract_layout.setSpacing(8)
        
        tesseract_label = QtWidgets.QLabel("Tesseract OCR Path")
        tesseract_label.setStyleSheet("font-weight: bold; color: #aaa;")
        tesseract_layout.addWidget(tesseract_label)
        
        tesseract_info = QtWidgets.QLabel(
            "Select the path to tesseract.exe. If not set, the application will try to auto-detect it."
        )
        tesseract_info.setStyleSheet("color: #888; font-size: 11px;")
        tesseract_info.setWordWrap(True)
        tesseract_layout.addWidget(tesseract_info)
        
        tesseract_input_layout = QtWidgets.QHBoxLayout()
        self.tesseract_path_edit = QtWidgets.QLineEdit()
        self.tesseract_path_edit.setText(self.saved_tesseract_path or "")
        self.tesseract_path_edit.setPlaceholderText("Auto-detect or browse to select...")
        tesseract_input_layout.addWidget(self.tesseract_path_edit, stretch=1)
        
        browse_btn = QtWidgets.QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_tesseract)
        tesseract_input_layout.addWidget(browse_btn)
        
        clear_btn = QtWidgets.QPushButton("Clear")
        clear_btn.clicked.connect(lambda: self.tesseract_path_edit.clear())
        tesseract_input_layout.addWidget(clear_btn)
        
        tesseract_layout.addLayout(tesseract_input_layout)
        
        # Status label
        self.tesseract_status = QtWidgets.QLabel("")
        self.tesseract_status.setStyleSheet("color: #888; font-size: 11px;")
        self._update_tesseract_status()
        tesseract_layout.addWidget(self.tesseract_status)
        
        layout.addWidget(tesseract_group)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        save_btn = QtWidgets.QPushButton("Save")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
            }
        """)
        save_btn.clicked.connect(self._save_settings)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
        
        # Update status when path changes
        self.tesseract_path_edit.textChanged.connect(self._update_tesseract_status)

    def _browse_tesseract(self) -> None:
        """Browse for Tesseract executable."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Tesseract Executable",
            "",
            "Executable Files (*.exe);;All Files (*.*)"
        )
        if path:
            self.tesseract_path_edit.setText(path)
            self._update_tesseract_status()

    def _update_tesseract_status(self) -> None:
        """Update Tesseract status label."""
        path = self.tesseract_path_edit.text().strip()
        if not path:
            self.tesseract_status.setText("Status: Will use auto-detection")
            self.tesseract_status.setStyleSheet("color: #888; font-size: 11px;")
            return
        
        tesseract_path = Path(path)
        if tesseract_path.exists() and tesseract_path.name.lower() == "tesseract.exe":
            self.tesseract_status.setText("✓ Valid Tesseract path")
            self.tesseract_status.setStyleSheet("color: #4CAF50; font-size: 11px;")
        elif tesseract_path.exists():
            self.tesseract_status.setText("⚠ File exists but may not be Tesseract")
            self.tesseract_status.setStyleSheet("color: #FFA500; font-size: 11px;")
        else:
            self.tesseract_status.setText("✗ File not found")
            self.tesseract_status.setStyleSheet("color: #f44336; font-size: 11px;")

    def _save_settings(self) -> None:
        """Save settings to config file."""
        tesseract_path = self.tesseract_path_edit.text().strip()
        
        config = {
            "tesseract_path": tesseract_path if tesseract_path else None,
        }
        
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            
            # Update settings immediately
            if tesseract_path:
                settings.tesseract_cmd = tesseract_path
                # Also update pytesseract directly
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
            else:
                # Reset to auto-detect
                from core.config import _find_tesseract_path
                auto_path = _find_tesseract_path()
                settings.tesseract_cmd = auto_path
                if auto_path:
                    import pytesseract
                    pytesseract.pytesseract.tesseract_cmd = auto_path
            
            logger.info("Settings saved: Tesseract path = %s", tesseract_path or "auto-detect")
            QtWidgets.QMessageBox.information(
                self,
                "Settings Saved",
                "Settings have been saved. The changes will take effect immediately."
            )
            self.accept()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to save settings: %s", exc)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to save settings:\n{exc}"
            )

