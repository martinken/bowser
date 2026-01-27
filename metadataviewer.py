"""Metadata viewer widget for displaying image and video metadata.

This module provides a widget for displaying structured metadata from
images (EXIF, IPTC) and videos, with support for JSON formatting and
sidecar metadata files.
"""

import json
import os

from PIL import Image
from PIL.ExifTags import TAGS
from PySide6.QtWidgets import QTextEdit
from tinytag import TinyTag

from utils import (
    get_swarm_json_path,
    is_video_file,
)


class MetadataViewer(QTextEdit):
    """A widget for displaying structured metadata information.

    Features include:
    - Display of EXIF data from images (using PIL)
    - Display of metadata from videos (using tinytag)
    - Support for sidecar JSON files (e.g., SwarmUI .swarm.json files)
    - Formatted JSON output with indentation
    - Error handling for corrupted or missing metadata
    - Automatic detection of image vs video files
    """

    def __init__(self, parent=None):
        """Initialize the MetadataViewer widget.

        Args:
            parent: Parent widget (optional).
        """
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
            # Extract key values first
            extracted_values = self._extract_values_from_metadata(metadata)

            # Format extracted values as Key: Value pairs
            if extracted_values:
                extracted_text = "\n".join(
                    f"{key}: {value}" for key, value in extracted_values.items()
                )
            else:
                extracted_text = "No extracted values found"

            # Format full metadata as JSON
            formatted_json = json.dumps(metadata, indent=2)

            # Combine extracted values and full metadata
            combined_text = (
                f"{extracted_text}\n\n=== FULL METADATA ===\n{formatted_json}"
            )
            self.setPlainText(combined_text)
        else:
            # Treat as string
            self.setPlainText(metadata)

    def loadFileMetadata(self, file_path):
        """Load and display metadata from an image or video file.

        This method automatically detects whether the file is an image or video
        and delegates to the appropriate handler method.

        Args:
            file_path (str): Path to the image or video file.
        """
        if not os.path.exists(file_path):
            self.setMetadata(f"Error: File not found - {file_path}")
            return

        # Check file extension to determine handler
        if is_video_file(file_path):
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
        swarm_json_path = get_swarm_json_path(video_path)
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

    def expandMetadata(self, data, max_length=1000):
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

    def _extract_values_from_metadata(self, metadata):
        values_to_extract = [
            "File",
            "seed",
            "Size",
            "model",
            "generation_time",
            "prompt",
            "original_prompt",
            "initimage_filename",
            "filename",
            "variationseed",
            "steps",
            "frames",
            "overlap",
            "trimstartframes",
            "trimendframes",
            "myvideo_filename",
            "Path",
        ]

        extracted_values = {}

        # Traverse the metadata looking for values_to_extract
        # when found extract them and store them as Key value pairs
        # in extracted_values
        self._traverse_and_extract(metadata, values_to_extract, extracted_values)

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
                if key in keys_to_find and key not in extracted_values:
                    extracted_values[key] = value
                # Recursively traverse the value
                self._traverse_and_extract(value, keys_to_find, extracted_values)
        elif isinstance(data, list):
            # Traverse each item in the list
            for item in data:
                self._traverse_and_extract(item, keys_to_find, extracted_values)
        # For primitive types (str, int, float, etc.), do nothing
