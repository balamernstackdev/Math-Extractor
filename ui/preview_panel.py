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
import re
import sys
from PyQt6 import QtCore, QtGui, QtWidgets
from latex2mathml.converter import convert as latex2mathml_convert

from services.ocr.strict_pipeline import StrictMathpixPipeline
from core.logger import logger


# ============================================================================
# CORRUPTION DETECTION (patched & precise)
# ============================================================================

def is_structural_mathml(xml: str) -> bool:
    """Does the MathML contain real structure?"""
    if not xml:
        return False

    structural_tags = [
        "<mfrac", "<msub", "<msup", "<msubsup",
        "<mrow", "<munderover", "<mtable"
    ]
    return any(tag in xml for tag in structural_tags)


def is_corrupted_mathml(xml: str) -> bool:
    """Detect *real* MathML corruption, not simple OCR imperfections."""
    if not xml or "<math" not in xml:
        return False

    # Shredded OCR patterns — TRUE corruption (letter-by-letter subscripts)
    shredded_patterns = [
        r"<mi>\\?[lmr]</mi>\s*<mi>\\?[aei]</mi>\s*<mi>\\?[fgh]</mi>\s*<mi>\\?[t]</mi>",  # left, right
        r"<mi>\\?[fs]</mi>\s*<mi>\\?[ru]</mi>\s*<mi>\\?[am]</mi>\s*<mi>\\?[cm]</mi>",  # frac, sum
        r"<mi>\\?[mb]</mi>\s*<mi>\\?[ai]</mi>\s*<mi>\\?[tg]</mi>\s*<mi>\\?[hc]</mi>",  # math, big
        r"<mi>\\?[ne]</mi>\s*<mi>\\?[eq]</mi>",  # ne, eq
        r"<mi>\\?[ld]</mi>\s*<mi>\\?[do]</mi>\s*<mi>\\?[ot]</mi>\s*<mi>\\?[ts]</mi>",  # ldots, dots
        r"<mi>\\?[bi]</mi>\s*<mi>\\?[ig]</mi>\s*<mi>\\?[gc]</mi>\s*<mi>\\?[cu]</mi>\s*<mi>\\?[up]</mi>",  # bigcup
        r"<mi>\\?[un]</mi>\s*<mi>\\?[nd]</mi>\s*<mi>\\?[de]</mi>\s*<mi>\\?[er]</mi>\s*<mi>\\?[rl]</mi>\s*<mi>\\?[li]</mi>\s*<mi>\\?[in]</mi>\s*<mi>\\?[ne]</mi>",  # underline
        r"<mi>\\?[ov]</mi>\s*<mi>\\?[ve]</mi>\s*<mi>\\?[er]</mi>\s*<mi>\\?[rl]</mi>\s*<mi>\\?[li]</mi>\s*<mi>\\?[in]</mi>\s*<mi>\\?[ne]</mi>",  # overline
        r"<mi>\\?[su]</mi>\s*<mi>\\?[um]</mi>",  # sum (shredded)
        r"<mi>\\?[in]</mi>\s*<mi>\\?[nt]</mi>\s*<mi>\\?[te]</mi>\s*<mi>\\?[eg]</mi>\s*<mi>\\?[gr]</mi>\s*<mi>\\?[ra]</mi>\s*<mi>\\?[al]</mi>",  # integral
    ]
    for pat in shredded_patterns:
        if re.search(pat, xml, re.IGNORECASE):
            return True

    # Check for backslash tokens in <mi> tags (corrupted LaTeX commands)
    if re.search(r"<mi>\\[a-zA-Z]+</mi>", xml):
        # Check if it's a shredded command (multiple <mi> tags with backslashes)
        if len(re.findall(r"<mi>\\[a-zA-Z]</mi>", xml)) > 2:
            return True

    # Check for <mtext> containing LaTeX commands (corrupted)
    if re.search(r"<mtext>.*\\[a-zA-Z]+\{.*\}", xml):
        return True

    # Unbalanced tags detection
    tag_pairs = [
        ("<msub", "</msub>"),
        ("<msup", "</msup>"),
        ("<mrow", "</mrow>"),
        ("<mfrac", "</mfrac>"),
    ]
    for open_tag, close_tag in tag_pairs:
        if xml.count(open_tag) != xml.count(close_tag):
            return True

    # Check for nested subscripts that look shredded (e.g., m_{a}t_{h})
    if re.search(r"<msub><mi>[a-z]</mi><mrow><mi>[a-z]</mi><msub>", xml):
        return True

    return False


def extract_tex_from_mathml(xml: str) -> str:
    """Extract fallback TeX only if MathML truly corrupted."""
    txt = re.sub(r"<[^>]+>", " ", xml)
    return txt.strip()


# ============================================================================
# PREVIEW PANEL
# ============================================================================

class PreviewPanel(QtWidgets.QFrame):

    copy_mathml_requested = QtCore.pyqtSignal(str)
    export_requested = QtCore.pyqtSignal(str)

    # ----------------------------------------------------------------------
    def __init__(self) -> None:
        super().__init__()
        # Use strict pipeline to enforce correct pipeline flow:
        # 1. OCR → LaTeX (raw)
        # 2. Regex + AST Corruption Gate → Clean LaTeX
        # 3. OpenAI (LaTeX ONLY, semantic rewrite) → Clean LaTeX
        # 4. Deterministic LaTeX→MathML compiler
        # 5. MathML Validator
        self.pipeline = StrictMathpixPipeline()
        self._stored_latex = ""  # Store LaTeX for direct rendering
        self._mathml_validated = False  # Track if MathML was validated by pipeline
        self._build_ui()

    # ----------------------------------------------------------------------
    def _build_ui(self):
        self.setFixedWidth(380)
        self.setStyleSheet("""
            QFrame { 
                background: #1a1a1a; 
                border-left: 1px solid #2d2d2d; 
            }
            QLabel { 
                color: #e0e0e0; 
            }
            QTextEdit {
                background: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                color: #e0e0e0;
                font-family: 'Segoe UI', 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                padding: 10px;
                selection-background-color: #0078d4;
            }
            QTextEdit:focus {
                border: 1px solid #0078d4;
            }
            QPushButton { 
                background: #0078d4; 
                color: white; 
                border-radius: 6px; 
                padding: 8px 16px;
                font-weight: 600;
                font-size: 13px;
                border: none;
            }
            QPushButton:hover { 
                background: #106ebe; 
            }
            QPushButton:pressed {
                background: #005a9e;
            }
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Title with modern styling
        title_frame = QtWidgets.QFrame()
        title_frame.setStyleSheet("background: transparent;")
        title_layout = QtWidgets.QHBoxLayout(title_frame)
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        title = QtWidgets.QLabel("Preview")
        title.setStyleSheet("""
            font-size: 20px; 
            font-weight: 700; 
            color: #ffffff;
            letter-spacing: 0.5px;
        """)
        title_layout.addWidget(title)
        title_layout.addStretch()
        layout.addWidget(title_frame)

        # Image preview (small, optional) - Modern card
        self.image_label = QtWidgets.QLabel("")
        self.image_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMaximumHeight(120)
        self.image_label.setScaledContents(True)
        self.image_label.setStyleSheet("""
            QLabel {
                background: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        self.image_label.hide()
        layout.addWidget(self.image_label)

        # MathML section - Modern card
        mathml_card = QtWidgets.QFrame()
        mathml_card.setStyleSheet("background: transparent;")
        mathml_card_layout = QtWidgets.QVBoxLayout(mathml_card)
        mathml_card_layout.setContentsMargins(0, 0, 0, 0)
        mathml_card_layout.setSpacing(8)
        
        mathml_label = QtWidgets.QLabel("MathML")
        mathml_label.setStyleSheet("""
            color: #b0b0b0; 
            font-size: 11px; 
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            padding: 0px;
        """)
        mathml_card_layout.addWidget(mathml_label)

        self.mathml_edit = QtWidgets.QTextEdit()
        self.mathml_edit.setReadOnly(True)
        self.mathml_edit.setMinimumHeight(120)
        self.mathml_edit.setMaximumHeight(200)
        self.mathml_edit.setPlaceholderText("No MathML available")
        self.mathml_edit.setStyleSheet("""
            QTextEdit {
                background: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                color: #c0c0c0;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                padding: 10px;
            }
        """)
        self.mathml_edit.textChanged.connect(self._update_equation)
        mathml_card_layout.addWidget(self.mathml_edit)
        layout.addWidget(mathml_card)

        # Action buttons - Modern design
        button_frame = QtWidgets.QFrame()
        button_frame.setStyleSheet("background: transparent;")
        button_layout = QtWidgets.QHBoxLayout(button_frame)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(10)
        
        copy_btn = QtWidgets.QPushButton("📋 Copy MathML")
        copy_btn.setMinimumHeight(38)
        copy_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(lambda: self.copy_mathml_requested.emit(self.mathml_edit.toPlainText()))
        
        export_btn = QtWidgets.QPushButton("💾 Export")
        export_btn.setMinimumHeight(38)
        export_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        export_btn.clicked.connect(lambda: self.export_requested.emit(self.mathml_edit.toPlainText()))
        
        button_layout.addWidget(copy_btn)
        button_layout.addWidget(export_btn)
        layout.addWidget(button_frame)
        
        layout.addSpacing(4)

        # Rendered Equation section - Modern card
        rendered_card = QtWidgets.QFrame()
        rendered_card.setStyleSheet("background: transparent;")
        rendered_card_layout = QtWidgets.QVBoxLayout(rendered_card)
        rendered_card_layout.setContentsMargins(0, 0, 0, 0)
        rendered_card_layout.setSpacing(8)
        
        rendered_label = QtWidgets.QLabel("Rendered Equation")
        rendered_label.setStyleSheet("""
            color: #b0b0b0; 
            font-size: 11px; 
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            padding: 0px;
        """)
        rendered_card_layout.addWidget(rendered_label)

        # MathML viewer with modern frame
        viewer_frame = QtWidgets.QFrame()
        viewer_frame.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 0px;
            }
        """)
        viewer_layout = QtWidgets.QVBoxLayout(viewer_frame)
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        
        self.equation_view = self._create_viewer()
        viewer_layout.addWidget(self.equation_view)
        rendered_card_layout.addWidget(viewer_frame)
        layout.addWidget(rendered_card)

        layout.addStretch()

    # ----------------------------------------------------------------------
    def _create_viewer(self):
        """Try WebEngine, else fallback label."""
        try:
            # CRITICAL: Initialize QtWebEngine before importing
            import sys
            import os
            if getattr(sys, 'frozen', False):
                # Running as EXE - ensure paths are set
                from pathlib import Path
                base_path = Path(sys._MEIPASS)
                
                # Add DLL directories (same as runtime hook)
                dll_paths = [
                    base_path / 'PyQt6' / 'Qt6' / 'bin',
                    base_path,  # Root where PyInstaller places binaries
                    base_path / 'PyQt6',  # PyQt6 root
                ]
                
                for dll_path in dll_paths:
                    if dll_path.exists():
                        try:
                            os.add_dll_directory(str(dll_path))
                            logger.debug(f"[PreviewPanel] Added DLL directory: {dll_path}")
                        except (AttributeError, OSError):
                            # Fallback to PATH
                            current_path = os.environ.get('PATH', '')
                            if str(dll_path) not in current_path:
                                os.environ['PATH'] = str(dll_path) + os.pathsep + current_path
                
                # Set QtWebEngine process path (try multiple locations)
                possible_process_paths = [
                    base_path / 'PyQt6' / 'Qt6' / 'bin' / 'QtWebEngineProcess.exe',
                    base_path / 'PyQt6' / 'Qt6' / 'libexec' / 'QtWebEngineProcess.exe',
                    base_path / 'QtWebEngineProcess.exe',
                ]
                
                for webengine_process in possible_process_paths:
                    if webengine_process.exists():
                        os.environ['QTWEBENGINEPROCESS_PATH'] = str(webengine_process)
                        logger.info(f"[PreviewPanel] Set QTWEBENGINEPROCESS_PATH: {webengine_process}")
                        break
                else:
                    logger.warning("[PreviewPanel] QtWebEngineProcess.exe not found in any standard location")
            
            # Now try to import and create WebEngine view
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            from PyQt6.QtCore import QUrl
            logger.info("[PreviewPanel] QtWebEngineWidgets imported successfully")
            
            view = QWebEngineView()
            view.setMinimumHeight(180)
            view.setStyleSheet("""
                QWebEngineView {
                    background: #ffffff;
                    border: none;
                    border-radius: 8px;
                }
            """)
            
            # Set initial HTML with error handling
            try:
                initial_html = """
                <html>
                <head>
                    <style>
                        body {
                            background: #ffffff;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            min-height: 100vh;
                            margin: 0;
                            font-family: 'Segoe UI', sans-serif;
                            color: #666;
                        }
                    </style>
                </head>
                <body>
                    <div>Waiting for MathML...</div>
                </body>
                </html>
                """
                view.setHtml(initial_html)
                logger.info("[PreviewPanel] QWebEngineView created and initialized successfully")
            except Exception as e:
                logger.error(f"[PreviewPanel] Failed to set initial HTML in QWebEngineView: {e}")
                # View created but can't set HTML - might still work later
                # Don't fail here, let it try again when rendering actual content
            
            return view
        except ImportError as e:
            logger.error(f"[PreviewPanel] QtWebEngine import failed: {e}")
            logger.error(f"[PreviewPanel] sys.path: {sys.path}")
            if getattr(sys, 'frozen', False):
                logger.error(f"[PreviewPanel] Running as EXE, _MEIPASS: {getattr(sys, '_MEIPASS', 'N/A')}")
            lbl = QtWidgets.QLabel(
                f"QtWebEngine not available.\n\n"
                f"Error: {str(e)}\n\n"
                f"Please ensure PyQt6-WebEngine is installed and bundled correctly."
            )
            lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("""
                background: #ffffff; 
                color: #666; 
                padding: 20px;
                border-radius: 8px;
                font-family: 'Segoe UI', sans-serif;
            """)
            lbl.setMinimumHeight(180)
            return lbl
        except Exception as e:
            logger.exception(f"[PreviewPanel] Failed to create QWebEngineView: {e}")
            lbl = QtWidgets.QLabel(
                f"Failed to initialize QtWebEngine.\n\n"
                f"Error: {str(e)}\n\n"
                f"Check logs for details."
            )
            lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("""
                background: #ffffff; 
                color: #666; 
                padding: 20px;
                border-radius: 8px;
                font-family: 'Segoe UI', sans-serif;
            """)
            lbl.setMinimumHeight(180)
            return lbl

    # ----------------------------------------------------------------------
    def update_preview(self, image_path: str | None, latex: str, mathml: str, is_valid: bool = False):
        """Main entry — refresh content after selection.
        
        Args:
            image_path: Path to cropped image
            latex: LaTeX string
            mathml: MathML string
            is_valid: Whether MathML was validated by the pipeline (trust this over corruption detection)
        """

        # Image preview (optional, show if available)
        if image_path:
            pm = QtGui.QPixmap(image_path)
            if not pm.isNull():
                scaled_pm = pm.scaled(
                    280, 100,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pm)
                self.image_label.show()
            else:
                self.image_label.hide()
        else:
            self.image_label.hide()

        # Store LaTeX for direct rendering (always store, even if empty)
        self._stored_latex = latex.strip() if latex else ""
        self._mathml_validated = is_valid  # Store validation status
        logger.debug("[PreviewPanel] update_preview called with is_valid=%s, mathml length=%d", 
                    is_valid, len(mathml) if mathml else 0)

        # If MathML is missing but LaTeX is available, try to generate MathML
        if not mathml or mathml.strip() == "No MathML available" or not mathml.strip():
            if self._stored_latex and self._stored_latex.strip():
                logger.info("[PreviewPanel] MathML missing, attempting to generate from LaTeX: %s", self._stored_latex[:50])
                try:
                    # Try direct conversion using latex2mathml
                    generated_mathml = latex2mathml_convert(self._stored_latex)
                    if generated_mathml and "<math" in generated_mathml:
                        mathml = generated_mathml
                        self._mathml_validated = False  # Generated, not validated
                        logger.info("[PreviewPanel] Successfully generated MathML from LaTeX (length: %d)", len(mathml))
                    else:
                        logger.warning("[PreviewPanel] MathML conversion returned invalid result")
                except ImportError as e:
                    logger.error("[PreviewPanel] latex2mathml not available: %s", e)
                    logger.error("[PreviewPanel] This may indicate missing imports in EXE build")
                except Exception as e:
                    logger.warning("[PreviewPanel] Failed to generate MathML from LaTeX: %s", e)
                    # Try using the pipeline as fallback
                    try:
                        result = self.pipeline.process_latex(self._stored_latex)
                        pipeline_mathml = result.get("mathml", "")
                        if pipeline_mathml and "<math" in pipeline_mathml:
                            mathml = pipeline_mathml
                            self._mathml_validated = result.get("is_valid", False)  # Use pipeline validation
                            logger.info("[PreviewPanel] Generated MathML via pipeline (length: %d, valid: %s)", len(mathml), self._mathml_validated)
                    except Exception as pipeline_exc:
                        logger.warning("[PreviewPanel] Pipeline fallback also failed: %s", pipeline_exc)

        # MathML panel
        self.mathml_edit.blockSignals(True)
        self.mathml_edit.setPlainText(mathml or "No MathML available")
        self.mathml_edit.blockSignals(False)

        # Always delegate rendering decision to _update_equation so that
        # validated MathML from the strict pipeline is preferred, with LaTeX
        # used only as a fallback when MathML is missing/invalid.
        logger.info("[PreviewPanel] Updating equation from latest LaTeX/MathML (validated: %s, mathml length: %d)", 
                   self._mathml_validated, len(mathml) if mathml else 0)
        self._update_equation()

    # ============================================================================
    # CORE RENDERING LOGIC
    # ============================================================================

    def _update_equation(self):
        mathml = self.mathml_edit.toPlainText().strip()
        # Decode any HTML entities (e.g. &#x00029;) so they don't appear as
        # raw text and confuse downstream MathML validation/MathJax.
        if mathml:
            try:
                mathml = html.unescape(mathml)
            except Exception:
                pass

        # ----------------------------------------------------------
        # ----------------------------------------------------------
        if not mathml or "No MathML" in mathml:
            if self._stored_latex and self._stored_latex.strip():
                # Best-effort latex2mathml fallback
                fallback_mathml = self._fallback_mathml_from_latex(self._stored_latex)
                if fallback_mathml:
                    mathml = fallback_mathml
                    self.mathml_edit.blockSignals(True)
                    self.mathml_edit.setPlainText(fallback_mathml)
                    self.mathml_edit.blockSignals(False)
                else:
                    self._render_tex(self._stored_latex)
                    return
            else:
                self._render_html("<html><body>No equation</body></html>")
                return

        # ----------------------------------------------------------
        # CASE B: Detect corruption and ALWAYS recover before rendering
        # ----------------------------------------------------------
        # Trust pipeline validation if available (more reliable than pattern matching)
        # Only use corruption detection if MathML wasn't validated by pipeline
        logger.debug("[PreviewPanel] Checking validation status: _mathml_validated=%s", self._mathml_validated)
        if self._mathml_validated:
            # CRITICAL: Even if validated, check for incomplete multiline MathML
            # If LaTeX has multiple lines but MathML only has one row, it's incomplete
            if "<mtable" in mathml and self._stored_latex:
                # Count expected lines from LaTeX (check for \\ or \n)
                latex_line_count = max(1, self._stored_latex.count("\\\\") + self._stored_latex.count("\n") + 1)
                # Count actual rows in MathML
                mathml_row_count = mathml.count("<mtr>")
                if latex_line_count > mathml_row_count:
                    logger.warning("[PreviewPanel] ⚠️ Incomplete MathML detected: LaTeX has %d lines but MathML only has %d rows. Attempting recovery.", 
                                 latex_line_count, mathml_row_count)
                    # Mark as invalid to trigger recovery
                    self._mathml_validated = False
                    # Fall through to corruption detection/recovery
                else:
                    logger.info("[PreviewPanel] ✅ MathML was validated by pipeline (is_valid=True), trusting it and skipping corruption check")
                    # Render directly if validated and complete - pipeline already checked it
                    if is_structural_mathml(mathml):
                        logger.info("[PreviewPanel] Rendering validated MathML from pipeline (no recovery needed)")
                        self._render_mathml(mathml)
                        return
                    else:
                        # Even if validated, if it's not structural, render as LaTeX
                        logger.debug("[PreviewPanel] Validated MathML is not structural, rendering as LaTeX")
                        if self._stored_latex:
                            self._render_tex(self._stored_latex)
                            return
            else:
                logger.info("[PreviewPanel] ✅ MathML was validated by pipeline (is_valid=True), trusting it and skipping corruption check")
                # Render directly if validated - pipeline already checked it
                if is_structural_mathml(mathml):
                    logger.info("[PreviewPanel] Rendering validated MathML from pipeline (no recovery needed)")
                    self._render_mathml(mathml)
                    return
                else:
                    # Even if validated, if it's not structural, render as LaTeX
                    logger.debug("[PreviewPanel] Validated MathML is not structural, rendering as LaTeX")
                    if self._stored_latex:
                        self._render_tex(self._stored_latex)
                        return
        else:
            logger.debug("[PreviewPanel] MathML was NOT validated by pipeline (is_valid=False), using corruption detection")
        
        # Fallback: Use corruption detection if not validated
        is_corrupted = is_corrupted_mathml(mathml)
        
        if is_corrupted:
            logger.info("[PreviewPanel] Corrupted MathML detected, attempting recovery")
            # NEVER render corrupted MathML directly - always try to recover first
            
            # Use strict pipeline recovery (OpenAI is disabled per MANDATORY PIPELINE rules)
            # The pipeline will handle LaTeX semantic rewriting via OpenAI internally if needed
            try:
                result = self.pipeline.process_mathml(mathml)
                recovered_latex = result.get("clean_latex", "")
                recovered_mathml = result.get("mathml", "")

                # Use recovered MathML if valid (PREFERRED)
                if recovered_mathml and '<math' in recovered_mathml and 'data-error' not in recovered_mathml:
                    logger.info("[PreviewPanel] FORCE recovery produced clean MathML (preferred)")
                    self._render_mathml(recovered_mathml)
                    return

                # Fallback: use recovered LaTeX if available
                if recovered_latex and recovered_latex.strip() and 'data-error' not in recovered_latex:
                    logger.info("[PreviewPanel] FORCE recovery produced clean LaTeX (fallback)")
                    self._render_tex(recovered_latex)
                    return
            except Exception as exc:
                logger.exception("[PreviewPanel] FORCE recovery failed")
            
            # Last resort: try to extract LaTeX from corrupted MathML
            tex = extract_tex_from_mathml(mathml)
            if tex and tex.strip():
                logger.warning("[PreviewPanel] Using extracted LaTeX as last resort")
                self._render_tex(tex)
                return
            
            # If all recovery failed, show error message
            self._render_html("<html><body style='background:white; padding:20px; text-align:center; color:red;'>Failed to recover equation</body></html>")
            return

        # ----------------------------------------------------------
        # CASE D: MathML appears clean - process locally
        # ----------------------------------------------------------
        try:
            result = self.pipeline.process_mathml(mathml)
            recovered_latex = result.get("clean_latex", "")
            recovered_mathml = result.get("mathml", "")
            
            # Priority 1: Use recovered MathML if valid (no TeX parsing involved)
            if recovered_mathml and '<math' in recovered_mathml and 'data-error' not in recovered_mathml:
                logger.info("[PreviewPanel] Rendering strict-pipeline MathML (preferred)")
                self._render_mathml(recovered_mathml)
                return
            
            # Priority 2: Fallback to recovered LaTeX if available
            if recovered_latex and recovered_latex.strip() and 'data-error' not in recovered_latex:
                logger.info("[PreviewPanel] Rendering strict-pipeline LaTeX (fallback)")
                self._render_tex(recovered_latex)
                return
        except Exception as exc:
            logger.debug("[PreviewPanel] Pipeline processing failed: %s", exc)

        # ----------------------------------------------------------
        # CASE F: Final fallback - render original MathML if structural
        # ----------------------------------------------------------
        if is_structural_mathml(mathml):
            logger.debug("[PreviewPanel] Rendering original MathML")
            self._render_mathml(mathml)
        else:
            # Invalid MathML - show error
            self._render_html("<html><body style='background:white; padding:20px; text-align:center;'>Invalid MathML</body></html>")

    def _fallback_mathml_from_latex(self, latex: str) -> str:
        """Best-effort MathML from LaTeX when strict pipeline returns none."""
        try:
            converted = latex2mathml_convert(latex)
            if converted and "<math" in converted:
                return converted
        except Exception:
            pass
        return ""

    # ============================================================================
    # RENDERING HELPERS
    # ============================================================================

    def _render_mathml(self, mathml: str):
        """Render valid MathML via MathJax with proper configuration."""
        # Detect if running in PyInstaller bundle (EXE)
        import sys
        import os
        from pathlib import Path
        from PyQt6.QtCore import QUrl
        
        is_bundled = getattr(sys, 'frozen', False)
        # For pure MathML rendering we use the dedicated MathML-only bundle
        # so that TeX parsing errors (e.g. "Misplaced &") cannot leak through.
        mathjax_src = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/mml-chtml.js"
        
        # Try to use local MathJax if bundled
        if is_bundled:
            base_path = Path(sys._MEIPASS)
            # Bundled MathJax path for the MathML-only build
            local_mathjax = base_path / 'mathjax' / 'mml-chtml.js'
            if local_mathjax.exists():
                # Use QUrl.fromLocalFile() for proper local file access in QtWebEngine
                local_url = QUrl.fromLocalFile(str(local_mathjax))
                mathjax_src = local_url.toString()
                logger.info(f"[PreviewPanel] Using local MathJax from bundle: {mathjax_src}")
            else:
                # Fallback: Use CDN (will fail offline, but better than nothing)
                logger.warning(f"[PreviewPanel] Local MathJax not found at {local_mathjax}, using CDN (may fail offline)")
                logger.warning(f"[PreviewPanel] MathJax directory exists: {(base_path / 'mathjax').exists()}")
                if (base_path / 'mathjax').exists():
                    logger.warning(f"[PreviewPanel] MathJax directory contents: {list((base_path / 'mathjax').iterdir())[:5]}")
        
        html_code = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<script>
window.MathJax = {{
    options: {{
        skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre'],
        ignoreHtmlClass: 'tex2jax_ignore',
        processHtmlClass: 'tex2jax_process'
    }},
    loader: {{
        load: ['[tex]/mhchem']
    }},
    startup: {{
        ready: () => {{
            MathJax.startup.defaultReady();
            MathJax.startup.promise.then(() => {{
                console.log('MathJax loaded successfully');
                // Explicitly typeset the MathML after MathJax loads
                MathJax.typesetPromise().then(() => {{
                    console.log('MathML typeset complete');
                }}).catch((err) => {{
                    console.error('MathML typeset error:', err);
                }});
            }}).catch((err) => {{
                console.error('MathJax failed to load:', err);
                document.body.innerHTML += '<p style="color:red;">MathJax failed to load: ' + err + '</p>';
            }});
        }}
    }}commit 
}};
</script>
<script src="{mathjax_src}"></script>
<style>
body {{
    background: white;
    font-size: 140%;
    padding: 20px;
    text-align: center;
    margin: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
}}
</style>
</head>
<body>
{mathml}
<script>
// Ensure MathJax processes the MathML after page load
if (window.MathJax && window.MathJax.typesetPromise) {{
    window.MathJax.typesetPromise().then(() => {{
        console.log('MathML typeset complete');
    }}).catch((err) => {{
        console.error('MathML typeset error:', err);
    }});
}} else {{
    // Wait for MathJax to load
    window.addEventListener('load', () => {{
        if (window.MathJax && window.MathJax.typesetPromise) {{
            window.MathJax.typesetPromise().then(() => {{
                console.log('MathML typeset complete (after load)');
            }}).catch((err) => {{
                console.error('MathML typeset error (after load):', err);
            }});
        }}
    }});
}}
</script>
</body>
</html>
"""
        self._render_html(html_code)

    def _render_tex(self, tex: str):
        """Render TeX with proper MathJax configuration for exact structure."""
        # Detect if running in PyInstaller bundle (EXE)
        import sys
        from pathlib import Path
        from PyQt6.QtCore import QUrl
        
        is_bundled = getattr(sys, 'frozen', False)
        mathjax_src = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"
        
        # Try to use local MathJax if bundled
        if is_bundled:
            base_path = Path(sys._MEIPASS)
            local_mathjax = base_path / 'mathjax' / 'tex-mml-chtml.js'
            if local_mathjax.exists():
                # Use QUrl.fromLocalFile() for proper local file access in QtWebEngine
                local_url = QUrl.fromLocalFile(str(local_mathjax))
                mathjax_src = local_url.toString()
                logger.info(f"[PreviewPanel] Using local MathJax from bundle for TeX: {mathjax_src}")
            else:
                logger.warning(f"[PreviewPanel] Local MathJax not found for TeX at {local_mathjax}, using CDN")
        
        # Escape HTML but preserve LaTeX
        safe_tex = html.escape(tex)
        html_code = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<script>
window.MathJax = {{
    tex: {{
        inlineMath: [['\\\\(', '\\\\)']],
        displayMath: [['\\\\[', '\\\\]']],
        processEscapes: true,
        processEnvironments: true
    }},
    options: {{
        ignoreHtmlClass: 'tex2jax_ignore',
        processHtmlClass: 'tex2jax_process'
    }}
}};
</script>
<script async src="{mathjax_src}"></script>
<style>
body {{
    background: white;
    font-size: 140%;
    padding: 20px;
    text-align: center;
    margin: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
}}
</style>
</head>
<body>
\\({safe_tex}\\)
</body>
</html>
"""
        self._render_html(html_code)

    def _render_html(self, html_content: str):
        try:
            # Check if equation_view is actually a QWebEngineView
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            if isinstance(self.equation_view, QWebEngineView):
                self.equation_view.setHtml(html_content)
                logger.debug("[PreviewPanel] Successfully set HTML content in WebEngine view")
            else:
                # It's a QLabel fallback - can't render HTML
                logger.warning("[PreviewPanel] equation_view is not QWebEngineView, it's %s", type(self.equation_view).__name__)
                self.equation_view.setText("Rendering error: WebEngine not available")
        except Exception as e:
            # Log the actual error for debugging
            logger.exception(f"[PreviewPanel] Failed to render HTML: {e}")
            # Fallback if QLabel or if setHtml failed
            try:
                if hasattr(self.equation_view, 'setText'):
                    self.equation_view.setText(f"Rendering error: {str(e)[:100]}")
                else:
                    logger.error("[PreviewPanel] equation_view has no setText method")
            except Exception as e2:
                logger.exception(f"[PreviewPanel] Failed to set error text: {e2}")
    
    # ============================================================================
    # OPENAI DIRECT CONVERSION
    # ============================================================================
    
    def _try_openai_mathml_conversion(self, mathml: str) -> dict | None:
        """
        DEPRECATED: This method is no longer used.
        
        According to the MANDATORY PIPELINE:
        - OpenAI is ONLY used for LaTeX semantic rewriting (inside StrictMathpixPipeline)
        - MathML MUST come from deterministic LaTeX→MathML compiler (latex2mathml) ONLY
        - OpenAI MUST NOT generate MathML directly
        - OpenAI MUST NOT fix MathML directly
        
        Use StrictMathpixPipeline.process_mathml() instead, which will:
        1. Detect corruption in MathML
        2. Reconstruct LaTeX from corrupted MathML (LaTeX semantic rewrite - allowed)
        3. Convert clean LaTeX → MathML using deterministic compiler
        
        This method is kept for backward compatibility but should never be called.
        """
        # Method is deprecated - should not be called
        # No warnings needed since it's not being called anymore
        return None
