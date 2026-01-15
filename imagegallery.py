"""Image gallery widget for displaying thumbnails of images in a folder."""

import multiprocessing
import os
import threading
from multiprocessing import Pool

from PySide6.QtCore import (
    QMimeData,
    QSize,
    Qt,
    QUrl,
    Signal,
)
from PySide6.QtGui import QDrag, QPixmap
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

    def __init__(self, index, parent=None):
        super().__init__(parent)
        self._index = index
        self.setAcceptDrops(True)
        self._is_video = False
        self._marked = False
        self._highlighted = False
        self._update_border()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        # Make thumbnail clickable
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_highlighted(self, value):
        self._highlighted = value
        self._update_border()

    def set_image_path(self, image_path):
        video_extensions = [".mp4", ".mov"]
        # set _is_video if the file is a video (mp4 or mov)
        file_ext = os.path.splitext(image_path)[1].lower()
        if file_ext in video_extensions:
            self._is_video = True
        else:
            self._is_video = False
        self._image_path = image_path
        self._update_border()

    def _update_border(self):
        if self._marked:
            # Add a red checkmark overlay or change background
            self.setStyleSheet(
                "border: 2px solid #FF0000; background: rgba(255, 0, 0, 30);"
            )
            return
        if self._highlighted:
            if self._is_video:
                self.setStyleSheet("border: 2px solid #C0A0FF;")
            else:
                self.setStyleSheet("border: 2px solid #C0FFA0;")
        else:
            if self._is_video:
                self.setStyleSheet("border: 2px solid #603080;")
            else:
                self.setStyleSheet("border: 2px solid #608030;")

    def set_marked(self, value):
        """Mark or unmark the thumbnail.

        Args:
            value (bool): True to mark the thumbnail, False to unmark it.
        """
        self._marked = value
        self._update_border()

    def mouseMoveEvent(self, event):
        """Handle mouse move events to initiate drag operations."""
        if event.buttons() != Qt.MouseButton.LeftButton:
            return

        # Check if the mouse has moved enough to start dragging
        if (
            event.pos() - self.drag_start_position
        ).manhattanLength() < QApplication.startDragDistance():
            return

        # Create drag object
        drag = QDrag(self)

        # Create mime data with the file path
        mime_data = QMimeData()
        url = QUrl.fromLocalFile(self._image_path)
        mime_data.setUrls([url])
        drag.setMimeData(mime_data)

        # Create a transparent pixmap for the drag cursor
        drag.setPixmap(QPixmap())

        drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)

    def mousePressEvent(self, event):
        """Handle mouse press events to store the drag start position."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.pos()
        super().mousePressEvent(event)


def load_image_worker(image_path, thumbnail_size, index):
    """Worker function for loading images in a separate process.

    Args:
        image_path (str): Path to the image file
        thumbnail_size (tuple): Size of the thumbnail (width, height)

    Returns:
        tuple: (image_path, pixmap_data, size) where pixmap_data is PIL.Image or None
    """
    try:
        from PIL import Image

        # Load the image
        thumbnail_path = image_path
        # if there is a swarmpreview for the file then use it for the pixmap
        swarm_preview_path = os.path.splitext(image_path)[0] + ".swarmpreview.jpg"
        if os.path.exists(swarm_preview_path):
            thumbnail_path = swarm_preview_path

        image = Image.open(thumbnail_path)

        if image:
            image.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)
            return (image_path, image.convert("RGB"), image.size, index)
        else:
            return (image_path, None, index)
    except Exception as e:
        print(f"Error loading image {image_path}: {e}")
        return (image_path, None, [0, 0], index)


class ImageGallery(QWidget):
    """A widget that displays thumbnails of images in a folder."""

    # Signal emitted when a thumbnail is clicked
    thumbnailClicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None
        self._request_load_cancel = False
        self._thumbnail_widgets = []
        self._image_paths = []
        self._current_columns = -1
        self._last_thumbnail_clicked_index = 0
        self._thumbnail_size = QSize(192, 192)
        self.setStyleSheet("color: gray;")
        self._process_pool = None
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

        # Clear existing thumbnails and recreate with new layout
        self._clear_thumbnails()
        if len(self._image_paths):
            self._create_empty_thumbnails()
            self._build_thumbnails()
            self._display_thumbnails()
            self._on_thumbnail_clicked(0)
            # Load thumbnails in parallel using multiprocessing
            if self._thread:
                self._request_load_cancel = True
                self._thread.join()
                self._request_load_cancel = False
            self._thread = threading.Thread(target=self._load_thumbnails_in_parallel)
            self._thread.start()

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

    def _create_empty_thumbnails(self):
        if not self._image_paths:
            return
        # make sure to create enough widgets
        if len(self._image_paths) > len(self._thumbnail_widgets):
            for i in range(len(self._thumbnail_widgets), len(self._image_paths)):
                # Create thumbnail widget
                self._thumbnail_widgets.append(self._create_thumbnail_widget(i))

    def _build_thumbnails(self):
        if not self._image_paths:
            return

        for i, image_path in enumerate(self._image_paths):
            # build/reset thumbnail widget
            self._thumbnail_widgets[i].set_highlighted(False)
            self._thumbnail_widgets[i].set_marked(False)
            self._thumbnail_widgets[i].setFixedSize(self._thumbnail_size)
            # self._thumbnail_widgets[i].setMinimumSize(self._thumbnail_size)
            # self._thumbnail_widgets[i].setMaximumSize(self._thumbnail_size)
            # Set placeholder text while loading
            self._thumbnail_widgets[i].setText("Loading...")
            self._thumbnail_widgets[i].set_image_path(image_path)

    def _load_thumbnails_in_parallel(self):
        """Load thumbnails in parallel using multiprocessing."""
        if not self._image_paths:
            return

        # Prepare arguments for the worker function
        thumbnail_size = (self._thumbnail_size.width(), self._thumbnail_size.height())
        image_paths = self._image_paths

        # Initialize process pool if not already done
        # Use a reasonable number of processes (typically CPU count)
        num_processes = min(4, multiprocessing.cpu_count() or 1)
        process_pool = Pool(processes=num_processes)

        # process tasks in chunks of up to 16
        chunk_size = 16
        for i in range(0, len(image_paths), chunk_size):
            if not self._request_load_cancel:
                chunk = image_paths[i : i + chunk_size]
                # Submit tasks to the process pool
                results = []
                for j, image_path in enumerate(chunk):
                    result = process_pool.apply_async(
                        load_image_worker, args=(image_path, thumbnail_size, i + j)
                    )
                    results.append(result)

                # Process results as they become available
                for result in results:
                    try:
                        image_path, resized_image, size, index = result.get()
                        if resized_image is not None:
                            # Convert PIL Image to QPixmap in the main thread
                            from PySide6.QtGui import QImage, QPixmap

                            image = QImage(
                                resized_image.tobytes(),
                                size[0],
                                size[1],
                                size[0] * 3,
                                QImage.Format.Format_RGB888,
                            )
                            pixmap = QPixmap.fromImage(image)

                            # Update the thumbnail widget
                            self._thumbnail_widgets[index].setPixmap(pixmap)
                        else:
                            self._thumbnail_widgets[index].setText("Image")
                    except Exception as e:
                        print(
                            f"Error processing result for {self._image_paths[i]}: {e}"
                        )
                        self._thumbnail_widgets[i].setText("Error")

        # cleanup
        process_pool.close()
        process_pool.join()

    def _display_thumbnails(self):
        """Display thumbnails for all loaded images."""
        if not self._image_paths:
            return

        columns = self._get_target_number_of_columns()
        self._current_columns = columns

        for i, image_path in enumerate(self._image_paths):
            row = i // columns
            col = i % columns
            self._content_layout.removeWidget(self._thumbnail_widgets[i])
            self._content_layout.addWidget(self._thumbnail_widgets[i], row, col)

    def _create_thumbnail_widget(self, index):
        """Create a widget for displaying a thumbnail.

        Args:
            image_path (str): Path to the image file.

        Returns:
            QWidget: A widget containing the thumbnail.
        """
        # Create label for thumbnail with drag support
        thumbnail_label = DragLabel(index)

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
        self._thumbnail_widgets[self._last_thumbnail_clicked_index].set_highlighted(
            False
        )
        self._last_thumbnail_clicked_index = index
        self._thumbnail_widgets[self._last_thumbnail_clicked_index].set_highlighted(
            True
        )

        # Scroll to make the selected thumbnail visible
        self._scroll_to_thumbnail(index)

        # Emit signal with the image path
        self.thumbnailClicked.emit(self._image_paths[index])

    def _scroll_to_thumbnail(self, index):
        """Scroll the scroll area to make the specified thumbnail visible.

        Args:
            index (int): Index of the thumbnail to scroll to.
        """
        if (
            not self._thumbnail_widgets
            or index < 0
            or index >= len(self._thumbnail_widgets)
        ):
            return

        thumbnail_widget = self._thumbnail_widgets[index]

        # Use the built-in method to ensure the widget is visible
        # This handles all the coordinate calculations automatically
        self._scroll_area.ensureWidgetVisible(thumbnail_widget, 0, 0)

    def nextThumbnail(self):
        """Navigate to the next thumbnail in the gallery.

        Returns:
            bool: True if navigation was successful, False if already at the last thumbnail.
        """
        if not self._image_paths:
            return False

        # Move to next thumbnail, no wrapping
        new_index = min(
            self._last_thumbnail_clicked_index + 1, len(self._image_paths) - 1
        )

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

        # Move to previous thumbnail, no wrapping
        new_index = max(self._last_thumbnail_clicked_index - 1, 0)

        # Only emit signal if index changed
        if new_index != self._last_thumbnail_clicked_index:
            self._on_thumbnail_clicked(new_index)
            return True

        return False

    def _clear_thumbnails(self):
        """hide all thumbnails from the gallery."""
        self._last_thumbnail_clicked_index = 0
        self._current_columns = -1
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                self._content_layout.removeWidget(widget)

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

    def get_current_file_path(self):
        """Get the path of the currently selected thumbnail.

        Returns:
            str: Path to the currently selected file, or None if no file is selected.
        """
        if not self._image_paths or self._last_thumbnail_clicked_index < 0:
            return None
        return self._image_paths[self._last_thumbnail_clicked_index]

    def mark_current_file(self, value):
        """Mark the currently selected thumbnail.

        Returns:
            bool: True if a file was marked, False if no file is selected.
        """
        if not self._image_paths or self._last_thumbnail_clicked_index < 0:
            return False

        # Get the thumbnail widget for the current file
        thumbnail_widget = self._thumbnail_widgets[self._last_thumbnail_clicked_index]
        # set the mark to value
        thumbnail_widget.set_marked(value)
        return True

    def set_thumbnail_size(self, size):
        """Set the size for thumbnails.

        Args:
            size (QSize): The size for thumbnails.
        """
        self._thumbnail_size = size
        # Reload thumbnails with new size
        if self._image_paths:
            # Clear existing process pool before reloading
            if self._process_pool is not None:
                self._process_pool.close()
                self._process_pool.join()
                self._process_pool = None
            self.load_images_from_folder(os.path.dirname(self._image_paths[0]))
