"""Utility functions and constants for the Bowser application.

This module provides common functionality used across multiple components,
including file operations, constants, and helper functions.

Key functionality:
- File format detection and validation
- Path manipulation for related files (Swarm metadata, preview images, frames)
- Directory operations (checking if empty, safe removal)
- File size formatting
- Constants for supported file formats and default settings
"""

import os
import time
from typing import List, Tuple

# File format constants
SUPPORTED_IMAGE_EXTENSIONS: List[str] = [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"]

SUPPORTED_VIDEO_EXTENSIONS: List[str] = [".mp4", ".mov", ".avi", ".mkv", ".flv"]

ALL_SUPPORTED_EXTENSIONS: List[str] = SUPPORTED_IMAGE_EXTENSIONS + SUPPORTED_VIDEO_EXTENSIONS

# Default values
DEFAULT_THUMBNAIL_SIZE: Tuple[int, int] = (192, 192)
DEFAULT_FRAME_RATE: float = 30.0
DEFAULT_VOLUME: int = 100
MAX_PROCESSES: int = 8
PROCESSING_CHUNK_SIZE: int = 24

def numpy_to_qimage(image_array):
    """
    Converts a 2D or 3D numpy array to a QImage.
    Assumes uint8 data type and 'C' memory order.
    """
    height, width = image_array.shape[:2]

    if len(image_array.shape) == 2:
        # Grayscale image
        bytes_per_line = width
        # Ensure array is contiguous in memory
        image_array = np.require(image_array, np.uint8, "C")
        q_image_format = QImage.Format.Format_Grayscale8

        q_image = QImage(
            image_array.data, width, height, bytes_per_line, q_image_format
        )

    elif len(image_array.shape) == 3 and image_array.shape[2] == 3:
        # RGB image
        bytes_per_line = 3 * width
        # OpenCV reads in BGR, so swap to RGB
        # If your array is already RGB, skip the swap
        image_array = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)
        image_array = np.require(image_array, np.uint8, "C")
        q_image_format = QImage.Format.Format_RGB888
        q_image = QImage(
            image_array.data, width, height, bytes_per_line, q_image_format
        )

    elif len(image_array.shape) == 3 and image_array.shape[2] == 4:
        # RGBA image
        bytes_per_line = 4 * width
        image_array = np.require(image_array, np.uint8, "C")
        q_image_format = QImage.Format.Format_RGBA8888
        q_image = QImage(
            image_array.data, width, height, bytes_per_line, q_image_format
        )

    else:
        raise ValueError("Unsupported NumPy array shape or number of channels")

    return q_image



# extract GPU number from COmfyUI device string
def get_gpu_from_device_string(device: str) -> str:
    gpu = "N/A"
    if isinstance(device, str):
        # Look for common GPU patterns like 3090, 5080, 4070, etc. in device
        # Make sure it occurs after RTX, should work with a string like
        # "cuda:0 NVIDIA GeForce RTX 3090 : cudaMallocAsync" -> 3090
        import re

        # First try to match GPU model numbers that follow RTX or GTX
        gpu_match = re.search(
            r"(RTX|GTX)\s+(\b(30[0-9]{2}|40[0-9]{2}|50[0-9]{2}|60[0-9]{2}|70[0-9]{2}|80[0-9]{2}|90[0-9]{2}|10[0-9]{2}|20[0-9]{2}|16[0-9]{2}|24[0-9]|A[0-9]{4})\b)",
            device,
            re.IGNORECASE,
        )
        if gpu_match:
            gpu = gpu_match.group(2)
        else:
            # Fallback: try to match standalone GPU model numbers
            gpu_match = re.search(
                r"\b(30[0-9]{2}|40[0-9]{2}|50[0-9]{2}|60[0-9]{2}|70[0-9]{2}|80[0-9]{2}|90[0-9]{2}|10[0-9]{2}|20[0-9]{2}|16[0-9]{2}|24[0-9]|A[0-9]{4}|RTX|GTX)\b",
                device,
                re.IGNORECASE,
            )
            if gpu_match:
                gpu = gpu_match.group(0)
    return gpu


# return true if it is a valid int
def check_int(s: str) -> bool:
    if s[0] in ("-", "+"):
        return s[1:].isdigit()
    return s.isdigit()


def replace_variables_in_string(input: str) -> str:
    now = time.localtime()
    input = input.replace("%year%", str(now.tm_year))
    input = input.replace("%month%", str(now.tm_mon).zfill(2))
    input = input.replace("%day%", str(now.tm_mday).zfill(2))
    input = input.replace("%hour%", str(now.tm_hour).zfill(2))
    input = input.replace("%minute%", str(now.tm_min).zfill(2))
    input = input.replace("%second%", str(now.tm_sec).zfill(2))
    return input


def get_file_extension(file_path: str) -> str:
    """Get the file extension in lowercase.

    This function extracts the file extension from a given file path and returns it
    in lowercase format. The extension includes the dot (e.g., '.jpg', '.png').

    Args:
        file_path (str): Path to the file.

    Returns:
        str: File extension in lowercase, including the dot.

    Example:
        >>> get_file_extension("/path/to/image.JPG")
        '.jpg'
    """
    return os.path.splitext(file_path)[1].lower()


def is_image_file(file_path: str) -> bool:
    """Check if a file is an image file.

    Args:
        file_path (str): Path to the file.

    Returns:
        bool: True if the file has an image extension, False otherwise.
    """
    ext = get_file_extension(file_path)
    return ext in SUPPORTED_IMAGE_EXTENSIONS


def is_video_file(file_path: str) -> bool:
    """Check if a file is a video file.

    Args:
        file_path (str): Path to the file.

    Returns:
        bool: True if the file has a video extension, False otherwise.
    """
    ext = get_file_extension(file_path)
    return ext in SUPPORTED_VIDEO_EXTENSIONS


def is_supported_file(file_path: str) -> bool:
    """Check if a file has a supported extension.

    Args:
        file_path (str): Path to the file.

    Returns:
        bool: True if the file has a supported extension, False otherwise.
    """
    ext = get_file_extension(file_path)
    return ext in ALL_SUPPORTED_EXTENSIONS


def get_swarm_preview_path(image_path: str) -> str:
    """Get the path to the corresponding Swarm preview image.

    Args:
        image_path (str): Path to the original image file.

    Returns:
        str: Path to the Swarm preview image (with .swarmpreview.jpg extension).
    """
    base_name = os.path.splitext(image_path)[0]
    return f"{base_name}.swarmpreview.jpg"


def get_swarm_json_path(file_path: str) -> str:
    """Get the path to the corresponding Swarm JSON metadata file.

    Args:
        file_path (str): Path to the original file.

    Returns:
        str: Path to the Swarm JSON metadata file (with .swarm.json extension).
    """
    base_name = os.path.splitext(file_path)[0]
    return f"{base_name}.swarm.json"


def get_frame_filename(video_path: str, frame_number: int) -> str:
    """Generate a filename for a captured video frame.

    Args:
        video_path (str): Path to the video file.
        frame_number (int): Frame number to include in the filename.

    Returns:
        str: Generated frame filename with format: video_name_frame_000123.png
    """
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    return f"{base_name}_frame_{frame_number:06d}.png"


def get_base_filename(file_path: str) -> str:
    """Get the base filename without extension.

    Args:
        file_path (str): Path to the file.

    Returns:
        str: Base filename without extension.
    """
    return os.path.splitext(os.path.basename(file_path))[0]


def is_directory_empty(directory: str) -> bool:
    """Check if a directory is empty (no files or subdirectories).

    This function considers a directory empty if it contains only:
    - Hidden directories (starting with .)
    - Swarm metadata files (swarm_metadata.ldb, swarm_metadata-log.ldb)

    Args:
        directory (str): Path to the directory to check.

    Returns:
        bool: True if the directory is empty, False otherwise.

    Note:
        This function handles permission errors gracefully by considering
        inaccessible directories as non-empty to prevent accidental data loss.
    """
    try:
        # Check if directory exists and is readable
        if not os.path.exists(directory):
            return True

        # List all entries in the directory
        with os.scandir(directory) as entries:
            for entry in entries:
                # Skip special directories
                if entry.name.startswith(".") and entry.is_dir():
                    continue
                # Skip swarm metadata files
                if entry.name in [
                    "swarm_metadata.ldb",
                    "swarm_metadata-log.ldb",
                ]:
                    continue
                return False
        return True
    except (OSError, PermissionError):
        # If we can't access the directory, consider it non-empty
        return False


def safe_remove_file(file_path: str) -> bool:
    """Safely remove a file with error handling.

    Args:
        file_path (str): Path to the file to remove.

    Returns:
        bool: True if the file was successfully removed, False otherwise.
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
    except (OSError, PermissionError) as e:
        print(f"Error removing {file_path}: {e}")
        return False
    return False


def get_file_size(file_path: str) -> int:
    """Get the size of a file in bytes.

    Args:
        file_path (str): Path to the file.

    Returns:
        int: File size in bytes, or 0 if file doesn't exist or error occurs.
    """
    try:
        if os.path.exists(file_path):
            return os.path.getsize(file_path)
    except (OSError, PermissionError):
        pass
    return 0


def format_file_size(bytes_size: int) -> str:
    """Format file size in human-readable format.

    Args:
        bytes_size (int): File size in bytes.

    Returns:
        str: Formatted file size (e.g., "1.2 MB", "42 KB").
    """
    if bytes_size == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while bytes_size >= 1024 and i < len(size_names) - 1:
        bytes_size = int(bytes_size / 1024)
        i += 1

    return f"{bytes_size:.1f} {size_names[i]}"
