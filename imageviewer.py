"""Image viewer widget for displaying and manipulating images.

This module provides a zoomable, pannable image viewer with support for
fit-to-window and 1:1 scaling, as well as mouse-based navigation.
"""

import os

os.environ["QT_LOGGING_RULES"] = "*.debug=false;qt.multimedia.*=false"

from PySide6.QtCore import QPointF, Qt, Slot
from PySide6.QtGui import (
    QPainter,
    QPalette,
    QPixmap,
    QTransform,
)
from PySide6.QtWidgets import (
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QSizePolicy,
    QWidget,
)


class ImageViewer(QWidget):
    """A widget for displaying and manipulating images with zoom and pan capabilities.

    Features include:
    - Fit-to-window scaling (normalSize method)
    - 1:1 scale viewing (fullSize method)
    - Mouse wheel zooming for precise control
    - Mouse dragging for panning around large images
    - Smooth rendering with anti-aliasing
    - Large scene area to handle very high resolution images
    """

    def __init__(self, parent=None):
        """Initialize the ImageViewer widget.

        Args:
            parent: Parent widget (optional).
        """
        super().__init__(parent)
        self._transform = QTransform()
        self._image_view = QGraphicsView()
        self._image_view.setInteractive(False)
        self._image_view.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self._image_view.setBackgroundRole(QPalette.ColorRole.Base)
        self._image_view.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored
        )
        self._image_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._image_view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._image_view.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._image_scene = QGraphicsScene()
        self._image_scene.setSceneRect(-16000, -16000, 32000, 32000)
        self._image_view.setScene(self._image_scene)

        # Enable scroll wheel zooming
        self._image_view.viewport().setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._image_view.viewport().installEventFilter(self)

        # Create a horizontal layout to hold the image
        images_layout = QHBoxLayout(self)
        images_layout.addWidget(self._image_view)
        self.setLayout(images_layout)

    def setImage(self, new_image):
        """Load and display an image.

        Args:
            new_image (str): Path to the image file to load.
        """
        self._image = QPixmap(new_image)
        if not self._image.isNull():
            # Clear previous scenes and add new pixmap items
            self._image_scene.clear()
            self._image_scene.addPixmap(self._image)

        self._image_view.setVisible(True)
        self.normalSize()

    @Slot()
    def normalSize(self):
        image_size = self._image.size()
        view_size = self._image_view.size()
        hscale = view_size.width() / image_size.width()
        vscale = view_size.height() / image_size.height()
        scale = min(hscale, vscale)
        self._transform = self._image_view.transform()
        self._transform.setMatrix(
            scale,
            0.0,
            0.0,
            0.0,
            scale,
            0.0,
            (view_size.width() - image_size.width() * scale) / 2,
            (view_size.height() - image_size.height() * scale) / 2,
            1.0,
        )
        self._image_view.setTransform(self._transform)

    def fullSize(self):
        image_size = self._image.size()
        view_size = self._image_view.size()
        scale = 1.0
        self._transform = self._image_view.transform()
        self._transform.setMatrix(
            scale,
            0.0,
            0.0,
            0.0,
            scale,
            0.0,
            (view_size.width() - image_size.width() * scale) / 2,
            (view_size.height() - image_size.height() * scale) / 2,
            1.0,
        )
        self._image_view.setTransform(self._transform)

    def scaleImage(self, zoom_factor, zoompos=None):
        if zoompos is None:
            zoompos = QPointF(
                self._image_view.size().width() * 0.5,
                self._image_view.size().height() * 0.5,
            )

        self._transform = self._image_view.transform()
        oldscale = self._transform.m11()
        cosx = (zoompos.x() - self._transform.dx()) / oldscale
        cosy = (zoompos.y() - self._transform.dy()) / oldscale
        self._transform.setMatrix(
            oldscale * zoom_factor,
            0.0,
            0.0,
            0.0,
            oldscale * zoom_factor,
            0.0,
            zoompos.x() - cosx * oldscale * zoom_factor,
            zoompos.y() - cosy * oldscale * zoom_factor,
            1.0,
        )
        self._image_view.setTransform(self._transform)

    def eventFilter(self, source, event):
        """Handle scroll wheel events for zooming and mouse dragging for panning"""
        if event.type() == event.Type.Wheel:
            scroll_event = event
            # Determine which view received the event
            if source != self._image_view.viewport():
                return super().eventFilter(source, event)

            # Calculate zoom factor based on scroll direction
            delta = scroll_event.angleDelta().y()
            if delta > 0:
                # Scroll up - zoom in
                zoom_factor = 1.1
            else:
                # Scroll down - zoom out
                zoom_factor = 0.9

            # Get the current transformation
            zoompos = event.position()
            self.scaleImage(zoom_factor, zoompos)
            return True
        elif event.type() == event.Type.MouseButtonPress:
            # Start dragging
            if source == self._image_view.viewport():
                self._drag_start_pos = event.position()
                return True
        elif event.type() == event.Type.MouseMove:
            # Handle dragging
            if hasattr(self, "_drag_start_pos"):
                delta = event.position() - self._drag_start_pos
                self._drag_start_pos = event.position()

                # Translate the view
                self._transform = self._image_view.transform()
                scale = self._transform.m11()
                self._transform.translate(delta.x() / scale, delta.y() / scale)
                self._image_view.setTransform(self._transform)
                return True
        elif event.type() == event.Type.MouseButtonRelease:
            # End dragging
            if hasattr(self, "_current_view"):
                delattr(self, "_drag_start_pos")
            return True

        return super().eventFilter(source, event)
