"""
Upload View Component
Dedicated page for Drag & Drop file upload.
"""

from PyQt6 import QtCore, QtGui, QtWidgets
from pathlib import Path
from ui.styles import Theme

class DragDropArea(QtWidgets.QFrame):
    """Clickable and draggable upload area."""
    
    file_dropped = QtCore.pyqtSignal(str)  # Emits file path
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.SURFACE};
                border: 2px dashed {Theme.BORDER};
                border-radius: 16px;
            }}
            QFrame:hover {{
                border-color: {Theme.BORDER_FOCUS};
                background-color: {Theme.SURFACE_HOVER};
            }}
        """)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)
        
        # Icon
        icon_label = QtWidgets.QLabel("📄")
        icon_label.setStyleSheet("font-size: 64px; background: transparent; border: none;")
        icon_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)
        
        # Text
        text_label = QtWidgets.QLabel("Drag & drop PDF or Image here")
        text_label.setStyleSheet(f"""
            color: {Theme.TEXT_PRIMARY};
            font-size: 20px;
            font-weight: 700;
            background: transparent;
            border: none;
        """)
        text_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text_label)
        
        # Subtext
        sub_label = QtWidgets.QLabel("or click to browse files")
        sub_label.setStyleSheet(f"""
            color: {Theme.TEXT_SECONDARY};
            font-size: 14px;
            background: transparent;
            border: none;
        """)
        sub_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub_label)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._open_file_dialog()
            
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()
            
    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if Path(path).suffix.lower() in ['.pdf', '.png', '.jpg', '.jpeg']:
                self.file_dropped.emit(path)
                return  # Handle one file at a time for now

    def _open_file_dialog(self):
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select PDF or Image", "", "Documents (*.pdf *.png *.jpg *.jpeg)"
        )
        if fname:
            self.file_dropped.emit(fname)


class UploadView(QtWidgets.QWidget):
    """Main upload view container."""
    
    file_selected = QtCore.pyqtSignal(str)
    
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {Theme.BACKGROUND};
                color: {Theme.TEXT_PRIMARY};
            }}
        """)
        
        # Main layout with scrolling support
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        
        content_widget = QtWidgets.QWidget()
        self.layout = QtWidgets.QVBoxLayout(content_widget)
        self.layout.setContentsMargins(60, 60, 60, 60)
        self.layout.setSpacing(32)
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        
        # --- Header ---
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(16)
        
        title_box = QtWidgets.QVBoxLayout()
        title_box.setSpacing(4)
        
        title = QtWidgets.QLabel("File Management")
        title.setStyleSheet(f"""
            font-size: 32px;
            font-weight: 800;
            color: {Theme.TEXT_PRIMARY};
            letter-spacing: -0.5px;
        """)
        
        subtitle = QtWidgets.QLabel("Upload, manage, and convert your documents.")
        subtitle.setStyleSheet(f"font-size: 16px; color: {Theme.TEXT_SECONDARY};")
        
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header_layout.addLayout(title_box)
        header_layout.addStretch()
        
        # Search Input
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("🔍  Filter files...")
        self.search_input.setFixedWidth(300)
        self.search_input.setFixedHeight(42)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 21px;
                padding: 0 16px;
                font-size: 13px;
                color: {Theme.TEXT_PRIMARY};
            }}
            QLineEdit:focus {{
                border-color: {Theme.ACCENT};
                background-color: {Theme.SURFACE_HOVER};
            }}
        """)
        header_layout.addWidget(self.search_input)
        
        self.layout.addLayout(header_layout)
        self.layout.addSpacing(10)
        
        # --- Drag & Drop Area ---
        self.drop_area = DragDropArea()
        self.drop_area.setFixedHeight(240)
        # Connect to internal handler instead of emitting immediately
        self.drop_area.file_dropped.connect(self._on_file_dropped)
        
        self.layout.addWidget(self.drop_area)
        
        # --- File Action Area (Hidden by default) ---
        self.action_area = QtWidgets.QWidget()
        self.action_area.setVisible(False)
        self.action_layout = QtWidgets.QVBoxLayout(self.action_area)
        self.action_layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.action_area)
        
        self.layout.addSpacing(20)
        
        # --- Quick Actions Grid ---
        actions_label = QtWidgets.QLabel("Quick Actions")
        actions_label.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {Theme.TEXT_TERTIARY}; text-transform: uppercase; letter-spacing: 0.8px;")
        self.layout.addWidget(actions_label)
        
        actions_grid = QtWidgets.QHBoxLayout()
        actions_grid.setSpacing(20)
        
        btn_url = self._create_action_button("🌐", "Import from URL", "Download PDF from link")
        actions_grid.addWidget(btn_url)
        
        btn_batch = self._create_action_button("⚡", "Batch Convert", "Process multiple files")
        actions_grid.addWidget(btn_batch)
        
        btn_scan = self._create_action_button("📷", "Scan Document", "From connected scanner")
        actions_grid.addWidget(btn_scan)
        
        actions_grid.addStretch()
        self.layout.addLayout(actions_grid)
        
        self.layout.addStretch()

    def _on_file_dropped(self, path: str):
        """Handle dropped file: Show options instead of auto-opening."""
        self._show_file_options(path)

    
    def _show_file_options(self, path: str):
        # Clear previous options
        for i in reversed(range(self.action_layout.count())): 
            self.action_layout.itemAt(i).widget().setParent(None)
            
        self.action_area.setVisible(True)
        
        # Create Card
        self.card = QtWidgets.QFrame()
        self.card.setFixedHeight(120)
        self.card.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.SURFACE};
                border: 1px solid {Theme.ACCENT};
                border-radius: 12px;
            }}
        """)
        
        card_layout = QtWidgets.QHBoxLayout(self.card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(24)
        
        # File Icon
        icon_lbl = QtWidgets.QLabel("📄")
        icon_lbl.setStyleSheet("font-size: 48px; border: none; background: transparent;")
        card_layout.addWidget(icon_lbl)
        
        # File Info Container
        info_layout = QtWidgets.QVBoxLayout()
        info_layout.setSpacing(4)
        
        name_lbl = QtWidgets.QLabel(Path(path).name)
        name_lbl.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {Theme.TEXT_PRIMARY}; border: none; background: transparent;")
        
        self.status_lbl = QtWidgets.QLabel("Ready for processing")
        self.status_lbl.setStyleSheet(f"font-size: 14px; color: {Theme.SUCCESS}; border: none; background: transparent;")
        
        # Progress Bar (Hidden by default)
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                background-color: {Theme.BORDER};
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {Theme.ACCENT};
                border-radius: 3px;
            }}
        """)
        
        info_layout.addWidget(name_lbl)
        info_layout.addWidget(self.status_lbl)
        info_layout.addWidget(self.progress_bar)
        card_layout.addLayout(info_layout)
        
        card_layout.addStretch()
        
        # Actions Container
        self.actions_container = QtWidgets.QWidget()
        self.actions_layout = QtWidgets.QHBoxLayout(self.actions_container)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(16)
        
        # Actions
        self.btn_convert = QtWidgets.QPushButton("Convert to HTML")
        self.btn_convert.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_convert.setFixedSize(160, 44)
        self.btn_convert.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.SURFACE_HOVER};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {Theme.ACCENT};
            }}
        """)
        self.btn_convert.clicked.connect(lambda: self._convert_pdf(path))
        self.actions_layout.addWidget(self.btn_convert)
        
        self.btn_open = QtWidgets.QPushButton("Open in Viewer")
        self.btn_open.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_open.setFixedSize(160, 44)
        self.btn_open.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.ACCENT};
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Theme.ACCENT_HOVER};
            }}
        """)
        self.btn_open.clicked.connect(lambda: self.file_selected.emit(path))
        self.actions_layout.addWidget(self.btn_open)
        
        card_layout.addWidget(self.actions_container)
        
        self.action_layout.addWidget(self.card)

    def _convert_pdf(self, path: str):
        suggested_name = Path(path).stem + ".html"
        output_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save HTML", suggested_name, "HTML Files (*.html)"
        )
        
        if not output_path:
            return
            
        from services.export.export_worker import HTMLConversionWorker
        
        # Switch UI to loading state
        self.actions_container.setVisible(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0) # Indeterminate
        self.status_lbl.setText("Converting PDF to HTML...")
        self.status_lbl.setStyleSheet(f"font-size: 14px; color: {Theme.ACCENT}; border: none; background: transparent;")
        
        self.conversion_worker = HTMLConversionWorker(path, output_path)
        # Update text if worker provides progress strings
        self.conversion_worker.progress.connect(self.status_lbl.setText)
        self.conversion_worker.finished.connect(self._on_conversion_finished)
        self.conversion_worker.start()

    def _on_conversion_finished(self, success, result):
        # Reset UI or show success state
        self.progress_bar.setVisible(False)
        self.actions_container.setVisible(True)
        
        if success:
            self.status_lbl.setText("Conversion Complete ✅")
            self.status_lbl.setStyleSheet(f"font-size: 14px; color: {Theme.SUCCESS}; border: none; background: transparent;")
            # Maybe offer to open the folder?
            result_path = Path(result)
            QtWidgets.QMessageBox.information(self, "Conversion Complete", f"Saved to:\n{result}")
        else:
            self.status_lbl.setText("Conversion Failed ❌")
            self.status_lbl.setStyleSheet(f"font-size: 14px; color: {Theme.ERROR}; border: none; background: transparent;")
            QtWidgets.QMessageBox.critical(self, "Conversion Failed", f"Error:\n{result}")


    def _create_action_button(self, icon, title, subtitle):
        btn = QtWidgets.QPushButton()
        btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(80)
        btn.setFixedWidth(260)
        
        # We need a custom layout inside the button or use a QFrame that is clickable
        # Using QFrame for better styling control
        frame = QtWidgets.QFrame()
        frame.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        frame.setFixedHeight(90)
        frame.setFixedWidth(280)
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 12px;
            }}
            QFrame:hover {{
                border-color: {Theme.ACCENT};
                background-color: {Theme.SURFACE_HOVER};
            }}
        """)
        
        layout = QtWidgets.QHBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        icon_lbl = QtWidgets.QLabel(icon)
        icon_lbl.setStyleSheet(f"font-size: 24px; background: transparent; border: none;")
        layout.addWidget(icon_lbl)
        
        text_layout = QtWidgets.QVBoxLayout()
        text_layout.setSpacing(2)
        
        t_lbl = QtWidgets.QLabel(title)
        t_lbl.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {Theme.TEXT_PRIMARY}; border: none; background: transparent;")
        
        s_lbl = QtWidgets.QLabel(subtitle)
        s_lbl.setStyleSheet(f"font-size: 12px; color: {Theme.TEXT_SECONDARY}; border: none; background: transparent;")
        
        text_layout.addWidget(t_lbl)
        text_layout.addWidget(s_lbl)
        
        layout.addLayout(text_layout)
        layout.addStretch()
        
        # Return frame (caller adds to layout)
        return frame
