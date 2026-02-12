import io
import json
import os
import struct
import time
from collections import deque

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
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .comfyserver import comfyServer
from .job import Job
from .jobwidget import JobWidget

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
    # Signal emitted when status needs to be updated
    status_update = Signal(str)

    def __init__(self, index, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Queue Widget")
        self._server_index = index
        self._new_job_widgets = deque()
        self._queue_update_time = 4000  # in ms
        self._active_job_widgets = {}
        self._old_job_widgets = deque()
        self._output_count = 10
        self._output_root = ""
        self._current_device = "unknown"
        self._paused = False

        # Create the main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create the tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)
        self.tab_widget.setStyleSheet("""QTabBar::tab:selected { background-color: #444; }""")


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
        # Pause/Resume button
        self.pause_button = QPushButton("Pause Queue")
        self.pause_button.setStyleSheet(
            """QPushButton {
                background-color: #a33;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover {
                background-color: #c22;
            }"""
        )
        self.pause_button.clicked.connect(self._toggle_pause)

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
        self.stats_layout.addWidget(self.pause_button)
        self.stats_layout.addSpacing(20)
        self.stats_layout.addWidget(self.system_info_label)
        self.stats_layout.addWidget(self.system_info_widget)
        self.stats_layout.addWidget(self.devices_label)
        self.stats_layout.addWidget(self.devices_widget)

        # Add some spacing
        self.stats_layout.addStretch()

    def _job_canceled(self, job_widget):
        # Check if the job is in the old job widgets and remove/delete it
        for old_widget in list(self._old_job_widgets):
            if old_widget is job_widget:
                self._old_job_widgets.remove(old_widget)
                self.history_layout.removeWidget(old_widget)
                old_widget.deleteLater()
                break

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

    def _toggle_pause(self):
        """Toggle the pause state of the queue."""
        self._paused = not self._paused
        if self._paused:
            self.pause_button.setText("Resume Queue")
            self.pause_button.setStyleSheet(
                """QPushButton {
                    background-color: #3a3;
                    color: black;
                    font-weight: bold;
                    padding: 10px;
                    border-radius: 5px;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #2e2;
                }"""
            )
        else:
            self.pause_button.setText("Pause Queue")
            self.pause_button.setStyleSheet(
                """QPushButton {
                    background-color: #a33;
                    color: white;
                    font-weight: bold;
                    padding: 10px;
                    border-radius: 5px;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #c22;
                }"""
            )

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

    def set_performance_data(self, performance_data):
        """Set the performance data for this queue widget.

        Args:
            performance_data (dict): A dictionary containing performance data
        """
        self._performance_data = performance_data

    def get_performance_rate(self, name, gpu):
        """Get the rate for a workflow and GPU from performance_data.

        Args:
            name (str): The workflow name
            gpu (str): The GPU identifier

        Returns:
            float: The rate for this workflow and GPU, or an average if not found
        """
        # Check if we have performance data
        if not self._performance_data:
            return 100000.0  # Default rate, low end

        # Try to get the exact match
        if name in self._performance_data and gpu in self._performance_data[name]:
            return self._performance_data[name][gpu]

        # If workflow_name not found, average all entries that match the GPU
        matching_rates = []
        for workflow_name, gpu_data in self._performance_data.items():
            if gpu in gpu_data:
                matching_rates.append(self._performance_data[workflow_name][gpu])

        if matching_rates:
            return sum(matching_rates) / len(matching_rates)

        # If GPU not found, average all entries that match the workflow_name
        if name in self._performance_data:
            gpu_rates = list(self._performance_data[name].values())
            if gpu_rates:
                return sum(gpu_rates) / len(gpu_rates)

        # If neither is found, average all entries
        all_rates = []
        for workflow_data in self._performance_data.values():
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
        # Check the workflow to make sure the models are all available
        missing_models = self._check_workflow_models(workflow)

        if missing_models:
            missing_models_str = ", ".join(missing_models)
            print(
                f"Error: The following models are not available on the ComfyUI server: {missing_models_str}"
            )
            # Show a user-friendly error dialog
            QMessageBox.critical(
                self,
                "Missing Models",
                f"The following models are not available on the ComfyUI server:\n\n{missing_models_str}\n\n"
                "Please ensure these models are installed in your ComfyUI models directory.",
                QMessageBox.StandardButton.Ok,
            )
            return

        # Create a QueuedWorkflow and QueuedWorkflowWidget for this job
        job = Job(workflow_name, workflow, count)
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

                    if active_widget.job.is_completed():
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
                        if not active_widget.job.error and not self._paused:
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
            elif type_num == 5:  # swarmui mp4 result, 6 is webm 7 is prores
                data = bytesmessage[8:]
                self._save_result_video(data)
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
                full_name = f"{dir}/bowser-temp-preview{self._server_index}.webp"
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
            "generation_time": job.results[job.completions]["elapsed_time"],
        }
        if "original_prompt" in job.results[job.completions]:
            sui_extra_data["original_prompt"] = job.results[job.completions]["original_prompt"]

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

    def _update_performance_data(self, workflow_name, device, generation_time, ops):
        # ignore instant generations or empty workflows
        if generation_time <= 0 or ops <= 0:
            return
        
        gpu = get_gpu_from_device_string(device)
        # remember is is a reference to a dict, so updates will be reflected in the original dict
        if gpu and workflow_name:
            # Update the performance data with a simple moving average
            if workflow_name not in self._performance_data:
                self._performance_data[workflow_name] = {}
            if gpu in self._performance_data[workflow_name]:
                old_rate = self._performance_data[workflow_name][gpu]
                new_rate = ops / generation_time
                self._performance_data[workflow_name][gpu] = round(0.9*old_rate + 0.1*new_rate)
            else:
                self._performance_data[workflow_name][gpu] = round(ops / generation_time)

    def _save_result_image(self, image):
        dir = replace_variables_in_string("%year%-%month%-%day%")
        if len(self._output_root):
            dir = f"{self._output_root}/{dir}"
        os.makedirs(dir, exist_ok=True)
        self._output_count = (self._output_count - 9) % 90 + 10
        filename = replace_variables_in_string(
            f"%year%%month%%day%%hour%%minute%%second%-{self._server_index}{self._output_count}.png"
        )
        full_name = f"{dir}/{filename}"
        if self._last_prompt_id in self._active_job_widgets:
            widget = self._active_job_widgets[self._last_prompt_id]
            # Store the filename in results
            widget.job.results[widget.job.completions]["output_files"] = [full_name]
            # Save workflow and count as metadata in the image
            datmetadata = self._build_metadata_for_result(widget.job)
            self._update_performance_data(
                widget.job.workflow_name, 
                self._current_device, 
                datmetadata["bowser_params"]["generation_time"],
                widget.job.ops)
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
            f"%year%%month%%day%%hour%%minute%%second%-{self._server_index}{self._output_count}.mp4"
        )
        full_name = f"{dir}/{filename}"
        if self._last_prompt_id in self._active_job_widgets:
            widget = self._active_job_widgets[self._last_prompt_id]

            metadata = self._build_metadata_for_result(widget.job)
            self._update_performance_data(
                widget.job.workflow_name, 
                self._current_device, 
                metadata["bowser_params"]["generation_time"],
                widget.job.ops)
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
            system_stats: dict = self._comfy_server.get_system_stats()

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
                            (vram_used / vram_total * 100) if vram_total > 0
                            else 0
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
        if len(self._active_job_widgets) == 0 and len(self._new_job_widgets) > 0 and not self._paused:
            # start the first new_job without an error
            for job_widget in self._new_job_widgets:
                if not job_widget.job.error:
                    queue_result = self._comfy_server.queue_prompt(job_widget.job)
                    if "error" in queue_result:
                        job_widget.error()
                        error_msg = f"Error queuing job: {queue_result['error']}"
                        QMessageBox.critical(
                            self, "Queue Error", error_msg, QMessageBox.StandardButton.Ok
                        )
                        continue
                    self._active_job_widgets[queue_result["prompt_id"]] = job_widget
                    self._active_job_widgets[queue_result["prompt_id"]].mark_submitted()
                    break

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

    def _find_alternative_model(self, model_name, available_models, node_data):
        """Find an alternative model when the requested model is not available.

        This method tries to find alternative models by:
        1. For GGUF models: trying different quantizations (Q8 -> Q6 -> Q4, etc.)
        2. For FP16 models: trying other precision (FP16 -> FP8)
        3. For other models: looking for similar names

        Args:
            model_name: The name of the model to find an alternative for
            available_models: List of available model names
            node_data: The node data dictionary

        Returns:
            str: The alternative model name if found, None otherwise
        """
        # Check if it's a GGUF model
        if model_name.endswith(".gguf"):
            # Try different quantizations
            quantization_levels = [
                "Q8_0",
                "Q6_K",
                "Q5_K_M",
                "Q5_K_S",
                "Q5_1",
                "Q5_0",
                "Q4_K_M",
                "Q4_K_S",
            ]
            base_name = model_name.replace(".gguf", "")

            # Extract the current quantization if present
            current_quant = None
            for quant in quantization_levels:
                if quant in base_name:
                    current_quant = quant
                    break

            # If we found a quantization, try others
            if current_quant:
                for quant in quantization_levels:
                    if quant == current_quant:
                        continue
                    # Try to replace the quantization
                    alternative = (
                        base_name.replace(current_quant, quant) + ".gguf"
                    )
                    if alternative in available_models:
                        return alternative

            # If no quantization found or none worked, try common patterns
            for quant in quantization_levels:
                # Try adding quantization suffix
                alternative = f"{base_name}_{quant}.gguf"
                if alternative in available_models:
                    return alternative

                # Try uppercase quantization suffix
                alternative = f"{base_name}_{quant.upper()}.gguf"
                if alternative in available_models:
                    return alternative

        # Check if it's an FP16 model
        elif "fp16" in model_name.lower():
            base_name = model_name.replace(".fp16", "").replace("fp16", "")

            # Try FP8 version
            alternative = f"{base_name}.fp8"
            if alternative in available_models:
                return alternative

            # Try lowercase fp8
            alternative = f"{base_name}.fp8"
            if alternative in available_models:
                return alternative

        # Check if it's a safetensors model
        elif model_name.endswith(".safetensors"):
            base_name = model_name.replace(".safetensors", "")

            # Try .ckpt version
            alternative = f"{base_name}.ckpt"
            if alternative in available_models:
                return alternative

        # Try to find any model with similar name (fallback)
        base_name = model_name.split("_")[0]  # Get base name before any suffix
        for available_model in available_models:
            if base_name.lower() in available_model.lower():
                return available_model

        return None

    def _check_workflow_models(self, workflow):
        """Check if all models required by the workflow are available on the ComfyUI server.

        Args:
            workflow: The workflow dictionary

        Returns:
            list: List of missing model names, empty if all models are available
        """
        if not self._comfy_server or not self._comfy_server.is_connected():
            print(
                "Warning: ComfyUI server not connected, cannot check model availability"
            )
            return []

        models = self._comfy_server.get_all_models_available()

        # List of node classes that load models
        model_loader_classes = [
            "UnetLoaderGGUF",
            "VAELoader",
            "CLIPLoaderGGUF",
            "CheckpointLoaderSimple",
            "LoraLoader",
            "ModelLoader",
            "UNETLoader",
        ]

        missing_models = []

        # Check each node in the workflow
        for node_id, node_data in workflow.items():
            class_type = node_data.get("class_type", "")

            # Check if this node loads a model
            if class_type in model_loader_classes:
                inputs = node_data.get("inputs", {})

                # Get the model name from the appropriate input field
                if class_type == "UnetLoaderGGUF" and "unet_name" in inputs:
                    model_name = inputs["unet_name"]
                elif class_type == "UNETLoader" and "unet_name" in inputs:
                    model_name = inputs["unet_name"]
                elif class_type == "VAELoader" and "vae_name" in inputs:
                    model_name = inputs["vae_name"]
                elif class_type == "CLIPLoaderGGUF" and "clip_name" in inputs:
                    model_name = inputs["clip_name"]
                elif class_type == "CheckpointLoaderSimple" and "ckpt_name" in inputs:
                    model_name = inputs["ckpt_name"]
                elif class_type == "LoraLoader" and "lora_name" in inputs:
                    model_name = inputs["lora_name"]
                elif class_type == "ModelLoader" and "model_name" in inputs:
                    model_name = inputs["model_name"]
                else:
                    continue

                # if it is a link then ignore
                if type(model_name) is list:
                    continue

                # Check if the model is available
                if model_name not in models:
                    # Try to find an alternative AI model
                    alternative_model = self._find_alternative_model(
                        model_name, models, node_data
                    )
                    if alternative_model:
                        print(f"alt model for {model_name} is {alternative_model}")
                        # Update the node_data to use the alternative model
                        if class_type == "UnetLoaderGGUF" and "unet_name" in inputs:
                            node_data["inputs"]["unet_name"] = alternative_model
                        elif class_type == "UNETLoader" and "unet_name" in inputs:
                            node_data["inputs"]["unet_name"] = alternative_model
                        elif class_type == "VAELoader" and "vae_name" in inputs:
                            node_data["inputs"]["vae_name"] = alternative_model
                        elif class_type == "CLIPLoaderGGUF" and "clip_name" in inputs:
                            node_data["inputs"]["clip_name"] = alternative_model
                        elif (
                            class_type == "CheckpointLoaderSimple"
                            and "ckpt_name" in inputs
                        ):
                            node_data["inputs"]["ckpt_name"] = alternative_model
                        elif class_type == "LoraLoader" and "lora_name" in inputs:
                            node_data["inputs"]["lora_name"] = alternative_model
                        elif class_type == "ModelLoader" and "model_name" in inputs:
                            node_data["inputs"]["model_name"] = alternative_model
                        # Don't add to missing_models since we found an alternative
                    else:
                        missing_models.append(model_name)

        return missing_models
