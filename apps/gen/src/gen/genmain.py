"""
Main gen app for bowser using PySide6.
"""

from pathlib import Path

import toml
from core.imagegallery import ImageGallery
from core.imagevideoviewer import ImageVideoViewer
from core.metadataviewer import MetadataViewer
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMenuBar,
    QPushButton,
    QSplitter,
    QStyleFactory,
    QVBoxLayout,
    QWidget,
)

from .comfyserver import comfyServer
from .serverswidget import ServersWidget
from .workflowswidget import WorkflowsWidget


class SettingsDialog(QDialog):
    """
    Dialog for configuring application settings.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(400)

        # Create form layout
        form_layout = QFormLayout()

        # Server address field
        self.server_address_edit = QLineEdit()
        self.server_address_edit.setPlaceholderText("e.g., 127.0.0.1:8188, 192.168.1.100:8188")
        form_layout.addRow(QLabel("Server Address(es):"), self.server_address_edit)

        # Output root field
        self.output_root_edit = QLineEdit()
        output_root_layout = QHBoxLayout()
        output_root_layout.addWidget(self.output_root_edit)
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_output_root)
        output_root_layout.addWidget(browse_button)
        form_layout.addRow(QLabel("Output Root:"), output_root_layout)

        # Workflow root field
        self.workflow_root_edit = QLineEdit()
        workflow_layout = QHBoxLayout()
        workflow_layout.addWidget(self.workflow_root_edit)
        browse_workflow_button = QPushButton("Browse...")
        browse_workflow_button.clicked.connect(self._browse_workflow_root)
        workflow_layout.addWidget(browse_workflow_button)
        form_layout.addRow(QLabel("Workflow root:"), workflow_layout)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.addLayout(form_layout)
        main_layout.addWidget(button_box)
        self.setLayout(main_layout)

    def _browse_output_root(self):
        """Open file dialog to select output root directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Root Directory",
            "",
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
        )
        if directory:
            self.output_root_edit.setText(directory)

    def _browse_workflow_root(self):
        """Open file dialog to select workflow root directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Workflow root",
            "",
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
        )
        if directory:
            self.workflow_root_edit.setText(directory)

    def load_settings(self, settings):
        """Load settings into the dialog."""
        if settings:
            # Join server addresses with commas for display
            server_addr = settings.get("server_address", "127.0.0.1:8188")
            if isinstance(server_addr, list):
                server_addr = ", ".join(server_addr)
            self.server_address_edit.setText(server_addr)
            self.output_root_edit.setText(settings.get("output_root", ""))
            self.workflow_root_edit.setText(settings.get("workflow_root", ""))

    def get_settings(self):
        """Return the current settings as a dictionary."""
        return {
            "server_address": self.server_address_edit.text(),
            "output_root": self.output_root_edit.text(),
            "workflow_root": self.workflow_root_edit.text(),
        }


class GenMain(QMainWindow):
    """
    Main application window
    """

    def __init__(self, workflow_root, server_address):
        super().__init__()

        # handle command line args
        self._server_addresses = []
        self._workflow_root = ""
        if server_address is not None:
            # Split comma-separated server addresses
            self._server_addresses = [s.strip() for s in server_address.split(",") if s.strip()]
        if workflow_root is not None:
            self._workflow_root = workflow_root
        self._output_root = ""

        # Load settings from file
        self._settings_file = Path("bowser-gen.toml")
        self._settings = {}
        self._load_settings()

        # Apply dark mode (Fusion style with dark palette)
        self._apply_dark_mode()

        self.setWindowTitle("bowser-gen")
        self.setMinimumSize(800, 600)

        # Create menu bar
        self._create_menu_bar()

        # Create status label
        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet("color: #CCCCCC; padding: 2px 8px;")

        # Create the central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create horizontal splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Create comfy server instances for each server address
        self._comfy_servers = []
        if self._server_addresses:
            for address in self._server_addresses:
                self._comfy_servers.append(comfyServer(server_address=address))
        else:
            # Fallback to default server if none specified
            self._comfy_servers.append(comfyServer(server_address="127.0.0.1:8188"))

        # Create actual widgets
        self.workflows_widget = WorkflowsWidget()
        self.workflows_widget.setMinimumWidth(400)
        # comfy server is used to query node data which should be the same for
        # all servers if they have that node
        self.workflows_widget.set_comfy_server(self._comfy_servers[0])
        self.workflows_widget.set_output_root(self._output_root)

        # Create servers widget with tabbed interface
        self.servers_widget = ServersWidget()
        self.servers_widget.setMinimumWidth(360)
        
        # Add all servers to the servers widget
        for i, server in enumerate(self._comfy_servers):
            if i == 0:
                # First server is the default
                self.servers_widget.add_server(self._server_addresses[i], server)
            elif i < len(self._server_addresses):
                # Additional servers
                self.servers_widget.add_server(self._server_addresses[i], server)
            else:
                # Fallback servers without explicit addresses
                self.servers_widget.add_server("127.0.0.1:8188", server)
        
        # Connect signals from all queue widgets
        self.servers_widget.connect_signals(self)
        
        # Set output root for all servers
        self.servers_widget.set_output_root_for_all(self._output_root)

        # Image gallery
        self._image_gallery = ImageGallery()
        self._image_gallery.set_reverse_order(True)
        self._image_gallery.setStyleSheet("border: 0px;")

        # Connect thumbnail clicked signal
        self._image_gallery.thumbnail_clicked.connect(self._on_thumbnail_clicked)
        
        # Connect status update signal
        self._image_gallery.status_update.connect(self.set_status_message)

        # Image Video Viewer (handles both image and video viewing)
        self._image_video_viewer = ImageVideoViewer()

        # Connect button signals
        self._image_video_viewer.connect_previous_button(self._on_previous_clicked)
        self._image_video_viewer.connect_mark_file_button(self._on_mark_file_clicked)
        self._image_video_viewer.connect_next_button(self._on_next_clicked)

        # JSON metadata display
        self._metadata_display = MetadataViewer()
        self._metadata_display.input_file_selected.connect(self._on_input_file_selected)

        # image viewer
        self._image_video_viewer.setMinimumWidth(400)

        # Connect the job_queued signal to handle queued jobs
        self.workflows_widget.job_queued.connect(self._handle_job_queued)

        # Add widgets to splitter
        self.splitter.addWidget(self.workflows_widget)
        self.splitter.addWidget(self.servers_widget)
        self.splitter.addWidget(self._image_gallery)
        self.splitter.addWidget(self._image_video_viewer)
        self.splitter.addWidget(self._metadata_display)

        # Set initial sizes for the splitter
        # Third column (image/video viewer) gets extra space with stretch factor
        self.splitter.setSizes([400, 360, 270, 400, 250])
        self.splitter.setStretchFactor(0, 0)  # Jobs - no stretch
        self.splitter.setStretchFactor(1, 0)  # Servers - no stretch
        self.splitter.setStretchFactor(2, 0)  # gallery - no stretch,
        self.splitter.setStretchFactor(3, 1)  # Output - gets extra space
        self.splitter.setStretchFactor(4, 0)  # metadata

        # Set up main layout with menu bar and status bar
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create horizontal layout for menu bar
        menu_layout = QHBoxLayout()
        menu_layout.setContentsMargins(0, 0, 0, 0)
        menu_layout.addWidget(self.menuBar())
        menu_layout.addStretch()
        menu_layout.addWidget(self._status_label)

        # Add menu bar and central widget to main layout
        main_layout.addLayout(menu_layout)
        main_layout.addWidget(self.splitter)
        main_layout.setStretchFactor(self.splitter, 1)  # Splitter takes all extra space

        central_widget.setLayout(main_layout)

        # Get screen size and calculate 60% of it
        screen_size = QGuiApplication.primaryScreen().availableSize()
        new_width = int(screen_size.width() * 3 / 5)
        new_height = int(screen_size.height() * 2 / 3)
        self.resize(new_width, new_height)

        # If workflow_root is set, open it as workflows directory
        if len(self._workflow_root):
            self.open_workflows_directory(self._workflow_root)

    def _reload_job(self, job):
        self.workflows_widget.load_workflow_and_settings_from_job(job)

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

    def _clear_history(self):
        """Clear the queue history and image gallery."""
        self.servers_widget.clear_history()
        self._image_gallery.clear_images()

    def _load_settings(self):
        """Load settings from bowser-gen.toml file."""
        try:
            if self._settings_file.exists():
                self._settings = toml.load(self._settings_file)
                # Update values if not already set
                if (
                    "server_address" in self._settings
                    and len(self._server_addresses) == 0
                ):
                    # Split comma-separated server addresses from settings
                    server_addr = self._settings["server_address"]
                    if server_addr:
                        self._server_addresses = [s.strip() for s in server_addr.split(",") if s.strip()]
                if "workflow_root" in self._settings and len(self._workflow_root) == 0:
                    self._workflow_root = self._settings["workflow_root"]
                if "output_root" in self._settings and len(self._output_root) == 0:
                    self._output_root = self._settings["output_root"]
        except Exception as e:
            print(f"Error loading settings: {e}")

    def _save_settings(self):
        """Save settings to dueser.toml file."""
        try:
            with open(self._settings_file, "w") as f:
                toml.dump(self._settings, f)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def show_settings_dialog(self):
        """Show the settings dialog and handle user input."""
        dialog = SettingsDialog(self)
        dialog.load_settings(self._settings)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Get updated settings from dialog
            new_settings = dialog.get_settings()

            # Update our settings
            self._settings.update(new_settings)
            # Split comma-separated server addresses
            self._server_addresses = [s.strip() for s in new_settings["server_address"].split(",") if s.strip()]
            self._workflow_root = new_settings["workflow_root"]
            self._output_root = new_settings["output_root"]
            self.workflows_widget.set_output_root(self._output_root)
            self.servers_widget.set_output_root_for_all(self._output_root)

            # Save to file
            self._save_settings()

            # Apply workflow root if set
            if new_settings["workflow_root"]:
                self.open_workflows_directory(new_settings["workflow_root"])

    def got_new_file(self, file):
        self._image_gallery.add_image(file)

    def got_show_file(self, file):
        self._image_gallery.show_image(file)

    def got_new_image(self, image):
        self._image_video_viewer.display_PIL_image(image)

    def closeEvent(self, event):
        """
        Handle the window close event.
        """
        for comfy_server in self._comfy_servers:
            if comfy_server is not None:
                comfy_server.close_websocket_connection()

        self.servers_widget.save_performance_data()
        event.accept()  # Accept the event to close the window

    def _create_menu_bar(self):
        """Create the menu bar with File menu."""
        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)

        # Create File menu
        file_menu = QMenu("File", self)
        menu_bar.addMenu(file_menu)

        # Add Open Workflows action
        open_workflows_action = file_menu.addAction("Open Workflows Directory")
        open_workflows_action.triggered.connect(self.open_workflows_directory)

        # Add Settings action
        settings_action = file_menu.addAction("Settings...")
        settings_action.triggered.connect(self.show_settings_dialog)

        # Create Delete Marked Files action
        delete_marked_action = file_menu.addAction("Delete Marked Files...")
        delete_marked_action.setShortcut("Ctrl+D")
        delete_marked_action.triggered.connect(self._delete_marked_files)

        # Add separator
        file_menu.addSeparator()

        # Create Clear History action
        clear_history_action = file_menu.addAction("Clear History")
        clear_history_action.setShortcut("Ctrl+Shift+H")
        clear_history_action.triggered.connect(self._clear_history)

    def _on_input_file_selected(self, file_path: str) -> None:
        """Handle input file selection event.

        Args:
            file_path (str): Path to the selected input file.
        """
        # Load and display file metadata
        self._metadata_display.load_file_metadata(file_path)
        self._image_video_viewer.display_file(file_path)

    def open_workflows_directory(self, directory_path=None):
        """Prompt user to select a workflows directory or use provided path and update JobsWidget."""
        # If no directory path provided, open directory selection dialog
        if directory_path is None or directory_path is False:
            directory = QFileDialog.getExistingDirectory(
                self,
                "Select Workflows Directory",
                "",
                QFileDialog.Option.ShowDirsOnly
                | QFileDialog.Option.DontResolveSymlinks,
            )
        else:
            directory = directory_path

        # If user selected a directory (or one was provided), update the JobsWidget
        if directory:
            # Store the workflows directory path
            self.workflows_directory = directory

            # Update the JobsWidget with the new directory
            self.workflows_widget.set_workflows_directory(directory)

    def _handle_job_queued(self, workflow_name, workflow_data, count):
        """
        Handle the job_queued signal from JobsWidget.

        Args:
            workflow_data: Dictionary containing the workflow data
            count: Number of jobs to queue
        """
        # Queue the job on the current tab
        self.servers_widget.queue_job_on_current_tab(workflow_name, workflow_data, count)

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
        # if event.key() == Qt.Key.Key_W:
        #     self._directory_tree.navigate_to_previous_folder()
        # elif event.key() == Qt.Key.Key_S:
        #     self._directory_tree.navigate_to_next_folder()
        if event.key() == Qt.Key.Key_A:
            self._on_previous_clicked()
        elif event.key() == Qt.Key.Key_D:
            self._on_next_clicked()
        elif event.key() == Qt.Key.Key_R:
            self._image_video_viewer.get_image_viewer().normalSize()
        elif event.key() == Qt.Key.Key_1:
            self._image_video_viewer.get_image_viewer().fullSize()
        elif event.key() == Qt.Key.Key_X:
            self._on_mark_file_clicked()

    def set_status_message(self, message: str):
        """Update the status label with a message.
        
        Args:
            message: The status message to display.
        """
        self._status_label.setText(message)

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
