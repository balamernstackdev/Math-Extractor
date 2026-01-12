"""
Centralized styles and theme definitions for the Mathpix Clone UI.
Modern, dark-themed, professional aesthetic.
"""

from PyQt6.QtGui import QColor

class Theme:
    # Core Colors
    BACKGROUND = "#1a1d23"        # Deep Charcoal
    SURFACE = "#25282f"           # Card Surface
    SURFACE_HOVER = "#2a2e36"     # Hover Surface
    SIDEBAR = "#1e2128"           # Sidebar Background
    
    # Text
    TEXT_PRIMARY = "#ffffff"      # white
    TEXT_SECONDARY = "#b0b0b0"    # gray-400
    TEXT_TERTIARY = "#808080"     # gray-500
    
    # Borders
    BORDER = "#3a3d45"            # dark gray border
    BORDER_FOCUS = "#4a9eff"      # blue focus
    
    # Accents
    ACCENT = "#2563EB"            # primary blue
    ACCENT_BG = "#2563EB33"       # primary blue ~20% opacity
    ACCENT_HOVER = "#1d4ed8"      
    ACCENT_PRESSED = "#1e40af"    
    ACCENT_TEXT = "#FFFFFF"
    
    # Functional
    SUCCESS = "#10B981"           
    WARNING = "#F59E0B"           
    ERROR = "#EF4444"             
    
    # Components
    CARD_BG = "#25282f"
    CARD_BORDER = "#3a3d45"
    CARD_SHADOW = "0 8px 16px rgba(0, 0, 0, 0.2)" 

    # Navigation items (Mathpix Structure)
    # Structure: (ID, Icon, Tooltip)
    nav_items = [
        ("snips", "✂️", "Snips"),    # Home
        ("upload", "📄", "PDFs"),    # Files
        ("preview", "👁️", "Preview"), # Active View
        ("history", "🕐", "History"),
    ]
    
    # Fonts
    FONT_FAMILY = "'Inter', system-ui, sans-serif"
    
    @staticmethod
    def get_qss():
        """Return global QSS stylesheet."""
        return f"""
            QMainWindow, QWidget {{
                background-color: {Theme.BACKGROUND};
                color: {Theme.TEXT_PRIMARY};
                font-family: {Theme.FONT_FAMILY};
            }}
            
            QFrame {{
                border: none;
            }}
            
            /* Scrollbars */
            QScrollBar:vertical {{
                background: {Theme.BACKGROUND};
                width: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {Theme.BORDER};
                min-height: 20px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {Theme.SURFACE_HOVER};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            
            /* Tooltips */
            QToolTip {{
                background-color: {Theme.SURFACE};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                padding: 4px;
                border-radius: 4px;
            }}
            
            /* Buttons */
            QPushButton {{
                background-color: {Theme.ACCENT};
                color: {Theme.ACCENT_TEXT};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Theme.ACCENT_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {Theme.ACCENT_PRESSED};
            }}
            QPushButton:disabled {{
                background-color: {Theme.BORDER};
                color: {Theme.TEXT_TERTIARY};
            }}
        """

    @staticmethod
    def card_style():
        """Style for card-like containers."""
        return f"""
            background-color: {Theme.SURFACE};
            border: 1px solid {Theme.BORDER};
            border-radius: 12px;
        """

