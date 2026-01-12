"""
Equation Card Component

Displays a single equation with:
- Rendered MathML preview
- Status badge (🟢/🟡/🔴)
- Metadata (type, timestamp)
- Action buttons (Copy, Save, Star)
- Hover effects
"""

from PyQt6 import QtCore, QtGui, QtWidgets
from datetime import datetime
from ui.styles import Theme


class EquationCard(QtWidgets.QFrame):
    """
    Card component for displaying an equation.
    
    Signals:
        copy_clicked: User clicked copy button
        save_clicked: User clicked save button
        star_clicked: User clicked star button
        card_clicked: User clicked the card
    """
    
    copy_clicked = QtCore.pyqtSignal()
    save_clicked = QtCore.pyqtSignal()
    star_clicked = QtCore.pyqtSignal()
    card_clicked = QtCore.pyqtSignal()
    
    def __init__(self, equation_data: dict, parent=None):
        """
        Args:
            equation_data: Dict with keys:
                - mathml: str (MathML code)
                - is_valid: bool
                - has_warnings: bool
                - equation_type: str ('single-line', 'align', 'cases', etc.)
                - timestamp: datetime
                - is_starred: bool
        """
        super().__init__(parent)
        self.equation_data = equation_data
        self._build_ui()
    
    def _build_ui(self):
        """Build the card UI."""
        self.setFixedHeight(200)
        self.setStyleSheet(f"""
            QFrame {{
                background: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 8px;
            }}
            QFrame:hover {{
                background: {Theme.SURFACE};
                border: 1px solid {Theme.ACCENT};
                box-shadow: 0 4px 12px rgba(37, 99, 235, 0.15);
            }}
        """)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header: Status + Type Badge
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(8)
        
        # Status indicator
        status_icon = self._get_status_icon()
        status_label = QtWidgets.QLabel(status_icon)
        status_label.setStyleSheet("font-size: 20px;")
        header_layout.addWidget(status_label)
        
        # Type badge (if multiline)
        eq_type = self.equation_data.get('equation_type', 'single-line')
        if eq_type != 'single-line':
            type_badge = QtWidgets.QLabel(f"📐 {eq_type.upper()}")
            type_badge.setStyleSheet(f"""
                background: {Theme.ACCENT};
                color: white;
                font-size: 10px;
                font-weight: 600;
                padding: 4px 8px;
                border-radius: 4px;
            """)
            header_layout.addWidget(type_badge)
        
        header_layout.addStretch()
        
        # Star indicator (if starred)
        if self.equation_data.get('is_starred', False):
            star_label = QtWidgets.QLabel("⭐")
            star_label.setStyleSheet("font-size: 16px;")
            header_layout.addWidget(star_label)
        
        layout.addLayout(header_layout)
        
        # Rendered equation preview
        preview_frame = QtWidgets.QFrame()
        preview_frame.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BACKGROUND};
                border: 1px solid {Theme.BORDER};
                border-radius: 8px;
            }}
        """)
        preview_frame.setMinimumHeight(100)
        
        preview_layout = QtWidgets.QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(12, 12, 12, 12)
        
        # Simple text preview (in real app, would render MathML)
        mathml = self.equation_data.get('mathml', '')
        preview_text = self._extract_preview_text(mathml)
        
        preview_label = QtWidgets.QLabel(preview_text)
        preview_label.setStyleSheet(f"""
            color: {Theme.TEXT_PRIMARY};
            font-size: 16px;
            font-family: 'Cambria Math', 'Times New Roman', serif;
        """)
        preview_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        preview_label.setWordWrap(True)
        preview_layout.addWidget(preview_label)
        
        layout.addWidget(preview_frame, stretch=1)
        
        # Footer: Metadata + Actions
        footer_layout = QtWidgets.QHBoxLayout()
        footer_layout.setSpacing(8)
        
        # Metadata
        timestamp = self.equation_data.get('timestamp', datetime.now())
        if isinstance(timestamp, datetime):
            time_ago = self._get_time_ago(timestamp)
        else:
            time_ago = "Just now"
        
        meta_label = QtWidgets.QLabel(f"{eq_type} • {time_ago}")
        meta_label.setStyleSheet(f"""
            color: {Theme.TEXT_TERTIARY};
            font-size: 11px;
        """)
        footer_layout.addWidget(meta_label)
        
        footer_layout.addStretch()
        
        # Action buttons
        actions_layout = QtWidgets.QHBoxLayout()
        actions_layout.setSpacing(4)
        
        # Copy button
        copy_btn = QtWidgets.QPushButton("📋")
        copy_btn.setFixedSize(28, 28)
        copy_btn.setStyleSheet(self._button_style())
        copy_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(self._on_copy_clicked)
        actions_layout.addWidget(copy_btn)
        
        # Save button
        save_btn = QtWidgets.QPushButton("💾")
        save_btn.setFixedSize(28, 28)
        save_btn.setStyleSheet(self._button_style())
        save_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._on_save_clicked)
        actions_layout.addWidget(save_btn)
        
        # Star button
        star_icon = "⭐" if self.equation_data.get('is_starred', False) else "☆"
        star_btn = QtWidgets.QPushButton(star_icon)
        star_btn.setFixedSize(28, 28)
        star_btn.setStyleSheet(self._button_style())
        star_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        star_btn.clicked.connect(self._on_star_clicked)
        actions_layout.addWidget(star_btn)
        
        footer_layout.addLayout(actions_layout)
        layout.addLayout(footer_layout)
    
    def _get_status_icon(self) -> str:
        """Get status emoji based on validation."""
        is_valid = self.equation_data.get('is_valid', True)
        has_warnings = self.equation_data.get('has_warnings', False)
        
        if is_valid and not has_warnings:
            return "🟢"
        elif is_valid and has_warnings:
            return "🟡"
        else:
            return "🔴"
    
    def _extract_preview_text(self, mathml: str) -> str:
        """Extract simple preview text from MathML."""
        # Simple extraction - remove tags
        import re
        text = re.sub(r'<[^>]+>', '', mathml)
        text = text.strip()
        
        # Limit length
        if len(text) > 50:
            text = text[:50] + "..."
        
        return text if text else "No preview available"
    
    def _get_time_ago(self, timestamp: datetime) -> str:
        """Get human-readable time ago."""
        now = datetime.now()
        delta = now - timestamp
        
        seconds = delta.total_seconds()
        
        if seconds < 60:
            return "Just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes}min ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours}h ago"
        else:
            days = int(seconds / 86400)
            return f"{days}d ago"
    
    def _button_style(self) -> str:
        """Get button stylesheet."""
        return f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: {Theme.SURFACE_HOVER};
                border: 1px solid {Theme.ACCENT};
            }}
            QPushButton:pressed {{
                background: {Theme.BORDER};
            }}
        """
    
    def _on_copy_clicked(self):
        """Handle copy button click."""
        self.copy_clicked.emit()
    
    def _on_save_clicked(self):
        """Handle save button click."""
        self.save_clicked.emit()
    
    def _on_star_clicked(self):
        """Handle star button click."""
        self.star_clicked.emit()
    
    def mousePressEvent(self, event):
        """Handle card click."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.card_clicked.emit()
        super().mousePressEvent(event)
