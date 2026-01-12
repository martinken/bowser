"""Image gallery widget for displaying thumbnails of images in a folder."""

import os

from PySide6.QtCore import QMimeData, QSize, Qt, Signal
from PySide6.QtGui import QPixmap, QDrag
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class DragLabel(QLabel):
    """A custom QLabel that supports drag and drop operations."""

    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.setAcceptDrops(True)

    def mouseMoveEvent(self, event):
        """Handle mouse move events to initiate drag operations."""
        if event.buttons() != Qt.MouseButton.LeftButton:
            return
        
        # Check if the mouse has moved enough to start dragging
        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return
        
        # Create drag object
        drag = QDrag(self)
        
        # Create mime data with the file path
        mime_data = QMimeData()
        mime_data.setText(self.image_path)
        mime_data.setUrls([self.image_path])
        
        drag.setMimeData(mime_data)
        
        # Create a transparent pixmap for the drag cursor
        drag.setPixmap(QPixmap())
        
        drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)

    def mousePressEvent(self, event):
        """Handle mouse press events to store the drag start position."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.pos()
        super().mousePressEvent(event)


class ImageGallery(QWidget):
    """A widget that displays thumbnails of images in a folder."""

    # Signal emitted when a thumbnail is clicked
    thumbnailClicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thumbnail_widgets = []
        self._image_paths = []
        self._current_columns = -1
        self._last_thumbnail_clicked_index = 0
        self._thumbnail_size = QSize(192, 192)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Scroll area for thumbnails
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        # Widget to hold the grid layout
        self._content_widget = QWidget()
        self._content_layout = QGridLayout(self._content_widget)
        self._content_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self._content_layout.setSpacing(3)
        self._content_layout.setContentsMargins(3, 3, 3, 3)

        self._scroll_area.setWidget(self._content_widget)
        main_layout.addWidget(self._scroll_area)

    def load_images_from_folder(self, folder_path):
        """Load and display images from the specified folder.

        Args:
            folder_path (str): Path to the folder containing images.
        """
        self._image_paths = []

        # Clear existing thumbnails
        self._clear_thumbnails()

        # Get all image files from the folder
        supported_extensions = [
            ".jpg",
            ".jpeg",
            ".png",
            ".bmp",
            ".gif",
            ".tiff",
            ".webp",
            ".mp4",
            ".mov",
        ]

        for file_name in os.listdir(folder_path):
            # exclude .swarmpreview images
            if ".swarmpreview.jpg" not in file_name:
                file_path = os.path.join(folder_path, file_name)
                if os.path.isfile(file_path):
                    ext = os.path.splitext(file_name)[1].lower()
                    if ext in supported_extensions:
                        self._image_paths.append(file_path)

        # Display new thumbnails
        self._clear_thumbnails()
        self._build_thumbnails()
        self._display_thumbnails()

    def _get_target_number_of_columns(self):
        # Calculate grid layout based on available width
        # Get the width of the content widget
        content_width = self._content_widget.width()
        if content_width <= 0:
            # If width is not yet available, use a default
            columns = 5
        else:
            # Calculate how many columns fit based on thumbnail size and spacing
            # Each thumbnail takes: thumbnail_width + spacing
            # We subtract the left and right margins (3 pixels each)
            available_width = content_width - 6  # margins
            spacing = self._content_layout.spacing()
            thumbnail_width = self._thumbnail_size.width()

            # Calculate number of columns that fit
            columns = max(1, available_width // (thumbnail_width + spacing))
        return columns

    def _build_thumbnails(self):
        if not self._image_paths:
            return

        # Clear existing thumbnails and recreate with new layout
        self._clear_thumbnails()
        for i, image_path in enumerate(self._image_paths):
            # Create thumbnail widget
            self._thumbnail_widgets.append(self._create_thumbnail_widget(image_path, i))

    def _display_thumbnails(self):
        """Display thumbnails for all loaded images."""
        if not self._image_paths:
            return

        columns = self._get_target_number_of_columns()
        self._current_columns = columns

        for i, thumbnail_widget in enumerate(self._thumbnail_widgets):
            row = i // columns
            col = i % columns
            self._content_layout.addWidget(thumbnail_widget, row, col)

    def _create_thumbnail_widget(self, image_path, index):
        """Create a widget for displaying a thumbnail.

        Args:
            image_path (str): Path to the image file.

        Returns:
            QWidget: A widget containing the thumbnail.
        """
        # Create label for thumbnail with drag support
        thumbnail_label = DragLabel(image_path)
        thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumbnail_label.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        thumbnail_label.setMinimumSize(self._thumbnail_size)
        thumbnail_label.setMaximumSize(self._thumbnail_size)

        # Load and display thumbnail
        thumbnail_path = image_path
        # if there is a swarmpreview for the file then use it for the pixmap
        swarm_preview_path = os.path.splitext(image_path)[0] + ".swarmpreview.jpg"
        if os.path.exists(swarm_preview_path):
            thumbnail_path = swarm_preview_path
        pixmap = QPixmap(thumbnail_path)
        if not pixmap.isNull():
            # Scale pixmap to thumbnail size while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(
                self._thumbnail_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            thumbnail_label.setPixmap(scaled_pixmap)
        else:
            thumbnail_label.setText("Image")
            thumbnail_label.setStyleSheet("color: gray;")

        # Change outline color to blue if the file is a video (mp4 or mov)
        video_extensions = [".mp4", ".mov"]
        file_ext = os.path.splitext(image_path)[1].lower()
        if file_ext in video_extensions:
            thumbnail_label.setStyleSheet("border: 2px solid #1E90FF;")

        # Make thumbnail clickable
        thumbnail_label.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Store the index for click handling
        thumbnail_label.thumbnail_index = index
        
        # Override mousePressEvent to handle both click and drag initialization
        def handle_mouse_press(event):
            # Initialize drag start position for drag functionality
            thumbnail_label.drag_start_position = event.pos()
            
            # Handle click functionality
            if event.button() == Qt.MouseButton.LeftButton:
                self._on_thumbnail_clicked(index)
        
        thumbnail_label.mousePressEvent = handle_mouse_press

        return thumbnail_label

    def _on_thumbnail_clicked(self, index):
        """Handle thumbnail click event.

        Args:
            image_path (str): Path to the clicked image file.
        """
        self._last_thumbnail_clicked_index = index
        # Emit signal with the image path
        self.thumbnailClicked.emit(self._image_paths[index])

    def nextThumbnail(self):
        """Navigate to the next thumbnail in the gallery.

        Returns:
            bool: True if navigation was successful, False if already at the last thumbnail.
        """
        if not self._image_paths:
            return False

        # Move to next thumbnail (wrap around to first if at end)
        new_index = (self._last_thumbnail_clicked_index + 1) % len(self._image_paths)

        # Only emit signal if index changed
        if new_index != self._last_thumbnail_clicked_index:
            self._on_thumbnail_clicked(new_index)
            return True

        return False

    def previousThumbnail(self):
        """Navigate to the previous thumbnail in the gallery.

        Returns:
            bool: True if navigation was successful, False if already at the first thumbnail.
        """
        if not self._image_paths:
            return False

        # Move to previous thumbnail (wrap around to last if at beginning)
        new_index = (self._last_thumbnail_clicked_index - 1) % len(self._image_paths)

        # Only emit signal if index changed
        if new_index != self._last_thumbnail_clicked_index:
            self._on_thumbnail_clicked(new_index)
            return True

        return False

    def _clear_thumbnails(self):
        """Clear all thumbnails from the gallery."""
        # Remove all widgets from the grid layout
        self._thumbnail_widgets = []
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._current_columns = -1

    def resizeEvent(self, event):
        """Handle resize events to adjust the thumbnail layout.

        Args:
            event: QResizeEvent
        """
        # Call the parent class implementation
        super().resizeEvent(event)

        # if the number of columns changed then adjust the widgets
        columns = self._get_target_number_of_columns()
        if columns != self._current_columns and self._image_paths:
            self._display_thumbnails()

    def get_image_paths(self):
        """Get the list of image paths currently loaded.

        Returns:
            list: List of image file paths.
        """
        return self._image_paths.copy()

    def set_thumbnail_size(self, size):
        """Set the size for thumbnails.

        Args:
            size (QSize): The size for thumbnails.
        """
        self._thumbnail_size = size
        # Reload thumbnails with new size
        if self._image_paths:
            self.load_images_from_folder(os.path.dirname(self._image_paths[0]))
