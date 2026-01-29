"""Main entry point for Bowser - Image and Video Browser.

This module initializes the Qt application and creates the main window.

The Bowser application is a desktop tool for browsing, viewing, and managing
image and video files with special support for AI-generated content and SwarmUI metadata.

Key Features:
    - Multi-panel interface with directory tree, thumbnail gallery, image/video viewer, and metadata display
    - Support for various image formats (JPG, JPEG, PNG, BMP, GIF, TIFF, WEBP)
    - Video playback with frame-by-frame navigation (MP4, MOV, AVI, MKV, FLV)
    - Dark mode theme for comfortable viewing
    - File management system with marking and batch deletion
    - Parallel thumbnail loading for improved performance
    - Metadata viewing including EXIF and JSON sidecar files
    - Keyboard shortcuts for efficient navigation

Usage:
    python main.py [folder_path]

Where [folder_path] is an optional path to a folder or file to open initially.

Example:
    python main.py /path/to/images
    python main.py image.jpg
"""

import sys
from argparse import ArgumentParser, RawTextHelpFormatter

from PySide6.QtWidgets import QApplication

from .viewmain import ViewMain


def main() -> int:
    """Main function to launch the Bowser application.

    Parses command line arguments, initializes the Qt application,
    and creates the main window.

    The application provides a multi-panel interface with:
    - Directory tree for folder navigation
    - Thumbnail gallery for image/video browsing
    - Image/video viewer for detailed viewing
    - Metadata display for EXIF and JSON metadata

    Returns:
        int: Exit code from the Qt application (0 for success).
    """
    # Parse command line arguments
    arg_parser = ArgumentParser(
        description="Bowser - Image and Video Browser",
        formatter_class=RawTextHelpFormatter,
    )
    arg_parser.add_argument(
        "file", type=str, nargs="?", help="Image file or folder to open initially"
    )
    args = arg_parser.parse_args()

    # Initialize Qt application
    app = QApplication(sys.argv)

    # Create main window with optional folder path
    folder_path = args.file if args.file else None
    main_window = ViewMain(folder_path=folder_path)

    # Show the main window and start the application
    main_window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
