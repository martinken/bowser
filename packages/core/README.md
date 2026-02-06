# Core Package

A PySide6-based library providing UI components and utilities for image and video viewing, metadata handling, and gallery management.

## Overview

The `core` package is a foundational library for the Bowser application, providing reusable widgets and utility functions for handling images, videos, and their associated metadata. It's designed to work with AI-generated content, particularly from tools like SwarmUI.

## Features

### Core Components

#### 1. **ImageViewer** (`imageviewer.py`)
A zoomable, pannable image viewer widget with:
- Fit-to-window scaling
- 1:1 scale viewing
- Mouse wheel zooming
- Mouse dragging for panning
- Support for animated WebP images
- Smooth anti-aliased rendering

#### 2. **VideoViewer** (`videoviewer.py`)
A comprehensive video player with:
- Playback controls (play, pause, stop)
- Frame-by-frame navigation
- Frame capture to PNG files
- Video metadata display
- Infinite looping
- Audio output with volume control

#### 3. **ImageGallery** (`imagegallery.py`)
A thumbnail gallery widget featuring:
- Parallel thumbnail loading using multiprocessing
- Dynamic grid layout that adjusts to window size
- Drag-and-drop support for thumbnails
- Visual highlighting of selected and marked files
- Keyboard navigation
- Support for both images and videos with distinct coloring
- File filtering and search
- Mark and delete functionality

#### 4. **MetadataViewer** (`metadataviewer.py`)
A widget for displaying structured metadata:
- EXIF data from images
- Metadata from videos
- Support for sidecar JSON files (e.g., SwarmUI `.swarm.json`)
- Dedicated fields for File, Size, Seed, Prompt, etc.
- Copy-to-clipboard functionality
- Formatted JSON output
- Dark mode support

#### 5. **MetadataHandler** (`metadatahandler.py`)
A non-GUI handler for metadata processing:
- Extracts metadata from images and videos
- Handles nested metadata structures
- Supports SwarmUI metadata format
- Recursive metadata extraction
- Field configuration for common metadata keys

#### 6. **ImageVideoViewer** (`imagevideoviewer.py`)
A composite widget that handles both image and video viewing:
- Automatic detection of file type
- Navigation controls (Previous, Next, 1:1, Fit)
- Mark file functionality
- Unified interface for both media types

### Utility Functions (`utils.py`)

Common functionality used across components:

**File Format Detection:**
- `is_image_file()` - Check if a file is an image
- `is_video_file()` - Check if a file is a video
- `is_supported_file()` - Check if a file has a supported extension

**Path Manipulation:**
- `get_swarm_preview_path()` - Get path to Swarm preview image
- `get_swarm_json_path()` - Get path to Swarm JSON metadata
- `get_frame_filename()` - Generate filename for video frames

**Directory Operations:**
- `is_directory_empty()` - Check if directory is empty (with safety checks)
- `safe_remove_file()` - Safely remove files with error handling

**File Information:**
- `get_file_size()` - Get file size in bytes
- `format_file_size()` - Format file size as human-readable string

**Constants:**
- Supported image extensions: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.gif`, `.tiff`, `.webp`
- Supported video extensions: `.mp4`, `.mov`, `.avi`, `.mkv`, `.flv`
- Default thumbnail size: 192×192 pixels
- Default frame rate: 30.0 fps
- Default volume: 100%

## Installation

The package is installed as part of the Bowser application:

```bash
uv sync
```

## Dependencies

- Python 3.12+
- PySide6 >= 6.10.1
- Pillow >= 10.0.0

## Usage

### Basic Example

```python
from core import ImageViewer, VideoViewer, ImageGallery, MetadataViewer

# Create an image viewer
image_viewer = ImageViewer()
image_viewer.setImageFile("path/to/image.jpg")

# Create a video viewer
video_viewer = VideoViewer()
video_viewer.loadVideo("path/to/video.mp4")
video_viewer.play()

# Create an image gallery
gallery = ImageGallery()
gallery.load_images_from_folder("/path/to/images")

# Create a metadata viewer
metadata_viewer = MetadataViewer()
metadata_viewer.load_file_metadata("path/to/image.jpg")
```

### Using ImageVideoViewer

```python
from core import ImageVideoViewer

viewer = ImageVideoViewer()
viewer.display_file("path/to/image.jpg")  # Automatically detects file type
viewer.display_file("path/to/video.mp4")  # Automatically detects file type
```

## Architecture

The package follows a modular design:

1. **`utils.py`** - Pure utility functions (no UI dependencies)
2. **`metadatahandler.py`** - Non-GUI metadata processing logic
3. **UI Components** - PySide6 widgets for displaying and interacting with media
4. **Composite Components** - Higher-level components that combine basic widgets

## Supported File Formats

### Images
- JPEG/JPG
- PNG
- BMP
- GIF
- TIFF
- WebP (including animated)

### Videos
- MP4
- MOV
- AVI
- MKV
- FLV

## Metadata Support

The package supports metadata from multiple sources:

1. **Image EXIF Data** - Standard EXIF tags from PIL/Pillow
2. **Video Metadata** - Media metadata from QtMultimedia
3. **SwarmUI Metadata** - JSON sidecar files (`.swarm.json`)
4. **Custom Metadata** - Any metadata embedded in image files

### Common Metadata Fields

The `MetadataHandler` extracts and displays these common fields:
- **Seed** - Generation seed
- **File** - Original filename
- **InImage** - Input image filename
- **InVideo** - Input video filename
- **Size** - Image/video dimensions and frame count
- **Steps** - Generation steps
- **CFG** - CFG scale
- **Model** - AI model used
- **Time** - Generation time
- **Prompt** - Generation prompt
- **Prompt2** - Original prompt
- **Guidance** - Guidance scale (Flux)

## Threading and Performance

The `ImageGallery` uses multiprocessing for parallel thumbnail loading:
- Configurable number of processes (up to `MAX_PROCESSES`)
- Chunked processing for memory efficiency
- Graceful cancellation support
- Automatic cleanup of process pools

## Styling

All widgets support dark mode and can be styled with custom CSS:

```python
image_viewer.setStyleSheet("""
    QWidget {
        background-color: #252525;
        border: 1px solid #555555;
    }
""")
```

## Error Handling

The package includes comprehensive error handling:
- Graceful handling of missing or corrupted files
- Permission error handling for file operations
- Validation of file extensions
- Safe cleanup of resources

## License

This package is part of the Bowser application.

## Contributing

Contributions are welcome! Please ensure:
- Code follows PEP 8 style guidelines
- New features include tests
- Documentation is updated
- Changes are backward compatible when possible
