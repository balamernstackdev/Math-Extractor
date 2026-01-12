"""PDF viewer with image pages and overlay."""
from __future__ import annotations

from pathlib import Path
from typing import List
import shutil

from PyQt6 import QtCore, QtGui, QtWidgets
from utils.image_utils import crop_image
from core.logger import logger
from ui.styles import Theme



class PDFViewer(QtWidgets.QGraphicsView):
    """Displays rendered PDF pages as images."""
    
    status_message = QtCore.pyqtSignal(str)

    def __init__(self) -> None:
        scene = QtWidgets.QGraphicsScene()
        super().__init__(scene)
        self.scene = scene
        self.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)

        # Mathpix-like backdrop and minimalist scrollbars
        self.setStyleSheet(f"""
            QGraphicsView {{
                background: {Theme.BACKGROUND};
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 12px;
                margin: 8px 0 8px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {Theme.BORDER};
                min-height: 40px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {Theme.SURFACE_HOVER};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        self.scene.setBackgroundBrush(QtGui.QColor(Theme.BACKGROUND))

        # Layout tuning to mimic Mathpix' roomy column
        self._images: List[Path] = []
        self._page_items: List[QtWidgets.QGraphicsPixmapItem] = []
        self._last_layout_width = 0
        self._page_padding = 16  # white border padding around each page
        self._page_shadow_color = QtGui.QColor(0, 0, 0, 90)
        
        # Initial empty state
        self._show_empty_state()

    def _show_empty_state(self):
        """Show empty state message."""
        self.scene.clear()
        text = self.scene.addText("No PDF loaded.\nClick 'Upload PDF' to start.")
        text.setDefaultTextColor(QtGui.QColor(Theme.TEXT_TERTIARY))
        font = text.font()
        font.setPointSize(16)
        text.setFont(font)
        
        # Center text (approximate)
        text.setPos(100, 100)  # Position will be adjusted in resizeEvent if needed but this is better than nothing

    def clear_pages(self) -> None:
        """Clear all pages from the viewer."""
        self.scene.clear()
        self._images = []
        self._page_items.clear()
        self._show_empty_state()
    
    def add_page(self, image_path: Path) -> None:
        """Add a single page incrementally to the viewer."""
        if image_path in self._images:
            return  # Already added
        
        self._images.append(image_path)
        page_num = len(self._images)
        
        # Get viewport dimensions
        viewport_width = self.viewport().width() if self.viewport().width() > 0 else 1200
        self._last_layout_width = viewport_width
        
        # Layout constants (same as load_pages)
        page_margin = 48
        page_spacing = 36
        column_width = max(600, min(viewport_width - (page_margin * 2), 1180))
        page_padding = self._page_padding
        
        # Calculate y_offset based on existing pages
        y_offset = page_margin
        for existing_item in self._page_items:
            pixmap = existing_item.pixmap()
            if pixmap:
                card_height = pixmap.height() + (page_padding * 2)
                y_offset += card_height + page_spacing
        
        # Load the new page
        pixmap = QtGui.QPixmap(str(image_path))
        if pixmap.isNull():
            return
        
        # Scale to fit the comfortable column width
        target_width = min(column_width, pixmap.width())
        scaled_pixmap = pixmap.scaledToWidth(
            target_width,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        
        # Card-like container around the page
        card_width = scaled_pixmap.width() + (page_padding * 2)
        card_height = scaled_pixmap.height() + (page_padding * 2)
        x_pos = page_margin + (column_width - card_width) // 2
        
        card_rect = QtWidgets.QGraphicsRectItem(0, 0, card_width, card_height)
        card_rect.setPos(x_pos, y_offset)
        card_rect.setBrush(QtGui.QBrush(QtGui.QColor("#ffffff")))
        card_rect.setPen(QtGui.QPen(QtGui.QColor("#e7e9ed"), 1))
        card_rect.setZValue(-2)
        shadow = QtWidgets.QGraphicsDropShadowEffect()
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 8)
        shadow.setColor(self._page_shadow_color)
        card_rect.setGraphicsEffect(shadow)
        self.scene.addItem(card_rect)
        
        # Rendered page image
        item = self.scene.addPixmap(scaled_pixmap)
        item.setPos(x_pos + page_padding, y_offset + page_padding)
        item.setData(0, str(image_path))
        item.setData(1, page_num)
        self._page_items.append(item)
        
        # Page badge
        badge_width = 86
        badge_height = 26
        badge_x = x_pos + (card_width - badge_width) / 2
        badge_y = y_offset + card_height - badge_height - 8
        badge_bg = QtWidgets.QGraphicsRectItem(0, 0, badge_width, badge_height)
        badge_bg.setBrush(QtGui.QBrush(QtGui.QColor(15, 17, 21, 220)))
        badge_bg.setPen(QtGui.QPen(QtCore.Qt.PenStyle.NoPen))
        badge_bg.setPos(badge_x, badge_y)
        badge_bg.setZValue(2)
        self.scene.addItem(badge_bg)
        
        badge_text = QtWidgets.QGraphicsSimpleTextItem(f"Page {page_num}")
        badge_text.setBrush(QtGui.QBrush(QtGui.QColor("#f3f4f6")))
        font = badge_text.font()
        font.setPointSize(9)
        font.setBold(True)
        badge_text.setFont(font)
        badge_text.setPos(badge_x + 14, badge_y + 6)
        badge_text.setZValue(3)
        self.scene.addItem(badge_text)
        
        # Update scene rect
        scene_width = max(viewport_width, card_width + (page_margin * 2))
        scene_height = y_offset + card_height + page_margin
        self.scene.setSceneRect(0, 0, scene_width, scene_height)
    
    # Signal emitting visible page indices
    visible_pages_changed = QtCore.pyqtSignal(list)

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        """Handle scroll events to track visible pages."""
        super().scrollContentsBy(dx, dy)
        self._check_visible_pages()
        
    def _check_visible_pages(self):
        """Determine which pages are currently visible and emit signal."""
        if not self._page_items:
            return
            
        viewport_rect = self.mapToScene(self.viewport().rect()).boundingRect()
        visible_indices = []
        
        for idx, item in enumerate(self._page_items):
            # Items are simple pixmaps or groups?
            # In load_pages, we added items and set their data
            # item is QGraphicsPixmapItem
            if item.sceneBoundingRect().intersects(viewport_rect):
                # Retrieve page num from data (stored as 1-based index)
                page_num = item.data(1)
                visible_indices.append(page_num)
        
        if visible_indices:
            self.visible_pages_changed.emit(visible_indices)

    def load_pages(self, images: List[Path]) -> None:
        """Load page images into the scene with a Mathpix-inspired layout."""
        self.scene.clear()
        self._images = images
        self._page_items.clear()

        if not images:
            self._show_empty_state()
            return

        # Get viewport dimensions
        viewport_width = self.viewport().width() if self.viewport().width() > 0 else 1200
        self._last_layout_width = viewport_width

        # Layout constants
        page_margin = 48  # outer margin from viewport edges
        page_spacing = 36  # vertical space between pages
        column_width = max(600, min(viewport_width - (page_margin * 2), 1180))
        page_padding = self._page_padding

        y_offset = page_margin  # Top margin
        max_width = 0

        for page_num, img_path in enumerate(images, start=1):
            # Create placeholder if image not loaded yet? 
            # Current logic requires images to exist.
            # But with Async worker, we might getting calls one by one.
            # The worker calls add_page incrementally.
            # load_pages is likely used less often now or for resize.
            
            pixmap = QtGui.QPixmap(str(img_path))
            if pixmap.isNull():
                continue

            # Scale to fit the comfortable column width
            target_width = min(column_width, pixmap.width())
            scaled_pixmap = pixmap.scaledToWidth(
                target_width,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )

            # Card-like container around each page
            card_width = scaled_pixmap.width() + (page_padding * 2)
            card_height = scaled_pixmap.height() + (page_padding * 2)
            x_pos = page_margin + (column_width - card_width) // 2

            card_rect = QtWidgets.QGraphicsRectItem(0, 0, card_width, card_height)
            card_rect.setPos(x_pos, y_offset)
            card_rect.setBrush(QtGui.QBrush(QtGui.QColor("#ffffff")))
            card_rect.setPen(QtGui.QPen(QtGui.QColor(Theme.BORDER), 1))
            card_rect.setZValue(-2)
            # Subtle depth similar to Mathpix page cards
            shadow = QtWidgets.QGraphicsDropShadowEffect()
            shadow.setBlurRadius(24)
            shadow.setOffset(0, 8)
            shadow.setColor(self._page_shadow_color)
            card_rect.setGraphicsEffect(shadow)
            self.scene.addItem(card_rect)

            # Rendered page image
            item = self.scene.addPixmap(scaled_pixmap)
            item.setPos(x_pos + page_padding, y_offset + page_padding)
            item.setData(0, str(img_path))  # Store image path in item
            item.setData(1, page_num)  # Store page number
            self._page_items.append(item)

            # Page badge centered near bottom
            badge_width = 86
            badge_height = 26
            badge_x = x_pos + (card_width - badge_width) / 2
            badge_y = y_offset + card_height - badge_height - 8
            badge_bg = QtWidgets.QGraphicsRectItem(0, 0, badge_width, badge_height)
            badge_bg.setBrush(QtGui.QBrush(QtGui.QColor(15, 17, 21, 220)))
            badge_bg.setPen(QtGui.QPen(QtCore.Qt.PenStyle.NoPen))
            badge_bg.setPos(badge_x, badge_y)
            badge_bg.setZValue(2)
            self.scene.addItem(badge_bg)

            badge_text = QtWidgets.QGraphicsSimpleTextItem(f"Page {page_num}")
            badge_text.setBrush(QtGui.QBrush(QtGui.QColor("#f3f4f6")))
            font = badge_text.font()
            font.setPointSize(9)
            font.setBold(True)
            badge_text.setFont(font)
            badge_text.setPos(badge_x + 14, badge_y + 6)
            badge_text.setZValue(3)
            self.scene.addItem(badge_text)

            max_width = max(max_width, card_width)
            y_offset += card_height + page_spacing

        # Set scene rect to include all pages with proper margins
        scene_width = max(viewport_width, max_width + (page_margin * 2))
        self.scene.setSceneRect(0, 0, scene_width, y_offset)

        # Reset transform - don't auto-fit, show pages at their natural size
        self.resetTransform()
        # Scroll to top to show first page
        self.ensureVisible(0, 0, 10, 10)
        
        # Trigger initial check
        QtCore.QTimer.singleShot(100, self._check_visible_pages)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        """Handle mouse wheel for zooming."""
        if event.modifiers() == QtCore.Qt.KeyboardModifier.ControlModifier:
            # Zoom with Ctrl + wheel
            scale_factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(scale_factor, scale_factor)
        else:
            # Normal scrolling
            super().wheelEvent(event)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        """Handle resize to adjust page layout."""
        super().resizeEvent(event)
        if self._images:
            current_width = self.viewport().width()
            # Reload layout only when width change is meaningful to avoid jitter
            if current_width > 0 and abs(current_width - self._last_layout_width) > 32:
                self.load_pages(self._images)

    @property
    def images(self) -> List[Path]:
        """Return current images."""
        return self._images

    def get_page_image_path(self, page_index: int) -> Path | None:
        """Get the image path for a specific page index (0-based)."""
        if 0 <= page_index < len(self._images):
            return self._images[page_index]
        return None

    def get_active_page_index(self) -> int:
        """Get the index of the currently most visible page (0-based)."""
        if not self._page_items:
            return 0
            
        visible_rect = self.mapToScene(self.viewport().rect()).boundingRect()
        center_y = visible_rect.center().y()
        
        # simple heuristic: page center closest to viewport center
        closest_page_idx = 0
        min_dist = float('inf')
        
        for idx, item in enumerate(self._page_items):
            # item is the image pixmap
            # page card background is z-value -2, likely relative to item pos or calculated
            # item.pos() is top-left of the image.
            # approximating page center using item bounding rect
            item_rect = item.sceneBoundingRect()
            item_center_y = item_rect.center().y()
            dist = abs(item_center_y - center_y)
            
            if dist < min_dist:
                min_dist = dist
                closest_page_idx = idx
                
        return closest_page_idx

    # Signal for actions (action_type, unique_data_dict)
    # unique_data_dict contains: image_path, bbox, etc.
    action_requested = QtCore.pyqtSignal(str, dict) 

    def show_context_menu(self, image_path: Path, bbox: dict, pos: QtCore.QPoint) -> None:
        """Show context menu when right-clicking on a region (triggered by Overlay).
        
        Args:
            image_path: Path to the full page image
            bbox: Bounding box dictionary
            pos: Screen position for the menu
        """
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {Theme.SURFACE};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 30px 8px 20px;
                border: none;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {Theme.ACCENT};
                color: white;
            }}
            QMenu::separator {{
                height: 1px;
                background: {Theme.BORDER};
                margin: 4px 0px;
            }}
            QMenu::section {{
                color: {Theme.TEXT_TERTIARY};
                padding: 4px 8px;
                font-size: 11px;
                background: transparent;
            }}
        """)
        
        # Data payload
        data = {
            "image_path": str(image_path),
            "bbox": bbox,
            "page_index": 0 # Placeholder, not strictly needed for copy actions
        }
        
        # COPY section
        menu.addSection("COPY")
        
        copy_latex = menu.addAction(r"\{\} LaTeX")
        copy_latex.triggered.connect(lambda: self.action_requested.emit("copy_latex", data))
        
        copy_mathml = menu.addAction("<ml> MathML")
        copy_mathml.triggered.connect(lambda: self.action_requested.emit("copy_mathml", data))
        
        copy_ascii = menu.addAction("AM AsciiMath")
        copy_ascii.triggered.connect(lambda: self.action_requested.emit("copy_asciimath", data))
        
        menu.addSeparator()
        
        # DOWNLOAD section
        menu.addSection("DOWNLOAD")
        
        download_action = menu.addAction("⬇️ Image")
        download_action.triggered.connect(lambda: self._handle_download_image(image_path, bbox))
        
        # Show menu at cursor position (pos is expected to be global/screen pos)
        menu.exec(pos)

    def _handle_download_image(self, image_path: Path, bbox: dict) -> None:
        """Crop and download the image region."""
        try:
            # 1. Ensure we have the crop
            self.status_message.emit("Preparing download...")
            QtWidgets.QApplication.processEvents()
            
            # This might re-crop, but that's safer than relying on external state. 
            # crop_image is relatively fast for single regions.
            crop_path = crop_image(image_path, bbox)
            
            # 2. Ask user where to save
            suggested_name = f"diagram_{bbox.get('id', 'region')}.png"
            
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Save Image",
                suggested_name,
                "PNG Images (*.png);;JPEG Images (*.jpg);;All Files (*.*)"
            )
            
            if file_path:
                shutil.copy2(crop_path, file_path)
                logger.info("Downloaded image to: %s", file_path)
                self.status_message.emit(f"✅ Image saved to {Path(file_path).name}")
            else:
                self.status_message.emit("Download cancelled")

        except Exception as exc:
            logger.exception("Failed to download image: %s", exc)
            self.status_message.emit("❌ Download failed")
            QtWidgets.QMessageBox.warning(
            )
            
    def scroll_to_page(self, page_index: int):
        """Scroll the viewport to the specified page index (0-based)."""
        if 0 <= page_index < len(self._page_items):
            item = self._page_items[page_index]
            # Ensure the top of the page is visible
            # item.scenePos() returns top-left in scene coords
            pos = item.scenePos()
            # 100 margin for context
            self.ensureVisible(pos.x(), pos.y(), item.pixmap().width(), 200, 10, 10)


