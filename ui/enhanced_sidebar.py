"""Enhanced sidebar with navigation and file list."""
from __future__ import annotations

from pathlib import Path
from typing import List

from PyQt6 import QtCore, QtGui, QtWidgets

from ui.styles import Theme


class EnhancedSidebar(QtWidgets.QFrame):
    """Modern sidebar with navigation and PDF file list."""

    upload_requested = QtCore.pyqtSignal(str)
    pdf_selected = QtCore.pyqtSignal(str)
    navigation_changed = QtCore.pyqtSignal(str)  # "home", "files", "notes", "pdfs", "snips"
    formula_selected = QtCore.pyqtSignal(dict)  # Emit when a formula is clicked

    def __init__(self) -> None:
        super().__init__()
        self.setFixedWidth(300)
        self._pdf_paths: set[str] = set()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.BACKGROUND};
            }}
            QPushButton {{
                background-color: transparent;
                color: {Theme.TEXT_SECONDARY};
                border: none;
                padding: 12px 16px;
                text-align: left;
                border-radius: 6px;
                font-weight: 500;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {Theme.SURFACE_HOVER};
                color: {Theme.TEXT_PRIMARY};
            }}
            QPushButton:checked {{
                background-color: {Theme.ACCENT};
                color: {Theme.ACCENT_TEXT};
            }}
            QLineEdit {{
                background-color: {Theme.SURFACE};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                padding: 10px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {Theme.BORDER_FOCUS};
            }}
            QListWidget {{
                background-color: transparent;
                color: {Theme.TEXT_SECONDARY};
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                padding: 10px 14px;
                border: none;
                border-radius: 6px;
                margin: 2px 0px;
                min-height: 42px;
                color: {Theme.TEXT_SECONDARY};
                background-color: transparent;
            }}
            QListWidget::item:hover {{
                background-color: {Theme.SURFACE_HOVER};
                color: {Theme.TEXT_PRIMARY};
            }}
            QListWidget::item:selected {{
                background-color: {Theme.ACCENT};
                color: {Theme.ACCENT_TEXT};
            }}
            QListWidget::item:selected:hover {{
                background-color: {Theme.ACCENT_HOVER};
                color: {Theme.ACCENT_TEXT};
            }}
        """)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(12)
        layout.setSizeConstraint(QtWidgets.QLayout.SizeConstraint.SetMinimumSize)

        # Logo/Brand - Modern design
        logo_frame = QtWidgets.QFrame()
        logo_frame.setStyleSheet("background: transparent;")
        logo_layout = QtWidgets.QHBoxLayout(logo_frame)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        
        logo_label = QtWidgets.QLabel("MathML Extractor")
        logo_label.setStyleSheet("""
            font-size: 22px; 
            font-weight: 700; 
            color: #ffffff;
            letter-spacing: 1px;
            padding-left: 5px;
        """)
        
        # Add Icon if present
        from pathlib import Path
        if Path("app_icon.png").exists():
             logo_icon = QtWidgets.QLabel()
             pixmap = QtGui.QPixmap("app_icon.png")
             # Scale if needed
             pixmap = pixmap.scaled(32, 32, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation)
             logo_icon.setPixmap(pixmap)
             logo_layout.addWidget(logo_icon)
             logo_layout.addSpacing(6)
        
        logo_layout.addWidget(logo_label)
        logo_layout.addStretch()
        layout.addWidget(logo_frame)
        
        layout.addSpacing(8)

        # Navigation buttons
        nav_group = QtWidgets.QButtonGroup(self)
        nav_group.setExclusive(True)
        self.home_btn = self._create_nav_button("Home", "home")
        self.files_btn = self._create_nav_button("Files", "files")
        self.notes_btn = self._create_nav_button("Notes", "notes")
        self.pdfs_btn = self._create_nav_button("PDFs", "pdfs")
        self.snips_btn = self._create_nav_button("Snips", "snips")
        self.history_btn = self._create_nav_button("History", "history")

        for btn in [self.home_btn, self.files_btn, self.notes_btn, self.pdfs_btn, self.snips_btn, self.history_btn]:
            nav_group.addButton(btn)
            layout.addWidget(btn)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, name=btn.property("nav_name"): self.navigation_changed.emit(name))

        layout.addSpacing(20)

        # Support and Settings
        support_btn = QtWidgets.QPushButton("Support")
        support_btn.setCheckable(False)
        support_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        layout.addWidget(support_btn)
        
        settings_btn = QtWidgets.QPushButton("Settings")
        settings_btn.setCheckable(False)
        settings_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        layout.addWidget(settings_btn)
        
        # Connect settings button (will be connected in main window)
        self.settings_btn = settings_btn

        layout.addSpacing(16)
        
        # Separator
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        separator.setStyleSheet(f"color: {Theme.BORDER}; max-height: 1px;")
        layout.addWidget(separator)
        
        layout.addSpacing(8)

        # PDFs section
        pdfs_label = QtWidgets.QLabel("PDFs")
        pdfs_label.setStyleSheet(f"""
            color: {Theme.TEXT_TERTIARY}; 
            font-size: 11px; 
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            padding: 4px 0px;
        """)
        layout.addWidget(pdfs_label)

        # Search bar
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search your content")
        layout.addWidget(self.search_edit)

        # PDF file list - scrollable and filling space
        self.pdf_list = QtWidgets.QListWidget()
        self.pdf_list.setSpacing(2)
        self.pdf_list.itemClicked.connect(self._on_pdf_selected)
        self.pdf_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self._current_selected_pdf: str | None = None
        
        # Add placeholder message when list is empty
        self._update_list_placeholder()
        layout.addWidget(self.pdf_list)
        
        # Add stretch to push everything up (PDF list will expand)
        # layout.addStretch()

        # Status label - modern design
        status_frame = QtWidgets.QFrame()
        status_frame.setStyleSheet(f"""
            QFrame {{
                background: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                padding: 0px;
            }}
        """)
        status_layout = QtWidgets.QVBoxLayout(status_frame)
        status_layout.setContentsMargins(12, 10, 12, 10)
        
        self.status_label = QtWidgets.QLabel("Ready to upload")
        self.status_label.setStyleSheet("""
            color: #4CAF50; 
            font-size: 12px; 
            font-weight: 600;
            padding: 0px;
        """)
        self.status_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(self.status_label)
        layout.addWidget(status_frame)

        # Upload button - modern prominent design
        self.upload_btn = QtWidgets.QPushButton("📄 Upload PDF")
        self.upload_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.ACCENT};
                color: {Theme.ACCENT_TEXT};
                padding: 14px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 14px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {Theme.ACCENT_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {Theme.ACCENT_PRESSED};
            }}
        """)
        self.upload_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.upload_btn.clicked.connect(self._on_upload)
        layout.addWidget(self.upload_btn)

        # Set Home as default active
        self.home_btn.setChecked(True)

    def _create_nav_button(self, text: str, nav_name: str) -> QtWidgets.QPushButton:
        """Create a navigation button."""
        btn = QtWidgets.QPushButton(text)
        btn.setProperty("nav_name", nav_name)
        btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        return btn

    def _on_upload(self) -> None:
        """Handle PDF upload."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select PDF", "", "PDF Files (*.pdf)"
        )
        if path:
            self.upload_requested.emit(path)
            self._add_pdf_to_list(path)

    def _on_pdf_selected(self, item: QtWidgets.QListWidgetItem) -> None:
        """Handle PDF selection from list."""
        pdf_path = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if pdf_path and pdf_path != self._current_selected_pdf:
            self._current_selected_pdf = pdf_path
            self.pdf_selected.emit(pdf_path)
    
    def _on_formula_clicked(self, item: QtWidgets.QListWidgetItem) -> None:
        """Handle formula item click - emit signal to show in preview."""
        formula_data = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if formula_data and isinstance(formula_data, dict):
            self.formula_selected.emit(formula_data)
    
    def set_selected_pdf(self, pdf_path: str) -> None:
        """Set the currently selected PDF in the list."""
        for i in range(self.pdf_list.count()):
            item = self.pdf_list.item(i)
            if item and item.data(QtCore.Qt.ItemDataRole.UserRole) == pdf_path:
                self.pdf_list.setCurrentItem(item)
                self._current_selected_pdf = pdf_path
                break
    
    def set_active_nav(self, nav_name: str) -> None:
        """Set the active navigation button programmatically."""
        nav_buttons = {
            "home": self.home_btn,
            "files": self.files_btn,
            "notes": self.notes_btn,
            "pdfs": self.pdfs_btn,
            "snips": self.snips_btn,
            "history": self.history_btn
        }
        
        btn = nav_buttons.get(nav_name)
        if btn:
            btn.setChecked(True)

    def _add_pdf_to_list(self, pdf_path: str) -> None:
        """Add a PDF to the file list with Mathpix-style formatting."""
        if pdf_path in self._pdf_paths:
            # Update existing item if already in list
            for i in range(self.pdf_list.count()):
                item = self.pdf_list.item(i)
                if item and item.data(QtCore.Qt.ItemDataRole.UserRole) == pdf_path:
                    return
            return
        
        # Remove placeholder if it exists
        self._remove_placeholder()
        self._pdf_paths.add(pdf_path)
        path = Path(pdf_path)
        
        # Create item with icon
        item = QtWidgets.QListWidgetItem()
        item.setText(path.name)
        item.setData(QtCore.Qt.ItemDataRole.UserRole, pdf_path)
        
        # Set PDF icon
        icon = QtGui.QIcon.fromTheme("application-pdf")
        if icon.isNull():
            # Fallback: use a text-based icon indicator
            item.setText(f"📄 {path.name}")
        else:
            item.setIcon(icon)
        
        # Set font and styling - ensure text is visible
        font = item.font()
        font.setPointSize(10)
        item.setFont(font)
        
        # Explicitly set text color to white
        item.setForeground(QtGui.QColor("white"))
        
        self.pdf_list.addItem(item)
        
        # Auto-select if it's the first item
        if self.pdf_list.count() == 1:
            self.pdf_list.setCurrentItem(item)
            self._current_selected_pdf = pdf_path

    def _remove_placeholder(self) -> None:
        """Remove placeholder item if it exists."""
        for i in range(self.pdf_list.count()):
            item = self.pdf_list.item(i)
            if item and item.text() == "No PDFs uploaded yet":
                self.pdf_list.takeItem(i)
                break

    def _update_list_placeholder(self) -> None:
        """Update placeholder message based on list state."""
        self._remove_placeholder()
        if self.pdf_list.count() == 0:
            # Show placeholder message with better styling
            placeholder = QtWidgets.QListWidgetItem("No PDFs uploaded yet")
            placeholder.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)  # Make it non-selectable
            placeholder.setForeground(QtGui.QColor("#888"))
            font = placeholder.font()
            font.setItalic(True)
            font.setPointSize(10)
            placeholder.setFont(font)
            placeholder.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.pdf_list.addItem(placeholder)

    def load_pdf_list(self, pdf_paths: List[str]) -> None:
        """Load a list of PDFs into the sidebar."""
        self.pdf_list.clear()
        self._pdf_paths.clear()
        for pdf_path in pdf_paths:
            self._add_pdf_to_list(pdf_path)
        self._update_list_placeholder()

    def set_active_nav(self, nav_name: str) -> None:
        """Set the active navigation button."""
        buttons = {
            "home": self.home_btn,
            "files": self.files_btn,
            "notes": self.notes_btn,
            "pdfs": self.pdfs_btn,
            "snips": self.snips_btn,
        }
        # Clear all first
        for btn in buttons.values():
            btn.setChecked(False)
        if btn := buttons.get(nav_name):
            btn.setChecked(True)

    def set_status(self, text: str, mode: str = "normal") -> None:
        """Update sidebar status text with contextual styling."""
        self.status_label.setText(text)
        
        if mode == "success":
            self.status_label.setStyleSheet("color: #4CAF50; font-size: 11px; font-weight: 700; text-transform: uppercase;")
        elif mode == "error":
            self.status_label.setStyleSheet("color: #F44336; font-size: 11px; font-weight: 700; text-transform: uppercase;")
        elif mode == "working":
            self.status_label.setStyleSheet(f"color: {Theme.ACCENT}; font-size: 11px; font-weight: 700; text-transform: uppercase;")
        else:
            self.status_label.setStyleSheet(f"color: {Theme.TEXT_TERTIARY}; font-size: 11px; font-weight: 600; text-transform: uppercase;")
    
    def update_formulas_display(self, formulas_by_page: dict[int, List[dict]]) -> None:
        """Update the formulas list with page-wise extracted formulas."""
        # DEPRECATED: Formula list is now in the main view's right sidebar
        pass
    
    def _on_formula_clicked(self, item: QtWidgets.QListWidgetItem) -> None:
        """Handle formula item click - emit signal to show in preview."""
        formula_data = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if formula_data and isinstance(formula_data, dict):
            self.formula_selected.emit(formula_data)

