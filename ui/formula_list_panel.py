"""
Formula List Panel
Displays a scrollable list of detected formulas.
"""
from PyQt6 import QtWidgets, QtCore, QtGui
from pathlib import Path
from ui.styles import Theme

class FormulaCard(QtWidgets.QFrame):
    clicked = QtCore.pyqtSignal(dict)

    def __init__(self, formula_data: dict, parent=None):
        super().__init__(parent)
        self.data = formula_data
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(100)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 8px;
            }}
            QFrame:hover {{
                border-color: {Theme.ACCENT};
                background-color: {Theme.SURFACE_HOVER};
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        # 1. Image Thumbnail
        self.image_label = QtWidgets.QLabel()
        self.image_label.setFixedSize(200, 76)
        self.image_label.setStyleSheet(f"background: {Theme.BACKGROUND}; border-radius: 4px;")
        self.image_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        # Load image
        import shutil
        crop_path = formula_data.get("crop_path")
        if crop_path and Path(crop_path).exists():
            pixmap = QtGui.QPixmap(str(crop_path))
            if not pixmap.isNull():
                self.image_label.setPixmap(pixmap.scaled(
                    self.image_label.size(),
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation
                ))
        else:
            self.image_label.setText("No Image")
            
        layout.addWidget(self.image_label)
        
        # 2. Info / Latex Preview
        info_layout = QtWidgets.QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(4)
        
        # ID / Confidence
        header_text = f"Formula {formula_data.get('formula_id', 'Unknown')}"
        # You could add confidence here if available
        header = QtWidgets.QLabel(header_text)
        header.setStyleSheet(f"color: {Theme.ACCENT}; font-weight: bold; font-size: 11px;")
        info_layout.addWidget(header)
        
        # LaTeX snippet
        latex = formula_data.get("latex", "")
        # Shorten for display
        short_latex = (latex[:40] + "...") if len(latex) > 40 else latex
        latex_lbl = QtWidgets.QLabel(short_latex)
        latex_lbl.setWordWrap(True)
        latex_lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 11px; font-family: monospace;")
        info_layout.addWidget(latex_lbl)
        
        info_layout.addStretch()
        layout.addLayout(info_layout)
        
        # 3. Status Indicator (Valid/Invalid)
        # Using a simple colored dot or text
        is_valid = formula_data.get("is_valid", False)
        status_color = Theme.SUCCESS if is_valid else Theme.ERROR
        status_indicator = QtWidgets.QFrame()
        status_indicator.setFixedSize(8, 8)
        status_indicator.setStyleSheet(f"""
            background-color: {status_color};
            border-radius: 4px;
        """)
        layout.addWidget(status_indicator)

    def mousePressEvent(self, event):
        self.clicked.emit(self.data)
        super().mousePressEvent(event)


class FormulaListPanel(QtWidgets.QWidget):
    formula_selected = QtCore.pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {Theme.BACKGROUND};")
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = QtWidgets.QLabel("Detected Formulas")
        header.setStyleSheet(f"""
            padding: 16px;
            font-size: 14px;
            font-weight: bold;
            color: {Theme.TEXT_PRIMARY};
            border-bottom: 1px solid {Theme.BORDER};
        """)
        layout.addWidget(header)
        
        # Scroll Area
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("background: transparent;")
        
        self.container = QtWidgets.QWidget()
        self.container_layout = QtWidgets.QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(16, 16, 16, 16)
        self.container_layout.setSpacing(12)
        self.container_layout.addStretch()
        
        self.scroll_area.setWidget(self.container)
        layout.addWidget(self.scroll_area)
        
        self._cards = []

    def add_formulas(self, formulas: list):
        from core.logger import logger
        logger.info(f"FormulaListPanel: Adding {len(formulas)} formulas")
        
        # Remove stretch
        if self.container_layout.count() > 0:
            item = self.container_layout.takeAt(self.container_layout.count() - 1)
            # Check if it was a spacer or widget
            if item.widget():
                item.widget().setParent(None)
            elif item.spacerItem():
                pass # Just removed it from layout
            del item

        # If empty
        if not formulas and not self._cards:
            # We could show empty state
            pass

        for f in formulas:
            card = FormulaCard(f)
            card.clicked.connect(self._on_card_clicked)
            self.container_layout.addWidget(card)
            self._cards.append(card)
            
        # Add stretch back
        self.container_layout.addStretch()
        
    def clear_formulas(self):
        # Clear layout safely
        while self.container_layout.count():
            child = self.container_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.spacerItem():
                pass # Spacer removed
        self._cards.clear()
        self.container_layout.addStretch()
        
    def _on_card_clicked(self, data):
        from core.logger import logger
        logger.info(f"FormulaListPanel: Card clicked - {data.get('formula_id')}")
        self.formula_selected.emit(data)
