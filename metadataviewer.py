"""Metadata viewer widget for displaying image and video metadata.

This module provides a widget for displaying structured metadata from
images (EXIF, IPTC) and videos, with support for JSON formatting and
sidecar metadata files.
"""

import json
import os

from PIL import Image
from PIL.ExifTags import TAGS
from PySide6.QtCore import Qt
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

# from tinytag import TinyTag
from utils import (
    get_swarm_json_path,
    is_video_file,
)


class MetadataViewer(QWidget):
    """A widget for displaying structured metadata information.

    Features include:
    - Display of EXIF data from images (using PIL)
    - Display of metadata from videos (using tinytag)
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

    # Class constant for field configuration
    field_config = {
        "Seed": {"keys": ["seed"], "default": "", "convert": str},
        "File": {"keys": ["file"], "default": ""},
        "InImage": {
            "keys": ["myimage_filename", "initimage_filename"],
            "default": "",
        },
        "InVideo": {"keys": ["myvideo_filename"], "default": ""},
        "Size": {"keys": ["size"], "default": ""},
        "Steps": {"keys": ["steps"], "default": "", "convert": str},
        "CFG": {"keys": ["cfgscale"], "default": "", "convert": str},
        "Model": {"keys": ["model"], "default": ""},
        "Time": {"keys": ["generation_time"], "default": "", "convert": str},
        "Prompt": {"keys": ["prompt"], "default": ""},
        "Prompt2": {"keys": ["original_prompt"], "default": ""},
        "Guidance": {
            "keys": ["fluxguidance", "fluxguidance_scale"],
            "default": "",
            "convert": str,
        },
    }

    def __init__(self, parent=None):
        """Initialize the MetadataViewer widget.

        Args:
            parent: Parent widget (optional).
        """
        super().__init__(parent)

        # Initialize field labels dictionary early
        self.field_labels = {}

        # Initialize field frames dictionary for showing/hiding
        self.field_frames = {}

        # Build values_to_extract from field_config keys
        self.values_to_extract = []
        for field_config_dict in self.field_config.values():
            self.values_to_extract.extend(field_config_dict["keys"])

        # Add additional keys needed for Size construction
        self.values_to_extract.extend(
            [
                "aspect",
                "aspectratio",
                "frames",
                "height",
                "initimage_resolution",
                "myimage_resolution",
                "myvideo_resolution",
                "width",
            ]
        )

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
        self, label_text, initial_value, grid_layout, set_minimum_size=False
    ):
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
        value_label.setMaximumHeight(69)
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

        # Connect click signal to toggle height
        value_label.mousePressEvent = (
            lambda e, vl=value_label: self._toggle_value_height(vl)
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

    def _copy_to_clipboard(self, text):
        """Copy text to clipboard."""
        if text and text != "":
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            # Show visual feedback
            self._show_copy_feedback()

    def _show_copy_feedback(self):
        """Show visual feedback when text is copied."""
        # Change cursor to indicate success
        QApplication.setOverrideCursor(Qt.CursorShape.PointingHandCursor)
        QApplication.processEvents()
        QApplication.restoreOverrideCursor()

    def _toggle_value_height(self, value_label):
        """Toggle the maximum height of a value label between unlimited and 69 pixels.

        Args:
            value_label: The QLabel whose height should be toggled.
        """
        current_max_height = value_label.maximumHeight()
        if current_max_height == 69:
            # Expand to unlimited height
            value_label.setMaximumHeight(16777215)  # Maximum possible value for int
        else:
            # Collapse to 69 pixels
            value_label.setMaximumHeight(69)

    def set_metadata(self, metadata):
        """Set the metadata to display.

        Args:
            metadata (str or dict): The metadata text or dictionary to display.
        """
        if isinstance(metadata, dict):
            # Extract key values first
            extracted_values = self._extract_values_from_metadata(metadata)

            # Update dedicated fields
            self._update_dedicated_fields(extracted_values)

            # Format full metadata as JSON
            formatted_json = json.dumps(metadata, indent=2)

            # Set full metadata in text edit
            self.metadata_text.setPlainText(formatted_json)
        else:
            # Treat as string
            self.metadata_text.setPlainText(metadata)

    def _update_dedicated_fields(self, extracted_values):
        """Update the dedicated GUI fields with extracted values.

        This method iterates through all field labels and updates them based on
        the extracted values. Special handling is provided for fields that need
        to check multiple keys (e.g., Prompt checks both 'prompt' and 'original_prompt').

        Fields with empty values are hidden, while fields with values are shown.
        """
        # Update each field
        for field_name, config in self.field_config.items():
            if field_name in self.field_labels:
                # Try to get value from any of the configured keys
                value = ""
                for key in config["keys"]:
                    if key in extracted_values and extracted_values[key]:
                        value = extracted_values[key]
                        break

                # Apply conversion if specified
                if "convert" in config and value:
                    value = config["convert"](value)

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

    def load_file_metadata(self, file_path):
        """Load and display metadata from an image or video file.

        This method automatically detects whether the file is an image or video
        and delegates to the appropriate handler method.

        Args:
            file_path (str): Path to the image or video file.
        """
        if not os.path.exists(file_path):
            self.set_metadata(f"Error: File not found - {file_path}")
            return

        # Check file extension to determine handler
        if is_video_file(file_path):
            self._load_video_metadata(file_path)
        else:
            self._load_image_metadata(file_path)

    def _load_image_metadata(self, image_path):
        """Load and display metadata from an image file (original implementation).

        Args:
            image_path (str): Path to the image file.
        """
        if not os.path.exists(image_path):
            self.set_metadata(f"Error: File not found - {image_path}")
            return

        try:
            with Image.open(image_path) as img:
                # Get basic image info
                metadata = {}
                metadata["file"] = os.path.basename(image_path)
                metadata["format"] = img.format
                metadata["width"] = img.size[0]
                metadata["height"] = img.size[1]
                metadata["mode"] = img.mode

                # Get EXIF data
                if hasattr(img, "_getexif"):
                    exif_data = img.getexif()
                    exif_result = {}
                    if exif_data is not None:
                        for tag_id, value in exif_data.items():
                            tag_name = TAGS.get(tag_id, tag_id)
                            exif_result[tag_name] = {value}
                    metadata["EXIF"] = exif_result

                # Get all metadata (including non-EXIF)
                all_metadata = img.info
                if all_metadata:
                    other_data = {}
                    for key, value in all_metadata.items():
                        # Skip binary data
                        if isinstance(value, (bytes, bytearray)):
                            other_data[key] = "[Binary data]"
                        else:
                            other_data[key] = value
                    metadata["Other Data"] = other_data

                result = self._expand_metadata(metadata)
                # result = metadata
                self.set_metadata(result)

        except Exception as e:
            self.set_metadata(f"Error loading metadata: {str(e)}")

    def _load_video_metadata(self, video_path):
        """Load and display metadata from a video file.

        Args:
            video_path (str): Path to the video file.
        """
        metadata = {}
        metadata["File"] = os.path.basename(video_path)
        metadata["Path"] = video_path

        # look for .swarm.json file
        swarm_json_path = get_swarm_json_path(video_path)
        if os.path.exists(swarm_json_path):
            try:
                with open(swarm_json_path, "r", encoding="utf-8") as f:
                    swarm_data = json.load(f)
                    metadata.update(swarm_data)
            except Exception as e:
                metadata["SwarmJSON"] = f"Error reading swarm.json: {str(e)}"

        # try:
        #     # Pass the file path to TinyTag.get()
        #     tag = TinyTag.get(video_path)

        #     metadata.update(tag.as_dict())
        #     # print(tag.as_dict())

        # except Exception as e:
        #     metadata["TinyTAG"] = f"An error occurred: {e}"

        result = self._expand_metadata(metadata)
        self.set_metadata(result)

    def _expand_metadata(self, data, max_length=1000):
        if isinstance(data, dict):
            # Recursively process each item and merge the results
            result = {}
            for key, value in data.items():
                result[key] = self._expand_metadata(value, max_length)
            return result
        elif isinstance(data, list):
            # Recursively process each item and merge the results
            result = []
            for value in data:
                result.append(self._expand_metadata(value, max_length))
            return result
        elif isinstance(data, (bytes, bytearray)):
            return "[Binary data]"
        elif isinstance(data, str):
            # Check if the string is itself a JSON structure
            try:
                # Try to parse as JSON
                parsed_value = json.loads(data)
                return self._expand_metadata(parsed_value)
            except (json.JSONDecodeError, TypeError):
                # If JSON parsing fails, treat as plain string
                value = data
                if len(data) > max_length:
                    value = data[:max_length] + "..."
                return value
        return data

    def _extract_values_from_metadata(self, metadata):
        extracted_values = {}

        # Traverse the metadata looking for values_to_extract
        # when found extract them and store them as Key value pairs
        # in extracted_values
        self._traverse_and_extract(metadata, self.values_to_extract, extracted_values)

        # Clean and enhance extracted values (e.g., build Size from width/height/frames)
        self._clean_extracted_values(extracted_values)

        return extracted_values

    def _traverse_and_extract(self, data, keys_to_find, extracted_values):
        """Recursively traverse metadata and extract specific key-value pairs.

        Args:
            data: The metadata to traverse (can be dict, list, or primitive)
            keys_to_find: List of keys to extract
            extracted_values: Dictionary to store extracted key-value pairs
        """
        if isinstance(data, dict):
            for key, value in data.items():
                # Check if this key is in our list of keys to extract
                if key.lower() in keys_to_find and key not in extracted_values:
                    extracted_values[key.lower()] = value
                # Recursively traverse the value
                self._traverse_and_extract(value, keys_to_find, extracted_values)
        elif isinstance(data, list):
            # Traverse each item in the list
            for item in data:
                self._traverse_and_extract(item, keys_to_find, extracted_values)
        # For primitive types (str, int, float, etc.), do nothing

    def _clean_extracted_values(self, extracted_values):
        """Clean and enhance extracted values, particularly for the Size field.

        This method constructs a human-readable Size string based on available
        metadata fields like width, height, frames, and aspectratio.

        Args:
            extracted_values: Dictionary of extracted metadata values
        """
        # Build Size string from available components if not already set
        if "size" not in extracted_values:
            size_parts = []

            # Add dimensions if available
            if "width" in extracted_values and "height" in extracted_values:
                width = extracted_values["width"]
                height = extracted_values["height"]
                size_parts.append(f"{width}×{height}")
            elif "initimage_resolution" in extracted_values:
                size_parts.append(f"{extracted_values['initimage_resolution']}")
            elif "myimage_resolution" in extracted_values:
                size_parts.append(f"{extracted_values['myimage_resolution']}")
            elif "myvideo_resolution" in extracted_values:
                size_parts.append(f"{extracted_values['myvideo_resolution']}")

            # Add aspect ratio if available
            if "aspectratio" in extracted_values:
                size_parts.append(f"{extracted_values['aspectratio']}")
            elif "aspect" in extracted_values:
                size_parts.append(f"{extracted_values['aspect']}")

            # Add frames if available (typically for videos)
            if "frames" in extracted_values:
                size_parts.append(f" {extracted_values['frames']}f")
            # Join all parts with spaces
            extracted_values["size"] = " ".join(size_parts)
