# Bowser

A collection of Qt-based applications for AI image generation workflow
management and media browsing.

Did this to get more familiiar with vibe coding, used devstral2 small 24B Q6 via
Mistral Vibe. The viewer is fairly nice for quickly going through lots of gens,
similar to reviewing photos in a photography workflow app. The generator
requires a working SwarmUI install and, while quite nice, is more of a
playground. Just use SwarmUI or ComfyUI directly both of which are really nice
and have great setup/onboarding/community etc.

## Overview

Bowser is a suite of tools built with PySide6 (Qt for Python) for working with
AI-generated images and videos. It consists of:

1. **bowser-gen** - A GUI front end for ComfyUI with SwarmUI 
2. **bowser-view** - An image and video browser with metadata support
3. **core** - Shared UI components and utilities

## Applications

### bowser-gen

A Qt-based graphical user interface for ComfyUI, designed to provide an
intuitive workflow management system for stable diffusion and other AI image
generation tasks.

**Key Features:**
- Workflow management with directory-based organization
- Job queueing with batch processing support
- Image and video gallery with viewer
- Metadata handling and import/export
- ComfyUI server integration via WebSocket

**See:** [apps/gen/README.md](apps/gen/README.md)

### bowser-view

A desktop application for browsing, viewing, and managing image and video files, with special support for AI-generated content and metadata.

**Key Features:**
- Multi-panel interface (directory tree, thumbnail gallery, viewer, metadata)
- Support for multiple image and video formats
- Dark mode theme
- File management (mark, delete, prune empty directories)
- Metadata viewing for EXIF and JSON data
- Keyboard shortcuts for efficient navigation

**See:** [apps/view/README.md](apps/view/README.md)

## Core Package

A shared library providing reusable UI components and utilities for image and video viewing, metadata handling, and gallery management.

**Key Components:**
- ImageViewer - Zoomable, pannable image viewer
- VideoViewer - Video player with frame capture
- ImageGallery - Thumbnail gallery with parallel loading
- MetadataViewer - Display structured metadata
- MetadataHandler - Process metadata from images and videos
- ImageVideoViewer - Composite viewer for both image and video

**See:** [packages/core/README.md](packages/core/README.md)

## Installation

### Prerequisites

- Python 3.12 or higher
- uv package manager (recommended)

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/bowser.git
cd bowser

# Install dependencies
uv sync
```

## Usage

### Running bowser-gen

```bash
# From the project root
gen

# With custom server address
gen --server 192.168.1.100:8188

# With custom workflows directory
gen --workflows /path/to/workflows
```

### Running bowser-view

```bash
# From the project root
view [folder_path]

# Or from the view app directory
cd apps/view
python main.py [folder_path]
```

## Project Structure

```
bowser/
├── apps/
│   ├── gen/
│   │   ├── src/
│   │   │   └── gen/
│   │   ├── pyproject.toml
│   │   └── README.md
│   │
│   └── view/
│       ├── src/
│       │   └── view/
│       ├── pyproject.toml
│       └── README.md
│
├── packages/
│   └── core/
│       ├── src/
│       │   └── core/
│       ├── pyproject.toml
│       └── README.md
│
├── pyproject.toml
├── uv.lock
└── README.md
```

## Development

### Building

```bash
# Build the packages
uv build
```

### Running Tests

No formal test suite is currently included, but you can run the applications directly:

```bash
# Run bowser-gen
python -m gen

# Run bowser-view
python -m view
```

## Architecture

### bowser-gen Architecture

1. **GenMain** - Main application window
2. **WorkflowsWidget** - Workflow management and GUI node extraction
3. **QueueWidget** - Job queue and ComfyUI server communication
4. **comfyServer** - WebSocket client for ComfyUI

### bowser-view Architecture

1. **BowserMain** - Main window and UI management
2. **DirectoryTree** - Directory browsing
3. **ImageGallery** - Thumbnail gallery
4. **ImageViewer** - Image display
5. **VideoViewer** - Video playback
6. **MetadataViewer** - Metadata display

### Shared Core Components

The `core` package provides shared components used by both applications:
- Image and video viewers
- Gallery widgets
- Metadata handlers
- Utility functions

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

## Configuration

### bowser-gen Configuration

Settings are stored in `bowser-gen.toml`:

```toml
[settings]
server_address = "127.0.0.1:8188"
output_root = "/path/to/output"
workflow_root = "/path/to/workflows"
```

### bowser-view Configuration

No configuration file is required. You can open folders directly via:
- Command line argument
- File > Open Folder menu
- Keyboard shortcut (Ctrl+O)

## Keyboard Shortcuts

### bowser-gen

| Key | Action |
|-----|--------|
| **A** | Previous thumbnail |
| **D** | Next thumbnail |
| **R** | Fit image to window |
| **1** | Display image at 1:1 scale |
| **X** | Mark/unmark current file |
| **Ctrl+D** | Delete marked files |
| **Ctrl+Shift+H** | Clear history |

### bowser-view

| Key | Action |
|-----|--------|
| **W** | Previous folder |
| **S** | Next folder |
| **A** | Previous thumbnail |
| **D** | Next thumbnail |
| **R** | Fit image to window |
| **1** | Display image at 1:1 scale |
| **X** | Mark/unmark current file |
| **Ctrl+O** | Open folder |
| **Ctrl+D** | Delete marked files |
| **Ctrl+P** | Prune empty directories |
| **Ctrl+Q** | Exit |

## Metadata Support

Both applications support metadata from multiple sources:

1. **Image EXIF Data** - Standard EXIF tags
2. **Video Metadata** - Media metadata
3. **SwarmUI Metadata** - JSON sidecar files (`.swarm.json`)
4. **Custom Metadata** - Any metadata embedded in image files

Common metadata fields include:
- Seed
- File
- InImage/InVideo
- Size
- Steps
- CFG
- Model
- Time
- Prompt
- Guidance

## Contributing

Contributions are welcome! Please follow these guidelines:

1. **Code Style**: Follow PEP 8 guidelines
2. **Type Hints**: Add type hints to all public functions and methods
3. **Documentation**: Keep docstrings updated
4. **Testing**: Test changes across different file types and edge cases

## License

This project is licensed under the MIT License.

## Support

For issues and questions, please open an issue on the GitHub repository.
