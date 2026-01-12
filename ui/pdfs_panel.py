"""
PDFs Panel Component
Secondary sidebar that displays a list of PDF files.
Matches Mathpix's "PDFs" view structure.
"""

from PyQt6 import QtCore, QtGui, QtWidgets
from pathlib import Path
from ui.styles import Theme

class PDFListItem(QtWidgets.QWidget):
    """Single item in the PDF list."""
    
    def __init__(self, file_path: Path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)
        
        # PDF Icon
        icon_label = QtWidgets.QLabel("📄")  # Could use a proper icon image
        icon_label.setStyleSheet("color: #ff4444; font-size: 16px;")
        layout.addWidget(icon_label)
        
        # Main container for text
        text_container = QtWidgets.QWidget()
        text_layout = QtWidgets.QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        
        # Filename
        name_label = QtWidgets.QLabel(file_path.name)
        name_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-weight: 500;")
        text_layout.addWidget(name_label)
        
        # Subtitle (Size/Date - placeholder)
        # size_mb = file_path.stat().st_size / (1024 * 1024)
        # sub_label = QtWidgets.QLabel(f"{size_mb:.1f} MB")
        # sub_label.setStyleSheet(f"color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
        # text_layout.addWidget(sub_label)
        
        layout.addWidget(text_container)
        layout.addStretch()

class PDFsPanel(QtWidgets.QWidget):
    """
    Secondary sidebar for listing PDF files.
    """
    
    pdf_selected = QtCore.pyqtSignal(str) # Emits full path
    
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(280) # Match approximate width of secondary panel
        self._build_ui()
        
        # Context Menu
        self.list_widget.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        
        self.conversion_worker = None
        self.progress_dialog = None
        
    def _build_ui(self):
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {Theme.SURFACE};
                border-right: 1px solid {Theme.BORDER};
            }}
        """)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header "PDFs"
        header = QtWidgets.QWidget()
        header.setFixedHeight(50)
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)
        
        title = QtWidgets.QLabel("PDFs")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {Theme.TEXT_PRIMARY}; border: none;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        # Add Button
        add_btn = QtWidgets.QPushButton("+")
        add_btn.setFixedSize(28, 28)
        add_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                color: {Theme.TEXT_PRIMARY};
                font-size: 18px;
            }}
            QPushButton:hover {{
                background: {Theme.SURFACE_HOVER};
            }}
        """)
        header_layout.addWidget(add_btn)
        
        layout.addWidget(header)
        
        # Search Bar
        search_container = QtWidgets.QWidget()
        search_layout = QtWidgets.QVBoxLayout(search_container)
        search_layout.setContentsMargins(12, 0, 12, 12)
        
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Q Search your content")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Theme.BACKGROUND};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                padding: 8px;
                color: {Theme.TEXT_PRIMARY};
                selection-background-color: {Theme.ACCENT};
            }}
            QLineEdit:focus {{
                border: 1px solid {Theme.ACCENT};
            }}
        """)
        search_layout.addWidget(self.search_input)
        layout.addWidget(search_container)
        
        # File List
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: transparent;
                outline: none;
            }}
            QListWidget::item {{
                padding: 0px;
                border-bottom: 1px solid {Theme.BORDER}44; /* transparent border */
            }}
            QListWidget::item:selected {{
                background-color: {Theme.SURFACE_HOVER};
            }}
            QListWidget::item:hover {{
                background-color: {Theme.SURFACE_HOVER}88;
            }}
        """)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)
        
    def add_pdf(self, path: Path):
        """Add a PDF to the list."""
        path_str = str(path)
        # Check for duplicates
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(QtCore.Qt.ItemDataRole.UserRole) == path_str:
                return
 
        item = QtWidgets.QListWidgetItem(self.list_widget)
        item.setSizeHint(QtCore.QSize(0, 50))
        item.setData(QtCore.Qt.ItemDataRole.UserRole, str(path))
        
        widget = PDFListItem(path)
        self.list_widget.setItemWidget(item, widget)
        
    def _on_item_clicked(self, item):
        path_str = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if path_str:
            self.pdf_selected.emit(path_str)

    def _show_context_menu(self, position):
        item = self.list_widget.itemAt(position)
        if not item: return
        
        menu = QtWidgets.QMenu()
        convert_html_action = menu.addAction("Convert to HTML (Math Parity)")
        convert_pdf_action = menu.addAction("Convert to Searchable PDF")
        
        action = menu.exec(self.list_widget.mapToGlobal(position))
        
        path_str = item.data(QtCore.Qt.ItemDataRole.UserRole)
        
        if action == convert_html_action:
            self._convert_to_html(path_str)
        elif action == convert_pdf_action:
            self._convert_to_pdf(path_str)

    def _convert_to_html(self, pdf_path: str):
        suggested_name = Path(pdf_path).stem + ".html"
        output_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save HTML", suggested_name, "HTML Files (*.html)"
        )
        
        if not output_path:
            return
            
        self._start_html_conversion(pdf_path, output_path, is_pdf_flow=False)

    def _convert_to_pdf(self, pdf_path: str):
        suggested_name = Path(pdf_path).stem + "_searchable.pdf"
        output_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save PDF", suggested_name, "PDF Files (*.pdf)"
        )
        
        if not output_path:
            return
            
        # Create temp HTML path
        import tempfile
        import os
        fd, temp_html_path = tempfile.mkstemp(suffix=".html")
        os.close(fd)
        
        # We store the final PDF target path to use after HTML generation
        self._pdf_target_path = output_path
        self._temp_html_path = temp_html_path
        
        # Start HTML conversion first (to temp)
        self._start_html_conversion(pdf_path, temp_html_path, is_pdf_flow=True)

    def _start_html_conversion(self, pdf_path, output_path, is_pdf_flow):
        from services.export.export_worker import HTMLConversionWorker
        
        title = "Converting to Searchable PDF..." if is_pdf_flow else "Converting to HTML..."
        self.progress_dialog = QtWidgets.QProgressDialog(title, "Cancel", 0, 0, self)
        self.progress_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self.progress_dialog.show()
        
        self.conversion_worker = HTMLConversionWorker(pdf_path, output_path)
        self.conversion_worker.progress.connect(self._update_progress_label)
        
        # Use lambda or partial to pass context?
        # Simpler: just set state
        self._is_pdf_flow = is_pdf_flow
        
        self.conversion_worker.finished.connect(self._on_conversion_chunk_finished)
        self.conversion_worker.start()
        
    def _update_progress_label(self, msg):
        if self.progress_dialog:
            self.progress_dialog.setLabelText(msg)
            
    def _on_conversion_chunk_finished(self, success, result):
        # Result is the HTML path (or error)
        if not success:
            self._close_progress(False, result)
            return

        if self._is_pdf_flow:
            # HTML done, now print to PDF
            self.progress_dialog.setLabelText("Rendering PDF...")
            
            from services.export.pdf_printer import PDFPrinter
            self.pdf_printer = PDFPrinter(self) # Keep reference
            self.pdf_printer.finished.connect(self._on_pdf_print_finished)
            self.pdf_printer.print_html_to_pdf(result, self._pdf_target_path)
            
        else:
            # HTML flow done
            self._close_progress(True, result)
            
    def _on_pdf_print_finished(self, success, result):
        # Cleanup temp HTML
        if hasattr(self, '_temp_html_path'):
            try:
                Path(self._temp_html_path).unlink()
            except: pass
            
        self._close_progress(success, result)

    def _close_progress(self, success, result):
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
            
        if success:
            QtWidgets.QMessageBox.information(self, "Conversion Complete", f"Saved to:\n{result}")
        else:
            QtWidgets.QMessageBox.critical(self, "Conversion Failed", f"Error:\n{result}")
        
        self.conversion_worker = None
        self.pdf_printer = None
