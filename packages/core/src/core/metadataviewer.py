"""Metadata viewer widget for displaying image and video metadata.

This module provides a widget for displaying structured metadata from
images (EXIF, IPTC) and videos, with support for JSON formatting and
sidecar metadata files.
"""

import json
from typing import Any, Dict, Optional, Union

from PySide6.QtCore import Qt, QMimeData, QUrl, Signal
from PySide6.QtGui import QDrag, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .metadatahandler import MetadataHandler


class MetadataViewer(QWidget):
    # Constants for text box height management
    COMPACT_TEXT_BOX_HEIGHT = 69
    UNLIMITED_TEXT_BOX_HEIGHT = 16777215  # Maximum possible value for int
    
    # Signal emitted when an input file is selected via Ctrl+click
    input_file_selected = Signal(str)
    """A widget for displaying structured metadata information.

    Features include:
    - Display of EXIF data from images (using PIL)
    - Display of metadata from videos
    - Support for sidecar JSON files (e.g., SwarmUI .swarm.json files)
    - Dedicated GUI elements for File, Size, Seed, and Prompt with copy buttons
    - Copy-to-clipboard functionality for individual metadata fields
    - Formatted JSON output with indentation for complete metadata
    - Error handling for corrupted or missing metadata
    - Automatic detection of image vs video files
    - Recursive metadata extraction from nested structures
    - Dark mode support with custom styling
    - Automatic text wrapping for long metadata values
    """

    def __init__(self, parent: Optional[QWidget] = None, metadata_handler: Optional[MetadataHandler] = None):
        """Initialize the MetadataViewer widget.

        Args:
            parent: Parent widget (optional).
            metadata_handler: MetadataHandler instance for dependency injection.
                            If None, a default MetadataHandler will be created.
        """
        super().__init__(parent)

        # Initialize metadata handler (use provided or create default)
        self.metadata_handler = metadata_handler if metadata_handler is not None else MetadataHandler()

        # Initialize field labels dictionary early
        self.field_labels: Dict[str, QLabel] = {}

        # Initialize field frames dictionary for showing/hiding
        self.field_frames: Dict[str, QFrame] = {}

        # Create main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(6)

        # Create top section with dedicated fields
        self.top_section = QFrame()
        self.top_section.setFrameShape(QFrame.Shape.StyledPanel)
        self.top_section.setStyleSheet("""
            QFrame {
                background-color: #333333;
                border: 0px solid #555555;
                border-radius: 0px;
                padding: 0px;
            }
        """)

        top_layout = QVBoxLayout(self.top_section)
        top_layout.setSpacing(0)
        top_layout.setContentsMargins(0, 0, 0, 0)

        # Create grid layout for the fields
        grid_layout = QVBoxLayout()
        grid_layout.setSpacing(2)

        # Create dedicated field layouts
        self.field_layouts = []
        self._create_field_layout("Seed", "", grid_layout)
        self._create_field_layout("File", "", grid_layout)
        self._create_field_layout("Size", "", grid_layout)
        self._create_field_layout("Steps", "", grid_layout)
        self._create_field_layout("Model", "", grid_layout)
        self._create_field_layout("Time", "", grid_layout)
        self._create_field_layout("InImage", "", grid_layout)
        self._create_field_layout("InVideo", "", grid_layout)
        self._create_field_layout("CFG", "", grid_layout)
        self._create_field_layout("Guidance", "", grid_layout)
        self._create_field_layout("Prompt", "", grid_layout, set_minimum_size=True)
        self._create_field_layout("Prompt2", "", grid_layout, set_minimum_size=True)

        # Hide all frames initially
        for field_name in self.field_frames:
            self.field_frames[field_name].setVisible(False)

        top_layout.addLayout(grid_layout)

        # Add top section to main layout
        self.main_layout.addWidget(self.top_section)

        # Create text edit for full metadata
        self.metadata_text = QTextEdit()
        self.metadata_text.setReadOnly(True)
        self.metadata_text.setPlaceholderText("JSON Metadata will appear here...")
        self.metadata_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #555555;
                background-color: #252525;
                color: #ffffff;
            }
        """)
        self.metadata_text.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # Add text edit to main layout
        self.main_layout.addWidget(self.metadata_text, 1)  # Take remaining space

    def _create_field_layout(
        self, label_text: str, initial_value: str, grid_layout: QVBoxLayout, set_minimum_size: bool = False
    ) -> None:
        """Create a horizontal layout with label, value, and copy button.

        Args:
            label_text: Text for the label
            initial_value: Initial value for the value label
            grid_layout: The layout to which this field layout should be added
            set_minimum_size: Whether to set minimum size constraint (for Prompt field)
        """
        # Create a frame to hold the layout so we can show/hide it
        frame = QFrame()
        frame.setContentsMargins(0, 0, 0, 0)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)

        # Label
        label = QLabel(label_text)
        label.setMinimumWidth(60)
        label.setStyleSheet(
            "padding: 0px; border: 1px solid #555555; border-radius: 3px; font-weight: bold; color: #ffffff;"
        )
        layout.addWidget(label)

        # Value label (will be updated dynamically)
        value_label = QLabel(initial_value)
        value_label.setMaximumHeight(self.COMPACT_TEXT_BOX_HEIGHT)
        value_label.setStyleSheet(
            "border: 1px solid #555555; border-radius: 3px; padding-left: 4px; color: #ffffff;"
        )
        value_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextBrowserInteraction
        )
        value_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        value_label.setWordWrap(True)  # Enable word wrapping
        value_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )  # Align text to top-left
        layout.addWidget(value_label, 1)  # Take remaining space

        # Enable drag and drop for InImage and InVideo fields
        if label_text.rstrip(":") in ["InImage", "InVideo"]:
            value_label.setAcceptDrops(True)
            value_label.installEventFilter(self)
            value_label.drag_start_position = None # pyright: ignore[reportAttributeAccessIssue]
            
            # Connect mouse press event to store drag start position and handle Ctrl+click
            original_mousePressEvent = value_label.mousePressEvent
            def mousePressEvent(e):
                if e.button() == Qt.MouseButton.LeftButton:
                    value_label.drag_start_position = e.pos() # pyright: ignore[reportAttributeAccessIssue]
                    
                    # Check if Ctrl is pressed
                    if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
                        # Emit input_file_selected signal with the file path
                        self.input_file_selected.emit(value_label.text())
                if original_mousePressEvent:
                    original_mousePressEvent(e)
            value_label.mousePressEvent = mousePressEvent
            
            # Connect mouse move event to initiate drag
            original_mouseMoveEvent = value_label.mouseMoveEvent
            def mouseMoveEvent(e):
                if not value_label.drag_start_position: # pyright: ignore[reportAttributeAccessIssue]
                    return
                if e.buttons() != Qt.MouseButton.LeftButton:
                    return
                if (e.pos() - value_label.drag_start_position).manhattanLength() < QApplication.startDragDistance(): # pyright: ignore[reportAttributeAccessIssue]
                    return
                
                # Create drag object
                drag = QDrag(value_label)
                mime_data = QMimeData()
                url = QUrl.fromLocalFile(value_label.text())
                mime_data.setUrls([url])
                drag.setMimeData(mime_data)
                drag.setPixmap(QPixmap())
                drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)
                
                if original_mouseMoveEvent:
                    original_mouseMoveEvent(e)
            value_label.mouseMoveEvent = mouseMoveEvent
        else:
            # Connect click signal to toggle height for non-draggable fields
            value_label.mousePressEvent = lambda e, vl=value_label: (
                self._toggle_value_height(vl)
            )

        # Copy button
        copy_button = QPushButton("📋")
        copy_button.setToolTip("Copy to clipboard")
        copy_button.setFixedSize(24, 24)
        copy_button.setStyleSheet("""
            QPushButton {
                background-color: #444444;
                border: 1px solid #555555;
                border-radius: 3px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #555555;
            }
        """)
        layout.addWidget(copy_button)

        # Connect copy button
        copy_button.clicked.connect(lambda: self._copy_to_clipboard(value_label.text()))

        # Store reference to value label using label text as key
        field_name = label_text.rstrip(":")
        self.field_labels[field_name] = value_label

        # Store reference to frame for showing/hiding
        self.field_frames[field_name] = frame

        # Add to field layouts list
        self.field_layouts.append(layout)

        # Set minimum size constraint if requested
        if set_minimum_size:
            layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinimumSize)

        # Add frame to grid
        grid_layout.addWidget(frame)

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy text to clipboard."""
        if text and text != "":
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            # Show visual feedback
            self._show_copy_feedback()

    def _show_copy_feedback(self) -> None:
        """Show visual feedback when text is copied."""
        # Change cursor to indicate success
        QApplication.setOverrideCursor(Qt.CursorShape.PointingHandCursor)
        QApplication.processEvents()
        QApplication.restoreOverrideCursor()

    def eventFilter(self, obj, event):
        """Event filter to handle drag and drop events.

        Args:
            obj: The object that received the event
            event: The event
        
        Returns:
            bool: True if the event was handled, False otherwise
        """
        # Handle drag leave events for draggable labels
        if event.type() == event.Type.DragLeave:
            # Reset drag start position when leaving the widget
            if hasattr(obj, 'drag_start_position'):
                obj.drag_start_position = None
        
        return super().eventFilter(obj, event)

    def _toggle_value_height(self, value_label: QLabel) -> None:
        """Toggle the maximum height of a value label between unlimited and compact height.

        Args:
            value_label: The QLabel whose height should be toggled.
        """
        current_max_height = value_label.maximumHeight()
        if current_max_height == self.COMPACT_TEXT_BOX_HEIGHT:
            # Expand to unlimited height
            value_label.setMaximumHeight(self.UNLIMITED_TEXT_BOX_HEIGHT)
        else:
            # Collapse to compact height
            value_label.setMaximumHeight(self.COMPACT_TEXT_BOX_HEIGHT)

    def set_metadata(self, metadata: Union[str, Dict[str, Any]]) -> None:
        """Set the metadata to display.

        Args:
            metadata (str or dict): The metadata text or dictionary to display.
        """
        if isinstance(metadata, dict):
            # Extract key values first
            extracted_values = self.metadata_handler.extract_values_from_metadata(
                metadata
            )

            # Update dedicated fields
            self._update_dedicated_fields(extracted_values)

            # Format full metadata as JSON
            formatted_json = json.dumps(metadata, indent=2)

            # Set full metadata in text edit
            self.metadata_text.setPlainText(formatted_json)
        else:
            # Treat as string
            self.metadata_text.setPlainText(metadata)

    def _update_dedicated_fields(self, extracted_values: Dict[str, Any]) -> None:
        """Update the dedicated GUI fields with extracted values.

        This method iterates through all field labels and updates them based on
        the extracted values. Special handling is provided for fields that need
        to check multiple keys (e.g., Prompt checks both 'prompt' and 'original_prompt').

        Fields with empty values are hidden, while fields with values are shown.
        """
        # Update each field
        for field_name in self.field_labels:
            # Get value using the handler
            value = self.metadata_handler.get_field_value(field_name, extracted_values)

            # Update the field
            self.field_labels[field_name].setText(value)

            # Show or hide the frame based on whether value is empty
            if field_name in self.field_frames:
                if value and str(value).strip():
                    self.field_frames[field_name].setEnabled(True)
                    self.field_frames[field_name].setVisible(True)
                else:
                    self.field_frames[field_name].setEnabled(False)
                    self.field_frames[field_name].setVisible(False)

    def load_file_metadata(self, file_path: str) -> None:
        """Load and display metadata from an image or video file.

        This method automatically detects whether the file is an image or video
        and delegates to the appropriate handler method.

        Args:
            file_path (str): Path to the image or video file.
        """
        metadata = self.metadata_handler.load_file_metadata(file_path)
        self.set_metadata(metadata)
