"""
Modern Sidebar Navigation Component

Features:
- Collapsible/Expandable (240px ↔ 64px)
- Icon + label navigation
- Active state highlighting
- Smooth transitions
- Modern 2025 design aesthetic
"""

from PyQt6 import QtCore, QtGui, QtWidgets


from ui.styles import Theme

class SidebarItem(QtWidgets.QFrame):
    """Single navigation item in sidebar."""
    
    clicked = QtCore.pyqtSignal(str)  # Emit item ID when clicked
    
    def __init__(self, item_id: str, icon_text: str, label: str, parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self.icon_text = icon_text
        self.label_text = label
        self.is_active = False
        self.is_collapsed = False
        
        self._build_ui()
        self.set_active(False)  # Default inactive state
    
    def _build_ui(self):
        """Build the navigation item UI."""
        self.setFixedHeight(48)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)
        
        # Icon
        self.icon_label = QtWidgets.QLabel(self.icon_text)
        self.icon_label.setStyleSheet(f"""
            font-size: 24px;
            color: {Theme.TEXT_SECONDARY};
        """)
        self.icon_label.setFixedWidth(24)
        self.icon_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)
        
        # Label
        self.text_label = QtWidgets.QLabel(self.label_text)
        self.text_label.setStyleSheet(f"""
            font-size: 14px;
            font-weight: 600;
            color: {Theme.TEXT_SECONDARY};
        """)
        layout.addWidget(self.text_label)
        layout.addStretch()
    
    def set_active(self, active: bool):
        """Set the active state."""
        self.is_active = active
        
        if active:
            # Active state
            self.setStyleSheet(f"""
                QFrame {{
                    background: {Theme.ACCENT}22;  /* Low opacity accent */
                    border-left: 3px solid {Theme.ACCENT};
                    border-radius: 0px;
                }}
                QFrame:hover {{
                    background: {Theme.ACCENT}33;
                }}
            """)
            self.icon_label.setStyleSheet(f"font-size: 24px; color: {Theme.ACCENT};")
            self.text_label.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {Theme.TEXT_PRIMARY};")
        else:
            # Inactive state
            self.setStyleSheet(f"""
                QFrame {{
                    background: transparent;
                    border: none;
                }}
                QFrame:hover {{
                    background: {Theme.SURFACE_HOVER};
                    border-radius: 6px;
                }}
            """)
            self.icon_label.setStyleSheet(f"font-size: 24px; color: {Theme.TEXT_SECONDARY};")
            self.text_label.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {Theme.TEXT_SECONDARY};")
    
    def set_collapsed(self, collapsed: bool):
        """Show/hide label when collapsed."""
        self.is_collapsed = collapsed
        self.text_label.setVisible(not collapsed)
    
    def mousePressEvent(self, event):
        """Handle click."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit(self.item_id)
        super().mousePressEvent(event)


class ModernSidebar(QtWidgets.QFrame):
    """
    Modern collapsible sidebar with navigation.
    
    Signals:
        navigation_changed: Emitted when user clicks a nav item (str: item_id)
    """
    
    navigation_changed = QtCore.pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_collapsed = False
        self.current_view = "upload"  # Default view
        self.items = {}  # Store nav items
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the sidebar UI as a Rail."""
        self.setFixedWidth(64) # Fixed rail width
        
        self.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BACKGROUND};
                border-right: 1px solid {Theme.BORDER};
            }}
        """)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        
        # Logo (Top)
        logo_container = QtWidgets.QWidget()
        logo_container.setFixedHeight(64)
        logo_layout = QtWidgets.QVBoxLayout(logo_container)
        logo_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        logo_label = QtWidgets.QLabel("M") # Mathpix-like logo placeholder
        logo_label.setStyleSheet(f"""
            font-size: 24px; 
            font-weight: 900; 
            color: {Theme.TEXT_PRIMARY};
            background: transparent;
        """)
        logo_layout.addWidget(logo_label)
        layout.addWidget(logo_container)
        
        # Navigation items (Mathpix Structure - Strict Order)
        # Structure: (ID, Icon, Tooltip)
        nav_items = [
            ("snips", "✂️", "Snips"),      # Home
            ("upload", "📄", "PDFs"),      # Files/Upload
            ("preview", "👁️", "Preview"),   # Active Doc
            ("history", "🕐", "History"),
        ]
        
        for item_id, icon, label in nav_items:
            item = SidebarItem(item_id, icon, "") # No text label for rail
            item.setToolTip(label)
            item.clicked.connect(self._on_item_clicked)
            layout.addWidget(item)
            self.items[item_id] = item
        
        layout.addStretch()
        
        # Bottom Actions
        bottom_items = [
            ("support", "💬", "Support"),
            ("settings", "⚙️", "Settings"),
        ]
        
        for item_id, icon, label in bottom_items:
            item = SidebarItem(item_id, icon, "")
            item.setToolTip(label)
            item.clicked.connect(self._on_item_clicked)
            layout.addWidget(item)
            self.items[item_id] = item

    # Removed collapse/expand methods as it's a fixed rail now
    
    def _on_item_clicked(self, item_id: str):
        """Handle navigation item click."""
        self._set_active_item(item_id)
        self.navigation_changed.emit(item_id)
    
    def _set_active_item(self, item_id: str):
        """Set the active navigation item."""
        self.current_view = item_id
        for key, item in self.items.items():
            item.set_active(key == item_id)

    def set_current_view(self, item_id: str):
        """Programmatically set the current view."""
        if item_id in self.items:
            self._set_active_item(item_id)

    def set_status(self, message: str) -> None:
        """Update status - no textual footer in rail, maybe tooltip or log."""
        # For rail context, we might want to emit a signal up to main window 
        # to show on a different status bar, or just pass for now.
        pass


