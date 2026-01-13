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
            metadata (str or dict): The metadata text or dictionary to display.
        """
        if isinstance(metadata, dict):
            # Format dictionary as JSON with indentation
            formatted_json = json.dumps(metadata, indent=2)
            self.setPlainText(formatted_json)
        else:
            # Treat as string
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
                metadata = {}
                metadata["File"] = os.path.basename(image_path)
                metadata["Format"] = img.format
                metadata["Size"] = f"{img.size[0]} x {img.size[1]} pixels"
                metadata["Mode"] = img.mode

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

                result = self.expandMetadata(metadata)
                # result = metadata
                self.setMetadata(result)

        except Exception as e:
            self.setMetadata(f"Error loading metadata: {str(e)}")

    def loadVideoMetadata(self, video_path):
        """Load and display metadata from a video file.

        Args:
            video_path (str): Path to the video file.
        """
        metadata = {}
        metadata["File"] = os.path.basename(video_path)
        metadata["Path"] = video_path

        # look for .swarm.json file
        swarm_json_path = os.path.splitext(video_path)[0] + ".swarm.json"
        if os.path.exists(swarm_json_path):
            try:
                with open(swarm_json_path, "r", encoding="utf-8") as f:
                    swarm_data = json.load(f)
                    metadata.update(swarm_data)
            except Exception as e:
                metadata["SwarmJSON"] = f"Error reading swarm.json: {str(e)}"

        try:
            # Pass the file path to TinyTag.get()
            tag = TinyTag.get(video_path)

            metadata.update(tag.as_dict())
            # print(tag.as_dict())

        except Exception as e:
            metadata["TinyTAG"] = f"An error occurred: {e}"

        result = self.expandMetadata(metadata)
        self.setMetadata(result)

    def expandMetadata(self, data, max_length=300):
        if isinstance(data, dict):
            # Recursively process each item and merge the results
            result = {}
            for key, value in data.items():
                result[key] = self.expandMetadata(value, max_length)
            return result
        elif isinstance(data, list):
            # Recursively process each item and merge the results
            result = []
            for value in data:
                result.append(self.expandMetadata(value, max_length))
            return result
        elif isinstance(data, (bytes, bytearray)):
            return "[Binary data]"
        elif isinstance(data, str):
            # Check if the string is itself a JSON structure
            try:
                # Try to parse as JSON
                parsed_value = json.loads(data)
                return self.expandMetadata(parsed_value)
            except (json.JSONDecodeError, TypeError):
                # If JSON parsing fails, treat as plain string
                value = data
                if len(data) > max_length:
                    value = data[:max_length] + "..."
                return value
        return data
