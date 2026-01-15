"""Video viewer widget for playing and manipulating video files.

This module provides a comprehensive video player with frame-by-frame
navigation, frame capture, and metadata display capabilities.
"""

import os

from PySide6.QtCore import QUrl

from utils import (
    DEFAULT_FRAME_RATE,
    DEFAULT_VOLUME,
    SUPPORTED_VIDEO_EXTENSIONS,
    get_frame_filename,
    get_swarm_json_path,
)
from PySide6.QtMultimedia import QAudioOutput, QMediaMetaData, QMediaPlayer, QVideoSink
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class VideoViewer(QWidget):
    """A widget for displaying and playing video files with advanced controls.
    
    Features include:
    - Playback controls (play, pause, stop)
    - Frame-by-frame navigation (-1, +1 buttons)
    - Frame capture to PNG (Capture Frame button)
    - Video metadata display (title, duration, frame rate)
    - Infinite looping (enabled by default)
    - Status information with frame counts and timestamps
    - Audio output with volume control
    """

    def __init__(self, parent=None):
        """Initialize the VideoViewer widget.
        
        Args:
            parent: Parent widget (optional).
        """
        super().__init__(parent)
        self.setWindowTitle("Video Viewer")

        # Create video widget
        self.videoWidget = QVideoWidget()
        self.videoWidget.setStyleSheet("background-color: black;")
        self.videoWidget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # Create media player and audio output
        self.mediaPlayer = QMediaPlayer(self)
        self.audioOutput = QAudioOutput(self)
        self.mediaPlayer.setAudioOutput(self.audioOutput)
        self.mediaPlayer.setVideoOutput(self.videoWidget)

        # Create video sink for frame capture
        self.videoSink = QVideoSink(self)

        # Enable loop by default
        self.mediaPlayer.setLoops(-1)  # -1 means infinite looping

        # Create controls
        self.controlsLayout = QHBoxLayout()
        self.prevFrameButton = QPushButton("-1")
        self.playButton = QPushButton("Play")
        self.pauseButton = QPushButton("Pause")
        self.nextFrameButton = QPushButton("+1")
        self.captureFrameButton = QPushButton("Capture Frame")
        self.controlsLayout.addWidget(self.playButton)
        self.controlsLayout.addWidget(self.pauseButton)
        self.controlsLayout.addWidget(self.prevFrameButton)
        self.controlsLayout.addWidget(self.nextFrameButton)
        self.controlsLayout.addWidget(self.captureFrameButton)

        # Create status label
        self.statusLabel = QLabel("No video loaded")
        self.statusLabel.setStyleSheet("color: gray;")

        # Set up layout
        layout = QVBoxLayout()
        layout.addWidget(self.videoWidget, stretch=1)  # Video widget gets extra space
        layout.addLayout(self.controlsLayout)
        layout.addWidget(self.statusLabel)
        self.setLayout(layout)

        # Connect signals
        self.playButton.clicked.connect(self.play)
        self.pauseButton.clicked.connect(self.pause)
        self.prevFrameButton.clicked.connect(self.prevFrame)
        self.nextFrameButton.clicked.connect(self.nextFrame)
        self.captureFrameButton.clicked.connect(self.captureFrame)

        # Connect media player signals
        self.mediaPlayer.mediaStatusChanged.connect(self.handleMediaStatusChanged)
        self.mediaPlayer.errorOccurred.connect(self.handleError)
        self.mediaPlayer.positionChanged.connect(self.handlePositionChanged)
        self.mediaPlayer.durationChanged.connect(self.handleDurationChanged)

        # Connect video sink signal for frame capture
        self.videoSink.videoFrameChanged.connect(self.handleVideoFrameChanged)

    def loadVideo(self, video_path):
        """Load and prepare a video file for playback.
        
        This method:
        1. Validates the file exists
        2. Checks the file extension is supported
        3. Stops any currently playing video
        4. Sets the media source for playback
        
        Args:
            video_path (str): Path to the video file (MP4, MOV, etc.).
            
        Returns:
            bool: True if the video was loaded successfully, False otherwise.
        """
        if not os.path.exists(video_path):
            self.statusLabel.setText(f"Error: File not found - {video_path}")
            return False

        file_ext = os.path.splitext(video_path)[1].lower()
        if file_ext not in SUPPORTED_VIDEO_EXTENSIONS:
            self.statusLabel.setText(f"Error: Unsupported format - {file_ext}")
            return False

        # stop any current video
        self.stop()

        # Set the media source
        self.mediaPlayer.setSource(QUrl.fromLocalFile(video_path))

        return True

    def play(self):
        """Start or resume playback of the loaded video."""
        self.mediaPlayer.play()

    def pause(self):
        """Pause playback of the video."""
        self.mediaPlayer.pause()

    def stop(self):
        """Stop playback and reset the video."""
        self.mediaPlayer.stop()

    def prevFrame(self):
        """Move to previous frame (pause if playing)."""
        # Pause playback if it's playing
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.mediaPlayer.pause()

        # Move back one frame using actual frame rate
        fps = self.getFrameRate()
        frame_duration_ms = int(1000 / fps)
        current_pos = self.mediaPlayer.position()
        new_pos = max(0, current_pos - frame_duration_ms)
        self.mediaPlayer.setPosition(new_pos)

    def nextFrame(self):
        """Move to next frame (pause if playing)."""
        # Pause playback if it's playing
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.mediaPlayer.pause()

        # Move forward one frame using actual frame rate
        fps = self.getFrameRate()
        frame_duration_ms = int(1000 / fps)
        current_pos = self.mediaPlayer.position()
        new_pos = current_pos + frame_duration_ms

        # Don't go past the end of the video
        if new_pos < self.mediaPlayer.duration():
            self.mediaPlayer.setPosition(new_pos)

    def handleMediaStatusChanged(self, status):
        """Handle media player status changes.

        Args:
            status: The media status from QMediaPlayer.
        """
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            # Don't override the frame info that was set in handleDurationChanged
            pass
        elif status == QMediaPlayer.MediaStatus.BufferingMedia:
            self.statusLabel.setText("Buffering...")
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.statusLabel.setText("Playback completed (will loop)")

    def handleError(self, error, errorString):
        """Handle media player errors.

        Args:
            error: The error code from QMediaPlayer.
            errorString: Description of the error.
        """
        self.statusLabel.setText(f"Error: {errorString}")

    def setVolume(self, volume):
        """Set the audio volume.

        Args:
            volume (int): Volume level from 0 to 100.
        """
        self.audioOutput.setVolume(volume / 100.0)

    def setFullScreen(self, fullScreen):
        """Toggle full screen mode.

        Args:
            fullScreen (bool): Whether to enable full screen mode.
        """
        if fullScreen:
            self.videoWidget.setFullScreen(True)
        else:
            self.videoWidget.setFullScreen(False)

    def handlePositionChanged(self, position):
        """Handle position changes during playback.

        Args:
            position (int): Current playback position in milliseconds.
        """
        if self.mediaPlayer.duration() > 0:
            # Get the actual frame rate from metadata
            fps = self.getFrameRate()
            current_frame = int((position / 1000.0) * fps)
            total_frames = int((self.mediaPlayer.duration() / 1000.0) * fps)

            # Update status with frame information
            self.statusLabel.setText(
                f"Frame: {current_frame}/{total_frames} @ {fps}fps "
                f"({position / 1000:.1f}s/{self.mediaPlayer.duration() / 1000:.1f}s)"
            )

    def getFrameRate(self):
        """Get the frame rate from media metadata, or return default.

        Returns:
            float: Frame rate in frames per second
        """
        # Try to get frame rate from metadata
        fps = self.mediaPlayer.metaData().value(QMediaMetaData.Key.VideoFrameRate)
        if isinstance(fps, float):
            fps = float(fps) if fps is not None else DEFAULT_FRAME_RATE
            return fps
        return DEFAULT_FRAME_RATE

    def handleDurationChanged(self, duration):
        """Handle duration changes when media is loaded.

        Args:
            duration (int): Total duration in milliseconds.
        """
        if duration > 0:
            # Get the actual frame rate from metadata
            fps = self.getFrameRate()
            total_frames = int((duration / 1000.0) * fps)

            # Update status to include frame count and frame rate
            self.statusLabel.setText(
                f"Loaded: {os.path.basename(self.mediaPlayer.source().toLocalFile())} "
                f"({total_frames} frames @ {fps}fps, {duration / 1000:.1f}s)"
            )

    def hide(self):
        """Override hide to stop playback before hiding the widget."""
        self.stop()
        super().hide()

    def captureFrame(self):
        """Capture the current video frame.

        Returns:
            QImage: The captured video frame, or None if no frame is available
        """
        # backup two frames and forward one to get ready
        self.prevFrame()
        self.prevFrame()
        self.nextFrame()

        # set the video sink
        self._old_video_sink = self.mediaPlayer.videoSink()
        self.mediaPlayer.setVideoSink(self.videoSink)

        # play a frame
        self.nextFrame()

    def handleVideoFrameChanged(self, frame):
        """Handle video frame changes from the video sink.

        Args:
            frame: The video frame from QVideoSink
        """
        # Get the current video frame from the video sink
        videoFrame = self.videoSink.videoFrame()

        # remove the sink
        self.mediaPlayer.setVideoSink(self._old_video_sink)

        if videoFrame.isValid():
            # Convert the video frame to QImage
            image = videoFrame.toImage()

            # Save the frame as PNG
            # Generate a filename based on the video source and current frame number
            video_path = self.mediaPlayer.source().toLocalFile()
            fps = self.getFrameRate()
            current_frame = int((self.mediaPlayer.position() / 1000.0) * fps)
            frame_filename = get_frame_filename(video_path, current_frame)

            # Save the image
            if image.save(frame_filename):
                self.statusLabel.setText(f"Frame saved: {frame_filename}")
            else:
                self.statusLabel.setText("Error: Failed to save frame")

        return
