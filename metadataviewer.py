"""Metadata viewer widget for displaying image and video metadata."""

import json
import os

from PIL import Image
from PIL.ExifTags import TAGS
from PySide6.QtWidgets import QTextEdit
from tinytag import TinyTag


class MetadataViewer(QTextEdit):
    """A widget for displaying metadata information."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("JSON Metadata will appear here...")
        self.setStyleSheet("border: 1px solid gray;")

    def setMetadata(self, metadata):
        """Set the metadata to display.

        Args:
            metadata (str): The metadata text to display.
        """
        self.setPlainText(metadata)

    def loadFileMetadata(self, file_path):
        """Load and display metadata from an image or video file.

        Args:
            file_path (str): Path to the image or video file.
        """
        if not os.path.exists(file_path):
            self.setMetadata(f"Error: File not found - {file_path}")
            return

        # Check file extension to determine handler
        file_ext = os.path.splitext(file_path)[1].lower()

        if file_ext in [".mp4", ".mov", ".avi", ".mkv", ".flv"]:
            self.loadVideoMetadata(file_path)
        else:
            self.loadImageMetadata(file_path)

    def loadImageMetadata(self, image_path):
        """Load and display metadata from an image file (original implementation).

        Args:
            image_path (str): Path to the image file.
        """
        if not os.path.exists(image_path):
            self.setMetadata(f"Error: File not found - {image_path}")
            return

        try:
            with Image.open(image_path) as img:
                # Get basic image info
                metadata_lines = []
                metadata_lines.append(f"File: {os.path.basename(image_path)}")
                metadata_lines.append(f"Format: {img.format}")
                metadata_lines.append(f"Size: {img.size[0]} x {img.size[1]} pixels")
                metadata_lines.append(f"Mode: {img.mode}")

                # Get EXIF data
                if hasattr(img, "_getexif"):
                    exif_data = img.getexif()
                    if exif_data is not None:
                        metadata_lines.append("\nEXIF Data:")
                        for tag_id, value in exif_data.items():
                            tag_name = TAGS.get(tag_id, tag_id)
                            metadata_lines.append(f"  {tag_name}: {value}")

                # Get all metadata (including non-EXIF)
                all_metadata = img.info
                ai_metadata = None
                if all_metadata:
                    metadata_lines.append("\nAll Metadata:")
                    for key, value in all_metadata.items():
                        if key == "parameters":
                            ai_metadata = value
                        # Skip binary data and large values
                        elif (
                            isinstance(value, (bytes, bytearray))
                            or len(str(value)) > 200
                        ):
                            metadata_lines.append(
                                f"  {key}: [Binary data or large value]"
                            )
                        else:
                            metadata_lines.append(f"  {key}: {value}")

                # Display AI-specific metadata
                if ai_metadata:
                    metadata_lines.append("\nAI Generation Info:")
                    try:
                        # Try to parse as JSON if it's a string
                        if isinstance(ai_metadata, str):
                            parsed_metadata = json.loads(ai_metadata)
                            formatted_json = json.dumps(parsed_metadata, indent=2)
                            metadata_lines.append(f"\n{formatted_json}")
                        else:
                            # If it's already a dict, format it as JSON
                            formatted_json = json.dumps(ai_metadata, indent=2)
                            metadata_lines.append(f"\n{formatted_json}")
                    except (json.JSONDecodeError, TypeError):
                        # If JSON parsing fails, display as plain text
                        metadata_lines.append(f"\n{ai_metadata}")

                self.setMetadata("\n".join(metadata_lines))

        except Exception as e:
            self.setMetadata(f"Error loading metadata: {str(e)}")

    def _truncate_long_strings(self, data, max_length=100):
        """Recursively traverse a dictionary and truncate long strings.

        Args:
            data: Dictionary, list, or string to process
            max_length: Maximum length for strings before truncation

        Returns:
            Processed data with long strings truncated
        """
        if isinstance(data, dict):
            return {
                key: self._truncate_long_strings(value, max_length)
                for key, value in data.items()
            }
        elif isinstance(data, list):
            return [self._truncate_long_strings(item, max_length) for item in data]
        elif isinstance(data, str) and len(data) > max_length:
            return data[:max_length] + "..."
        else:
            return data

    def loadVideoMetadata(self, video_path):
        """Load and display metadata from a video file.

        Args:
            video_path (str): Path to the video file.
        """
        metadata_lines = []
        metadata_lines.append(f"File: {os.path.basename(video_path)}")
        metadata_lines.append(f"Path: {video_path}")

        # look for .swarm.json file
        swarm_json_path = os.path.splitext(video_path)[0] + ".swarm.json"
        if os.path.exists(swarm_json_path):
            metadata_lines.append(
                f"\nSwarm JSON File Found: {os.path.basename(swarm_json_path)}"
            )
            try:
                with open(swarm_json_path, "r", encoding="utf-8") as f:
                    swarm_data = json.load(f)
                formatted_json = json.dumps(swarm_data, indent=2)
                metadata_lines.append(f"\nSwarm JSON Content:\n{formatted_json}")
            except Exception as e:
                metadata_lines.append(f"Error reading swarm.json: {str(e)}")

        metadata_lines.append("\nVideo Metadata:")

        try:
            # Pass the file path to TinyTag.get()
            tag = TinyTag.get(video_path)

            # print(tag.as_dict())

            # If it's already a dict, format it as JSON
            # formatted_json = json.dumps(tag.as_dict(), indent=2)
            # metadata_lines.append(f"\n{formatted_json}")

            if tag.comment:
                parsed_metadata = json.loads(tag.comment)
                # Truncate long strings in the parsed metadata
                parsed_metadata = self._truncate_long_strings(parsed_metadata)
                formatted_json = json.dumps(parsed_metadata, indent=2)
                metadata_lines.append(f"\n{formatted_json}")
            else:
                metadata_lines.append("\nNo metadata found in comment field")

        except Exception as e:
            print(f"An error occurred: {e}")

        # metadata_lines.append(f"  {attr_name}: {value}")

        self.setMetadata("\n".join(metadata_lines))
