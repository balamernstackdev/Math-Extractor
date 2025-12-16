"""PDF viewer with image pages and overlay."""
from __future__ import annotations

from pathlib import Path
from typing import List

from PyQt6 import QtCore, QtGui, QtWidgets


class PDFViewer(QtWidgets.QGraphicsView):
    """Displays rendered PDF pages as images."""

    def __init__(self) -> None:
        scene = QtWidgets.QGraphicsScene()
        super().__init__(scene)
        self.scene = scene
        self.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        # Set normal cursor instead of hand cursor
        self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
        # Enable context menu
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)

        # Mathpix-like backdrop and minimalist scrollbars
        self.setStyleSheet("""
            QGraphicsView {
                background: #0f1115;
                border: none;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 12px;
                margin: 8px 0 8px 0;
            }
            QScrollBar::handle:vertical {
                background: #3a3f4a;
                min-height: 40px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background: #4c5362;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self.scene.setBackgroundBrush(QtGui.QColor("#0f1115"))

        # Layout tuning to mimic Mathpix' roomy column
        self._images: List[Path] = []
        self._page_items: List[QtWidgets.QGraphicsPixmapItem] = []
        self._last_layout_width = 0
        self._page_padding = 16  # white border padding around each page
        self._page_shadow_color = QtGui.QColor(0, 0, 0, 90)

    def load_pages(self, images: List[Path]) -> None:
        """Load page images into the scene with a Mathpix-inspired layout."""
        self.scene.clear()
        self._images = images
        self._page_items.clear()

        if not images:
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
            card_rect.setPen(QtGui.QPen(QtGui.QColor("#e7e9ed"), 1))
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

