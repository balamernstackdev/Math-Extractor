"""
Dashboard View Component - Welcome Screen

Main welcome/home view with:
- Upload cards (PDF, Note, Snip)
- Drag & drop area
- Recent items section
"""

from PyQt6 import QtCore, QtGui, QtWidgets
from datetime import datetime
from pathlib import Path
from ui.styles import Theme


class DashboardView(QtWidgets.QWidget):
    """
    Welcome screen dashboard.
    
    Signals:
        upload_pdf_clicked: User clicked upload PDF
        upload_note_clicked: User clicked upload note
        upload_snip_clicked: User clicked upload snip
    """
    
    upload_pdf_clicked = QtCore.pyqtSignal()
    upload_note_clicked = QtCore.pyqtSignal()
    upload_snip_clicked = QtCore.pyqtSignal()
    equation_selected = QtCore.pyqtSignal(dict)  # For compatibility
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.equations = []  # Store equation data for compatibility
        self._build_ui()
    
    def _build_ui(self):
        """Build welcome dashboard UI."""
        # Main Scroll Area to ensure dashboard fits small screens
        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background-color: {Theme.BACKGROUND}; border: none;")
        
        content = QtWidgets.QWidget()
        content.setStyleSheet(f"background-color: {Theme.BACKGROUND};")
        self.layout_main = QtWidgets.QVBoxLayout(self) # Attach scroll to self
        self.layout_main.setContentsMargins(0, 0, 0, 0)
        self.layout_main.addWidget(scroll)
        
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(60, 60, 60, 60)
        layout.setSpacing(32)
        
        scroll.setWidget(content)
        
        # --- Header Section ---
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(16)
        
        # Title Stack
        title_box = QtWidgets.QVBoxLayout()
        title_box.setSpacing(6)
        
        header_title = QtWidgets.QLabel("Welcome to Mathpix Clone")
        header_title.setStyleSheet(f"""
            font-size: 32px; 
            font-weight: 800; 
            color: {Theme.TEXT_PRIMARY};
            font-family: {Theme.FONT_FAMILY};
            letter-spacing: -0.5px;
        """)
        
        header_sub = QtWidgets.QLabel("Your workspace for mathematical document processing.")
        header_sub.setStyleSheet(f"font-size: 16px; color: {Theme.TEXT_SECONDARY};")
        
        title_box.addWidget(header_title)
        title_box.addWidget(header_sub)
        header_layout.addLayout(title_box)
        header_layout.addStretch()
        
        # Global Search
        search_input = QtWidgets.QLineEdit()
        search_input.setPlaceholderText("🔍  Search documents, snips, or notes...")
        search_input.setFixedWidth(360)
        search_input.setFixedHeight(42)
        search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 21px;
                padding: 0 16px;
                color: {Theme.TEXT_PRIMARY};
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {Theme.ACCENT};
                background-color: {Theme.SURFACE_HOVER};
            }}
        """)
        header_layout.addWidget(search_input)
        
        layout.addLayout(header_layout)
        layout.addSpacing(12)
        
        # --- Action Grid (Quick Actions) ---
        grid_label = QtWidgets.QLabel("Quick Actions")
        grid_label.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {Theme.TEXT_TERTIARY}; text-transform: uppercase; letter-spacing: 0.8px;")
        layout.addWidget(grid_label)
        
        grid = QtWidgets.QHBoxLayout()
        grid.setSpacing(20)
        
        # Card 1: Upload PDF
        card_pdf = self._create_action_card(
            "📄", "Upload PDF", "Process documents\nwith OCR", 
            Theme.ACCENT, self.upload_pdf_clicked
        )
        grid.addWidget(card_pdf)
        
        # Card 2: New Note (Stub)
        card_note = self._create_action_card(
            "📝", "Create Note", "Write with Markdown\n& LaTeX", 
            Theme.SUCCESS, self.upload_note_clicked
        )
        grid.addWidget(card_note)
        
        # Card 3: Screen Snip (Stub)
        card_snip = self._create_action_card(
            "✂️", "Paste Snip", "From clipboard\n(Ctrl+V)", 
            Theme.WARNING, self.upload_snip_clicked
        )
        grid.addWidget(card_snip)
        
        layout.addLayout(grid)
        layout.addSpacing(24)
        
        # --- Drag & Drop Zone ---
        drop_frame = QtWidgets.QFrame()
        drop_frame.setFixedHeight(140)
        drop_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.SURFACE}80; /* Transparent */
                border: 2px dashed {Theme.BORDER};
                border-radius: 16px;
            }}
            QFrame:hover {{
                border-color: {Theme.ACCENT};
                background-color: {Theme.ACCENT_BG};
            }}
        """)
        drop_layout = QtWidgets.QVBoxLayout(drop_frame)
        drop_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        drop_text = QtWidgets.QLabel("Drag and drop files here to upload")
        drop_text.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        drop_text.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {Theme.TEXT_SECONDARY}; border: none; background: transparent;")
        
        drop_sub = QtWidgets.QLabel("Supports PDF, JPG, PNG")
        drop_sub.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        drop_sub.setStyleSheet(f"font-size: 12px; color: {Theme.TEXT_TERTIARY}; margin-top: 4px; border: none; background: transparent;")
        
        drop_layout.addWidget(drop_text)
        drop_layout.addWidget(drop_sub)
        
        layout.addWidget(drop_frame)
        layout.addSpacing(24)
        
        # --- Recent Sections Split ---
        recents_split = QtWidgets.QHBoxLayout()
        recents_split.setSpacing(40)
        
        # Left: Recent PDFs
        pdfs_col = QtWidgets.QVBoxLayout()
        pdfs_col.setSpacing(12)
        pdf_label = QtWidgets.QLabel("Recent Documents")
        pdf_label.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {Theme.TEXT_PRIMARY};")
        pdfs_col.addWidget(pdf_label)
        
        self.recent_pdfs_container = QtWidgets.QWidget()
        self.recent_pdfs_layout = QtWidgets.QVBoxLayout(self.recent_pdfs_container)
        self.recent_pdfs_layout.setContentsMargins(0, 0, 0, 0)
        self.recent_pdfs_layout.setSpacing(8)
        self.empty_state = QtWidgets.QLabel("No recent documents") # Ref
        self.recent_pdfs_layout.addWidget(self.empty_state)
        
        pdfs_col.addWidget(self.recent_pdfs_container)
        pdfs_col.addStretch()
        
        # Right: Recent Snips
        snips_col = QtWidgets.QVBoxLayout()
        snips_col.setSpacing(12)
        snips_label = QtWidgets.QLabel("Latest Snips")
        snips_label.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {Theme.TEXT_PRIMARY};")
        snips_col.addWidget(snips_label)
        
        self.recent_snips_container = QtWidgets.QWidget()
        self.recent_snips_layout = QtWidgets.QVBoxLayout(self.recent_snips_container)
        self.recent_snips_layout.setContentsMargins(0, 0, 0, 0)
        self.recent_snips_layout.setSpacing(8)
        self.snips_empty_state = QtWidgets.QLabel("No recent snips") # Ref
        self.recent_snips_layout.addWidget(self.snips_empty_state)
        
        snips_col.addWidget(self.recent_snips_container)
        snips_col.addStretch()
        
        recents_split.addLayout(pdfs_col, 1)
        recents_split.addLayout(snips_col, 1)
        
        layout.addLayout(recents_split)
        layout.addStretch()

    def _create_action_card(self, icon, title, subtitle, accent_color, signal_to_emit):
        """Standardized action card for the dashboard."""
        card = QtWidgets.QFrame()
        card.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        card.setFixedHeight(110)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 12px;
            }}
            QFrame:hover {{
                border: 1px solid {accent_color};
                background-color: {Theme.SURFACE_HOVER};
            }}
        """)
        
        # Click handler trick for QFrame
        card.mousePressEvent = lambda e: signal_to_emit.emit()
        
        h_layout = QtWidgets.QHBoxLayout(card)
        h_layout.setContentsMargins(20, 20, 20, 20)
        h_layout.setSpacing(16)
        
        # Icon Circle
        icon_lbl = QtWidgets.QLabel(icon)
        icon_lbl.setFixedSize(48, 48)
        icon_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet(f"""
            background-color: {accent_color}20; 
            color: {accent_color};
            border-radius: 24px;
            font-size: 22px;
            border: none;
        """)
        
        # Text Stack
        v_layout = QtWidgets.QVBoxLayout()
        v_layout.setSpacing(4)
        
        t_lbl = QtWidgets.QLabel(title)
        t_lbl.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {Theme.TEXT_PRIMARY}; border: none; background: transparent;")
        
        s_lbl = QtWidgets.QLabel(subtitle)
        s_lbl.setStyleSheet(f"font-size: 12px; color: {Theme.TEXT_SECONDARY}; border: none; background: transparent;")
        
        v_layout.addWidget(t_lbl)
        v_layout.addWidget(s_lbl)
        
        h_layout.addWidget(icon_lbl)
        h_layout.addLayout(v_layout)
        h_layout.addStretch()
        
        return card
    
    # _create_upload_card is replaced by _create_action_card above
    # Removing old helper to avoid confusion

    
    def _darken_color(self, hex_color: str, factor: float = 0.15) -> str:
        """Darken a hex color."""
        # Simple darkening - just reduce RGB values
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r = int(r * (1 - factor))
        g = int(g * (1 - factor))
        b = int(b * (1 - factor))
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def update_recent_snips(self, snips: list):
        """Update recent snips displayed on the dashboard."""
        while self.recent_snips_layout.count():
            item = self.recent_snips_layout.takeAt(0)
            widget = item.widget()
            if widget and widget != self.snips_empty_state:
                widget.deleteLater()
        
        if not snips:
            self.recent_snips_layout.addWidget(self.snips_empty_state)
            self.snips_empty_state.show()
            return
            
        self.snips_empty_state.hide()
        
        for snip in snips[:4]: # Show 4 recent snips
            card = QtWidgets.QFrame()
            # Vertical layout for snip card in grid
            card.setFixedSize(200, 140)
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {Theme.SURFACE};
                    border: 1px solid {Theme.BORDER};
                    border-radius: 8px;
                }}
                QFrame:hover {{ border-color: {Theme.ACCENT}; }}
            """)
            card.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            
            c_layout = QtWidgets.QVBoxLayout(card)
            
            # Thumbnail if available
            if snip.get("image") and Path(snip["image"]).exists():
                img = QtWidgets.QLabel()
                pix = QtGui.QPixmap(snip["image"]).scaled(180, 80, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
                img.setPixmap(pix)
                img.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                c_layout.addWidget(img)
            else:
                latex = snip.get("latex", "")
                preview = (latex[:30] + "...") if len(latex) > 30 else latex
                lbl = QtWidgets.QLabel(preview)
                lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                lbl.setWordWrap(True)
                lbl.setStyleSheet("font-size: 11px;")
                c_layout.addWidget(lbl)
                
            card.mousePressEvent = lambda e, s=snip: self.equation_selected.emit(s)
            self.recent_snips_layout.addWidget(card)
            
        self.recent_snips_layout.addStretch()
    
    def update_recent_pdfs(self, paths: list):
        """Update the list of recent PDFs displayed on the dashboard."""
        # Clear current list
        while self.recent_pdfs_layout.count():
            item = self.recent_pdfs_layout.takeAt(0)
            widget = item.widget()
            if widget and widget != self.empty_state:
                widget.deleteLater()
        
        if not paths:
            self.recent_pdfs_layout.addWidget(self.empty_state)
            self.empty_state.show()
            return
            
        self.empty_state.hide()
        
        # Add up to 5 recent PDFs
        for path_str in paths[:5]:
            path = Path(path_str)
            if not path.exists(): continue
            
            btn = QtWidgets.QPushButton(f"📄  {path.name}")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Theme.SURFACE};
                    border: 1px solid {Theme.BORDER};
                    border-radius: 6px;
                    padding: 12px 16px;
                    text-align: left;
                    font-size: 14px;
                    color: {Theme.TEXT_PRIMARY};
                }}
                QPushButton:hover {{
                    background-color: {Theme.SURFACE_HOVER};
                    border-color: {Theme.ACCENT};
                }}
            """)
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            
            # Connect click to a signal that main window can handle
            # For now, we'll reuse the existing signal or create a new one
            # Actually, we can use a lambda but be careful with scope
            btn.clicked.connect(lambda checked, p=path_str: self.equation_selected.emit({"path": p, "type": "pdf_jump"}))
            
            self.recent_pdfs_layout.addWidget(btn)
        
        self.recent_pdfs_layout.addStretch()

    # Compatibility methods for existing code
    def add_equation(self, equation_data: dict):
        """Add an equation (compatibility)."""
        self.equations.append(equation_data)
    
    def set_equations(self, equations: list):
        """Set all equations (compatibility)."""
        self.equations = equations
