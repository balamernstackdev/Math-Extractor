"""
Enterprise Sidebar Component (Semrush-style).
Fixed width, text labels, grouping, professional admin look.
"""
from PyQt6 import QtCore, QtGui, QtWidgets
from ui.styles import Theme

class SidebarItem(QtWidgets.QPushButton):
    """Navigation item with Icon + Text."""
    
    def __init__(self, item_id: str, icon_text: str, label_text: str, parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self.setCheckable(True)
        self.setFixedHeight(44)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        
        self.icon_label = QtWidgets.QLabel(icon_text)
        self.icon_label.setStyleSheet("font-size: 18px; border: none; background: transparent;")
        self.icon_label.setFixedWidth(30)
        self.icon_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        self.text_label = QtWidgets.QLabel(label_text)
        self.text_label.setStyleSheet("font-size: 14px; font-weight: 500; border: none; background: transparent;")
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        layout.addStretch()
        
        # Initial style
        self.update_style(False)
        
    def update_style(self, active: bool):
        if active:
            self.setStyleSheet(f"""
                SidebarItem {{
                    background-color: {Theme.SURFACE_HOVER};
                    border-left: 4px solid {Theme.ACCENT};
                    border-radius: 0px; 
                    text-align: left;
                }}
            """)
            self.text_label.setStyleSheet(f"color: {Theme.ACCENT}; font-weight: 600; border: none; background: transparent;")
        else:
            self.setStyleSheet(f"""
                SidebarItem {{
                    background-color: transparent;
                    border-left: 4px solid transparent;
                    border-radius: 0px;
                    text-align: left;
                }}
                SidebarItem:hover {{
                    background-color: {Theme.BACKGROUND};
                }}
            """)
            self.text_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-weight: 500; border: none; background: transparent;")

class EnterpriseSidebar(QtWidgets.QWidget):
    """
    Full height sidebar with groups and navigation items.
    """
    
    navigation_changed = QtCore.pyqtSignal(str) # view_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(260)
        self.setStyleSheet(f"background-color: {Theme.SURFACE}; border-right: 1px solid {Theme.BORDER};")
        
        self.items = {}
        self.current_item_id = None
        
        self._build_ui()
        
    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 1. Brand / Logo Area
        logo_area = QtWidgets.QWidget()
        logo_area.setFixedHeight(64)
        logo_layout = QtWidgets.QHBoxLayout(logo_area)
        logo_layout.setContentsMargins(20, 0, 20, 0)
        
        logo = QtWidgets.QLabel("MathpixAdmin")
        logo.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {Theme.TEXT_PRIMARY};")
        logo_layout.addWidget(logo)
        logo_layout.addStretch()
        
        layout.addWidget(logo_area)
        
        # 2. Scrollable Navigation
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")
        
        content = QtWidgets.QWidget()
        self.nav_layout = QtWidgets.QVBoxLayout(content)
        self.nav_layout.setContentsMargins(0, 10, 0, 10)
        self.nav_layout.setSpacing(4)
        
        # --- GROUPS & ITEMS ---
        self._add_group_header("WORKSPACE")
        self._add_nav_item("dashboard", "📊", "Dashboard")
        self._add_nav_item("snips", "✂️", "Snips Library")
        
        self.nav_layout.addSpacing(16)
        self._add_group_header("EXTRACTION")
        self._add_nav_item("upload", "📄", "Upload & Convert")
        self._add_nav_item("preview", "👁️", "Preview Results")
        
        self.nav_layout.addSpacing(16)
        self._add_group_header("MANAGEMENT")
        self._add_nav_item("history", "🕒", "Activity Log")
        
        self.nav_layout.addSpacing(16)
        self._add_group_header("SYSTEM")
        self._add_nav_item("settings", "⚙️", "Settings")
        
        self.nav_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        # 3. User Profile / Bottom (Optional)
        user_area = QtWidgets.QWidget()
        user_area.setFixedHeight(60)
        user_area.setStyleSheet(f"border-top: 1px solid {Theme.BORDER};")
        user_layout = QtWidgets.QHBoxLayout(user_area)
        user_layout.setContentsMargins(20, 0, 20, 0)
        
        avatar = QtWidgets.QLabel("AD")
        avatar.setFixedSize(32, 32)
        avatar.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(f"background: {Theme.ACCENT}; color: white; border-radius: 16px; font-weight: bold;")
        
        user_info = QtWidgets.QLabel("Admin User")
        user_info.setStyleSheet(f"font-weight: 600; color: {Theme.TEXT_PRIMARY};")
        
        user_layout.addWidget(avatar)
        user_layout.addWidget(user_info)
        user_layout.addStretch()
        
        layout.addWidget(user_area)

    def _add_group_header(self, text: str):
        label = QtWidgets.QLabel(text)
        label.setStyleSheet(f"""
            padding-left: 20px;
            color: {Theme.TEXT_TERTIARY};
            font-size: 11px;
            font-weight: 700;
            margin-bottom: 4px;
            letter-spacing: 0.5px;
        """)
        self.nav_layout.addWidget(label)

    def _add_nav_item(self, item_id: str, icon: str, label: str):
        item = SidebarItem(item_id, icon, label)
        item.clicked.connect(lambda: self.set_current_view(item_id))
        self.nav_layout.addWidget(item)
        self.items[item_id] = item

    def set_current_view(self, view_id: str):
        """Update active state and emit signal."""
        if view_id == self.current_item_id:
            return
            
        # Update UI
        if self.current_item_id and self.current_item_id in self.items:
            self.items[self.current_item_id].setChecked(False)
            self.items[self.current_item_id].update_style(False)
            
        if view_id in self.items:
            self.items[view_id].setChecked(True)
            self.items[view_id].update_style(True)
            self.current_item_id = view_id
            self.navigation_changed.emit(view_id)

    def set_status(self, message: str):
        """Optional status handler integration."""
        pass # Enterprise sidebar might simplify status or show it elsewhere
