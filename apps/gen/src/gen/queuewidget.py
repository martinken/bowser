import copy
import io
import json
import os
import struct
import time
from collections import deque
from random import randint

import cv2
from core.imageviewer import ImageViewer
from core.utils import (
    get_gpu_from_device_string,
    get_swarm_json_path,
    get_swarm_preview_path,
    replace_variables_in_string,
)

# import random
# from requests_toolbelt import MultipartEncoder
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .comfyserver import comfyServer

# workflow:gpu:rate
# Performance data based on GPU compute power and VRAM capacity
# Values represent operations per second (higher is better)
# RTX 3090 used as baseline reference (600,000 ops/sec)
performance_data = {
    "Wan22-I2V-Lora-Lightning-API": {"3090": 566065, "5090": 1850000},
    "z_image_turbo-API": {"3090": 800920, "5090": 1900000},
    "Wan22-Extend-24G-Q6-API": {"3090": 500000, "5090": 1750000},
    # Performance estimates for various GPUs
    "Guesses": {
        # NVIDIA RTX 30 Series
        "3090": 600000,  # Baseline reference
        "3090ti": 650000,  # Slightly faster than 3090
        "3080ti": 550000,  # Similar to 3090 but with less VRAM
        "3080": 500000,  # Good performance, 10GB VRAM
        "3070ti": 420000,  # Slightly faster than 3070
        "3070": 400000,  # Mid-range, 8GB VRAM
        "3060ti": 350000,  # Good value, 8GB VRAM
        "3060": 280000,  # Entry level, 12GB VRAM but slower
        # NVIDIA RTX 40 Series
        "4090": 1100000,  # Much faster than 3090
        "4080": 900000,  # Fast, 16GB VRAM
        "4070ti": 750000,  # Good performance
        "4070": 650000,  # Mid-range
        "4060ti": 500000,  # Good value
        "4060": 400000,  # Entry level
        # NVIDIA RTX 20 Series (older generation)
        "2080ti": 350000,  # Older but still capable
        "2080super": 300000,
        "2080": 280000,
        "2070super": 250000,
        "2070": 230000,
        "2060super": 200000,
        "2060": 180000,
        # NVIDIA RTX 50 Series
        "5090": 1500000,  # Next-gen flagship
        "5080": 900000,  # Next-gen high-end
        "5070": 650000,  # Mid-range
        "5060": 400000,  # Entry level
        # AMD Radeon GPUs (estimated based on relative performance)
        "rx7900xtx": 700000,  # AMD flagship
        "rx7900xt": 650000,
        "rx7800xt": 550000,
        "rx6950xt": 500000,  # Older AMD high-end
        "rx6900xt": 480000,
        "rx6800xt": 450000,
        "rx6800": 420000,
        "rx6700xt": 380000,
        # Laptop GPUs (lower performance due to power limits)
        "3080laptop": 400000,  # Laptop version of 3080
        "3070laptop": 320000,  # Laptop version of 3070
        "4070laptop": 550000,  # Laptop version of 4070
        "4060laptop": 350000,  # Laptop version of 4060
    },
}


class Job:
    def __init__(self, workflow_name, workflow, count, parent=None):
        self._workflow = workflow
        self.workflow_name = workflow_name
        self.completions = 0
        self.count = count
        self.start_seed = -1
        self.results = {}
        self.error = False
        self.ops = 1
        self.estimated_runtime = 1.0
        self.compute_ops()

    def compute_estimated_runtime(self, rate):
        self.estimated_runtime = self.count * self.ops / rate

    def get_remaining_estimated_runtime(self):
        if len(self.results) > 0 and "start_time" in self.results[0]:
            return (
                self.estimated_runtime
                - time.time()
                + self.results[self.completions]["start_time"]
            )
        else:
            return self.estimated_runtime

    def compute_ops(self):
        metadata = {}
        width = 1000
        height = 1000
        for id, node in self._workflow.items():
            if node["class_type"].startswith("SwarmInput"):
                # extract important values from workflow
                node_metadata = {}

                # extract dimension in case we find no other dims
                if node["class_type"] == "SwarmInputImage":
                    width = node["input_width"]
                    height = node["input_height"]
                elif node["class_type"] == "SwarmInputVideo":
                    width = node["input_width"]
                    height = node["input_height"]

                # Get title for identification
                if "title" in node.get("inputs", {}):
                    node_metadata["title"] = node["inputs"]["title"]

                # Extract Steps, Width, Height, Aspect Ratio, Frames based on title
                title_lower = node_metadata.get("title", "").lower()

                # Check if this node contains a value we're interested in
                if "value" in node.get("inputs", {}):
                    value = node["inputs"]["value"]

                    # Try to extract Steps
                    if "steps" in title_lower or "step" in title_lower:
                        node_metadata["steps"] = value
                    # Try to extract Width
                    elif "width" in title_lower:
                        node_metadata["width"] = value
                    # Try to extract Height
                    elif "height" in title_lower:
                        node_metadata["height"] = value
                    # Try to extract Aspect Ratio
                    elif "aspect" in title_lower or "ratio" in title_lower:
                        node_metadata["aspectratio"] = value
                    # Try to extract Frames
                    elif "frames" in title_lower or "frame" in title_lower:
                        node_metadata["frames"] = value

                # Only add to metadata_list if we found relevant data
                if node_metadata:
                    metadata.update(node_metadata)

        # Process metadata to extract width and height from aspectratio if needed
        # If width and height are missing, try to extract them from the aspectratio field
        # examples "1M  4:3 1152, 864" would be 1152 width and 864 height
        if metadata.get("width") is None or metadata.get("height") is None:
            aspectratio = metadata.get("aspectratio", "")
            if aspectratio:
                # Try to extract width and height from aspectratio
                # Pattern: look for two numbers separated by comma or space
                import re

                match = re.search(r"(\d+)\s*[xX,]\s*(\d+)", str(aspectratio))
                if match:
                    if metadata.get("width") is None:
                        metadata["width"] = match.group(1)
                    if metadata.get("height") is None:
                        metadata["height"] = match.group(2)

        # Compute total of width*height*steps*frames
        width = int(metadata.get("width", width))
        height = int(metadata.get("height", height))
        steps = int(metadata.get("steps", 10))
        frames = int(metadata.get("frames", 1))
        self.ops = width * height * steps * frames

    def set_start_time(self, timestamp):
        self.results[self.completions]["start_time"] = timestamp

    def set_end_time(self, timestamp):
        self.results[self.completions]["end_time"] = timestamp
        self.results[self.completions]["elapsed_time"] = round(
            timestamp - self.results[self.completions]["start_time"], 2
        )

    def is_completed(self):
        return self.completions >= self.count

    def get_workflow(self, comfy_server):
        workflow = copy.deepcopy(self._workflow)
        self.results[self.completions] = {}
        if self.completions == 0:
            self.results[0]["input_images"] = {}
            self.results[0]["input_videos"] = {}
        for id, node in workflow.items():
            # remove any options entries
            if "options" in node:
                del node["options"]
            # replace any seed nodes that have -1 as a value
            if node["class_type"] == "SwarmInputInteger":
                if (
                    node["inputs"]["view_type"] == "seed"
                    and node["inputs"]["value"] == -1
                ):
                    if self.start_seed == -1:
                        self.start_seed = randint(0, 2**63 - 1)
                    node["inputs"]["value"] = self.start_seed + self.completions

            # send any input images over when the completions are zero
            # otherwise assume they are already there
            if node["class_type"] == "SwarmInputImage":
                if self.completions == 0:
                    image_path = node["inputs"]["image"]
                    self.results[0]["input_images"][id] = image_path
                    file_ext = os.path.splitext(image_path)[1].lstrip(".")
                    result = comfy_server.upload_image(
                        node["inputs"]["image"],
                        f"dueser.{file_ext}",
                        image_type="input",
                        overwrite=False,
                    )
                    self._image_name = result["name"]
                node["inputs"]["image"] = self._image_name

            # send any input videos over when the completions are zero
            # otherwise assume they are already there
            if node["class_type"] == "SwarmInputVideo":
                if self.completions == 0:
                    video_path = node["inputs"]["video"]
                    self.results[0]["input_videos"][id] = video_path
                    file_ext = os.path.splitext(video_path)[1].lstrip(".")
                    result = comfy_server.upload_video(
                        node["inputs"]["video"],
                        f"dueser.{file_ext}",
                        image_type="input",
                        overwrite=False,
                    )
                    self._video_name = result["name"]
                node["inputs"]["video"] = self._video_name

        self.results[self.completions]["seed"] = self.start_seed + self.completions
        self.results[self.completions]["submitted_workflow"] = workflow

        return workflow

    def add_completion(self):
        self.completions += 1


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


class QueueWidget(QWidget):
    """A widget containing a QTabWidget with Queue and History tabs."""

    _comfy_server: comfyServer

    # Signal emitted when a result is produced
    new_file = Signal(str)
    new_pil_image = Signal(object)
    # Signal emitted when a job is reloaded
    reload_job = Signal(object)
    # Signal emitted when a job is selected and it has a result file to show
    show_file = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Queue Widget")

        self._new_job_widgets = deque()
        self._queue_update_time = 4000  # in ms
        self._active_job_widgets = {}
        self._old_job_widgets = deque()
        self._output_count = 10
        self._output_root = ""
        self._current_device = "unknown"

        # Create the main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create the tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)

        # Create Queue tab
        self.queue_tab = QWidget()
        self.queue_tab.setObjectName("queueTab")

        # Create layout for queue tab with scroll area
        self.queue_scroll = QWidget()
        self.queue_layout = QVBoxLayout()
        self.queue_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.queue_scroll.setLayout(self.queue_layout)

        self.queue_scroll_area = QScrollArea()
        self.queue_scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.queue_scroll_area.setWidgetResizable(True)
        self.queue_scroll_area.setWidget(self.queue_scroll)

        # Create label for total estimated runtime
        self.total_runtime_label = QLabel("Total estimated runtime: Calculating...")
        self.total_runtime_label.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        self.total_runtime_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Create History tab
        self.history_tab = QWidget()
        self.history_tab.setObjectName("historyTab")

        # Create layout for history tab with scroll area
        self.history_scroll = QWidget()
        self.history_layout = QVBoxLayout()
        self.history_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.history_scroll.setLayout(self.history_layout)

        self.history_scroll_area = QScrollArea()
        self.history_scroll_area.setWidgetResizable(True)
        self.history_scroll_area.setStyleSheet(
            "QScrollArea { border: none; } QScrollArea > QWidget { background-color: transparent; }"
        )
        self.history_scroll_area.setWidget(self.history_scroll)

        # Create Stats tab
        self.stats_tab = QWidget()
        self.stats_tab.setObjectName("statsTab")

        # Create layout for stats tab
        self.stats_layout = QVBoxLayout()
        self.stats_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.stats_tab.setLayout(self.stats_layout)

        # Add scroll areas to tabs
        queue_layout_wrapper = QVBoxLayout()
        queue_layout_wrapper.addWidget(self.total_runtime_label)
        queue_layout_wrapper.addWidget(self.queue_scroll_area)
        queue_layout_wrapper.setContentsMargins(0, 0, 0, 0)
        queue_layout_wrapper.setSpacing(0)
        self.queue_tab.setLayout(queue_layout_wrapper)

        history_layout_wrapper = QVBoxLayout()
        history_layout_wrapper.addWidget(self.history_scroll_area)
        history_layout_wrapper.setContentsMargins(0, 0, 0, 0)
        history_layout_wrapper.setSpacing(0)
        self.history_tab.setLayout(history_layout_wrapper)

        # Add tabs to the tab widget
        self.tab_widget.addTab(self.queue_tab, "Queue")
        self.tab_widget.addTab(self.history_tab, "History")
        self.tab_widget.addTab(self.stats_tab, "Stats")

        # Initialize stats display
        self._init_stats_display()

        # Add tab widget to the main layout
        layout.addWidget(self.tab_widget)

        # Create ImageViewer widget
        self.image_viewer = ImageViewer()
        self.image_viewer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.image_viewer.setMaximumHeight(256)

        # Add ImageViewer to the main layout (below the tabs)
        layout.addWidget(self.image_viewer)

        # Set the main layout
        self.setLayout(layout)

        # Create and start the timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_deque)
        self._timer.start(self._queue_update_time)

    def set_comfy_server(self, comfy_server):
        self._comfy_server = comfy_server
        self._comfy_server.textMessageReceived.connect(self._on_text_message_received)
        self._comfy_server.binaryMessageReceived.connect(
            self._on_binary_message_received
        )

    def set_output_root(self, root: str):
        self._output_root = root

    def _init_stats_display(self):
        """Initialize the stats display widgets."""
        # System info section
        self.system_info_label = QLabel("System Information")
        self.system_info_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.system_info_label.setStyleSheet("margin-bottom: 10px;")

        self.system_info_widget = QLabel("Connecting to server...")
        self.system_info_widget.setWordWrap(True)
        self.system_info_widget.setStyleSheet("margin-bottom: 20px;")

        # Devices section
        self.devices_label = QLabel("Devices")
        self.devices_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.devices_label.setStyleSheet("margin-bottom: 10px;")

        self.devices_widget = QLabel("No device information available.")
        self.devices_widget.setWordWrap(True)

        # Add widgets to stats layout
        self.stats_layout.addWidget(self.system_info_label)
        self.stats_layout.addWidget(self.system_info_widget)
        self.stats_layout.addWidget(self.devices_label)
        self.stats_layout.addWidget(self.devices_widget)

        # Add some spacing
        self.stats_layout.addStretch()

    def _job_canceled(self, job_widget):
        if job_widget in self._new_job_widgets:
            self._new_job_widgets.remove(job_widget)
            self.queue_layout.removeWidget(job_widget)
            self._old_job_widgets.append(job_widget)
            self.history_layout.insertWidget(0, job_widget)

        for prompt_id, widget in self._active_job_widgets.items():
            if widget is job_widget:
                self._comfy_server.cancel_prompt(prompt_id)
                del self._active_job_widgets[prompt_id]
                break

        # Update the total runtime label after cancellation
        self._update_total_runtime_label()

    def _reload_job(self, job_widget):
        """Handle reload button click."""
        # Emit the reload signal
        self.reload_job.emit(job_widget.job)

    def _job_selected(self, job_widget):
        """Handle job selection."""
        # Check if the job is completed
        if (
            job_widget.job.is_completed()
            and len(job_widget.job.results)
            and "output_files" in job_widget.job.results[0]
        ):
            # Emit the show_result signal
            self.show_file.emit(job_widget.job.results[0]["output_files"][0])

    def _format_time(self, seconds):
        """Format seconds into a human-readable time string (HH:MM:SS).

        Args:
            seconds (float): Time in seconds

        Returns:
            str: Formatted time string
        """
        if seconds < 0:
            return "00:00:00"

        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)

        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _calculate_total_estimated_runtime(self):
        """Calculate the total estimated runtime of all queued jobs.

        Returns:
            float: Total estimated runtime in seconds
        """
        total_runtime = 0.0

        for job_widget in self._new_job_widgets:
            total_runtime += job_widget.job.get_remaining_estimated_runtime()

        return total_runtime

    def _update_total_runtime_label(self):
        """Update the label showing total estimated runtime."""
        total_seconds = self._calculate_total_estimated_runtime()
        formatted_time = self._format_time(total_seconds)

        if len(self._new_job_widgets) == 0:
            self.total_runtime_label.setText("Total estimated runtime: No jobs queued")
        elif len(self._new_job_widgets) == 1:
            self.total_runtime_label.setText(
                f"Total estimated runtime: {formatted_time} for {len(self._new_job_widgets)} job"
            )
        else:
            self.total_runtime_label.setText(
                f"Total estimated runtime: {formatted_time} for {len(self._new_job_widgets)} jobs"
            )

    def get_performance_rate(self, name, gpu):
        """Get the rate for a workflow and GPU from performance_data.

        Args:
            name (str): The workflow name
            gpu (str): The GPU identifier

        Returns:
            float: The rate for this workflow and GPU, or an average if not found
        """
        # Check if we have performance data
        if not performance_data:
            return 100000.0  # Default rate, low end

        # Try to get the exact match
        if name in performance_data and gpu in performance_data[name]:
            return performance_data[name][gpu]

        # If workflow_name not found, average all entries that match the GPU
        matching_rates = []
        for workflow_name, gpu_data in performance_data.items():
            if gpu in gpu_data:
                matching_rates.append(performance_data[workflow_name][gpu])

        if matching_rates:
            return sum(matching_rates) / len(matching_rates)

        # If GPU not found, average all entries that match the workflow_name
        if name in performance_data:
            gpu_rates = list(performance_data[name].values())
            if gpu_rates:
                return sum(gpu_rates) / len(gpu_rates)

        # If neither is found, average all entries
        all_rates = []
        for workflow_data in performance_data.values():
            all_rates.extend(workflow_data.values())

        if all_rates:
            return sum(all_rates) / len(all_rates)

        # Fallback default rate
        return 1.0

    def queue_job(self, workflow_name, workflow, count):
        """Queue a job with the given workflow name, workflow, and count.

        Args:
            workflow_name (str): The name of the workflow to queue.
            workflow: The workflow object to execute.
            count (int): The number of times to run the workflow.
        """
        # Create a QueuedWorkflow and QueuedWorkflowWidget for this job
        job = Job(workflow_name, workflow, count)
        # todo compute the rate based on the gpu and workkflow name
        gpu = get_gpu_from_device_string(self._current_device)
        rate = self.get_performance_rate(workflow_name, gpu)
        job.compute_estimated_runtime(rate)
        job_widget = JobWidget(job)
        job_widget.job_canceled.connect(self._job_canceled)
        job_widget.reload_job.connect(self._reload_job)
        job_widget.job_selected.connect(self._job_selected)

        # Add the job widget to the queue layout
        self.queue_layout.addWidget(job_widget)
        self._new_job_widgets.append(job_widget)

        # Update the total runtime label
        self._update_total_runtime_label()

    def _on_text_message_received(self, messagestr):
        """Handle incoming text messages."""
        try:
            # print(messagestr)
            message = json.loads(messagestr)
            if message["type"] == "progress":
                data = message["data"]
                current_step = data["value"]
                if "prompt_id" in data:
                    prompt_id = data["prompt_id"]
                    self._last_prompt_id = prompt_id
                    if prompt_id in self._active_job_widgets:
                        self._active_job_widgets[prompt_id].set_progress(
                            current_step / data["max"]
                        )
                        self._active_job_widgets[prompt_id].set_elapsed_progress()

            if message["type"] == "execution_start":
                data = message["data"]
                if "prompt_id" in data:
                    prompt_id = data["prompt_id"]
                    self._last_prompt_id = prompt_id
                    if prompt_id in self._active_job_widgets:
                        active_widget = self._active_job_widgets[prompt_id]
                        active_widget.job.set_start_time(time.time())

            if message["type"] == "execution_success":
                data = message["data"]
                self.image_viewer.clear()
                if "prompt_id" in data:
                    prompt_id = data["prompt_id"]
                    self._last_prompt_id = prompt_id
                    if prompt_id in self._active_job_widgets:
                        active_widget = self._active_job_widgets[prompt_id]
                        active_widget.job.set_end_time(time.time())
                        # get the results through a history call
                        # history = self._comfy_server.get_history(prompt_id)
                        results = self._comfy_server.get_results(prompt_id)
                        # Save all result images
                        for result in results:
                            if "image_data" in result:
                                image = Image.open(io.BytesIO(result["image_data"]))
                                self._save_result_image(image)
                            elif "video_data" in result:
                                # Save video data
                                self._save_result_video(result["video_data"])
                        active_widget.add_completion()

                        if self._active_job_widgets[prompt_id].job.is_completed():
                            widget = self._new_job_widgets.popleft()
                            widget.mark_completed()
                            del self._active_job_widgets[prompt_id]
                            self._old_job_widgets.append(widget)
                            self.queue_layout.removeWidget(widget)
                            self.history_layout.insertWidget(0, widget)
                            # Update total runtime label after job completion
                            self._update_total_runtime_label()
                        else:
                            del self._active_job_widgets[prompt_id]
                            if not active_widget.job.error:
                                queue_result = self._comfy_server.queue_prompt(
                                    active_widget.job
                                )
                                self._active_job_widgets[queue_result["prompt_id"]] = (
                                    active_widget
                                )

            if message["type"] == "execution_error":
                data = message["data"]
                if "prompt_id" in data:
                    prompt_id = data["prompt_id"]
                    self._last_prompt_id = prompt_id
                    if prompt_id in self._active_job_widgets:
                        self._active_job_widgets[prompt_id].error()
                error_msg = self._format_error_message(data)
                QMessageBox.critical(
                    self, "Execution Error", error_msg, QMessageBox.StandardButton.Ok
                )
        except Exception as e:
            print(f"Error parsing message: {e}")

    def _format_error_message(self, error_data):
        """Format error data into a readable message."""
        lines = []
        lines.append(f"<b>Error in Node {error_data.get('node_id', 'unknown')}</b>")
        lines.append(f"Node Type: {error_data.get('node_type', 'unknown')}")
        lines.append(
            f"<br><br><b>Exception:</b> {error_data.get('exception_type', 'unknown')}"
        )
        lines.append(
            f"<br><b>Message:</b> {error_data.get('exception_message', 'No message')}"
        )

        if "traceback" in error_data and error_data["traceback"]:
            lines.append("<br><br><b>Traceback:</b>")
            for line in error_data["traceback"]:
                lines.append(line)

        return "".join(lines)

    def _on_binary_message_received(self, message):
        """Handle incoming binary messages."""
        bytesmessage = bytes(message)

        # Read the 4-byte header (big-endian unsigned int)
        event_type = struct.unpack(">I", bytesmessage[:4])[0]
        # The rest of the message is the actual data
        # print(f"Binary message: {event_type}")

        # Try to handle the data based on type
        if event_type == 1:
            type_num = struct.unpack(">I", bytesmessage[4:8])[0]
            if type_num == 2:  # PNG data
                data = bytesmessage[8:]
                image = Image.open(io.BytesIO(data))
                self._save_result_image(image)
            elif type_num == 1:  # preview image
                data = bytesmessage[8:]
                image = Image.open(io.BytesIO(data))
                self.image_viewer.setPILImage(image)
        elif event_type == 4:  # preview image with metadata
            metadata_length = struct.unpack(">I", bytesmessage[4:8])[0]
            # metadata = json.loads(bytesmessage[8 : 8 + metadata_length].decode("utf-8"))
            # print(metadata)
            data = bytesmessage[8 + metadata_length :]
            image = Image.open(io.BytesIO(data))
            frames = getattr(image, "n_frames", 1)
            if frames > 1:
                # store as a file instead
                dir = replace_variables_in_string("%year%-%month%-%day%")
                if len(self._output_root):
                    dir = f"{self._output_root}/{dir}"
                os.makedirs(dir, exist_ok=True)
                full_name = f"{dir}/bowser-temp-preview.webp"
                image.save(full_name, format="WEBP", save_all=True)
                self.image_viewer.setImageFile(full_name)
            else:
                if image.mode == "RGBA":
                    image = image.convert("RGB")
                self.image_viewer.setPILImage(image)
        # except Exception as e:
        #     print(f"Error processing binary message: {e}")

    def _build_metadata_for_result(self, job):
        if "elapsed_time" not in job.results[job.completions]:
            job.set_end_time(time.time())

        sui_image_params = {
            "generation_time": job.results[job.completions]["elapsed_time"]
        }
        submitted_workflow = job.results[job.completions]["submitted_workflow"]
        for id, node in submitted_workflow.items():
            if (
                "inputs" in node
                and "class_type" in node
                and node["class_type"].startswith("SwarmInput")
                and "title" in node["inputs"]
                and "value" in node["inputs"]
            ):
                if node["class_type"] == "SwarmInputImage":
                    sui_image_params[
                        node["inputs"]["title"].lower().replace(" ", "")
                    ] = job.results[0]["input_images"][id]
                elif node["class_type"] == "SwarmInputVideo":
                    sui_image_params[
                        node["inputs"]["title"].lower().replace(" ", "")
                    ] = job.results[0]["input_videos"][id]
                else:
                    sui_image_params[
                        node["inputs"]["title"].lower().replace(" ", "")
                    ] = node["inputs"]["value"]

        bowser_params = {}
        bowser_params["workflow_name"] = job.workflow_name
        bowser_params["generation_time"] = job.results[job.completions]["elapsed_time"]
        bowser_params["device"] = self._current_device

        sui_extra_data = {
            "generation_time": job.results[job.completions]["elapsed_time"]
        }

        parameters = {
            "sui_image_params": sui_image_params,
            "sui_extra_data": sui_extra_data,
            "bowser_params": bowser_params,
        }

        # "sui_extra_data": {
        #   "date": "2026-01-29",
        #   "initimage_filename": "20260128173127-1178442556.png",
        #   "initimage_resolution": "1152x896",
        #   "prep_time": "85.13 min",
        #   "generation_time": "4.98 min",
        #   "unused_parameters": [
        #     "automaticvae"
        #   ]
        # }

        return parameters

    def _save_result_image(self, image):
        dir = replace_variables_in_string("%year%-%month%-%day%")
        if len(self._output_root):
            dir = f"{self._output_root}/{dir}"
        os.makedirs(dir, exist_ok=True)
        self._output_count = (self._output_count - 9) % 90 + 10
        filename = replace_variables_in_string(
            f"%year%%month%%day%%hour%%minute%%second%-{self._output_count}.png"
        )
        full_name = f"{dir}/{filename}"
        if self._last_prompt_id in self._active_job_widgets:
            widget = self._active_job_widgets[self._last_prompt_id]
            # Store the filename in results
            widget.job.results[widget.job.completions]["output_files"] = [full_name]
            # Save workflow and count as metadata in the image
            datmetadata = self._build_metadata_for_result(widget.job)
            dat = json.dumps(datmetadata)
            metadata = PngInfo()
            metadata.add_text("parameters", dat)
            metadata.add_text("dueser_completion", str(widget.job.completions))
            image.save(full_name, pnginfo=metadata)
            self.new_file.emit(full_name)

    def _save_result_video(self, video_data):
        dir = replace_variables_in_string("%year%-%month%-%day%")
        if len(self._output_root):
            dir = f"{self._output_root}/{dir}"
        os.makedirs(dir, exist_ok=True)
        self._output_count = (self._output_count - 9) % 90 + 10
        filename = replace_variables_in_string(
            f"%year%%month%%day%%hour%%minute%%second%-{self._output_count}.mp4"
        )
        full_name = f"{dir}/{filename}"
        if self._last_prompt_id in self._active_job_widgets:
            widget = self._active_job_widgets[self._last_prompt_id]

            metadata = self._build_metadata_for_result(widget.job)
            swarm_json_path = get_swarm_json_path(full_name)
            try:
                with open(swarm_json_path, "w") as json_file:
                    json.dump(metadata, json_file, indent=2)
            except IOError as e:
                print(f"Error saving file: {e}")

            # Save the video data to file
            with open(full_name, "wb") as f:
                f.write(video_data)

            swarm_preview_path = get_swarm_preview_path(full_name)
            # Use cv2 to grab first frame from the video and save as a swarmpreview.jpg
            try:
                # Open the video file
                cap = cv2.VideoCapture(full_name)
                if cap.isOpened():
                    # Read the first frame
                    ret, frame = cap.read()
                    if ret:
                        # Save the first frame as JPEG
                        cv2.imwrite(swarm_preview_path, frame)
                    cap.release()
            except Exception as e:
                print(f"Error creating video preview: {e}")

            # Store the filename in results
            if "output_files" not in widget.job.results[widget.job.completions]:
                widget.job.results[widget.job.completions]["output_files"] = []
            widget.job.results[widget.job.completions]["output_files"].append(full_name)
            self.new_file.emit(full_name)

    def _update_stats(self):
        """Fetch and display system statistics from the ComfyUI server."""
        try:
            # Check if we have a connected comfy server
            if not hasattr(self, "_comfy_server") or not self._comfy_server:
                self.system_info_widget.setText("ComfyUI server not connected.")
                self.devices_widget.setText("No device information available.")
                return

            # Get system stats from the server
            system_stats = self._comfy_server.get_system_stats("stats")

            # Format and display system information
            system_info_lines = []
            if "system" in system_stats:
                system = system_stats["system"]
                system_info_lines.append(f"<b>OS:</b> {system.get('os', 'N/A')}")
                system_info_lines.append(
                    f"<b>Python Version:</b> {system.get('python_version', 'N/A')}"
                )
                system_info_lines.append(
                    f"<b>PyTorch Version:</b> {system.get('pytorch_version', 'N/A')}"
                )
                system_info_lines.append(
                    f"<b>ComfyUI Version:</b> {system.get('comfyui_version', 'N/A')}"
                )

                # RAM information
                ram_total = system.get("ram_total", 0)
                ram_free = system.get("ram_free", 0)
                if ram_total > 0:
                    ram_used = ram_total - ram_free
                    ram_percent = (ram_used / ram_total * 100) if ram_total > 0 else 0
                    system_info_lines.append(
                        f"<b>RAM:</b> {ram_used / (1024**3):.2f}GB / {ram_total / (1024**3):.2f}GB ({ram_percent:.1f}% used)"
                    )

                # Frontend version info
                if "required_frontend_version" in system:
                    system_info_lines.append(
                        f"<b>Frontend Version:</b> {system.get('required_frontend_version', 'N/A')}"
                    )

                # Templates version info
                if "installed_templates_version" in system:
                    installed = system.get("installed_templates_version", "N/A")
                    required = system.get("required_templates_version", "N/A")
                    version_status = "✓" if installed == required else "⚠"
                    system_info_lines.append(
                        f"<b>Templates:</b> {version_status} {installed} (required: {required})"
                    )

                # Embedded Python info
                if "embedded_python" in system:
                    embedded_status = "Yes" if system["embedded_python"] else "No"
                    system_info_lines.append(
                        f"<b>Embedded Python:</b> {embedded_status}"
                    )

            self.system_info_widget.setText("<br>".join(system_info_lines))

            # Format and display devices information
            devices_lines = []
            if "devices" in system_stats and system_stats["devices"]:
                for i, device in enumerate(system_stats["devices"]):
                    # store the device name for inserting into metadata
                    self._current_device = device.get("name", "N/A")
                    devices_lines.append(
                        f"<b>Device {i + 1}:</b> {device.get('name', 'N/A')}"
                    )
                    devices_lines.append(f"  <b>Type:</b> {device.get('type', 'N/A')}")
                    devices_lines.append(
                        f"  <b>Index:</b> {device.get('index', 'N/A')}"
                    )

                    # VRAM information
                    vram_total = device.get("vram_total", 0)
                    vram_free = device.get("vram_free", 0)
                    if vram_total > 0:
                        vram_used = vram_total - vram_free
                        vram_percent = (
                            (vram_used / vram_total * 100) if vram_total > 0 else 0
                        )
                        devices_lines.append(
                            f"  <b>VRAM:</b> {vram_used / (1024**3):.2f}GB / {vram_total / (1024**3):.2f}GB ({vram_percent:.1f}% used)"
                        )

                    # Torch VRAM information
                    torch_vram_total = device.get("torch_vram_total", 0)
                    torch_vram_free = device.get("torch_vram_free", 0)
                    if torch_vram_total > 0:
                        torch_vram_used = torch_vram_total - torch_vram_free
                        torch_vram_percent = (
                            (torch_vram_used / torch_vram_total * 100)
                            if torch_vram_total > 0
                            else 0
                        )
                        devices_lines.append(
                            f"  <b>Torch VRAM:</b> {torch_vram_used / (1024**3):.2f}GB / {torch_vram_total / (1024**3):.2f}GB ({torch_vram_percent:.1f}% used)"
                        )

                    devices_lines.append("")  # Add spacing between devices
            else:
                devices_lines.append("No devices detected.")

            self.devices_widget.setText("<br>".join(devices_lines))

        except Exception as e:
            error_msg = f"Error fetching stats: {str(e)}"
            self.system_info_widget.setText(error_msg)
            self.devices_widget.setText("No device information available.")

    def _update_deque(self):
        # update stats
        self._update_stats()

        # Update total runtime label
        self._update_total_runtime_label()

        if len(self._new_job_widgets) < 1:
            return

        # make sure we are connected
        if not self._comfy_server.is_connected():
            return

        # Update elapsed progress for all active jobs
        for job_widget in self._active_job_widgets.values():
            job_widget.set_elapsed_progress()

        # move to next job if ready
        if len(self._active_job_widgets) == 0 and len(self._new_job_widgets) > 0:
            job_widget = self._new_job_widgets[0]
            if not job_widget.job.error:
                queue_result = self._comfy_server.queue_prompt(job_widget.job)
                self._active_job_widgets[queue_result["prompt_id"]] = job_widget
                self._active_job_widgets[queue_result["prompt_id"]].mark_submitted()

    def clear_history(self):
        """Clear the history tab by removing all completed job widgets."""
        # Clear all widgets from the history layout
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

        # Clear the old job widgets deque
        self._old_job_widgets.clear()
