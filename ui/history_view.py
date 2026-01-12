"""
History View Component

Displays a complete chronological list of extracted equations.
"""

from PyQt6 import QtCore, QtGui, QtWidgets
from ui.equation_card import EquationCard
from ui.styles import Theme

class HistoryView(QtWidgets.QWidget):
    """
    History view displaying all extractions in a chronological list/grid.
    
    Signals:
        equation_selected: Emitted when user clicks an equation card
    """
    
    equation_selected = QtCore.pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.equations = []
        self._build_ui()
    
    def _build_ui(self):
        """Build history UI."""
        self.setStyleSheet(f"background: {Theme.BACKGROUND};")
        
        # Main layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)
        
        # Header
        header_layout = QtWidgets.QHBoxLayout()
        
        title_layout = QtWidgets.QVBoxLayout()
        title = QtWidgets.QLabel("History")
        title.setStyleSheet(f"font-size: 32px; font-weight: 700; color: {Theme.TEXT_PRIMARY};")
        sub = QtWidgets.QLabel("All your extracted equations")
        sub.setStyleSheet(f"font-size: 16px; color: {Theme.TEXT_SECONDARY};")
        title_layout.addWidget(title)
        title_layout.addWidget(sub)
        header_layout.addLayout(title_layout)
        
        header_layout.addStretch()
        
        # Search
        search_frame = QtWidgets.QFrame()
        search_frame.setStyleSheet(f"""
            QFrame {{
                background: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 8px;
            }}
        """)
        search_frame.setFixedWidth(300)
        search_frame.setFixedHeight(40)
        
        search_layout = QtWidgets.QHBoxLayout(search_frame)
        search_layout.setContentsMargins(12, 0, 12, 0)
        
        search_icon = QtWidgets.QLabel("🔍")
        search_icon.setStyleSheet("font-size: 16px;")
        search_layout.addWidget(search_icon)
        
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Search history...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #e0e0e0;
                font-size: 14px;
            }
        """)
        self.search_input.textChanged.connect(self._refresh_list)
        search_layout.addWidget(self.search_input)
        
        header_layout.addWidget(search_frame)
        layout.addLayout(header_layout)
        
        # Content Scroll Area
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")
        
        self.content_widget = QtWidgets.QWidget()
        self.grid_layout = QtWidgets.QGridLayout(self.content_widget)
        self.grid_layout.setSpacing(16)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll.setWidget(self.content_widget)
        layout.addWidget(scroll)
        
        # Empty State
        self.empty_state = QtWidgets.QLabel("No history yet", self)
        self.empty_state.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.empty_state.setStyleSheet("font-size: 18px; color: #808080;")
        layout.addWidget(self.empty_state)
        self.empty_state.hide()
        # We overlay empty state in center if needed, but simple layout add works too if we hide scroll
        # Actually easier to just toggle visibilty of scroll vs empty label
        
    def set_equations(self, equations: list):
        """Set history equations."""
        self.equations = equations
        self._refresh_list()
        
    def _refresh_list(self):
        """Refresh the list of history items."""
        # Clear
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        search_text = self.search_input.text().lower().strip()
        filtered = [
            eq for eq in self.equations
            if not search_text or 
               search_text in eq.get('latex', '').lower() or 
               search_text in eq.get('mathml', '').lower()
        ]
        
        if not filtered:
            self.empty_state.show()
            return
        
        self.empty_state.hide()

        # Use 1 column for history list
        for idx, eq_data in enumerate(filtered):
            card = self._create_history_item(eq_data)
            self.grid_layout.addWidget(card, idx, 0)
            
        # Push everything to top
        self.grid_layout.setRowStretch(len(filtered), 1)

    def _create_history_item(self, data: dict) -> QtWidgets.QWidget:
        """Create a compact history list item."""
        widget = ClickableFrame(data)
        widget.setObjectName("HistoryItem")
        widget.setFixedHeight(80)
        widget.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        widget.setStyleSheet(f"""
            QFrame#HistoryItem {{
                background-color: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 8px;
            }}
            QFrame#HistoryItem:hover {{
                background-color: {Theme.SURFACE_HOVER};
                border: 1px solid {Theme.ACCENT};
            }}
        """)
        
        # Connect click signal
        widget.clicked.connect(self.equation_selected.emit)
        
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(16)
        
        # 1. Status/Icon
        status_icon = "🟢" if data.get('is_valid', True) else "🔴"
        icon_label = QtWidgets.QLabel(status_icon)
        icon_label.setStyleSheet("font-size: 14px; background: transparent; border: none;")
        icon_label.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(icon_label)
        
        # 2. Content (LaTeX)
        latex = str(data.get('latex', ''))
        preview_text = (latex[:80] + '...') if len(latex) > 80 else latex
        text_label = QtWidgets.QLabel(preview_text)
        text_label.setStyleSheet(f"""
            color: {Theme.TEXT_PRIMARY};
            font-family: {Theme.FONT_FAMILY};
            font-size: 14px;
            background: transparent;
            border: none;
        """)
        text_label.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(text_label, stretch=1)
        
        # 3. Time
        timestamp = data.get('timestamp', None)
        time_text = "Just now"
        if timestamp:
            try:
                # simple time format
                time_text = timestamp.strftime("%H:%M")
            except:
                pass
        
        time_label = QtWidgets.QLabel(time_text)
        time_label.setStyleSheet(f"color: {Theme.TEXT_TERTIARY}; font-size: 12px; background: transparent; border: none;")
        time_label.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(time_label)
        
        # 4. Action (Copy)
        copy_btn = QtWidgets.QPushButton("📋") # Copy icon
        copy_btn.setFixedSize(32, 32)
        copy_btn.setToolTip("Copy LaTeX")
        copy_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 4px;
                font-size: 16px;
            }}
            QPushButton:hover {{
                background: {Theme.SURFACE}88;
                color: {Theme.ACCENT};
            }}
        """)
        copy_btn.clicked.connect(lambda: self._copy_latex(latex, copy_btn))
        layout.addWidget(copy_btn)
        
        return widget

    def _copy_latex(self, text: str, sender: QtWidgets.QWidget):
        QtWidgets.QApplication.clipboard().setText(text)
        QtWidgets.QToolTip.showText(sender.mapToGlobal(QtCore.QPoint(0,0)), "Copied!", sender)


class ClickableFrame(QtWidgets.QFrame):
    """A QFrame that emits a signal when clicked."""
    clicked = QtCore.pyqtSignal(dict)

    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.data = data

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit(self.data)
        super().mousePressEvent(event)
