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

# File format constants
SUPPORTED_IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"]

SUPPORTED_VIDEO_EXTENSIONS = [".mp4", ".mov", ".avi", ".mkv", ".flv"]

ALL_SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS + SUPPORTED_VIDEO_EXTENSIONS

# Default values
DEFAULT_THUMBNAIL_SIZE = (192, 192)
DEFAULT_FRAME_RATE = 30.0
DEFAULT_VOLUME = 100
MAX_PROCESSES = 8
PROCESSING_CHUNK_SIZE = 24


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
