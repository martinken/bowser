import os

from core.imagegallery import ImageGallery
from core.imagevideoviewer import ImageVideoViewer
from core.metadataviewer import MetadataViewer
from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QAction,
    QColor,
    QGuiApplication,
    QPalette,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QStyleFactory,
    QVBoxLayout,
    QWidget,
)

from .directorytree import DirectoryTree


class KeybindingsDialog(QDialog):
    """Dialog to display all keybindings for the application."""

    def __init__(self, parent=None):
        """Initialize the KeybindingsDialog.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Keybindings")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        # Create main layout
        main_layout = QVBoxLayout(self)

        # Create title
        title = QLabel("Application Keybindings")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        main_layout.addWidget(title)

        # Create scroll area for keybindings
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        # Create content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # Add keybindings information
        keybindings_info = """
        <html>
        <head>
            <style>
                table {
                    width: 100%;
                    border-collapse: collapse;
                }
                th, td {
                    padding: 8px;
                    text-align: left;
                    border-bottom: 1px solid #555;
                }
                th {
                    background-color: #333;
                    font-weight: bold;
                }
                tr:hover {
                    background-color: #444;
                }
            </style>
        </head>
        <body>
            <table>
                <tr>
                    <th>Action</th>
                    <th>Shortcut</th>
                </tr>
                <tr>
                    <td>Open Folder</td>
                    <td>Ctrl+O</td>
                </tr>
                <tr>
                    <td>Delete Marked Files</td>
                    <td>Ctrl+D</td>
                </tr>
                <tr>
                    <td>Prune Empty Directories</td>
                    <td>Ctrl+P</td>
                </tr>
                <tr>
                    <td>Exit Application</td>
                    <td>Ctrl+Q</td>
                </tr>
                <tr>
                    <td>Navigate to Previous Folder</td>
                    <td>W</td>
                </tr>
                <tr>
                    <td>Navigate to Next Folder</td>
                    <td>S</td>
                </tr>
                <tr>
                    <td>Previous Image/Video</td>
                    <td>A</td>
                </tr>
                <tr>
                    <td>Next Image/Video</td>
                    <td>D</td>
                </tr>
                <tr>
                    <td>Fit Image to Viewer</td>
                    <td>R</td>
                </tr>
                <tr>
                    <td>View Image at 1:1 Size</td>
                    <td>1</td>
                </tr>
                <tr>
                    <td>Mark Current File</td>
                    <td>X</td>
                </tr>
            </table>
        </body>
        </html>
        """

        info_label = QLabel(keybindings_info)
        info_label.setWordWrap(True)
        content_layout.addWidget(info_label)

        # Add some spacing
        content_layout.addStretch()

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

        self.setLayout(main_layout)


class ViewMain(QMainWindow):
    """Main viewer window for Bowser.

    This class manages the overall application layout, including:
    - Directory tree navigation
    - Thumbnail gallery display
    - Image/video viewer
    - Metadata viewer
    - Menu bar and keybindings
    - File marking and deletion system
    """

    def __init__(self, parent=None, folder_path=None):
        """Initialize the main application window.

        Args:
            parent: Parent widget (optional).
            folder_path: Optional path to a folder to open initially.
        """
        super().__init__(parent)

        # Track marked files for batch deletion
        self._marked_files = []
        self._last_file_path = ""

        # Apply dark mode (Fusion style with dark palette)
        self._apply_dark_mode()

        # Create menu bar
        self._create_menu_bar()

        # Enable drag and drop
        self.setAcceptDrops(True)

        # Create the three main widgets
        # 1. Directory tree
        self._directory_tree = DirectoryTree()
        self._directory_tree.clicked.connect(self._on_folder_clicked)

        # 2. Image gallery
        self._image_gallery = ImageGallery()
        self._image_gallery.setStyleSheet("border: 1px solid gray;")

        # Connect thumbnail clicked signal
        self._image_gallery.thumbnailClicked.connect(self._on_thumbnail_clicked)

        # 3. Image Video Viewer (handles both image and video viewing)
        self._image_video_viewer = ImageVideoViewer()

        # Connect button signals
        self._image_video_viewer.connect_previous_button(self._on_previous_clicked)
        self._image_video_viewer.connect_mark_file_button(self._on_mark_file_clicked)
        self._image_video_viewer.connect_next_button(self._on_next_clicked)

        # 4. JSON metadata display
        self._metadata_display = MetadataViewer()

        # Create a splitter for horizontal layout
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter.addWidget(self._directory_tree)
        self._main_splitter.addWidget(self._image_gallery)
        self._main_splitter.addWidget(self._image_video_viewer)
        self._main_splitter.addWidget(self._metadata_display)

        # Set initial sizes for the splitter
        # Third column (image/video viewer) gets extra space with stretch factor
        self._main_splitter.setSizes([200, 420, 600, 400])
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
            self._open_root_folder_from_path(folder_path)

    def _create_menu_bar(self):
        """Create the menu bar with File menu and actions."""
        menu_bar = self.menuBar()

        # Create Main menu
        main_menu = menu_bar.addMenu("Menu")

        # Create Open Folder action
        open_folder_action = QAction("Open Folder", self)
        open_folder_action.setShortcut("Ctrl+O")
        open_folder_action.triggered.connect(self._open_root_folder)
        main_menu.addAction(open_folder_action)

        # Create Refresh action
        refresh_action = QAction("Refresh", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self._refresh_current_folder)
        main_menu.addAction(refresh_action)

        # Add separator
        main_menu.addSeparator()

        # Create Delete Marked Files action
        delete_marked_action = QAction("Delete Marked Files", self)
        delete_marked_action.setShortcut("Ctrl+D")
        delete_marked_action.triggered.connect(self._delete_marked_files)
        main_menu.addAction(delete_marked_action)

        # Create Prune Empty Directories action
        prune_action = QAction("Prune Empty Directories", self)
        prune_action.setShortcut("Ctrl+P")
        prune_action.triggered.connect(self._prune_empty_directories_action)
        main_menu.addAction(prune_action)

        # Add separator
        main_menu.addSeparator()

        # Create Keybindings action
        keybindings_action = QAction("Keybindings", self)
        keybindings_action.setShortcut("Ctrl+K")
        keybindings_action.triggered.connect(self._show_keybindings)
        main_menu.addAction(keybindings_action)

        # Add separator
        main_menu.addSeparator()

        # Create Exit action
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        main_menu.addAction(exit_action)

    def _show_keybindings(self):
        """Show the keybindings dialog."""
        dialog = KeybindingsDialog(self)
        dialog.exec()

    def _prune_empty_directories_action(self):
        """Handle Prune Empty Directories menu action."""
        # Get the current root folder from the file system model
        root_path = self._directory_tree.get_root_folder()

        if not root_path or not os.path.isdir(root_path):
            QMessageBox.warning(
                self,
                "No Folder Selected",
                "Please select a folder first.",
                QMessageBox.StandardButton.Ok,
            )
            return

        # Confirm with user
        confirm = QMessageBox.question(
            self,
            "Confirm Prune Empty Directories",
            f"Are you sure you want to remove all empty directories below:\n{root_path}?\n\n"
            + "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if confirm == QMessageBox.StandardButton.Yes:
            # Prune empty directories
            removed_count = self._directory_tree.prune_empty_directories(root_path)

            # Show result message
            QMessageBox.information(
                self,
                "Directories Pruned",
                f"Successfully removed {removed_count} empty directory(ies).",
                QMessageBox.StandardButton.Ok,
            )

            # Refresh the directory tree
            if root_path:
                self._directory_tree.open_root_folder(root_path)

    def _open_root_folder(self):
        """Open a file dialog to select a folder."""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Folder",
            "",
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
        )
        if folder_path:
            self._open_root_folder_from_path(folder_path)

    def _refresh_current_folder(self):
        """Refresh the current folder by reloading it and reading its contents."""
        # Get the current root folder
        root_path = self._directory_tree.get_root_folder()

        if root_path:
            # Re-open the root folder to refresh the directory tree
            self._open_root_folder_from_path(root_path)

            # Re-read the current folder contents
            if self._last_file_path:
                self.read_folder(self._last_file_path)

    def _open_root_folder_from_path(self, folder_path: str) -> None:
        """Open a folder from a given path.

        Args:
            folder_path (str): Path to the folder to open.
        """
        # Check if the path is a valid directory
        if os.path.isdir(folder_path):
            # Set the window title to show the folder path
            self.setWindowTitle(f"bowser-view - {folder_path}")
            # Use the directory tree's method to open the folder
            self._directory_tree.open_root_folder(folder_path)

    def _on_folder_clicked(self, index) -> None:
        """Handle folder click event and invoke read_folder callback.

        This method is triggered when a user clicks on a folder in the directory tree.
        It retrieves the folder path and loads the images from that folder into the gallery.

        Args:
            index: The model index of the clicked folder.
        """
        if index.isValid():
            # Get the file path from the model
            file_path = self._directory_tree.get_folder_path_from_index(index)
            if self._last_file_path != file_path:
                # Invoke the read_folder callback with the folder path
                self._last_file_path = file_path
                self.read_folder(file_path)

    def read_folder(self, folder_path: str) -> None:
        """Callback method to be invoked when a folder is clicked.

        This method loads images and videos from the specified folder into the thumbnail gallery.
        It's called when a user selects a folder in the directory tree.

        Args:
            folder_path (str): The path to the folder that was clicked.

        Note:
            Only files with supported extensions (as defined in utils.py) will be loaded.
        """
        # Load images from the selected folder into the gallery
        self._image_gallery.load_images_from_folder(folder_path)

    def _on_thumbnail_clicked(self, file_path: str) -> None:
        """Handle thumbnail click event.

        Args:
            file_path (str): Path to the clicked file (image or video).
        """
        # Load and display file metadata
        self._metadata_display.load_file_metadata(file_path)
        self._image_video_viewer.display_file(file_path)

    def _on_previous_clicked(self):
        """Handle Previous button click event."""
        self._image_gallery.previous_thumbnail()

    def _on_next_clicked(self):
        """Handle Next button click event."""
        self._image_gallery.next_thumbnail()

    def _on_mark_file_clicked(self):
        self._image_gallery.on_mark_file_clicked()

    def _delete_marked_files(self):
        self._image_gallery.delete_marked_files()

    def dragEnterEvent(self, event):
        """Handle drag enter event.

        Args:
            event: QDragEnterEvent
        """
        # Check if the drag contains URLs (files/folders)
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Handle drop event.

        Args:
            event: QDropEvent
        """
        # Get the URLs from the drop event
        urls = event.mimeData().urls()
        if urls:
            # Get the first URL's local path
            folder_path = urls[0].toLocalFile()

            # Check if it's a valid directory
            if os.path.isdir(folder_path):
                # Open the folder
                self._open_root_folder_from_path(folder_path)
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()

    def keyPressEvent(self, event):
        """Handle key press events for global keyboard shortcuts.

        Supported keybindings:
        - W: Navigate to previous folder
        - S: Navigate to next folder
        - A: Previous thumbnail
        - D: Next thumbnail
        - R: Fit image to window
        - 1: Display image at 1:1 scale
        - X: Mark/unmark current file

        Args:
            event: QKeyEvent containing the key press information.
        """
        if event.key() == Qt.Key.Key_W:
            self._directory_tree.navigate_to_previous_folder()
        elif event.key() == Qt.Key.Key_S:
            self._directory_tree.navigate_to_next_folder()
        elif event.key() == Qt.Key.Key_A:
            self._on_previous_clicked()
        elif event.key() == Qt.Key.Key_D:
            self._on_next_clicked()
        elif event.key() == Qt.Key.Key_R:
            self._image_video_viewer.get_image_viewer().normalSize()
        elif event.key() == Qt.Key.Key_1:
            self._image_video_viewer.get_image_viewer().fullSize()
        elif event.key() == Qt.Key.Key_X:
            self._on_mark_file_clicked()

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
