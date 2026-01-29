"""Image gallery widget for displaying thumbnails of images and videos.

This module provides a thumbnail gallery that supports parallel loading,
drag-and-drop operations, and keyboard navigation for efficient browsing.
"""

import multiprocessing
import os
import threading
from multiprocessing import Pool

from PySide6.QtCore import (
    QMimeData,
    Qt,
    QUrl,
    Signal,
)
from PySide6.QtGui import QDrag, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .utils import (
    ALL_SUPPORTED_EXTENSIONS,
    MAX_PROCESSES,
    PROCESSING_CHUNK_SIZE,
    get_swarm_json_path,
    get_swarm_preview_path,
    is_video_file,
    safe_remove_file,
)


class DragLabel(QLabel):
    """A custom QLabel that supports drag and drop operations."""

    thumbnailClicked = Signal(int)

    def __init__(self, index, parent=None):
        super().__init__(parent)
        self.index = index
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
        # set _is_video if the file is a video
        self._is_video = is_video_file(image_path)
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
            self.thumbnailClicked.emit(self.index)
        else:
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
        swarm_preview_path = get_swarm_preview_path(image_path)
        if os.path.exists(swarm_preview_path):
            thumbnail_path = swarm_preview_path

        image = Image.open(thumbnail_path)

        if image:
            image.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)
            return (image_path, image.convert("RGB"), image.size, index)
        else:
            return (image_path, None, [0, 0], index)
    except Exception as e:
        print(f"Error loading image {image_path}: {e}")
        return (image_path, None, [0, 0], index)


class ImageGallery(QWidget):
    """A widget that displays thumbnails of images and videos in a folder.

    Features:
    - Parallel thumbnail loading using multiprocessing
    - Dynamic grid layout that adjusts to window size
    - Drag-and-drop support for thumbnails
    - Visual highlighting of selected and marked files
    - Keyboard navigation support
    - Support for both images and videos with distinct coloring
    """

    # Signal emitted when a thumbnail is clicked
    thumbnailClicked = Signal(str)

    def __init__(self, parent=None):
        """Initialize the ImageGallery widget.

        Args:
            parent: Parent widget (optional).
        """
        super().__init__(parent)
        self._thread = None
        self._request_load_cancel = False
        self._thumbnail_widgets = []
        self._image_paths = []
        self._marked_files = []
        self._current_columns = -1
        self._last_thumbnail_clicked_index = 0
        self._thumbnail_size = [192, 192]
        # self.setStyleSheet("color: gray;")
        self._process_pool = None
        self._setup_ui()

    def _setup_ui(self):
        """Set up the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # Filter box
        self._filter_input = QLineEdit()
        self._filter_input.setPlaceholderText("Filter files...")
        self._filter_input.setStyleSheet(
            "QLineEdit { background-color: #333; color: white; border: 1px solid #555; padding: 5px; }"
        )
        self._filter_input.textChanged.connect(self._on_filter_text_changed)
        main_layout.addWidget(self._filter_input)

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

    def add_image(self, file_path):
        # Get all supported files from the folder
        supported_extensions = ALL_SUPPORTED_EXTENSIONS

        if os.path.isfile(file_path):
            ext = os.path.splitext(file_path)[1].lower()
            if ext in supported_extensions:
                i = len(self._image_paths)
                self._image_paths.append(file_path)
                # add a single thumbnail
                self._create_empty_thumbnails()
                self._build_thumbnail(i, file_path)
                self._display_thumbnails()
                (image_path, resized_image, size, index) = load_image_worker(
                    file_path, self._thumbnail_size, i
                )
                self._set_thumbnail(resized_image, size, index)
                self._on_thumbnail_clicked(index)

    def load_images_from_folder(self, folder_path):
        """Load and display images and videos from the specified folder.

        This method:
        1. Scans the folder for supported image and video files
        2. Excludes Swarm preview files (.swarmpreview.jpg)
        3. Creates thumbnail widgets for each file
        4. Loads thumbnails in parallel using multiprocessing
        5. Selects the first thumbnail by default

        Args:
            folder_path (str): Path to the folder containing images and videos.
        """
        self._image_paths = []

        # Get all supported files from the folder
        supported_extensions = ALL_SUPPORTED_EXTENSIONS

        for file_name in os.listdir(folder_path):
            # exclude .swarmpreview images and bowser-temp images
            if ".swarmpreview.jpg" not in file_name and "bowser-temp" not in file_name:
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
            self._show_first_visible_thumbnail()
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
            thumbnail_width = self._thumbnail_size[0]

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
                widget = DragLabel(i)
                widget.thumbnailClicked.connect(self._on_thumbnail_clicked)
                self._thumbnail_widgets.append(widget)

    def _build_thumbnail(self, i, image_path):
        # build/reset thumbnail widget
        self._thumbnail_widgets[i].set_highlighted(False)
        self._thumbnail_widgets[i].set_marked(False)
        self._thumbnail_widgets[i].setFixedSize(
            self._thumbnail_size[0], self._thumbnail_size[1]
        )
        # Set placeholder text while loading
        self._thumbnail_widgets[i].setText("Loading...")
        self._thumbnail_widgets[i].set_image_path(image_path)

    def _build_thumbnails(self):
        if not self._image_paths:
            return
        for i, image_path in enumerate(self._image_paths):
            self._build_thumbnail(i, image_path)

    def _set_thumbnail(self, resized_image, size, index):
        try:
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
            print(f"Error processing result for {self._image_paths[index]}: {e}")
            self._thumbnail_widgets[index].setText("Error")

    def _load_thumbnails_in_parallel(self):
        """Load thumbnails in parallel using multiprocessing."""
        if not self._image_paths:
            return

        # Prepare arguments for the worker function
        image_paths = self._image_paths

        # Initialize process pool if not already done
        num_processes = min(MAX_PROCESSES, multiprocessing.cpu_count() or 1)
        process_pool = Pool(processes=num_processes)

        # process tasks in chunks
        chunk_size = PROCESSING_CHUNK_SIZE
        for i in range(0, len(image_paths), chunk_size):
            if not self._request_load_cancel:
                chunk = image_paths[i : i + chunk_size]
                # Submit tasks to the process pool
                results = []
                for j, image_path in enumerate(chunk):
                    result = process_pool.apply_async(
                        load_image_worker,
                        args=(image_path, self._thumbnail_size, i + j),
                    )
                    results.append(result)

                # Process results as they become available
                for result in results:
                    image_path, resized_image, size, index = result.get()
                    self._set_thumbnail(resized_image, size, index)

        # cleanup
        process_pool.close()
        process_pool.join()

    def _display_thumbnails(self):
        """Display thumbnails for all loaded images."""
        if not self._image_paths:
            return

        columns = self._get_target_number_of_columns()
        self._current_columns = columns

        filter_lower = None
        _filter_text = self._filter_input.text()
        if _filter_text and _filter_text.strip() != "":
            filter_lower = _filter_text.lower()

        count = 0
        for i, image_path in enumerate(self._image_paths):
            self._content_layout.removeWidget(self._thumbnail_widgets[i])
            if (
                filter_lower is None
                or filter_lower in os.path.basename(image_path).lower()
            ):
                row = count // columns
                col = count % columns
                self._content_layout.addWidget(self._thumbnail_widgets[i], row, col)
                self._thumbnail_widgets[i].show()
                count += 1
            else:
                self._thumbnail_widgets[i].hide()

    def _on_filter_text_changed(self, text):
        """Handle filter text changed event.

        Args:
            text (str): The filter text entered by the user.
        """
        # Apply filtering to the image paths
        self._display_thumbnails()

    def show_image(self, filename):
        if not self._image_paths:
            return False

        # try to find the file
        for idx, path in enumerate(self._image_paths):
            if path == filename and not self._thumbnail_widgets[idx].isHidden():
                self._on_thumbnail_clicked(idx)
                return

    def _show_first_visible_thumbnail(self):
        if not self._image_paths:
            return False

        # Move to next shown thumbnail, no wrapping
        new_index = 0
        while (
            new_index < len(self._image_paths)
            and self._thumbnail_widgets[new_index].isHidden()
        ):
            new_index += 1

        # Only select if we found at least one visible thumbnail
        if new_index < len(self._image_paths):
            self._on_thumbnail_clicked(new_index)
            return True
        return False

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

    def next_thumbnail(self):
        """Navigate to the next thumbnail in the gallery.

        Returns:
            bool: True if navigation was successful, False if already at the last thumbnail.
        """
        if not self._image_paths:
            return False

        # Move to next shown thumbnail, no wrapping
        new_index = self._last_thumbnail_clicked_index + 1
        while (
            new_index < len(self._image_paths)
            and self._thumbnail_widgets[new_index].isHidden()
        ):
            new_index += 1

        # Only emit signal if index changed
        if (
            new_index < len(self._image_paths)
            and new_index != self._last_thumbnail_clicked_index
        ):
            self._on_thumbnail_clicked(new_index)
            return True

        return False

    def previous_thumbnail(self):
        """Navigate to the previous thumbnail in the gallery.

        Returns:
            bool: True if navigation was successful, False if already at the first thumbnail.
        """
        if not self._image_paths:
            return False

        # Move to previous thumbnail, no wrapping
        new_index = self._last_thumbnail_clicked_index - 1
        while new_index >= 0 and self._thumbnail_widgets[new_index].isHidden():
            new_index -= 1

        # Only emit signal if index changed
        if new_index >= 0 and new_index != self._last_thumbnail_clicked_index:
            self._on_thumbnail_clicked(new_index)
            return True

        return False

    def _clear_thumbnails(self):
        """hide all thumbnails from the gallery."""
        self._last_thumbnail_clicked_index = 0
        self._current_columns = -1
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.hide()

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

    def on_mark_file_clicked(self):
        """Handle Mark File button click event."""
        # Get the current file path from the image gallery
        current_file = self.get_current_file_path()
        if current_file:
            # is it already marked? if so toggle
            if current_file in self._marked_files:
                self._marked_files.remove(current_file)
                self.mark_current_file(False)
            else:
                self.mark_current_file(True)
                self._marked_files.append(current_file)
        # advance to the next file
        self.next_thumbnail()

    def delete_marked_files(self):
        """Delete all marked files.

        This method:
        1. Confirms deletion with the user
        2. Removes the marked files from disk
        3. Also removes associated Swarm metadata files (.swarm.json, .swarmpreview.jpg)
        4. Removes the deleted files from _image_paths and _thumbnail_widgets
        5. Refreshes the display without reloading the entire directory
        6. Shows a success message with the count of deleted files

        Error Handling:
        - Handles file permission errors gracefully
        - Provides detailed error messages in the console
        - Continues with remaining files if one fails
        """
        if not self._marked_files:
            return

        # Confirm deletion with user
        confirm = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete {len(self._marked_files)} marked file(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if confirm == QMessageBox.StandardButton.Yes:
            self._thumbnail_widgets[self._last_thumbnail_clicked_index].set_highlighted(
                False
            )
            self._last_thumbnail_clicked_index = 0

            # Delete each marked file
            deleted_count = 0
            error_count = 0

            # Create a list of indices to remove (in reverse order to avoid index shifting issues)
            indices_to_remove = []
            # List to store moved widgets and their paths
            moved_widgets = []

            for file_path in self._marked_files[:]:  # Use slice to iterate over a copy
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        deleted_count += 1

                        # Remove any matching .swarm.json and .swarmpreview.jpg files
                        swarm_json_path = get_swarm_json_path(file_path)
                        if os.path.exists(swarm_json_path):
                            if safe_remove_file(swarm_json_path):
                                deleted_count += 1

                        # Remove .swarmpreview.jpg file if it exists
                        swarm_preview_path = get_swarm_preview_path(file_path)
                        if os.path.exists(swarm_preview_path):
                            if safe_remove_file(swarm_preview_path):
                                deleted_count += 1

                        # Find the index of this file in _image_paths
                        if file_path in self._image_paths:
                            index = self._image_paths.index(file_path)
                            indices_to_remove.append(index)

                        # Remove from marked files list
                        self._marked_files.remove(file_path)
                    else:
                        print(f"Warning: File not found during deletion: {file_path}")
                        self._marked_files.remove(file_path)
                except PermissionError as e:
                    print(f"Permission error deleting {file_path}: {e}")
                    error_count += 1
                except OSError as e:
                    print(f"OS error deleting {file_path}: {e}")
                    error_count += 1
                except Exception as e:
                    print(f"Unexpected error deleting {file_path}: {e}")
                    error_count += 1

            # Move deleted widgets to the end of the list instead of deleting them
            # This saves the overhead of recreating them later
            for index in sorted(indices_to_remove, reverse=True):
                if index < len(self._image_paths):
                    # Remove from image paths
                    self._image_paths.pop(index)
                    # Move widget to end of list instead of deleting
                    if index < len(self._thumbnail_widgets):
                        widget = self._thumbnail_widgets.pop(index)
                        moved_widgets.append(widget)

            # Add moved widgets to the end of the list with empty paths
            for widget in moved_widgets:
                self._thumbnail_widgets.append(widget)
                widget.hide()

            # renumber the index value for the widgets
            for i, widget in enumerate(self._thumbnail_widgets):
                widget.index = i

            # Refresh the display
            if deleted_count > 0:
                self._display_thumbnails()

            # Show appropriate message based on results
            if error_count > 0:
                QMessageBox.warning(
                    self,
                    "Partial Success",
                    f"Successfully deleted {deleted_count} file(s), but {error_count} file(s) failed to delete.\n"
                    f"Check console for details.",
                )
            else:
                QMessageBox.information(
                    self,
                    "Files Deleted",
                    f"Successfully deleted {deleted_count} file(s).",
                )

    def set_thumbnail_size(self, size):
        """Set the size for thumbnails.

        Args:
            size list[width, height]: The size for thumbnails.
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

    def clear_images(self):
        """Clear all images from the gallery.

        This method clears all image paths, removes all thumbnail widgets,
        and resets the gallery to an empty state.
        """
        # Clear all image paths
        self._image_paths.clear()

        # Clear all thumbnail widgets
        for widget in self._thumbnail_widgets:
            widget.deleteLater()
        self._thumbnail_widgets.clear()

        # Clear marked files
        self._marked_files.clear()

        # Reset state variables
        self._last_thumbnail_clicked_index = 0
        self._current_columns = -1

        # Clear the content layout
        self._clear_thumbnails()
