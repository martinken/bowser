import json
import os

from PIL import Image
from PIL.ExifTags import TAGS

from .utils import (
    get_swarm_json_path,
    is_video_file,
)


class MetadataHandler:
    """A non-GUI handler for metadata processing and extraction.

    This class handles all the non-GUI logic for loading, extracting,
    and processing metadata from images and videos.
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
        "CFG": {"keys": ["cfg", "cfgscale"], "default": "", "convert": str},
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

    def __init__(self):
        """Initialize the MetadataHandler."""
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

    @classmethod
    def flatten(cls, adict):
        results = {}
        for key, value in adict.items():
            if type(value) is dict:
                results = results | cls.flatten(value)
            else:
                results[key] = value
        return results

    @classmethod
    def find_metadata_for_key(cls, input_key, values):
        key = input_key.lower().replace(" ", "")

        # Try to match metadata values to node widgets
        # First, try exact title match
        if key in values:
            return values[key]

        # Try alternative matches based on common field names
        if key == "cfg" and "cfgscale" in values:
            return values["cfgscale"]

        if key == "initimage" and "initimage_filename" in values:
            return values["initimage_filename"]

        return None

    def load_file_metadata(self, file_path):
        """Load and process metadata from an image or video file.

        This method automatically detects whether the file is an image or video
        and delegates to the appropriate handler method.

        Args:
            file_path (str): Path to the image or video file.

        Returns:
            dict: The processed metadata dictionary, or None if error occurred.
        """
        if not os.path.exists(file_path):
            return {"error": f"File not found - {file_path}"}

        # Check file extension to determine handler
        if is_video_file(file_path):
            return self._load_video_metadata(file_path)
        else:
            return self._load_image_metadata(file_path)

    def _load_image_metadata(self, image_path):
        """Load and process metadata from an image file.

        Args:
            image_path (str): Path to the image file.

        Returns:
            dict: The processed metadata dictionary.
        """
        if not os.path.exists(image_path):
            return {"error": f"File not found - {image_path}"}

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
                        # Skip binary data and sets
                        if isinstance(value, (bytes, bytearray)):
                            other_data[key] = "[Binary data]"
                        else:
                            other_data[key] = value
                    metadata["Other Data"] = other_data

                return self._expand_metadata(metadata)

        except Exception as e:
            return {"error": f"Error loading metadata: {str(e)}"}

    def _load_video_metadata(self, video_path):
        """Load and process metadata from a video file.

        Args:
            video_path (str): Path to the video file.

        Returns:
            dict: The processed metadata dictionary.
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

        return self._expand_metadata(metadata)

    def _expand_metadata(self, data, max_length=1000):
        """Recursively expand and normalize metadata structures.

        This method handles nested structures, sets, lists, and strings,
        converting them to a consistent dictionary format.

        Args:
            data: The metadata to expand (can be dict, list, set, str, etc.)
            max_length: Maximum length for string values

        Returns:
            dict: Expanded metadata
        """
        if isinstance(data, dict):
            # Recursively process each item and merge the results
            result = {}
            for key, value in data.items():
                result[key] = self._expand_metadata(value, max_length)
            return result
        elif isinstance(data, list):
            # if just one value use it directly
            if len(data) == 1:
                return self._expand_metadata(data[0], max_length)
            # Recursively process each item and merge the results
            result = {}
            for i, value in enumerate(data):
                result[i] = self._expand_metadata(value, max_length)
            return result
        elif isinstance(data, set):
            # if just one value use it directly
            if len(data) == 1:
                return self._expand_metadata(next(iter(data), None), max_length)
            # Recursively process each item and merge the results
            result = {}
            for i, value in enumerate(data):
                result[i] = self._expand_metadata(value, max_length)
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
        elif isinstance(data, int) or isinstance(data, float):
            return data
        return str(data)

    def extract_values_from_metadata(self, metadata):
        """Extract specific values from metadata for display in dedicated fields.

        Args:
            metadata (dict): The metadata dictionary to extract values from.

        Returns:
            dict: Dictionary of extracted values with keys matching values_to_extract.
        """
        extracted_values = {}

        # Traverse the metadata looking for values_to_extract
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
                key = str(key)
                # Check if this key is in our list of keys to extract
                if key.lower() in keys_to_find and key not in extracted_values:
                    extracted_values[key.lower()] = str(value)
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

    def get_field_value(self, field_name, extracted_values):
        """Get the value for a specific field based on configuration.

        Args:
            field_name (str): The field name (e.g., 'Seed', 'Prompt')
            extracted_values (dict): The extracted metadata values

        Returns:
            str: The field value, or empty string if not found.
        """
        if field_name not in self.field_config:
            return ""

        config = self.field_config[field_name]
        value = ""

        # Try to get value from any of the configured keys
        for key in config["keys"]:
            if key in extracted_values and extracted_values[key]:
                value = extracted_values[key]
                break

        # Apply conversion if specified
        if "convert" in config and value:
            value = config["convert"](value)

        return value
