"""
PreviewPanel.py
Production-ready MathML renderer with:
- Auto WebEngine upgrade
- Strict MathML corruption detection
- Safe MathML rendering via MathJax
- TeX fallback ONLY for true corruption
"""

from __future__ import annotations
import html
import os
import re
import sys
from PyQt6 import QtCore, QtGui, QtWidgets, QtWebChannel
from PyQt6.QtCore import pyqtSlot, pyqtSignal, QObject
import json

from core.logger import logger
from ui.styles import Theme
from ui.validation_status_widget import ValidationStatusWidget

from ui.controllers.preview_controller import PreviewController
from utils.resource_utils import get_resource_path

# ============================================================================
# CUSTOM TEXT EDIT WITH PASTE CLEANING
# ============================================================================

class EditableMathMLEdit(QtWidgets.QTextEdit):
    """QTextEdit that cleans pasted LaTeX automatically."""
    
    paste_cleaned = QtCore.pyqtSignal(str)  # Emit cleaned text after paste
    
    def insertFromMimeData(self, source: QtCore.QMimeData) -> None:
        """Intercept paste and clean LaTeX before inserting."""
        if source.hasText():
            pasted_text = source.text()
            # Clean the pasted LaTeX
            cleaned = self._clean_pasted_latex(pasted_text)
            # Create new mime data with cleaned text
            new_source = QtCore.QMimeData()
            new_source.setText(cleaned)
            # Call parent with cleaned data
            super().insertFromMimeData(new_source)
            # Emit signal for preview update
            self.paste_cleaned.emit(cleaned)
        else:
            # Not text, use default behavior
            super().insertFromMimeData(source)
    
    def _clean_pasted_latex(self, text: str) -> str:
        r"""Clean corrupted LaTeX from paste operations.
        
        Fixes:
        - Duplicate consecutive commands: {\\mathrm{order}}{\\mathrm{order}} → {\\mathrm{order}}
        - Corrupted text with pipes: \\mathrm{Wit}|\\mathrm{h} → \\mathrm{With}
        - Single-letter corruption: \mathrm{\piy} → \mathrm{pi}
        - Duplicate commands: \mathrm{arbitrary}\mathrm{arbitrary} → \mathrm{arbitrary}
        - Multiple repeated operators: \operatorname{hops}\operatorname{hops} → \operatorname{hops}
        - Converts LaTeX to MathML if pasted text is LaTeX
        """
        if not text:
            return text
        
        cleaned = text.strip()
        
        # Check if this looks like LaTeX (has LaTeX commands) but not MathML (no <math> tag)
        # We'll check again after cleaning
        original_was_latex = bool(re.search(r'\\[a-zA-Z]+\{', cleaned)) and '<math' not in cleaned
        
        # 1. Remove duplicate consecutive identical commands with same content
        # Pattern: {\mathrm{order}}{\mathrm{order}} → {\mathrm{order}}
        # Match: {\command{content}}{\command{content}} (exact duplicates)
        cleaned = re.sub(r'(\{[^}]*\})\1+', r'\1', cleaned)
        
        # 2. Remove duplicate consecutive commands (same command, same content)
        # Pattern: \mathrm{order}\mathrm{order} → \mathrm{order}
        # Match: \command{content}\command{content}
        cleaned = re.sub(r'(\\[a-zA-Z]+\{[^}]+\})\1+', r'\1', cleaned)
        
        # 3. Fix corrupted text with pipe characters
        # Pattern: \mathrm{Wit}|\mathrm{h} → \mathrm{With}
        # Remove pipes between command groups
        cleaned = re.sub(r'(\}[|])(\\[a-zA-Z]+\{)', r'\2', cleaned)
        # Fix: \mathrm{text}|\mathrm{more} → \mathrm{textmore}
        cleaned = re.sub(r'(\}[|])(\\[a-zA-Z]+\{([^}]+)\})', lambda m: r'\2' + m.group(3), cleaned)
        # Better: merge adjacent text in same command type
        # \mathrm{Wit}|\mathrm{h} → find and merge
        def merge_adjacent_commands(match):
            cmd1 = match.group(1)  # \mathrm
            content1 = match.group(2)  # Wit
            pipe = match.group(3)  # |
            cmd2 = match.group(4)  # \mathrm
            content2 = match.group(5)  # h
            if cmd1 == cmd2:
                return f"{cmd1}{{{content1}{content2}}}"
            return match.group(0)
        cleaned = re.sub(r'(\\[a-zA-Z]+\{)([^}]+)(\|)(\\[a-zA-Z]+\{)([^}]+)\}', merge_adjacent_commands, cleaned)
        
        # 4. Fix single-letter corruption in commands
        # Pattern: \mathrm{\piy} → \mathrm{pi} (remove 'y' if it's clearly corruption)
        # Pattern: \mathrm{\piy} → detect and fix
        cleaned = re.sub(r'\\mathrm\{\\(pi)y\}', r'\\mathrm{pi}', cleaned)
        # More general: if command content is single letter + corruption, try to fix
        # \mathrm{\lettercorruption} → \mathrm{letter} (if corruption is single char)
        cleaned = re.sub(r'\\mathrm\{(\w)(\w)\}', lambda m: r'\mathrm{' + m.group(1) + '}' if len(m.group(2)) == 1 and m.group(2).isalpha() else m.group(0), cleaned)
        
        # 5. Remove duplicate consecutive operators
        # Pattern: \operatorname{hops}\operatorname{hops} → \operatorname{hops}
        cleaned = re.sub(r'(\\operatorname\{[^}]+\})\1+', r'\1', cleaned)
        cleaned = re.sub(r'(\\mathbf\{[^}]+\})\1+', r'\1', cleaned)
        cleaned = re.sub(r'(\\mathrm\{[^}]+\})\1+', r'\1', cleaned)
        cleaned = re.sub(r'(\\mathit\{[^}]+\})\1+', r'\1', cleaned)
        cleaned = re.sub(r'(\\mathsf\{[^}]+\})\1+', r'\1', cleaned)
        cleaned = re.sub(r'(\\mathtt\{[^}]+\})\1+', r'\1', cleaned)
        cleaned = re.sub(r'(\\mathcal\{[^}]+\})\1+', r'\1', cleaned)
        cleaned = re.sub(r'(\\mathbb\{[^}]+\})\1+', r'\1', cleaned)
        
        # 6. Fix: \mathrm{d}\mathbf{u}\mathrm{d}\mathbf{u} → \mathrm{d}\mathbf{u} (remove duplicates)
        # This is trickier - need to detect repeated sequences
        # For now, just remove exact consecutive duplicates
        cleaned = re.sub(r'(\\mathrm\{d\}\\mathbf\{u\})\1+', r'\1', cleaned)
        
        # 7. Fix: {\mathrm{and}}\,{\mathrm{and}}\,{\mathrm{and}} → {\mathrm{and}}
        # Remove duplicate groups separated by \, or spaces
        cleaned = re.sub(r'(\{[^}]+\})(?:\\,|\s)*\1+', r'\1', cleaned)
        
        # 8. Remove stray pipe characters that aren't part of valid LaTeX
        # Keep | in \left| and \right|, but remove standalone |
        # Pattern: text|text → text text (if | is not in command context)
        cleaned = re.sub(r'([^\\])\|([^\\])', r'\1 \2', cleaned)
        # But preserve \left| and \right|
        cleaned = re.sub(r'\\left \|', r'\\left|', cleaned)
        cleaned = re.sub(r'\\right \|', r'\\right|', cleaned)
        
        # 9. Fix: \mathbf{wireless} nd\mathbf{OT} → \mathbf{wireless} and \mathbf{OT}
        # Add space before standalone text after closing brace
        cleaned = re.sub(r'\}([a-z]+)(\\[a-zA-Z]+\{)', r'} \1 \2', cleaned)
        
        # 10. Normalize whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = cleaned.strip()
        
        # 11. If this is LaTeX (not MathML), try to convert to MathML
        is_latex = bool(re.search(r'\\[a-zA-Z]+\{', cleaned)) and '<math' not in cleaned
        if is_latex:
            try:
                # Try to convert cleaned LaTeX to MathML
                mathml = latex2mathml_convert(cleaned)
                if mathml and '<math' in mathml:
                    logger.info(f"[PasteCleaner] Converted LaTeX to MathML ({len(cleaned)} → {len(mathml)} chars)")
                    return mathml
                else:
                    logger.warning(f"[PasteCleaner] LaTeX conversion failed, returning cleaned LaTeX")
            except Exception as e:
                logger.warning(f"[PasteCleaner] LaTeX conversion error: {e}, returning cleaned LaTeX")
        
        logger.info(f"[PasteCleaner] Cleaned text: {len(text)} → {len(cleaned)} chars")
        if text != cleaned:
            logger.debug(f"[PasteCleaner] Before: {text[:200]}")
            logger.debug(f"[PasteCleaner] After:  {cleaned[:200]}")
        
        return cleaned


# ============================================================================
# PREVIEW PANEL
# ============================================================================

class PreviewPanel(QtWidgets.QScrollArea):

    copy_mathml_requested = QtCore.pyqtSignal(str)
    copy_tsv_requested = QtCore.pyqtSignal(str)
    copy_asciimath_requested = QtCore.pyqtSignal(str)
    export_requested = QtCore.pyqtSignal(str)
    save_snip_requested = QtCore.pyqtSignal(dict)  # Emits dictionary with snip data

    # ----------------------------------------------------------------------
    def __init__(self) -> None:
        super().__init__()
        self._current_mathml = ""

        # Initialize Controller
        self.controller = PreviewController(self)
        self.controller.update_html.connect(self._load_html_content)
        self.controller.update_mathml_source.connect(self._update_mathml_text)
        self.controller.update_status.connect(self.show_validation_status)
        self.controller.snip_saved.connect(self.save_snip_requested.emit)
        self.controller.export_requested.connect(self.export_requested.emit)
        
        # Bridge is managed by controller now
        self.js_bridge = self.controller.bridge
        self.js_bridge.latexChanged.connect(self.controller.handle_visual_editor_change)
        
        self._stored_latex = ""  # Store LaTeX for direct rendering
        self._current_image_path = None # Store current image path
        self._mathml_validated = False  # Track if MathML was validated by pipeline
        self._updating_equation = False  # Guard to prevent infinite loops from textChanged signal
        self._last_rendered_mathml = ""  # Track last rendered MathML to prevent duplicate renders
        self._last_rendered_latex = ""  # Track last rendered LaTeX to prevent duplicate renders
        self._is_visual_editor_active = False # Visual Editor Mode state
        self._build_ui()

    # ----------------------------------------------------------------------
    def _build_ui(self):
        """Build professional Preview UI matching Mathpix style."""
        self.setObjectName("PreviewPanel")
        
        # ScrollArea Setup
        self.setWidgetResizable(True)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Main content widget
        self.content_widget = QtWidgets.QWidget()
        self.setWidget(self.content_widget)
        
        layout = QtWidgets.QVBoxLayout(self.content_widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6) # Even more reduced spacing

        # Initialize internal state
        self._current_mathml = ""
        self._stored_latex = ""
        self._current_image_path = None
        self._mathml_validated = False
        self._updating_equation = False
        self._last_rendered_mathml = ""
        self._last_rendered_latex = ""
        
        # 1. Header with Status
        header_frame = QtWidgets.QFrame()
        header_layout = QtWidgets.QHBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 4)
        
        title = QtWidgets.QLabel("Preview")
        title.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {Theme.TEXT_PRIMARY};") # Reduced font slightly
        header_layout.addWidget(title)
        header_layout.addStretch()

        # Toggles Removed as per user request
        
        header_layout.addSpacing(15)
        
        header_layout.addSpacing(15)
        
        self.validation_indicator = QtWidgets.QLabel("● Ready")
        self.validation_indicator.setStyleSheet(f"color: {Theme.TEXT_TERTIARY}; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; padding: 2px 6px; border-radius: 4px; border: 1px solid {Theme.BORDER};")
        
        # Validation Score Label (Confidence)
        self.confidence_label = QtWidgets.QLabel("")
        self.confidence_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 11px; margin-left: 10px;")
        
        # Refining Label (Flashes during AI/Pipeline work)
        self.refining_label = QtWidgets.QLabel("REFINING...")
        self.refining_label.setStyleSheet(f"color: {Theme.ACCENT}; font-weight: 800; font-size: 10px; margin-left: 10px; letter-spacing: 1px;")
        self.refining_label.hide()
        
        header_layout.addWidget(self.validation_indicator)
        header_layout.addWidget(self.confidence_label)
        header_layout.addWidget(self.refining_label)
        header_layout.addStretch()
        layout.addWidget(header_frame)

        # 2. Image Preview Section (Enhanced)
        self.img_section_widget = QtWidgets.QWidget()
        self.img_section_layout = QtWidgets.QVBoxLayout(self.img_section_widget)
        self.img_section_layout.setContentsMargins(0, 0, 0, 0)
        self.img_section_layout.setSpacing(6)
        
        img_header = QtWidgets.QLabel("IMAGE SOURCE")
        img_header.setStyleSheet(f"font-size: 10px; font-weight: 800; color: {Theme.TEXT_SECONDARY}; letter-spacing: 1.5px;")
        self.img_section_layout.addWidget(img_header)
        
        self.image_container = QtWidgets.QFrame()
        self.image_container.setStyleSheet(f"background: {Theme.SURFACE}; border: 1px solid {Theme.BORDER}; border-radius: 12px;")
        image_cont_layout = QtWidgets.QVBoxLayout(self.image_container)
        image_cont_layout.setContentsMargins(12, 12, 12, 12) 
        
        self.image_label = QtWidgets.QLabel("No selection")
        self.image_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumHeight(100) # Increased min height
        self.image_label.setMaximumHeight(400) # Increased max height for better visibility
        self.image_label.setStyleSheet(f"color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
        image_cont_layout.addWidget(self.image_label)
        
        self.img_section_layout.addWidget(self.image_container)
        layout.addWidget(self.img_section_widget)
        self.img_section_widget.show()


        # 3. Rendered Equation Section (Refined)
        self.render_container = QtWidgets.QWidget()
        self.render_container.setStyleSheet(f"""
            QWidget {{
                background: {Theme.SURFACE}; 
                border: 1px solid {Theme.BORDER}; 
                border-radius: 12px;
                outline: none;
            }}
        """)
        render_layout = QtWidgets.QVBoxLayout(self.render_container)
        render_layout.setContentsMargins(0,0,0,0)
        render_layout.setSpacing(0)
        
        # Header for Render View
        render_header_frame = QtWidgets.QFrame()
        render_header_frame.setFixedHeight(36) # More compact
        render_header_frame.setStyleSheet(f"background: transparent; border: none; border-bottom: 1px solid {Theme.BORDER}; border-radius: 0px;")
        render_header_layout = QtWidgets.QHBoxLayout(render_header_frame)
        render_header_layout.setContentsMargins(12, 0, 12, 0)
        
        render_label = QtWidgets.QLabel("PREVIEW")
        render_label.setStyleSheet(f"font-size: 10px; font-weight: 800; color: {Theme.TEXT_SECONDARY}; letter-spacing: 1.5px;")
        render_header_layout.addWidget(render_label)
        
        # Turbo Mode Toggle
        from core.config import settings
        self.turbo_btn = QtWidgets.QPushButton("⚡ TURBO")
        self.turbo_btn.setCheckable(True)
        self.turbo_btn.setChecked(settings.turbo_mode)
        self.turbo_btn.setToolTip("TURBO MODE: Skip AI Refinement for 10x Speed")
        self.turbo_btn.setFixedSize(75, 24) # Increased width and height
        self.turbo_btn.setStyleSheet(f"""
            QPushButton {{ 
                background: {Theme.SURFACE}; 
                border: 1px solid {Theme.BORDER}; 
                border-radius: 6px; 
                color: {Theme.TEXT_SECONDARY};
                font-size: 9px;
                font-weight: 800;
                padding-left: 2px;
            }} 
            QPushButton:hover {{
                border-color: {Theme.ACCENT};
                color: {Theme.TEXT_PRIMARY};
            }}
            QPushButton:checked {{ 
                background: #f59e0b; 
                border-color: #f59e0b;
                color: white; 
            }}
        """)
        self.turbo_btn.toggled.connect(self._toggle_turbo_mode)
        render_header_layout.addSpacing(12)
        render_header_layout.addWidget(self.turbo_btn)
        
        # Visual Editor Toggle
        self.edit_visual_btn = QtWidgets.QPushButton("✏️") # Minimalist
        self.edit_visual_btn.setCheckable(True)
        self.edit_visual_btn.setToolTip("Toggle Visual Editor")
        self.edit_visual_btn.setFixedSize(28, 22)
        self.edit_visual_btn.setStyleSheet(f"QPushButton {{ background: transparent; border: 1px solid {Theme.BORDER}; border-radius: 4px; }} QPushButton:checked {{ background: {Theme.ACCENT}; color: white; }}")
        self.edit_visual_btn.toggled.connect(self._toggle_visual_editor)
        render_header_layout.addSpacing(16)
        render_header_layout.addWidget(self.edit_visual_btn)
        
        render_header_layout.addStretch()
        
        # Zoom controls (Premium Ultra Compact)
        zoom_frame = QtWidgets.QFrame()
        zoom_layout = QtWidgets.QHBoxLayout(zoom_frame)
        zoom_layout.setContentsMargins(0, 0, 0, 0)
        zoom_layout.setSpacing(2)
        
        def create_zoom_btn(text):
            btn = QtWidgets.QPushButton(text)
            btn.setFixedSize(22, 22)
            btn.setStyleSheet(f"background: transparent; border: none; color: {Theme.TEXT_SECONDARY}; font-weight: bold;")
            return btn

        z_out = create_zoom_btn("-")
        z_out.clicked.connect(self._zoom_out)
        
        self.zoom_label = QtWidgets.QLabel("100%")
        self.zoom_label.setFixedWidth(32)
        self.zoom_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.zoom_label.setStyleSheet(f"font-size: 9px; font-weight: 700; color: {Theme.TEXT_TERTIARY}; border: none;")
        
        z_in = create_zoom_btn("+")
        z_in.clicked.connect(self._zoom_in)
        
        zoom_layout.addWidget(z_out)
        zoom_layout.addWidget(self.zoom_label)
        zoom_layout.addWidget(z_in)
        render_header_layout.addWidget(zoom_frame)
        
        render_layout.addWidget(render_header_frame)

        self.equation_view = self._create_viewer()
        self.equation_view.setMinimumHeight(150) # Balanced
        self.equation_view.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.equation_view.setStyleSheet(f"background: {Theme.SURFACE}; border: none; border-bottom-left-radius: 12px; border-bottom-right-radius: 12px;")
        render_layout.addWidget(self.equation_view)
        
        layout.addWidget(self.render_container)


        # 4. MathML Actions (Copy & Save)
        # Re-organized to be cleaner
        action_widget = QtWidgets.QWidget()
        action_layout = QtWidgets.QHBoxLayout(action_widget)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(12)

        # Copy MathML Button (Primary Action)
        self.copy_mml_btn = QtWidgets.QPushButton("Copy MathML")
        self.copy_mml_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.copy_mml_btn.setFixedHeight(32)
        self.copy_mml_btn.setStyleSheet(f"QPushButton {{ background: {Theme.SURFACE}; color: {Theme.ACCENT}; border: 1px solid {Theme.BORDER}; border-radius: 6px; font-size: 11px; font-weight: 600; padding: 0 16px; }} QPushButton:hover {{ border-color: {Theme.ACCENT}; background: {Theme.SURFACE_HOVER}; }}")
        self.copy_mml_btn.clicked.connect(self._copy_mathml)
        action_layout.addWidget(self.copy_mml_btn)

        action_layout.addWidget(self.copy_mml_btn)

        action_layout.addStretch()
        layout.addWidget(action_widget)
        self.action_widget = action_widget # Store reference so toggle can hide it if needed

        # 5. MML CONVERTER Section (Prominent)
        self.converter_widget = QtWidgets.QWidget()
        self.converter_layout = QtWidgets.QVBoxLayout(self.converter_widget)
        self.converter_layout.setContentsMargins(0, 10, 0, 0)
        self.converter_layout.setSpacing(6)
        
        cv_header_frame = QtWidgets.QFrame()
        cv_header_layout = QtWidgets.QHBoxLayout(cv_header_frame)
        cv_header_layout.setContentsMargins(0, 0, 0, 0)
        
        cv_label = QtWidgets.QLabel("MML CONVERTER CODE")
        cv_label.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {Theme.TEXT_TERTIARY}; letter-spacing: 1.2px;")
        cv_header_layout.addWidget(cv_label)
        cv_header_layout.addStretch()
        
        # Copy Converter Code Button
        self.copy_cv_btn = QtWidgets.QPushButton("Copy MML Code")
        self.copy_cv_btn.setMinimumWidth(100)
        self.copy_cv_btn.setFixedHeight(24)
        self.copy_cv_btn.setStyleSheet(f"QPushButton {{ background: {Theme.SURFACE}; color: {Theme.TEXT_SECONDARY}; border: 1px solid {Theme.BORDER}; border-radius: 4px; font-size: 10px; font-weight: 600; }} QPushButton:hover {{ border-color: {Theme.ACCENT}; background: {Theme.SURFACE_HOVER}; }}")
        self.copy_cv_btn.clicked.connect(self._copy_mml_converter_text)
        cv_header_layout.addWidget(self.copy_cv_btn)
        
        self.converter_layout.addWidget(cv_header_frame)
        
        self.converter_display = QtWidgets.QTextEdit()
        self.converter_display.setPlaceholderText("Converter output will appear here with mml: prefixes...")
        self.converter_display.setReadOnly(True)
        # Dynamic height
        self.converter_display.setMinimumHeight(150)
        self.converter_display.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.converter_display.setStyleSheet(f"background: {Theme.SURFACE}; border: 1px solid {Theme.BORDER}; border-radius: 8px; color: {Theme.TEXT_SECONDARY}; font-family: 'Consolas', monospace; font-size: 11px; padding: 8px;")
        self.converter_layout.addWidget(self.converter_display)
        
        layout.addWidget(self.converter_widget)
        
        
        layout.addStretch() # Push everything up


    # ----------------------------------------------------------------------
    def _load_html_content(self, html_content: str):
        """Load HTML into web view (Slot for controller)."""
        if isinstance(self.equation_view, QtWidgets.QLabel):
            self.equation_view.setText("WebEngine not available")
            return
            
        try:
            # CRITICAL: Use local base URL for MathJax discovery
            root_dir = get_resource_path("")
            base_url = QtCore.QUrl.fromLocalFile(root_dir + os.path.sep)
            self.equation_view.setHtml(html_content, base_url)
        except Exception as e:
            logger.error(f"Error setting HTML: {e}")

    def _update_mathml_text(self, mathml: str):
        """Update MathML display text (Slot for controller)."""
        self._current_mathml = mathml # Update local state
        
        # Populate MML Converter with prefixed MathML
        if hasattr(self, 'converter_display'):
             prefixed_mml = self._apply_mml_prefixes(mathml)
             self.converter_display.setPlainText(prefixed_mml)

    def _apply_mml_prefixes(self, mathml: str) -> str:
        """Helper to add mml: prefixes for the converter view."""
        if not mathml:
            return mathml
        # Simple regex based prefixing (same logic as LatexToMathML)
        import re
        # 1. Add prefixes to opening tags
        p = re.sub(r'<(?!(?:mml:|/|!|\?))([a-zA-Z0-9]+)', r'<mml:\1', mathml)
        # 2. Add prefixes to closing tags
        p = re.sub(r'</(?!(?:mml:))([a-zA-Z0-9]+)', r'</mml:\1', p)
        # 3. Add xmlns:mml if missing
        if 'xmlns:mml=' not in p and '<mml:math' in p:
            p = p.replace('<mml:math', '<mml:math xmlns:mml="http://www.w3.org/1998/Math/MathML"', 1)
        return p

    def _toggle_mml_visibility(self, checked: bool):
        """Toggle visibility of technical sections (MathML and Converter)."""
        if hasattr(self, 'converter_widget'):
            if checked:
                self.converter_widget.show()
                if hasattr(self, 'action_widget'):
                    self.action_widget.show()
            else:
                self.converter_widget.hide()
                if hasattr(self, 'action_widget'):
                     self.action_widget.hide()

    def _create_viewer(self):
        """Try WebEngine, else fallback label."""
        try:
            # CRITICAL: QApplication MUST exist before importing QtWebEngine
            # ... (imports omitted)
            app = QtWidgets.QApplication.instance()
            if app is None:
                logger.warning("[PreviewPanel] QApplication not yet created, creating fallback viewer")
                # Create a simple label as fallback
                lbl = QtWidgets.QLabel("Waiting for application initialization...")
                lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                lbl.setStyleSheet("background: #ffffff; color: #666; padding: 20px; border-radius: 8px;")
                lbl.setMinimumHeight(100) # COMPACT HEIGHT
                return lbl
            
            # ... (sys imports omitted)
            import sys
            import os
            
            # ... (frozen check omitted for brevity, keeping existing logic in real apply)
            # Assuming logic exists...
            
            # CRITICAL: Import QtWebEngine AFTER QApplication exists and DLL paths are set
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            from PyQt6.QtCore import QUrl
            logger.info("[PreviewPanel] QtWebEngineWidgets imported successfully")
            
            view = QWebEngineView()
            view.setMinimumHeight(100) # COMPACT HEIGHT
            view.setStyleSheet(f"""
                QWebEngineView {{
                    background: {Theme.SURFACE};
                    border: none;
                    border-radius: 8px;
                }}
            """)
            
            # Setup WebChannel for communication
            channel = QtWebChannel.QWebChannel(view.page())
            self.controller.bridge.setParent(channel) # Ensure ownership? or just register
            channel.registerObject("bridge", self.controller.bridge)
            view.page().setWebChannel(channel)

            # Connect console logs to python logger
            def _on_console_msg(level, msg, line, source):
                log_map = {0: logger.info, 1: logger.warning, 2: logger.error}
                log_func = log_map.get(level, logger.info)
                log_func(f"js: {msg} (at {source}:{line})")
            
            view.page().javaScriptConsoleMessage = _on_console_msg
            
            # Set initial HTML with error handling
            try:
                initial_html = f"""
                <html>
                <head>
                    <style>
                        body {{
                            background: {Theme.SURFACE};
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            min-height: 100vh;
                            margin: 0;
                            font-family: 'Segoe UI', sans-serif;
                            color: {Theme.TEXT_SECONDARY};
                        }}
                    </style>
                </head>
                <body>
                    <div>Waiting for MathML...</div>
                </body>
                </html>
                """
                root_dir = get_resource_path("")
                base_url = QtCore.QUrl.fromLocalFile(root_dir + os.path.sep)
                view.setHtml(initial_html, base_url)
                logger.info("[PreviewPanel] QWebEngineView created and initialized successfully")
            except Exception as e:
                logger.error(f"[PreviewPanel] Failed to set initial HTML in QWebEngineView: {e}")
            
            return view
        except ImportError as e:
            logger.error(f"[PreviewPanel] QtWebEngine import failed: {e}")
            lbl = QtWidgets.QLabel(f"QtWebEngine not available: {e}")
            lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"background: {Theme.SURFACE}; color: {Theme.TEXT_SECONDARY}; padding: 20px; border-radius: 8px;")
            lbl.setMinimumHeight(100)
            return lbl
        except Exception as e:
            logger.exception(f"[PreviewPanel] Failed to create QWebEngineView: {e}")
            lbl = QtWidgets.QLabel(f"Failed to initialize QtWebEngine: {e}")
            lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"background: {Theme.SURFACE}; color: {Theme.TEXT_SECONDARY}; padding: 20px; border-radius: 8px;")
            lbl.setMinimumHeight(100)
            return lbl

    # ----------------------------------------------------------------------
    def _zoom_in(self):
        """Increase the zoom level of the QWebEngineView."""
        if hasattr(self.equation_view, 'zoomFactor') and hasattr(self.equation_view, 'setZoomFactor'):
            self.equation_view.setZoomFactor(min(3.0, self.equation_view.zoomFactor() + 0.1))
            self._update_zoom_label()

    def _zoom_out(self):
        """Decrease the zoom level of the QWebEngineView."""
        if hasattr(self.equation_view, 'zoomFactor') and hasattr(self.equation_view, 'setZoomFactor'):
            self.equation_view.setZoomFactor(max(0.5, self.equation_view.zoomFactor() - 0.1))
            self._update_zoom_label()

    def _reset_zoom(self):
        """Reset the zoom level to 100%."""
        if hasattr(self.equation_view, 'setZoomFactor'):
            self.equation_view.setZoomFactor(1.0)
            self._update_zoom_label()

    def _update_zoom_label(self):
        """Update the zoom label to reflect the current zoom factor."""
        if hasattr(self.equation_view, 'zoomFactor'):
            zoom_percent = int(self.equation_view.zoomFactor() * 100)
            self.zoom_label.setText(f"{zoom_percent}%")
        else:
            self.zoom_label.setText("100%")

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    def show_loading(self, message: str = "Processing..."):
        """Show loading state in the preview panel and clear previous content."""
        # 1. Clear internal state
        self._current_mathml = ""
        self._stored_latex = ""
        self._current_image_path = None
        self._last_rendered_mathml = ""
        self._last_rendered_latex = ""
        
        # 2. Clear image preview
        self.image_label.clear()
        self.image_label.setText("Processing...")
        self.image_label.setStyleSheet(f"color: {Theme.ACCENT}; font-style: italic;")
        
        # 3. Update code areas (blocked signals to avoid triggering re-renders)
        if hasattr(self, 'converter_display'):
             self.converter_display.setPlaceholderText(message)
        
        # 4. Update Rendered Equation with Skeleton Placeholder
        loading_html = f"""
        <html>
        <head>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
            <style>
                body {{
                    background: {Theme.SURFACE};
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                    margin: 0;
                    font-family: 'Inter', sans-serif;
                    color: {Theme.TEXT_SECONDARY};
                }}
                .loader {{
                    border: 2px solid {Theme.BORDER};
                    border-top: 2px solid {Theme.ACCENT};
                    border-radius: 50%;
                    width: 28px;
                    height: 28px;
                    animation: spin 0.8s cubic-bezier(0.5, 0, 0.5, 1) infinite;
                    margin-bottom: 20px;
                }}
                .status-text {{
                    font-weight: 600;
                    font-size: 11px;
                    letter-spacing: 1px;
                    text-transform: uppercase;
                    color: {Theme.ACCENT};
                    opacity: 0.8;
                }}
                @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
            </style>
        </head>
        <body>
            <div class="loader"></div>
            <div class="status-text">{message}</div>
        </body>
        </html>
        """
        self._load_html_content(loading_html)
        
        self.validation_indicator.setText("● Processing")
        self.validation_indicator.setStyleSheet(f"color: {Theme.TEXT_TERTIARY}; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; padding: 2px 6px; border-radius: 4px; border: 1px solid {Theme.BORDER};")
        self.confidence_label.setText("")
        self.refining_label.show()


    def clear_all(self):
        """Reset the panel to its initial empty state."""
        self.show_loading("Ready")
        # Override loading state specific to 'Clear'
        self.image_label.setText("No selection")
        self.image_label.setStyleSheet(f"color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
        self.img_section_widget.hide()
        if hasattr(self, 'converter_display'):
             self.converter_display.setPlaceholderText("Select an equation to preview...")
        
        # Reset validation status
        self.validation_indicator.setText("● Ready")
        self.validation_indicator.setStyleSheet(f"color: {Theme.TEXT_TERTIARY}; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; padding: 2px 6px; border-radius: 4px; border: 1px solid {Theme.BORDER};")
        self.confidence_label.setText("")
        self.refining_label.hide()
        
        # Clear HTML view with friendly message
        self._load_html_content(f"""
        <html>
        <head>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
        </head>
        <body style='background-color:{Theme.SURFACE}; color:{Theme.TEXT_TERTIARY}; display:flex; justify-content:center; align-items:center; height:100vh; margin:0; font-family:"Inter", sans-serif;'>
            <div style='text-align:center;'>
                <div style='font-size:48px; margin-bottom:16px; opacity:0.5;'>✨</div>
                <div style='font-size:12px; font-weight:600; letter-spacing:1px; text-transform:uppercase;'>Select an equation to start</div>
            </div>
        </body>
        </html>
        """)



    def _show_image_preview(self, image_path: str):
        """Load and display the source image preview."""
        self._current_image_path = image_path
        
        # Check if file exists
        import os
        if not image_path or not os.path.exists(image_path):
            self.image_label.setText("No Image Preview")
            self.image_label.clear()
            self.image_label.setText("No Preview")
            return
            
        # Load pixmap
        pixmap = QtGui.QPixmap(image_path)
        if not pixmap.isNull():
            # Scale efficiently maintaining aspect ratio
            scaled = pixmap.scaled(
                self.image_container.width() - 20, 
                80, # Max height matches container constraint
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)
            self.img_section_widget.show() # Reveal section
        else:
            self.image_label.setText("Invalid Image")

    def show_validation_status(self, is_valid: bool, confidence: float, error_msg: str = None):
        """Update the validation status indicator."""
        self.refining_label.hide()
        
        if not is_valid:
            self.validation_indicator.setText("● Invalid")
            self.validation_indicator.setStyleSheet(f"color: {Theme.ERROR}; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; padding: 2px 6px; border-radius: 4px; border: 1px solid {Theme.BORDER};")
            self.confidence_label.setText("")
            if error_msg:
                self.validation_indicator.setToolTip(error_msg)
        else:
            self.validation_indicator.setText("● Valid")
            self.validation_indicator.setStyleSheet(f"color: #4CAF50; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; padding: 2px 6px; border-radius: 4px; border: 1px solid {Theme.BORDER};")
            
            # Show confidence if available
            if confidence > 0:
                score = int(confidence * 100)
                self.confidence_label.setText(f"{score}% Confidence")
                
                # Color code based on score
                if score > 90:
                    self.confidence_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 11px; margin-left: 10px;")
                elif score > 70:
                    self.confidence_label.setStyleSheet("color: #FFC107; font-weight: bold; font-size: 11px; margin-left: 10px;")
                else:
                    self.confidence_label.setStyleSheet("color: {Theme.ERROR}; font-weight: bold; font-size: 11px; margin-left: 10px;")
            else:
                self.confidence_label.setText("")

    # ----------------------------------------------------------------------
    def update_preview(self, latex: str, mathml: str = "", is_valid: bool = True, 
                      confidence: float = 0.0, image_path: str = None, 
                      error_msg: str = None, ast_data: dict = None):
        """Update preview with new OCR result."""
        # Update UI status
        self.show_validation_status(is_valid, confidence, error_msg)
        
        # Handling image preview
        if image_path:
            self._show_image_preview(image_path)
            self._current_image_path = image_path
            
        # UI Update: Update MathML source display explicitly
        if mathml:
            if hasattr(self, 'converter_display'):
                # Apply mml: prefixes for the converter display as requested
                prefixed = self._apply_mml_prefixes(mathml) if hasattr(self, '_apply_mml_prefixes') else mathml
                self.converter_display.setPlainText(prefixed)
            self._current_mathml = mathml
        else:
            if hasattr(self, 'converter_display'):
                self.converter_display.setPlainText("")
            
        # Confidence logic: If we have AST, we represent 100% confidence in the *structure*
        display_confidence = confidence
        if ast_data and is_valid:
            # If we successfully parsed AST, we are very confident
            display_confidence = 1.0
            # Update the status with new confidence
            self.show_validation_status(is_valid, display_confidence, error_msg)

        # Pass data to controller
        self.controller.update_content(latex, mathml, is_valid, display_confidence, image_path, ast_data)

    def update_partial_preview(self, image_path: str, raw_latex: str):
        """Show instantaneous raw LaTeX preview while OCR refines."""
        # 1. Show refining status
        from core.config import settings
        if settings.turbo_mode:
            self.refining_label.setText("Turbo Processing...")
            self.validation_indicator.setText("● Turbo")
        else:
            self.refining_label.setText("Refining Selection...")
            self.validation_indicator.setText("● Refining")
            
        self.refining_label.show()
        self.validation_indicator.setStyleSheet(f"color: {Theme.ACCENT}; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; padding: 2px 6px; border-radius: 4px; border: 1px solid {Theme.BORDER};")
        
        # 2. Update image preview if new
        if image_path and image_path != self._current_image_path:
            self._show_image_preview(image_path)
            
        # 3. CRITICAL: Render the raw LaTeX immediately!
        # This gives "Mathpix-like" instant feedback.
        # We pass empty mathml/ast, and partial confidence.
        # Controller now uses LaTeX for standard view, so this works perfectly.
        self.controller.update_content(raw_latex, "", True, 0.0, image_path, None)

    def update_image_preview(self, image_path: str):
        """Update just the image preview."""
        self._show_image_preview(image_path)



    def copy_latex(self):
        """Copy the stored LaTeX to clipboard."""
        if self._stored_latex:
            clipboard = QtWidgets.QApplication.clipboard()
            clipboard.setText(self._stored_latex)
            self.copy_latex_btn.setText("Copied!")
            QtCore.QTimer.singleShot(2000, lambda: self.copy_latex_btn.setText("Copy LaTeX"))
        else:
             self.copy_latex_btn.setText("No LaTeX")
             QtCore.QTimer.singleShot(2000, lambda: self.copy_latex_btn.setText("Copy LaTeX"))

    def _copy_mathml(self):
        """Copy current MathML to clipboard, generating on-demand if needed."""
        clipboard = QtWidgets.QApplication.clipboard()
        
        # 1. Try existing MathML
        if self._current_mathml:
            clipboard.setText(self._current_mathml)
            self._animate_copy_btn()
            return

        # 2. Try on-demand conversion
        if self._stored_latex:
            try:
                from latex2mathml.converter import convert as latex2mathml_convert
                mml = latex2mathml_convert(self._stored_latex)
                clipboard.setText(mml)
                self._animate_copy_btn()
                
                # Update display too since we have it
                self._current_mathml = mml
                return
            except Exception as e:
                logger.warning(f"On-demand MathML conversion failed: {e}")
                
        # 3. Failed
        if hasattr(self, 'copy_mml_btn'):
            original_text = self.copy_mml_btn.text()
            self.copy_mml_btn.setText("Error")
            QtCore.QTimer.singleShot(2000, lambda: self.copy_mml_btn.setText(original_text))

    def _animate_copy_btn(self):
        """Helper to animate copy button."""
        # Update: We now use self.copy_mml_btn in the action row
        if hasattr(self, 'copy_mml_btn'):
            original_text = "Copy MathML"
            self.copy_mml_btn.setText("Copied!")
            self.copy_mml_btn.setStyleSheet(f"QPushButton {{ background: {Theme.ACCENT}; color: white; border: 1px solid {Theme.ACCENT}; border-radius: 6px; font-size: 11px; font-weight: 600; padding: 0 16px; }}")
            
            def restore():
                self.copy_mml_btn.setText(original_text)
                self.copy_mml_btn.setStyleSheet(f"QPushButton {{ background: {Theme.SURFACE}; color: {Theme.ACCENT}; border: 1px solid {Theme.BORDER}; border-radius: 6px; font-size: 11px; font-weight: 600; padding: 0 16px; }} QPushButton:hover {{ border-color: {Theme.ACCENT}; background: {Theme.SURFACE_HOVER}; }}")
            
            QtCore.QTimer.singleShot(2000, restore)

    def _copy_mml_converter_text(self):
        """Copy MML Converter output and show feedback."""
        if hasattr(self, 'converter_display'):
            text = self.converter_display.toPlainText()
            if text:
                QtWidgets.QApplication.clipboard().setText(text)
                if hasattr(self, 'copy_cv_btn'):
                    original_text = "Copy MML Code"
                    self.copy_cv_btn.setText("Copied!")
                    self.copy_cv_btn.setStyleSheet(f"QPushButton {{ background: {Theme.ACCENT}; color: white; border: 1px solid {Theme.ACCENT}; border-radius: 4px; font-size: 10px; font-weight: 600; }}")
                    
                    def restore_cv():
                        self.copy_cv_btn.setText(original_text)
                        self.copy_cv_btn.setStyleSheet(f"QPushButton {{ background: {Theme.SURFACE}; color: {Theme.TEXT_SECONDARY}; border: 1px solid {Theme.BORDER}; border-radius: 4px; font-size: 10px; font-weight: 600; }} QPushButton:hover {{ border-color: {Theme.ACCENT}; background: {Theme.SURFACE_HOVER}; }}")
                    
                    QtCore.QTimer.singleShot(2000, restore_cv)

    def _handle_manual_convert(self):
        """Handle manual conversion request."""
        if not hasattr(self, 'manual_cv_input'):
            return
            
        text = self.manual_cv_input.toPlainText().strip()
        if not text:
            return
            
        # Determine if LaTeX or MathML
        if '<math' in text:
            # Already MathML? Just render
            self.update_preview("", text, True, 1.0) # Assume valid if user pasted it
        else:
            # LaTeX -> MathML
            try:
                from latex2mathml.converter import convert as latex2mathml_convert
                mml = latex2mathml_convert(text)
                self.update_preview(text, mml, True, 1.0)
                if hasattr(self, 'converter_display'):
                    self.converter_display.setPlainText(mml)
            except Exception as e:
                if hasattr(self, 'converter_display'):
                    self.converter_display.setPlainText(f"Conversion Error: {e}")



    def _on_save_snip(self):
        """Trigger save snip via controller."""
        self.controller.save_current_snip()

    def _on_copy_tsv(self):
        """Request TSV copy."""
        self.copy_tsv_requested.emit(self._stored_latex)
        
    def _on_copy_asciimath(self):
        """Request AsciiMath copy."""
        self.copy_asciimath_requested.emit(self._stored_latex)

    def _handle_manual_convert(self):
        """Handle manual conversion request."""
        text = self.manual_cv_input.toPlainText().strip()
        if not text:
            return
            
        # Determine if LaTeX or MathML
        if '<math' in text:
            # Already MathML? Just render
            self.update_preview("", text, True, 1.0) # Assume valid if user pasted it
        else:
            # LaTeX -> MathML
            try:
                mml = latex2mathml_convert(text)
                self.update_preview(text, mml, True, 1.0)
            except Exception as e:
                self.mathml_display.setPlainText(f"Conversion Error: {e}")

    # ============================================================================
    # VISUAL EDITOR (Delegated to Controller)
    # ============================================================================
    
    def _toggle_turbo_mode(self, checked: bool):
        """Update global turbo mode setting and UI feedback."""
        from core.config import settings
        settings.turbo_mode = checked
        logger.info(f"[PreviewPanel] Turbo Mode {'ENABLED' if checked else 'DISABLED'}")
        
        # Immediate UI feedback for running tasks
        if checked:
            if self.refining_label.isVisible():
                self.refining_label.setText("Turbo Processing...")
                self.validation_indicator.setText("● Turbo")
        else:
            if self.refining_label.isVisible() and "Turbo" in self.refining_label.text():
                self.refining_label.setText("Refining Selection...")
                self.validation_indicator.setText("● Refining")

    def _toggle_visual_editor(self, active: bool):
        """Switch between standard Preview and Visual Editor."""
        self._is_visual_editor_active = active
        
        # Update Button UI
        if active:
            self.edit_visual_btn.setText("👁️ Preview")
            self.edit_visual_btn.setStyleSheet(f"QPushButton {{ background: {Theme.ACCENT}; color: white; border: none; border-radius: 4px; padding: 4px 12px; font-weight: 600; }}")
        else:
            self.edit_visual_btn.setText("✏️ Edit Visual")
            self.edit_visual_btn.setStyleSheet(f"QPushButton {{ background: {Theme.SURFACE}; color: {Theme.TEXT_PRIMARY}; border: 1px solid {Theme.BORDER}; border-radius: 4px; padding: 4px 12px; font-weight: 600; }}")

        # Delegate to controller
        self.controller.set_visual_editor_mode(active)
