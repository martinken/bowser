"""ImageVideoViewer class that handles both image and video viewing functionality."""

from typing import Optional

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from .imageviewer import ImageViewer
from .utils import (
    is_video_file,
)
from .videoviewer import VideoViewer


class ImageVideoViewer(QWidget):
    """A widget that handles both image and video viewing with navigation controls.

    This class encapsulates the logic for displaying images and videos,
    managing the viewer widgets, and handling navigation between them.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the ImageVideoViewer.

        Args:
            parent: Parent widget (optional).
        """
        super().__init__(parent)

        # Create main layout
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)

        # Create navigation buttons layout
        self._navigation_buttons_layout = QHBoxLayout()
        self._navigation_buttons_layout.setContentsMargins(0, 0, 0, 0)

        # Create navigation buttons
        self._previous_button = QPushButton("Previous")
        self._one_to_one_button = QPushButton("1:1")
        self._fit_button = QPushButton("Fit")
        self._mark_file_button = QPushButton("Mark File")
        self._next_button = QPushButton("Next")

        self._navigation_buttons_layout.addWidget(self._previous_button)
        self._navigation_buttons_layout.addWidget(self._one_to_one_button)
        self._navigation_buttons_layout.addWidget(self._fit_button)
        self._navigation_buttons_layout.addWidget(self._mark_file_button)
        self._navigation_buttons_layout.addWidget(self._next_button)

        self._one_to_one_button.clicked.connect(self._on_one_to_one_clicked)
        self._fit_button.clicked.connect(self._on_fit_clicked)

        # Add navigation buttons to the main layout
        self._main_layout.addLayout(self._navigation_buttons_layout)

        # Create image and video viewers
        self._image_viewer = ImageViewer()
        self._image_viewer.setStyleSheet("border: 1px solid gray;")

        self._video_viewer = VideoViewer()
        self._video_viewer.setStyleSheet("border: 1px solid gray;")

        # Add viewers to the layout
        self._main_layout.addWidget(self._image_viewer)
        self._main_layout.addWidget(self._video_viewer)

        # Hide video viewer initially (image viewer will be shown by default)
        self._video_viewer.hide()

        # Set the layout
        self.setLayout(self._main_layout)

    def display_PIL_image(self, image):
        """Display an image in the ImageViewer widget."""
        self._video_viewer.hide()
        self._image_viewer.show()
        self._image_viewer.setPILImage(image)

    def display_file(self, file_path: str) -> None:
        # Check file extension to determine if it's an image or video
        if is_video_file(file_path):
            # Handle video files
            self.display_video_file(file_path)
        else:
            # Handle image files
            self.display_image_file(file_path)

    def display_image_file(self, image_path: str) -> None:
        """Display an image file in the ImageViewer widget.

        Args:
            image_path (str): Path to the image file.
        """
        self._video_viewer.hide()
        self._image_viewer.show()
        self._image_viewer.setImageFile(image_path)

    def display_video_file(self, video_path: str) -> None:
        """Display a video file in the VideoViewer widget.

        Args:
            video_path (str): Path to the video file.
        """
        self._image_viewer.hide()
        self._video_viewer.show()
        self._video_viewer.loadVideo(video_path)
        self._video_viewer.play()

    def _on_one_to_one_clicked(self) -> None:
        """Handle 1:1 button click event."""
        self._image_viewer.fullSize()

    def _on_fit_clicked(self) -> None:
        """Handle Fit button click event."""
        self._image_viewer.normalSize()

    def connect_previous_button(self, slot) -> None:
        """Connect the Previous button to a slot.

        Args:
            slot: The slot function to connect to.
        """
        self._previous_button.clicked.connect(slot)

    def connect_next_button(self, slot) -> None:
        """Connect the Next button to a slot.

        Args:
            slot: The slot function to connect to.
        """
        self._next_button.clicked.connect(slot)

    def connect_mark_file_button(self, slot) -> None:
        """Connect the Mark File button to a slot.

        Args:
            slot: The slot function to connect to.
        """
        self._mark_file_button.clicked.connect(slot)

    def get_image_viewer(self) -> ImageViewer:
        """Get the ImageViewer instance.

        Returns:
            ImageViewer: The ImageViewer instance.
        """
        return self._image_viewer

    def get_video_viewer(self) -> VideoViewer:
        """Get the VideoViewer instance.

        Returns:
            VideoViewer: The VideoViewer instance.
        """
        return self._video_viewer
