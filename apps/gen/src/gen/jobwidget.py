"""
JobWidget class for displaying queued jobs in the UI.
"""

import json
import time
from PySide6.QtCore import Signal, Qt, QMimeData
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)


class JobWidget(QFrame):
    """A widget to display a queued job with its name, count, and progress."""

    # Signal emitted when the job is canceled
    job_canceled = Signal(object)
    # Signal emitted when the job is reloaded
    reload_job = Signal(object)
    # Signal emitted when the job widget is clicked (excluding buttons)
    job_selected = Signal(object)

    def __init__(self, job, parent=None):
        super().__init__(parent)

        self.job = job

        self.setObjectName("QueuedJobWidget")

        # Create main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        hlayout = QHBoxLayout()
        hlayout.setContentsMargins(0, 0, 0, 0)

        # Workflow name label
        self.name_label = QLabel(job.workflow_name)
        self.name_label.setStyleSheet("font-weight: bold;")

        # Count label
        self.count_label = QLabel(f"{job.completions} of {job.count}")

        # Reload button
        self.reload_button = QPushButton("←")
        self.reload_button.setFixedSize(20, 20)
        self.reload_button.clicked.connect(self._on_reload_clicked)

        # Cancel button
        self.cancel_button = QPushButton("✕")
        self.cancel_button.setFixedSize(20, 20)
        self.cancel_button.clicked.connect(self._on_cancel_clicked)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border-radius: 2px;
                background-color: #181818;
                color: black;
                border-width: 2px;
                padding: 0px;
                margin: 1px;
            }
            QProgressBar::chunk {
                background-color: #66F;
                border-radius: 2px;
                border-width: 2px;
                padding: 0px;
            }
        """)

        # Second progress bar for elapsed time vs estimated runtime
        self.elapsed_progress_bar = QProgressBar()
        self.elapsed_progress_bar.setRange(0, 100)
        self.elapsed_progress_bar.setValue(0)
        self.elapsed_progress_bar.setFixedHeight(7)
        self.elapsed_progress_bar.setTextVisible(False)
        self.elapsed_progress_bar.setStyleSheet("""
            QProgressBar {
                border-radius: 2px;
                background-color: #181818;
                color: black;
                border-width: 2px;
                padding: 0px;
                margin: 1px;
            }
            QProgressBar::chunk {
                background-color: #FFD700;
                border-radius: 2px;
                border-width: 2px;
                padding: 0px;
            }
        """)

        # Add widgets to layout
        hlayout.addWidget(self.name_label)
        hlayout.addWidget(self.count_label)
        hlayout.addWidget(self.reload_button)
        hlayout.addWidget(self.cancel_button)
        layout.addLayout(hlayout)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.elapsed_progress_bar)

        # Set the layout
        self.setLayout(layout)

        # Add border
        self.setStyleSheet(
            "QFrame#QueuedJobWidget { border: 1px solid #666; border-radius: 3px; margin: 1px; padding: 3px;}"
        )

        # Connect mouse press event to handle clicks
        self.mousePressEvent = self._on_mouse_press

        # Enable drag and drop
        self.setAcceptDrops(False)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

    def update_count(self):
        self.count_label.setText(f"{self.job.completions} of {self.job.count}")

    def set_progress(self, value):
        self.progress_bar.setValue(value * 100.0)

    def set_elapsed_progress(self):
        """Update the elapsed progress bar based on elapsed time vs estimated runtime."""
        if not hasattr(self.job, "results") or len(self.job.results) == 0:
            return

        if 0 not in self.job.results or "start_time" not in self.job.results[0]:
            return

        try:
            start_time = self.job.results[0]["start_time"]
            elapsed_time = time.time() - start_time

            if self.job.estimated_runtime > 0:
                progress = min(elapsed_time / self.job.estimated_runtime, 1.0)
                self.elapsed_progress_bar.setValue(round(progress * 100.0))
        except (KeyError, TypeError, ValueError):
            # Handle any errors gracefully
            pass

    def mark_submitted(self):
        self.setStyleSheet(
            "QFrame#QueuedJobWidget { border: 1px solid #8f8; border-radius: 3px; margin: 1px; padding: 3px;}"
        )

    def error(self):
        self.setStyleSheet(
            "QFrame#QueuedJobWidget { border: 1px solid #f66; border-radius: 3px; margin: 1px; padding: 3px;}"
        )
        self.job.error = True

    def add_completion(self):
        self.job.add_completion()
        self.update_count()
        if self.job.completions == self.job.count:
            self.mark_completed()

    def mark_completed(self):
        self.set_progress(1)
        self.setStyleSheet(
            "QFrame#QueuedJobWidget { border: 1px solid #88f; border-radius: 3px; margin: 1px; padding: 3px;}"
        )

    def _on_cancel_clicked(self):
        """Handle cancel button click."""
        self.setStyleSheet(
            "QFrame#QueuedJobWidget { border: 1px solid #fb6; border-radius: 3px; margin: 1px; padding: 3px;}"
        )
        self.job_canceled.emit(self)
        self.job.error = True

    def _on_reload_clicked(self):
        """Handle reload button click."""
        self.reload_job.emit(self)

    def _on_mouse_press(self, event):
        """Handle mouse press event to detect clicks on the widget."""
        # Get the position of the mouse click
        pos = event.pos()

        # Check if the click is on one of the buttons
        # Convert widget coordinates to button coordinates
        reload_pos = self.reload_button.mapFrom(self, pos)
        cancel_pos = self.cancel_button.mapFrom(self, pos)

        # If the click is not on either button, emit the job_selected signal
        if not self.reload_button.rect().contains(
            reload_pos
        ) and not self.cancel_button.rect().contains(cancel_pos):
            self.job_selected.emit(self)

        # Start drag operation if left mouse button is pressed
        if event.button() == Qt.MouseButton.LeftButton:
            drag = QDrag(self)
            mime = self._create_mime_data()
            drag.setMimeData(mime)
            
            # Create a transparent pixmap for drag visual
            pixmap = self.grab()
            drag.setPixmap(pixmap)
            drag.setHotSpot(event.pos())
            
            # Execute drag and drop
            result = drag.exec(Qt.DropAction.MoveAction | Qt.DropAction.CopyAction)

    def _create_mime_data(self):
        """Create MIME data containing the job object."""        
        mime_data = QMimeData()
        
        # Store job data in custom format
        jdata = {
            "workflow_name": self.job.workflow_name,
            "workflow": self.job.workflow,
            "count": self.job.count}
        mime_data.setData("application/x-job-widget", json.dumps(jdata).encode("utf-8"))
        
        return mime_data