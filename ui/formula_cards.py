"""
Enhanced UI Component for Formula Card Display

This creates a modern, card-based UI for displaying extracted formulas
with thumbnails, LaTeX preview, and quick actions.
"""
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt, pyqtSignal
from pathlib import Path


class FormulaCard(QtWidgets.QFrame):
    """Modern card widget for displaying a single formula."""
    
    clicked = pyqtSignal(dict)  # Emits formula data when clicked
    copy_clicked = pyqtSignal(str, str)  # Emits (latex, mathml)
    export_clicked = pyqtSignal(dict)  # Emits formula data
    
    def __init__(self, formula_data: dict, index: int, parent=None):
        super().__init__(parent)
        self.formula_data = formula_data
        self.index = index
        self.is_selected = False
        
        self.setFixedHeight(140)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the card UI with modern design."""
        self.setStyleSheet("""
            FormulaCard {
                background: #2b2b2b;
                border: 2px solid #3a3a3a;
                border-radius: 8px;
                margin: 4px;
            }
            FormulaCard:hover {
                background: #323232;
                border: 2px solid #0078d4;
            }
        """)
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        # Left: Formula thumbnail
        thumbnail_container = QtWidgets.QFrame()
        thumbnail_container.setFixedSize(100, 100)
        thumbnail_container.setStyleSheet("""
            QFrame {
                background: #1e1e1e;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
            }
        """)
        
        thumb_layout = QtWidgets.QVBoxLayout(thumbnail_container)
        thumb_layout.setContentsMargins(0, 0, 0, 0)
        
        self.thumbnail_label = QtWidgets.QLabel()
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setScaledContents(False)
        
        # Load thumbnail if available
        crop_path = self.formula_data.get('crop_path')
        if crop_path and Path(crop_path).exists():
            pixmap = QtGui.QPixmap(str(crop_path))
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    90, 90,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.thumbnail_label.setPixmap(scaled)
        else:
            # Placeholder icon
            self.thumbnail_label.setText("📐")
            self.thumbnail_label.setStyleSheet("font-size: 32px; color: #666;")
        
        thumb_layout.addWidget(self.thumbnail_label)
        layout.addWidget(thumbnail_container)
        
        # Middle: Formula info
        info_layout = QtWidgets.QVBoxLayout()
        info_layout.setSpacing(6)
        
        # Formula number and page
        header_layout = QtWidgets.QHBoxLayout()
        
        formula_num = QtWidgets.QLabel(f"Formula #{self.index + 1}")
        formula_num.setStyleSheet("""
            font-size: 14px;
            font-weight: 700;
            color: #ffffff;
        """)
        header_layout.addWidget(formula_num)
        
        page_num = self.formula_data.get('page', 1)
        page_label = QtWidgets.QLabel(f"Page {page_num}")
        page_label.setStyleSheet("""
            font-size: 11px;
            color: #888;
            background: #1e1e1e;
            padding: 4px 10px;
            border-radius: 4px;
        """)
        header_layout.addWidget(page_label)
        header_layout.addStretch()
        
        info_layout.addLayout(header_layout)
        
        # LaTeX preview
        latex = self.formula_data.get('latex', '')
        latex_preview = latex[:80] + '...' if len(latex) > 80 else latex
        
        latex_label = QtWidgets.QLabel(latex_preview)
        latex_label.setWordWrap(True)
        latex_label.setStyleSheet("""
            font-size: 12px;
            color: #c0c0c0;
            background: #1e1e1e;
            padding: 8px;
            border-radius: 4px;
            font-family: 'Consolas', 'Monaco', monospace;
        """)
        latex_label.setMaximumHeight(50)
        info_layout.addWidget(latex_label)
        
        # Status badges
        badges_layout = QtWidgets.QHBoxLayout()
        badges_layout.setSpacing(6)
        
        # Multiline badge
        if self.formula_data.get('multiline', False):
            multiline_badge = QtWidgets.QLabel("📊 Multiline")
            multiline_badge.setStyleSheet("""
                font-size: 10px;
                color: #4CAF50;
                background: #1e3a1e;
                padding: 3px 8px;
                border-radius: 3px;
                font-weight: 600;
            """)
            badges_layout.addWidget(multiline_badge)
        
        # Valid badge
        if self.formula_data.get('is_valid', False):
            valid_badge = QtWidgets.QLabel("✓ Validated")
            valid_badge.setStyleSheet("""
                font-size: 10px;
                color: #2196F3;
                background: #1e2a3a;
                padding: 3px 8px;
                border-radius: 3px;
                font-weight: 600;
            """)
            badges_layout.addWidget(valid_badge)
        
        badges_layout.addStretch()
        info_layout.addLayout(badges_layout)
        
        layout.addLayout(info_layout, 1)
        
        # Right: Action buttons
        actions_layout = QtWidgets.QVBoxLayout()
        actions_layout.setSpacing(6)
        
        copy_btn = QtWidgets.QPushButton("📋 Copy")
        copy_btn.setFixedSize(80, 32)
        copy_btn.setStyleSheet("""
            QPushButton {
                background: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #106ebe;
            }
            QPushButton:pressed {
                background: #005a9e;
            }
        """)
        copy_btn.clicked.connect(self._on_copy)
        actions_layout.addWidget(copy_btn)
        
        export_btn = QtWidgets.QPushButton("💾 Export")
        export_btn.setFixedSize(80, 32)
        export_btn.setStyleSheet("""
            QPushButton {
                background: #2b2b2b;
                color: #c0c0c0;
                border: 1px solid #555;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #3a3a3a;
                border-color: #0078d4;
            }
        """)
        export_btn.clicked.connect(self._on_export)
        actions_layout.addWidget(export_btn)
        
        actions_layout.addStretch()
        layout.addLayout(actions_layout)
    
    def _on_copy(self):
        """Handle copy button click."""
        latex = self.formula_data.get('latex', '')
        mathml = self.formula_data.get('mathml', '')
        self.copy_clicked.emit(latex, mathml)
    
    def _on_export(self):
        """Handle export button click."""
        self.export_clicked.emit(self.formula_data)
    
    def mousePressEvent(self, event):
        """Handle card click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.formula_data)
            self.set_selected(True)
        super().mousePressEvent(event)
    
    def set_selected(self, selected: bool):
        """Set card selection state."""
        self.is_selected = selected
        if selected:
            self.setStyleSheet("""
                FormulaCard {
                    background: #1e3a5f;
                    border: 2px solid #0078d4;
                    border-radius: 8px;
                    margin: 4px;
                }
            """)
        else:
            self.setStyleSheet("""
                FormulaCard {
                    background: #2b2b2b;
                    border: 2px solid #3a3a3a;
                    border-radius: 8px;
                    margin: 4px;
                }
                FormulaCard:hover {
                    background: #323232;
                    border: 2px solid #0078d4;
                }
            """)


class FormulaListPanel(QtWidgets.QWidget):
    """Enhanced formula list panel with modern card-based UI."""
    
    formula_selected = pyqtSignal(dict)  # Emits formula data when selected
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.formulas = []
        self.formula_cards = []
        self.selected_card = None
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the panel UI."""
        self.setStyleSheet("""
            FormulaListPanel {
                background: #1e1e1e;
            }
        """)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header
        header_layout = QtWidgets.QHBoxLayout()
        
        title = QtWidgets.QLabel("Extracted Formulas")
        title.setStyleSheet("""
            font-size: 18px;
            font-weight: 700;
            color: #ffffff;
            letter-spacing: 0.5px;
        """)
        header_layout.addWidget(title)
        
        self.count_label = QtWidgets.QLabel("0 formulas")
        self.count_label.setStyleSheet("""
            font-size: 13px;
            color: #888;
            background: #2b2b2b;
            padding: 6px 12px;
            border-radius: 4px;
        """)
        header_layout.addWidget(self.count_label)
        
        header_layout.addStretch()
        
        # Filter/Sort controls
        sort_label = QtWidgets.QLabel("Sort:")
        sort_label.setStyleSheet("color: #888; font-size: 12px;")
        header_layout.addWidget(sort_label)
        
        self.sort_combo = QtWidgets.QComboBox()
        self.sort_combo.addItems(["Page Order", "Recently Added", "Multiline First"])
        self.sort_combo.setStyleSheet("""
            QComboBox {
                background: #2b2b2b;
                color: #c0c0c0;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 12px;
                min-width: 120px;
            }
            QComboBox:hover {
                border-color: #0078d4;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #888;
                margin-right: 5px;
            }
        """)
        self.sort_combo.currentTextChanged.connect(self._on_sort_changed)
        header_layout.addWidget(self.sort_combo)
        
        layout.addLayout(header_layout)
        
        # Search box
        search_layout = QtWidgets.QHBoxLayout()
        
        self.search_box = QtWidgets.QLineEdit()
        self.search_box.setPlaceholderText("🔍 Search formulas...")
        self.search_box.setStyleSheet("""
            QLineEdit {
                background: #2b2b2b;
                color: #c0c0c0;
                border: 2px solid #3a3a3a;
                border-radius: 6px;
                padding: 10px 14px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
        """)
        self.search_box.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search_box)
        
        layout.addLayout(search_layout)
        
        # Scroll area for formulas
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #2b2b2b;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #555;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #666;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        # Container for cards
        self.cards_container = QtWidgets.QWidget()
        self.cards_layout = QtWidgets.QVBoxLayout(self.cards_container)
        self.cards_layout.setSpacing(8)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        
        # Empty state
        self.empty_state = QtWidgets.QLabel()
        self.empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_state.setStyleSheet("""
            font-size: 14px;
            color: #666;
            padding: 60px 20px;
        """)
        self.empty_state.setText("📭\n\nNo formulas extracted yet\n\nUpload a PDF and detect formulas to get started")
        self.cards_layout.addWidget(self.empty_state)
        
        self.cards_layout.addStretch()
        
        scroll.setWidget(self.cards_container)
        layout.addWidget(scroll)
    
    def add_formula(self, formula_data: dict):
        """Add a formula to the list."""
        self.formulas.append(formula_data)
        self._refresh_display()
    
    def add_formulas(self, formulas: list):
        """Add multiple formulas."""
        self.formulas.extend(formulas)
        self._refresh_display()
    
    def clear_formulas(self):
        """Clear all formulas."""
        self.formulas.clear()
        self._refresh_display()
    
    def _refresh_display(self):
        """Refresh the formula cards display."""
        # Clear existing cards
        for card in self.formula_cards:
            card.deleteLater()
        self.formula_cards.clear()
        
        # Update count
        count = len(self.formulas)
        self.count_label.setText(f"{count} formula{'s' if count != 1 else ''}")
        
        # Show/hide empty state
        if count == 0:
            self.empty_state.show()
            return
        else:
            self.empty_state.hide()
        
        # Apply current sort
        sorted_formulas = self._get_sorted_formulas()
        
        # Apply search filter if active
        search_text = self.search_box.text().lower()
        if search_text:
            sorted_formulas = [
                f for f in sorted_formulas
                if search_text in f.get('latex', '').lower()
            ]
        
        # Create cards
        for idx, formula in enumerate(sorted_formulas):
            card = FormulaCard(formula, idx)
            card.clicked.connect(self._on_card_clicked)
            card.copy_clicked.connect(self._on_copy_formula)
            card.export_clicked.connect(self._on_export_formula)
            
            self.formula_cards.append(card)
            # Insert before stretch
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
    
    def _get_sorted_formulas(self):
        """Get formulas sorted by current sort option."""
        sort_mode = self.sort_combo.currentText()
        
        if sort_mode == "Recently Added":
            return list(reversed(self.formulas))
        elif sort_mode == "Multiline First":
            return sorted(self.formulas, key=lambda f: not f.get('multiline', False))
        else:  # Page Order
            return sorted(self.formulas, key=lambda f: (f.get('page', 0), f.get('bbox', {}).get('y', 0)))
    
    def _on_sort_changed(self, text):
        """Handle sort option change."""
        self._refresh_display()
    
    def _on_search(self, text):
        """Handle search text change."""
        self._refresh_display()
    
    def _on_card_clicked(self, formula_data):
        """Handle formula card click."""
        # Deselect previous
        if self.selected_card:
            self.selected_card.set_selected(False)
        
        # Find and select new card
        for card in self.formula_cards:
            if card.formula_data == formula_data:
                card.set_selected(True)
                self.selected_card = card
                break
        
        self.formula_selected.emit(formula_data)
    
    def _on_copy_formula(self, latex, mathml):
        """Handle copy button click."""
        # Copy LaTeX to clipboard
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(latex)
        
        # Show notification (you can add a toast notification here)
        print(f"Copied LaTeX to clipboard: {latex[:50]}...")
    
    def _on_export_formula(self, formula_data):
        """Handle export button click."""
        # Implement export logic
        print(f"Export formula: {formula_data.get('latex', '')[:50]}...")
