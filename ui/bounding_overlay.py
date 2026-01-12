"""Overlay for drawing bounding boxes and selection."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PyQt6 import QtCore, QtGui, QtWidgets


class ClickableFormulaBoxSignals(QtCore.QObject):
    """Signal holder for ClickableFormulaBox (QGraphicsItem can't have signals directly)."""
    formula_clicked = QtCore.pyqtSignal(Path, dict)
    formula_context_menu = QtCore.pyqtSignal(Path, dict, QtCore.QPoint)
    region_updated = QtCore.pyqtSignal(Path, dict) # Path, new_bbox


class ResizeHandle(QtWidgets.QGraphicsRectItem):
    """Small handles for resizing the bounding box."""
    def __init__(self, position_name: str, parent: ClickableFormulaBox):
        super().__init__(QtCore.QRectF(-4, -4, 8, 8), parent)
        self.position_name = position_name
        self.parent_box = parent
        self.setBrush(QtGui.QBrush(QtGui.QColor(0, 120, 212)))
        self.setPen(QtGui.QPen(QtCore.Qt.PenStyle.NoPen))
        self.setCursor(self._get_cursor())
        self.setAcceptHoverEvents(True)
        self.setVisible(False)
        self.setZValue(10)
        self._is_dragging = False

    def _get_cursor(self) -> QtCore.Qt.CursorShape:
        mapping = {
            "tl": QtCore.Qt.CursorShape.SizeFDiagCursor, "tr": QtCore.Qt.CursorShape.SizeBDiagCursor,
            "bl": QtCore.Qt.CursorShape.SizeBDiagCursor, "br": QtCore.Qt.CursorShape.SizeFDiagCursor,
            "tc": QtCore.Qt.CursorShape.SizeVerCursor, "bc": QtCore.Qt.CursorShape.SizeVerCursor,
            "ml": QtCore.Qt.CursorShape.SizeHorCursor, "mr": QtCore.Qt.CursorShape.SizeHorCursor
        }
        return mapping.get(self.position_name, QtCore.Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._is_dragging = True
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        if self._is_dragging:
            self.parent_box.handle_resize(self.position_name, event.pos())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        if self._is_dragging:
            self._is_dragging = False
            self.parent_box.finish_resize()
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class ClickableFormulaBox(QtWidgets.QGraphicsRectItem):
    """A clickable bounding box for formulas that shows context menu on right-click."""
    
    def __init__(self, image_path: Path, bbox: dict, parent: Optional[QtWidgets.QGraphicsItem] = None) -> None:
        super().__init__(parent)
        # Create signal holder (QObject for signals)
        self.signals = ClickableFormulaBoxSignals()
        self.image_path = image_path
        self.bbox = bbox
        self.setRect(bbox["x"], bbox["y"], bbox["w"], bbox["h"])
        # Make it transparent but clickable
        self.setPen(QtGui.QPen(QtCore.Qt.PenStyle.NoPen))
        self.setBrush(QtGui.QBrush(QtCore.Qt.BrushStyle.NoBrush))
        # Make it accept hover and mouse events
        self.setAcceptHoverEvents(True)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        # Store original bbox for coordinate conversion
        self._original_bbox = bbox.copy()
        # Hover menu dot (⋯) to trigger context menu like Mathpix
        self.menu_dot = QtWidgets.QGraphicsSimpleTextItem("⋯", self)
        self.menu_dot.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255)))
        # Position near top-right; adjust in resize hook
        self._position_menu_dot()
        self.menu_dot.setVisible(False)
        # Slight background for readability
        self.menu_bg = QtWidgets.QGraphicsRectItem(self)
        self.menu_bg.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0, 160)))
        self.menu_bg.setPen(QtGui.QPen(QtCore.Qt.PenStyle.NoPen))
        self.menu_bg.setVisible(False)
        self._update_menu_bg()
        self.menu_dot.setZValue(2)
        self.menu_bg.setZValue(1)
        
        # Create handles
        self.handles = {}
        for pos in ["tl", "tc", "tr", "ml", "mr", "bl", "bc", "br"]:
            self.handles[pos] = ResizeHandle(pos, self)
        self._update_handles_pos()

    def _update_handles_pos(self) -> None:
        """Position all handles based on current rect."""
        r = self.rect()
        self.handles["tl"].setPos(r.topLeft())
        self.handles["tc"].setPos(r.left() + r.width()/2, r.top())
        self.handles["tr"].setPos(r.topRight())
        self.handles["ml"].setPos(r.left(), r.top() + r.height()/2)
        self.handles["mr"].setPos(r.right(), r.top() + r.height()/2)
        self.handles["bl"].setPos(r.bottomLeft())
        self.handles["bc"].setPos(r.left() + r.width()/2, r.bottom())
        self.handles["br"].setPos(r.bottomRight())

    def handle_resize(self, pos: str, delta: QtCore.QPointF) -> None:
        """Update rect based on handle movement."""
        r = self.rect()
        # delta is in local coordinate space (relative to handle's (0,0) which is its center)
        # But we need to move the edge of the rect.
        # Simple implementation: move the edge to the scene mouse position
        scene_pos = self.handles[pos].mapToScene(delta)
        local_pos = self.mapFromScene(scene_pos)
        
        if "t" in pos: r.setTop(local_pos.y())
        if "b" in pos: r.setBottom(local_pos.y())
        if "l" in pos: r.setLeft(local_pos.x())
        if "r" in pos: r.setRight(local_pos.x())
        
        # Ensure minimum size
        if r.width() < 10: r.setWidth(10)
        if r.height() < 10: r.setHeight(10)
        
        self.setRect(r)
        self._update_handles_pos()
        self._position_menu_dot()
        self._update_menu_bg()

    def finish_resize(self) -> None:
        """Finalize resize and notify components to re-run OCR."""
        r = self.rect()
        # Find the pixmap item this box belongs to to get scaling
        # (This is a bit tricky since we don't store the pixmap item directly here)
        # But BoundingOverlay can do it.
        # For now, just emit the new local coords, and let BoundingOverlay convert them.
        self.signals.region_updated.emit(self.image_path, {
            "scene_rect": r, # Pass the scene rect for conversion
            "original_bbox": self._original_bbox
        })

    def _position_menu_dot(self) -> None:
        """Position the menu dot at the top-right corner of the rect."""
        r = self.rect()
        self.menu_dot.setPos(r.right() - 14, r.top() + 2)
    
    def _update_menu_bg(self) -> None:
        """Resize background behind the dot."""
        dot_rect = self.menu_dot.boundingRect().translated(self.menu_dot.pos())
        padding = 4
        bg_rect = QtCore.QRectF(
            dot_rect.left() - padding,
            dot_rect.top() - padding / 2,
            dot_rect.width() + padding * 2,
            dot_rect.height() + padding
        )
        self.menu_bg.setRect(bg_rect)
    
    def hoverEnterEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        """Show highlight and handles on hover."""
        self.setPen(QtGui.QPen(QtGui.QColor(0, 120, 212), 2, QtCore.Qt.PenStyle.DashLine))
        self.setBrush(QtGui.QBrush(QtGui.QColor(0, 120, 212, 20)))
        # Show menu dot and handles
        self.menu_dot.setVisible(True)
        self.menu_bg.setVisible(True)
        if hasattr(self, 'handles'):
            for h in self.handles.values():
                h.setVisible(True)
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        """Remove highlight and handles on leave."""
        self.setPen(QtGui.QPen(QtCore.Qt.PenStyle.NoPen))
        self.setBrush(QtGui.QBrush(QtCore.Qt.BrushStyle.NoBrush))
        self.menu_dot.setVisible(False)
        self.menu_bg.setVisible(False)
        if hasattr(self, 'handles'):
            for h in self.handles.values():
                h.setVisible(False)
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """Handle mouse clicks on formula."""
        # Check if click was on the menu dot
        if self.menu_dot.isVisible():
            # Convert to local coordinates to test hit
            if self.menu_dot.boundingRect().contains(event.pos() - self.menu_dot.pos()):
                # Emit context menu at screen position
                self.signals.formula_context_menu.emit(self.image_path, self._original_bbox, event.screenPos())
                return
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            # Left click - select formula
            self.signals.formula_clicked.emit(self.image_path, self._original_bbox)
        elif event.button() == QtCore.Qt.MouseButton.RightButton:
            # Right click - show context menu
            scene_pos = event.screenPos()
            self.signals.formula_context_menu.emit(self.image_path, self._original_bbox, scene_pos)
        super().mousePressEvent(event)


class BoundingOverlay(QtCore.QObject):
    """Handles bounding box drawing and region selection."""

    region_selected = QtCore.pyqtSignal(Path, dict)
    selection_started = QtCore.pyqtSignal() # Emit when user starts dragging a new box
    selection_changed = QtCore.pyqtSignal(QtCore.QRectF)  # Emit selection rectangle for preview
    formula_selected = QtCore.pyqtSignal(Path, dict)  # Emit when formula is clicked
    region_updated = QtCore.pyqtSignal(Path, dict)  # Emit when formula region is manually updated
    show_context_menu = QtCore.pyqtSignal(Path, dict, QtCore.QPoint)  # Emit for context menu

    def __init__(self, scene: QtWidgets.QGraphicsScene) -> None:
        super().__init__(scene)
        self.scene = scene
        self.box_items: List[QtWidgets.QGraphicsRectItem] = []
        self.formula_boxes: List[ClickableFormulaBox] = []  # Clickable formula boxes
        self.start_pos: QtCore.QPointF | None = None
        self.selection_rect: QtWidgets.QGraphicsRectItem | None = None
        self.image_paths: dict[QtWidgets.QGraphicsPixmapItem, Path] = {}  # Map pixmap items to image paths
        scene.installEventFilter(self)

    def draw_boxes(self, image_path: Path, boxes: List[dict[str, int | str]], show_boxes: bool = False) -> None:
        """Draw bounding boxes on the scene.
        
        Args:
            image_path: Path to the image
            boxes: List of bounding box dictionaries
            show_boxes: If True, show boxes (default False to avoid clutter)
        """
        # Clear existing boxes
        self.clear_boxes()
        
        if not show_boxes:
            return
        
        for box in boxes:
            rect = QtWidgets.QGraphicsRectItem(
                box["x"], box["y"], box["w"], box["h"]
            )
            # Use subtle blue color instead of red, with low opacity
            rect.setPen(QtGui.QPen(QtGui.QColor(0, 120, 212), 1, QtCore.Qt.PenStyle.DashLine))
            rect.setBrush(QtGui.QBrush(QtGui.QColor(0, 120, 212, 10)))  # Very transparent
            rect.setData(0, str(image_path))
            rect.setData(1, box)
            self.scene.addItem(rect)
            self.box_items.append(rect)
            
            # Optionally show text label if available
            if "text" in box and box["text"]:
                text_item = QtWidgets.QGraphicsTextItem(box["text"])
                text_item.setPos(box["x"], box["y"] - 15)
                text_item.setDefaultTextColor(QtGui.QColor(0, 120, 212))
                font = text_item.font()
                font.setPointSize(8)
                text_item.setFont(font)
                self.scene.addItem(text_item)

    def clear_boxes(self) -> None:
        """Clear all bounding boxes from the scene."""
        for item in self.box_items:
            self.scene.removeItem(item)
        self.box_items.clear()
        # Clear formula boxes
        for box in self.formula_boxes:
            self.scene.removeItem(box)
        self.formula_boxes.clear()
    
    def draw_formula_boxes(self, image_path: Path, formulas: List[dict[str, int | str]], 
                          pixmap_item: QtWidgets.QGraphicsPixmapItem) -> None:
        """Draw clickable formula boxes on the scene.
        
        Args:
            image_path: Path to the image
            formulas: List of formula bounding boxes (in image coordinates)
            pixmap_item: The pixmap item to position boxes relative to
        """
        # Clear existing formula boxes
        for box in self.formula_boxes:
            self.scene.removeItem(box)
        self.formula_boxes.clear()
        
        if not formulas:
            return
        
        # Get pixmap item position and scale
        item_pos = pixmap_item.pos()
        item_rect = pixmap_item.boundingRect()
        pixmap = pixmap_item.pixmap()
        
        if pixmap.isNull():
            return
        
        # Calculate scale factors (scene size / original image size)
        scale_x = item_rect.width() / pixmap.width()
        scale_y = item_rect.height() / pixmap.height()
        
        for formula in formulas:
            # Convert image coordinates to scene coordinates
            img_x = int(formula["x"])
            img_y = int(formula["y"])
            img_w = int(formula["w"])
            img_h = int(formula["h"])
            
            # Scale and position relative to pixmap item position
            scene_x = item_pos.x() + img_x * scale_x
            scene_y = item_pos.y() + img_y * scale_y
            scene_w = img_w * scale_x
            scene_h = img_h * scale_y
            
            # Create clickable box with original bbox (for coordinate conversion)
            box = ClickableFormulaBox(image_path, formula)
            box.setRect(scene_x, scene_y, scene_w, scene_h)
            box._position_menu_dot()  # adjust dot for scaled rect
            box._update_menu_bg()
            
            # Connect signals (use signals object since QGraphicsItem can't have signals directly)
            box.signals.formula_clicked.connect(self.formula_selected.emit)
            box.signals.formula_context_menu.connect(self.show_context_menu.emit)
            box.signals.region_updated.connect(lambda p, d: self._handle_region_updated(p, d, pixmap_item))
            
            # Set z-value to be above the pixmap but below selection rectangles
            box.setZValue(1)
            
            self.scene.addItem(box)
            self.formula_boxes.append(box)

    def _handle_region_updated(self, image_path: Path, data: dict, pixmap_item: QtWidgets.QGraphicsPixmapItem) -> None:
        """Convert scene rect back to image bbox and emit signal."""
        scene_rect = data["scene_rect"]
        
        # Get pixmap item position and scale
        item_pos = pixmap_item.pos()
        item_rect = pixmap_item.boundingRect()
        pixmap = pixmap_item.pixmap()
        
        if pixmap.isNull():
            return
            
        # Scaling factor: scene size / original image size
        scale_x = item_rect.width() / pixmap.width()
        scale_y = item_rect.height() / pixmap.height()
        
        # Invert the conversion: (scene - item_pos) / scale
        img_x = (scene_rect.x() - item_pos.x()) / scale_x
        img_y = (scene_rect.y() - item_pos.y()) / scale_y
        img_w = scene_rect.width() / scale_x
        img_h = scene_rect.height() / scale_y
        
        new_bbox = {
            "x": int(img_x),
            "y": int(img_y),
            "w": int(img_w),
            "h": int(img_h)
        }
        
        # Clamp to image boundaries
        new_bbox["x"] = max(0, new_bbox["x"])
        new_bbox["y"] = max(0, new_bbox["y"])
        new_bbox["w"] = min(pixmap.width() - new_bbox["x"], new_bbox["w"])
        new_bbox["h"] = min(pixmap.height() - new_bbox["y"], new_bbox["h"])
        
        logger.info(f"[BoundingOverlay] Region updated for {image_path.name}: {new_bbox}")
        self.region_updated.emit(image_path, new_bbox)

    def _clear_selection_rect(self) -> None:
        """Remove the selection rectangle from the scene."""
        if self.selection_rect:
            try:
                # Check if item still exists in scene before removing
                if self.selection_rect.scene() is not None:
                    self.scene.removeItem(self.selection_rect)
            except RuntimeError:
                # Item has already been deleted by Qt, just clear the reference
                pass
            finally:
                self.selection_rect = None

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802
        """Handle mouse events for selection."""
        from core.logger import logger
        
        if event.type() == QtCore.QEvent.Type.GraphicsSceneMousePress:
            self.start_pos = event.scenePos()
            self._clear_selection_rect()
            self.clear_boxes() # Clear old OCR boxes when starting new selection
            self.selection_started.emit()
            logger.debug("Selection started at: %s", self.start_pos)
        elif event.type() == QtCore.QEvent.Type.GraphicsSceneMouseMove and self.start_pos:
            # Draw selection rectangle while dragging
            end_pos = event.scenePos()
            x1, y1 = self.start_pos.x(), self.start_pos.y()
            x2, y2 = end_pos.x(), end_pos.y()
            x, y = min(x1, x2), min(y1, y2)
            w, h = abs(x2 - x1), abs(y2 - y1)
            
            if self.selection_rect:
                try:
                    # Check if item still exists in scene before removing
                    if self.selection_rect.scene() is not None:
                        self.scene.removeItem(self.selection_rect)
                except RuntimeError:
                    # Item has already been deleted by Qt, just clear the reference
                    self.selection_rect = None
            
            self.selection_rect = QtWidgets.QGraphicsRectItem(x, y, w, h)
            self.selection_rect.setPen(QtGui.QPen(QtGui.QColor(0, 120, 212), 2, QtCore.Qt.PenStyle.DashLine))
            self.selection_rect.setBrush(QtGui.QBrush(QtGui.QColor(0, 120, 212, 30)))
            self.scene.addItem(self.selection_rect)
            
            # Emit selection changed for preview
            self.selection_changed.emit(QtCore.QRectF(x, y, w, h))
        elif event.type() == QtCore.QEvent.Type.GraphicsSceneMouseRelease and self.start_pos:
            end_pos = event.scenePos()
            x1, y1 = self.start_pos.x(), self.start_pos.y()
            x2, y2 = end_pos.x(), end_pos.y()
            x, y = min(x1, x2), min(y1, y2)
            w, h = abs(x2 - x1), abs(y2 - y1)
            
            # Only process if selection is large enough
            if w > 10 and h > 10:
                # Find which page image the selection is on
                image_path, bbox = self._find_image_and_convert_coords(x, y, w, h)
                if image_path and bbox:
                    from core.logger import logger
                    logger.info("Selection completed: %s, bbox: %s (scene: %.1f,%.1f %.1fx%.1f)", 
                              image_path.name, bbox, x, y, w, h)
                    self.region_selected.emit(image_path, bbox)
                else:
                    from core.logger import logger
                    logger.warning("Could not find image for selection at scene (%s, %s) size %.1fx%.1f", x, y, w, h)
            
            self._clear_selection_rect()
            self.start_pos = None
        return super().eventFilter(obj, event)
    
    def _find_image_and_convert_coords(self, scene_x: float, scene_y: float, scene_w: float, scene_h: float) -> tuple[Path | None, dict]:
        """Find the image under the selection and convert scene coordinates to image coordinates."""
        # Calculate selection center - this is more reliable than checking intersection
        selection_center_x = scene_x + scene_w / 2
        selection_center_y = scene_y + scene_h / 2
        selection_rect = QtCore.QRectF(scene_x, scene_y, scene_w, scene_h)
        
        # Find all images that intersect with the selection
        candidate_items = []
        for item in self.scene.items():
            if isinstance(item, QtWidgets.QGraphicsPixmapItem):
                item_rect = item.boundingRect()
                item_pos = item.pos()
                item_global_rect = QtCore.QRectF(
                    item_pos.x(), item_pos.y(), item_rect.width(), item_rect.height()
                )
                
                # Check if selection center is inside this image (most reliable)
                if item_global_rect.contains(selection_center_x, selection_center_y):
                    # Get image path
                    image_path = self.image_paths.get(item)
                    if not image_path:
                        image_path_str = item.data(0)
                        if image_path_str:
                            image_path = Path(image_path_str)
                    
                    if image_path and image_path.exists():
                        # Calculate overlap area to find the best match
                        intersection = item_global_rect.intersected(selection_rect)
                        overlap_area = intersection.width() * intersection.height()
                        candidate_items.append((item, image_path, item_pos, item_rect, overlap_area))
        
        # If no image contains the center, find the one with the most overlap
        if not candidate_items:
            for item in self.scene.items():
                if isinstance(item, QtWidgets.QGraphicsPixmapItem):
                    item_rect = item.boundingRect()
                    item_pos = item.pos()
                    item_global_rect = QtCore.QRectF(
                        item_pos.x(), item_pos.y(), item_rect.width(), item_rect.height()
                    )
                    
                    if item_global_rect.intersects(selection_rect):
                        image_path = self.image_paths.get(item)
                        if not image_path:
                            image_path_str = item.data(0)
                            if image_path_str:
                                image_path = Path(image_path_str)
                        
                        if image_path and image_path.exists():
                            intersection = item_global_rect.intersected(selection_rect)
                            overlap_area = intersection.width() * intersection.height()
                            candidate_items.append((item, image_path, item_pos, item_rect, overlap_area))
        
        # Select the image with the most overlap (or first if center is inside)
        if candidate_items:
            # Sort by overlap area (descending), then by distance from center
            candidate_items.sort(key=lambda x: (
                -x[4],  # Negative for descending overlap
                abs(x[2].x() + x[3].width()/2 - selection_center_x) + 
                abs(x[2].y() + x[3].height()/2 - selection_center_y)  # Distance from center
            ))
            
            item, image_path, item_pos, item_rect, _ = candidate_items[0]
            
            # Convert scene coordinates to image coordinates
            pixmap = item.pixmap()
            if pixmap.isNull():
                return None, {}
            
            # Get the original pixmap dimensions (before scaling)
            original_pixmap = QtGui.QPixmap(str(image_path))
            if original_pixmap.isNull():
                return None, {}
            
            original_width = original_pixmap.width()
            original_height = original_pixmap.height()
            
            # Calculate scale factors: how much the displayed image is scaled from original
            # item_rect is the displayed size, original_pixmap is the actual image size
            scale_x = original_width / item_rect.width() if item_rect.width() > 0 else 1.0
            scale_y = original_height / item_rect.height() if item_rect.height() > 0 else 1.0
            
            # Convert relative to image position in scene
            rel_x = scene_x - item_pos.x()
            rel_y = scene_y - item_pos.y()
            
            # Convert to original image coordinates
            img_x = int(rel_x * scale_x)
            img_y = int(rel_y * scale_y)
            img_w = int(scene_w * scale_x)
            img_h = int(scene_h * scale_y)
            
            # Clamp to image bounds
            img_x = max(0, min(img_x, original_width - 1))
            img_y = max(0, min(img_y, original_height - 1))
            img_w = min(img_w, original_width - img_x)
            img_h = min(img_h, original_height - img_y)
            
            # Ensure minimum size
            if img_w < 5:
                img_w = 5
            if img_h < 5:
                img_h = 5
            
            # Log for debugging
            from core.logger import logger
            logger.debug("Coordinate conversion: scene(%.1f,%.1f %.1fx%.1f) -> image(%d,%d %dx%d) on %s", 
                        scene_x, scene_y, scene_w, scene_h, img_x, img_y, img_w, img_h, image_path.name)
            
            bbox = {
                "x": img_x,
                "y": img_y,
                "w": img_w,
                "h": img_h,
                "id": "manual"
            }
            return image_path, bbox
        
        return None, {}

