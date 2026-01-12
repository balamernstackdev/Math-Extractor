"""
validation_status_widget.py

UI component for displaying validation status and multiline equation info.
"""

from PyQt6 import QtCore, QtGui, QtWidgets
from ui.styles import Theme


class ValidationStatusWidget(QtWidgets.QFrame):
    """
    Widget showing validation status with traffic light indicators and multiline info.
    
    Features:
    - Traffic light status (🟢/🟡/🔴)
    - Multiline equation badge
    - Error detail panel (expandable)
    - Alignment information
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.reset()
    
    def _build_ui(self):
        """Build the UI components."""
        self.setStyleSheet(f"""
            QFrame {{
                background: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 8px;
                padding: 12px;
            }}
            QLabel {{
                color: {Theme.TEXT_PRIMARY};
            }}
        """)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # Status Row: [Icon][Status Text][Multiline Badge]
        status_row = QtWidgets.QHBoxLayout()
        status_row.setSpacing(8)
        
        # Status icon (traffic light)
        self.status_icon = QtWidgets.QLabel("●")
        self.status_icon.setStyleSheet(f"""
            font-size: 24px;
            color: {Theme.TEXT_TERTIARY};
        """)
        status_row.addWidget(self.status_icon)
        
        # Status text
        self.status_label = QtWidgets.QLabel("No validation")
        self.status_label.setStyleSheet(f"""
            font-size: 13px;
            font-weight: 600;
            color: {Theme.TEXT_PRIMARY};
        """)
        status_row.addWidget(self.status_label)
        
        status_row.addStretch()
        
        # Multiline badge (only shown for multiline equations)
        self.multiline_badge = QtWidgets.QLabel("")
        self.multiline_badge.setStyleSheet(f"""
            background: {Theme.ACCENT};
            color: white;
            font-size: 10px;
            font-weight: 600;
            padding: 4px 8px;
            border-radius: 4px;
        """)
        self.multiline_badge.hide()
        status_row.addWidget(self.multiline_badge)
        
        layout.addLayout(status_row)
        
        # Info row (alignment, columns, lines)
        self.info_label = QtWidgets.QLabel("")
        self.info_label.setStyleSheet(f"""
            font-size: 11px;
            color: {Theme.TEXT_SECONDARY};
        """)
        self.info_label.hide()
        layout.addWidget(self.info_label)
        
        # Error details (expandable)
        self.error_details = QtWidgets.QTextEdit()
        self.error_details.setReadOnly(True)
        self.error_details.setStyleSheet(f"""
            QTextEdit {{
                background: {Theme.BACKGROUND};
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                color: {Theme.ERROR};
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                padding: 8px;
            }}
        """)
        self.error_details.setMaximumHeight(100)
        self.error_details.hide()
        layout.addWidget(self.error_details)
    
    def reset(self):
        """Reset to default state."""
        self.status_icon.setText("●")
        self.status_icon.setStyleSheet(f"font-size: 24px; color: {Theme.TEXT_TERTIARY};")
        self.status_label.setText("No validation")
        self.status_label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {Theme.TEXT_TERTIARY};")
        self.multiline_badge.hide()
        self.info_label.hide()
        self.error_details.hide()
    
    def set_status(self, is_valid: bool, has_warnings: bool = False, errors: list = None, warnings: list = None):
        """
        Update validation status.
        
        Args:
            is_valid: Whether validation passed
            has_warnings: Whether there are warnings
            errors: List of error messages
            warnings: List of warning messages
        """
        errors = errors or []
        warnings = warnings or []
        
        if is_valid and not has_warnings:
            # ✅ GREEN: All valid
            self.status_icon.setText("●")
            self.status_icon.setStyleSheet(f"font-size: 24px; color: {Theme.SUCCESS};")
            self.status_label.setText("✅ Valid")
            self.status_label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {Theme.SUCCESS};")
            self.error_details.hide()
        
        elif is_valid and has_warnings:
            # ⚠️ YELLOW: Valid but with warnings
            self.status_icon.setText("●")
            self.status_icon.setStyleSheet(f"font-size: 24px; color: {Theme.WARNING};")
            self.status_label.setText(f"⚠️ Valid ({len(warnings)} warning{'s' if len(warnings) > 1 else ''})")
            self.status_label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {Theme.WARNING};")
            
            # Show warnings
            if warnings:
                warning_text = "\n".join([f"⚠️ {w}" for w in warnings[:5]])
                if len(warnings) > 5:
                    warning_text += f"\n... and {len(warnings) - 5} more"
                self.error_details.setPlainText(warning_text)
                self.error_details.setStyleSheet(f"""
                    QTextEdit {{
                        background: {Theme.BACKGROUND};
                        border: 1px solid {Theme.BORDER};
                        border-radius: 4px;
                        color: {Theme.WARNING};
                        font-family: 'Consolas', 'Monaco', monospace;
                        font-size: 11px;
                        padding: 8px;
                    }}
                """)
                self.error_details.show()
        
        else:
            # ❌ RED: Invalid
            self.status_icon.setText("●")
            self.status_icon.setStyleSheet(f"font-size: 24px; color: {Theme.ERROR};")
            self.status_label.setText(f"❌ Invalid ({len(errors)} error{'s' if len(errors) > 1 else ''})")
            self.status_label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {Theme.ERROR};")
            
            # Show errors
            if errors:
                error_text = "\n".join([f"❌ {e}" for e in errors[:5]])
                if len(errors) > 5:
                    error_text += f"\n... and {len(errors) - 5} more"
                self.error_details.setPlainText(error_text)
                self.error_details.setStyleSheet(f"""
                    QTextEdit {{
                        background: {Theme.BACKGROUND};
                        border: 1px solid {Theme.BORDER};
                        border-radius: 4px;
                        color: {Theme.ERROR};
                        font-family: 'Consolas', 'Monaco', monospace;
                        font-size: 11px;
                        padding: 8px;
                    }}
                """)
                self.error_details.show()
    
    def set_multiline_info(self, is_multiline: bool, environment: str = None, 
                           lines: int = 1, columns: int = 1, alignment: str = None):
        """
        Show multiline equation information.
        
        Args:
            is_multiline: Whether equation is multiline
            environment: Environment type ('align', 'cases', etc.)
            lines: Number of lines
            columns: Number of columns
            alignment: Column alignment string
        """
        if not is_multiline:
            self.multiline_badge.hide()
            self.info_label.hide()
            return
        
        # Show multiline badge
        if environment and environment != 'manual':
            self.multiline_badge.setText(f"📐 {environment.upper()}")
        else:
            self.multiline_badge.setText("📐 MULTILINE")
        self.multiline_badge.show()
        
        # Show info
        info_parts = []
        if lines > 1:
            info_parts.append(f"{lines} lines")
        if columns > 1:
            info_parts.append(f"{columns} cols")
        if alignment:
            info_parts.append(f"align: {alignment}")
        
        if info_parts:
            self.info_label.setText(" • ".join(info_parts))
            self.info_label.show()
        else:
            self.info_label.hide()
