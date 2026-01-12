"""Video viewer widget for playing MP4 and MOV videos."""

import os

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget


class VideoViewer(QWidget):
    """A widget for displaying and playing video files."""

    def __init__(self, parent=None):
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
        
        # Enable loop by default
        self.mediaPlayer.setLoops(-1)  # -1 means infinite looping

        # Create controls
        self.controlsLayout = QHBoxLayout()
        self.playButton = QPushButton("Play")
        self.pauseButton = QPushButton("Pause")
        self.stopButton = QPushButton("Stop")
        self.controlsLayout.addWidget(self.playButton)
        self.controlsLayout.addWidget(self.pauseButton)
        self.controlsLayout.addWidget(self.stopButton)

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
        self.stopButton.clicked.connect(self.stop)

        # Connect media player signals
        self.mediaPlayer.mediaStatusChanged.connect(self.handleMediaStatusChanged)
        self.mediaPlayer.errorOccurred.connect(self.handleError)

    def loadVideo(self, video_path):
        """Load and prepare a video file for playback.

        Args:
            video_path (str): Path to the video file (MP4, MOV, etc.).
        """
        if not os.path.exists(video_path):
            self.statusLabel.setText(f"Error: File not found - {video_path}")
            return False

        file_ext = os.path.splitext(video_path)[1].lower()
        if file_ext not in [".mp4", ".mov", ".avi", ".mkv", ".flv"]:
            self.statusLabel.setText(f"Error: Unsupported format - {file_ext}")
            return False

        # Set the media source
        self.mediaPlayer.setSource(QUrl.fromLocalFile(video_path))

        # Update status
        self.statusLabel.setText(f"Loaded: {os.path.basename(video_path)}")

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
        self.statusLabel.setText("Video stopped")

    def handleMediaStatusChanged(self, status):
        """Handle media player status changes.

        Args:
            status: The media status from QMediaPlayer.
        """
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            self.statusLabel.setText("Video loaded and ready to play (loop enabled)")
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
