# Bowser - Image and Video Browser

## Introduction

Bowser is a desktop application for browsing, viewing, and managing image and video files typically from AI sources. Built with PySide6 (Qt for Python), Bowser provides a user-friendly interface with a dark mode theme for comfortable viewing. It has specific code to handle sidecar files and json metadata files produced by SwarmUI. Mainly done as a vibe coding exercise for funzies using Devstral2 24B small Q6 running locally with a 48K context under llamacpp.

### Features

- **Multi-panel interface**: Directory tree, thumbnail gallery, image/video viewer, and metadata display
- **Image support**: JPG, JPEG, PNG, BMP, GIF, TIFF, WEBP
- **Video support**: MP4, MOV, AVI, MKV, FLV
- **Dark mode**: Built-in dark theme for reduced eye strain
- **File management**: Mark and delete files, prune empty directories
- **Metadata viewing**: Display JSON metadata for files
- **Keyboard navigation**: Efficient keyboard shortcuts for navigation

### Installation

Bowser was tested on Python 3.12 and PySide6. uv used for package management with a pyproject.toml Then run the application:

```bash
python main.py [folder_path]
```

You can optionally provide a folder path as an argument to open it directly.

## Key Bindings

Bowser provides comprehensive keyboard shortcuts for efficient navigation and file management:

### Navigation

- **W**: Navigate to the previous folder in the directory tree
- **S**: Navigate to the next folder in the directory tree
- **A**: Navigate to the previous thumbnail in the gallery
- **D**: Navigate to the next thumbnail in the gallery
- **R**: Fit image to window (normal size)
- **1**: Display image at 1:1 scale (full size)
- **X**: Mark/unmark the current file for deletion

### Menu Shortcuts

- **Ctrl+O**: Open a folder (File > Open Folder)
- **Ctrl+D**: Delete all marked files (File > Delete Marked Files)
- **Ctrl+P**: Prune empty directories (File > Prune Empty Directories)
- **Ctrl+Q**: Exit the application (File > Exit)

### Video Controls

- **Play**: Start/resume video playback
- **Pause**: Pause video playback
- **-1**: Move to previous frame
- **+1**: Move to next frame
- **Capture Frame**: Capture and save the current video frame as PNG

## Usage

1. **Browse folders**: Use the directory tree on the left to navigate through your file system
2. **View thumbnails**: The gallery panel shows thumbnails of images and videos in the selected folder
3. **View content**: Click on a thumbnail to view the image or video in the main viewer panel
4. **Manage files**: Mark files with the "Mark File" button or keyboard shortcut (X), then delete them using Ctrl+D
5. **Clean up**: Use Ctrl+P to remove empty directories after deleting files

## File Marking System

Bowser includes a file marking system for batch operations:

1. Navigate to files you want to delete
2. Press **X** or click "Mark File" to mark them (they'll be highlighted in red)
3. Continue marking additional files
4. Press **Ctrl+D** to delete all marked files at once

This is useful for cleaning up large numbers of files efficiently.

## Video Frame Capture

When viewing videos, you can capture individual frames:

1. Play the video and navigate to the desired frame using the frame controls
2. Click "Capture Frame" button
3. The frame will be saved as a PNG file with a name like `video_name_frame_000123.png`

## Dark Mode

Bowser automatically applies a dark theme for comfortable viewing in low-light conditions. The theme includes:

- Dark backgrounds with high contrast
- Custom color schemes for different UI elements
- Special highlighting for marked files (red border)
- Distinct colors for images (green) and videos (purple)

## Development

Bowser is built with:
- **PySide6**: Qt bindings for Python
- **Qt Multimedia**: For video playback
- **Python 3.7+**: Core language

The codebase is organized into modules:
- `main.py`: Entry point and application setup
- `bowsermain.py`: Main window and UI management
- `directorytree.py`: Directory browsing widget
- `imagegallery.py`: Thumbnail gallery widget
- `imageviewer.py`: Image display widget
- `videoviewer.py`: Video playback widget
- `metadataviewer.py`: Metadata display widget

## License

This project is open source. See the LICENSE file for details.
