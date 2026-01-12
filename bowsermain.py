import os

from PySide6.QtCore import QDir, Qt
from PySide6.QtGui import (
    QAction,
    QColor,
    QGuiApplication,
    QPalette,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFileSystemModel,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStyleFactory,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from imagegallery import ImageGallery
from imageviewer import ImageViewer
from metadataviewer import MetadataViewer
from videoviewer import VideoViewer


class BowserMain(QMainWindow):
    def __init__(self, parent=None, folder_path=None):
        super().__init__(parent)

        # Apply dark mode (Fusion style with dark palette)
        self._apply_dark_mode()

        # Create menu bar
        self._create_menu_bar()

        # Create the three main widgets
        # 1. Directory tree
        self._directory_tree = QTreeView()
        self._directory_tree.setHeaderHidden(True)
        self._directory_tree.setMinimumWidth(100)

        # Create file system model for the directory tree
        self._file_system_model = QFileSystemModel()
        self._file_system_model.setRootPath("")
        self._file_system_model.setFilter(
            QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot
        )
        self._directory_tree.setModel(self._file_system_model)

        # Hide all columns except the name column
        self._directory_tree.setColumnHidden(1, True)  # Hide size column
        self._directory_tree.setColumnHidden(2, True)  # Hide type column
        self._directory_tree.setColumnHidden(3, True)  # Hide date

        # Hide the header
        self._directory_tree.header().hide()

        # Set column width for the name column
        self._directory_tree.setColumnWidth(0, 80)

        # Connect the item clicked signal to handle folder selection
        self._directory_tree.clicked.connect(self._on_folder_clicked)

        # 2. Image gallery
        self._image_gallery = ImageGallery()
        self._image_gallery.setStyleSheet("border: 1px solid gray;")

        # Connect thumbnail clicked signal
        self._image_gallery.thumbnailClicked.connect(self._on_thumbnail_clicked)

        # 3. Image Viewer and Video Viewer
        self._viewer = QWidget()
        self._viewer_layout = QVBoxLayout(self._viewer)
        self._viewer.setLayout(self._viewer_layout)
        
        # Create navigation buttons
        self._navigation_buttons_layout = QHBoxLayout()
        self._previous_button = QPushButton("Previous")
        self._next_button = QPushButton("Next")
        self._navigation_buttons_layout.addWidget(self._previous_button)
        self._navigation_buttons_layout.addWidget(self._next_button)
        self._navigation_buttons_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add navigation buttons to the viewer layout
        self._viewer_layout.addLayout(self._navigation_buttons_layout)
        
        # Add image and video viewers
        self._image_viewer = ImageViewer()
        self._image_viewer.setStyleSheet("border: 1px solid gray;")
        self._viewer_layout.addWidget(self._image_viewer)
        self._video_viewer = VideoViewer()
        self._video_viewer.setStyleSheet("border: 1px solid gray;")
        self._viewer_layout.addWidget(self._video_viewer)
        
        # Connect button signals
        self._previous_button.clicked.connect(self._on_previous_clicked)
        self._next_button.clicked.connect(self._on_next_clicked)

        # 4. JSON metadata display
        self._metadata_display = MetadataViewer()

        # Create a splitter for horizontal layout
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter.addWidget(self._directory_tree)
        self._main_splitter.addWidget(self._image_gallery)
        self._main_splitter.addWidget(self._viewer)
        self._main_splitter.addWidget(self._metadata_display)

        # Set initial sizes for the splitter
        # Third column (image/video viewer) gets extra space with stretch factor
        self._main_splitter.setSizes([200, 420, 600, 300])
        self._main_splitter.setStretchFactor(0, 0)  # tree - no stretch
        self._main_splitter.setStretchFactor(1, 0)  # Gallery - no stretch
        self._main_splitter.setStretchFactor(2, 1)  # Viewer - gets extra space
        self._main_splitter.setStretchFactor(3, 0)  # metadata - no stretch

        # Create main vertical layout
        main_container = QWidget()
        main_layout = QVBoxLayout(main_container)
        main_layout.addWidget(self._main_splitter)
        main_container.setLayout(main_layout)

        self.setCentralWidget(main_container)

        # Get screen size and calculate 60% of it
        screen_size = QGuiApplication.primaryScreen().availableSize()
        new_width = int(screen_size.width() * 3 / 5)
        new_height = int(screen_size.height() * 3 / 5)
        self.resize(new_width, new_height)

        # If a folder path is provided, open it
        if folder_path:
            self._open_folder_from_path(folder_path)

    def _create_menu_bar(self):
        """Create the menu bar with File menu and actions."""
        menu_bar = self.menuBar()

        # Create File menu
        file_menu = menu_bar.addMenu("File")

        # Create Open Folder action
        open_folder_action = QAction("Open Folder", self)
        open_folder_action.setShortcut("Ctrl+O")
        open_folder_action.triggered.connect(self._open_folder)
        file_menu.addAction(open_folder_action)

        # Add separator
        file_menu.addSeparator()

        # Create Exit action
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def _open_folder(self):
        """Open a file dialog to select a folder."""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Folder",
            "",
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
        )
        if folder_path:
            self._open_folder_from_path(folder_path)

    def _open_folder_from_path(self, folder_path):
        """Open a folder from a given path.

        Args:
            folder_path (str): Path to the folder to open.
        """
        # Check if the path is a valid directory
        if os.path.isdir(folder_path):
            # Set the root path of the file system model to the selected folder
            self._file_system_model.setRootPath(folder_path)
            # Expand the root item
            self._directory_tree.setRootIndex(
                self._file_system_model.index(folder_path)
            )
            # Expand all directories under the root
            self._expand_all_directories(self._directory_tree.rootIndex())

    def _expand_all_directories(self, index):
        """Recursively expand all directories starting from the given index."""
        # Expand the current index
        self._directory_tree.setExpanded(index, True)

        # Iterate through all children
        for row in range(self._file_system_model.rowCount(index)):
            child_index = self._file_system_model.index(row, 0, index)
            # If the child is a directory, expand it
            if self._file_system_model.isDir(child_index):
                self._expand_all_directories(child_index)

    def _on_folder_clicked(self, index):
        """Handle folder click event and invoke read_folder callback."""
        if index.isValid():
            # Get the file path from the model
            file_path = self._file_system_model.filePath(index)
            # Invoke the read_folder callback with the folder path
            self.read_folder(file_path)

    def read_folder(self, folder_path):
        """Callback method to be invoked when a folder is clicked.

        Args:
            folder_path (str): The path to the folder that was clicked.
        """
        # Load images from the selected folder into the gallery
        self._image_gallery.load_images_from_folder(folder_path)

        # Update metadata display
        self._metadata_display.setMetadata(
            f"Selected folder: {folder_path}\n\nImages found: {len(self._image_gallery.get_image_paths())}"
        )

    def _on_thumbnail_clicked(self, file_path):
        """Handle thumbnail click event.

        Args:
            file_path (str): Path to the clicked file (image or video).
        """
        # Load and display file metadata
        self._metadata_display.loadFileMetadata(file_path)

        # Check file extension to determine if it's an image or video
        file_ext = os.path.splitext(file_path)[1].lower()

        if file_ext in [".mp4", ".mov", ".avi", ".mkv", ".flv"]:
            # Handle video files
            self._display_video(file_path)
        else:
            # Handle image files
            self._display_image(file_path)

    def _on_previous_clicked(self):
        """Handle Previous button click event."""
        self._image_gallery.previousThumbnail()

    def _on_next_clicked(self):
        """Handle Next button click event."""
        self._image_gallery.nextThumbnail()

    def _display_image(self, image_path):
        """Display a image file in a ImageViewer widget.

        Args:
            image_path (str): Path to the image file.
        """
        # Replace the image viewer with the video viewer in the splitter
        # current_index = self._viewer_layout.indexOf(self._video_viewer)
        # if current_index != -1:
        # self._viewer_layout.replaceWidget(self._video_viewer, self._image_viewer)
        self._video_viewer.hide()
        self._image_viewer.show()
        self._image_viewer.setImage(image_path)

    def _display_video(self, video_path):
        """Display a video file in a VideoViewer widget.

        Args:
            video_path (str): Path to the video file.
        """
        # Replace the image viewer with the video viewer in the splitter
        # current_index = self._viewer_layout.indexOf(self._image_viewer)
        # if current_index != -1:
        # self._viewer_layout.replaceWidget(self._image_viewer, self._video_viewer)
        self._image_viewer.hide()
        self._video_viewer.show()
        self._video_viewer.loadVideo(video_path)
        self._video_viewer.play()

    def keyPressEvent(self, event):
        """Handle key press events.

        Args:
            event: QKeyEvent
        """
        if event.key() == Qt.Key.Key_R:
            self._image_viewer.normalSize()
        elif event.key() == Qt.Key.Key_1:
            self._image_viewer.fullSize()

    def _apply_dark_mode(self):
        """Apply dark mode using Fusion style with custom dark palette."""
        # Set Fusion style
        QApplication.setStyle(QStyleFactory.create("Fusion"))

        # Create dark palette
        dark_palette = QPalette()

        # Base colors
        dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
        dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))

        # Disabled colors
        dark_palette.setColor(
            QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(128, 128, 128)
        )
        dark_palette.setColor(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.ButtonText,
            QColor(128, 128, 128),
        )

        # Apply the palette
        QApplication.setPalette(dark_palette)
