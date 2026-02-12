"""
ServersWidget module for bowser-gen.

This module provides a tabbed interface with one tab per ComfyUI server,
where each tab contains a QueueWidget instance for managing jobs on that server.
"""
import json
from collections import defaultdict
from pathlib import Path
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTabWidget, QWidget, QVBoxLayout
from .queuewidget import QueueWidget

# Performance data based on GPU compute power and VRAM capacity
# Values represent operations per second (higher is better)
# RTX 3090 used as baseline reference (600,000 ops/sec)
performance_data = {
    "Wan22-I2V-Lora-Lightning-API": {"3090": 566065, "5090": 1850000},
    "z_image_turbo-API": {"3090": 800920, "5090": 1900000},
    "Wan22-Extend-24G-Q6-API": {"3090": 500000, "5090": 1750000},
    "Flux2-IEdit-API": {"5090": 270000},
    "Qwen-IEdit-API": {"5090": 450000},
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

class ServersWidget(QWidget):
    """
    A widget containing a tabbed interface with one tab per server.
    Each tab contains a QueueWidget instance for managing jobs on that server.
    """

    # Signal emitted when status needs to be updated
    status_update = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Servers Widget")
        self._performance_data = performance_data.copy()  # Start with default performance data
        self._performance_file = Path("bowser-performance.json")

        # Dictionary to map server addresses to queue widgets
        self._server_queue_widgets = {}
        
        # Dictionary to map server addresses to comfy servers
        self._server_instances = {}
        
        # Dictionary to map server addresses to output roots
        self._server_output_roots = {}
        
        # Create the main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create the tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)
        self.tab_widget.setStyleSheet("""QTabBar::tab:selected { background-color: #666; }""")

        # Set the main layout
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.tab_widget)
        self.setLayout(layout)
        self.load_performance_data()

    def save_performance_data(self):
        """
        Save the performance data to a JSON file.

        """
        if len(self._server_queue_widgets) <= 0:
            return
        
        with open(self._performance_file, "w") as f:
            json.dump(self._performance_data, f, indent=4)

    def load_performance_data(self):
        """
        Load performance data from a JSON file.
        """
        try:
            with open(self._performance_file, "r") as f:
                self._performance_data.update(json.load(f))
        except FileNotFoundError:
            pass  # No performance data file found, use defaults

    def add_server(self, server_address, comfy_server):
        """
        Add a new server tab to the interface.

        Args:
            server_address (str): The address of the server (e.g., "127.0.0.1:8188")
            comfy_server: The comfyServer instance for this server
        """
        if server_address in self._server_queue_widgets:
            return  # Server already exists

        # Create a new queue widget for this server
        queue_widget = QueueWidget(len(self._server_queue_widgets))
        queue_widget.set_comfy_server(comfy_server)
        queue_widget.set_performance_data(self._performance_data)    
        
        # Store the queue widget and server instance
        self._server_queue_widgets[server_address] = queue_widget
        self._server_instances[server_address] = comfy_server
        
        # Add the queue widget to a tab
        tab_name = self._format_tab_name(server_address)
        self.tab_widget.addTab(queue_widget, tab_name)

    def set_output_root(self, server_address, root):
        """
        Set the output root for a specific server.

        Args:
            server_address (str): The address of the server
            root (str): The output root directory
        """
        if server_address in self._server_queue_widgets:
            self._server_output_roots[server_address] = root
            self._server_queue_widgets[server_address].set_output_root(root)

    def set_output_root_for_all(self, root):
        """
        Set the output root for all servers.

        Args:
            root (str): The output root directory
        """
        for server_address, queue_widget in self._server_queue_widgets.items():
            self._server_output_roots[server_address] = root
            queue_widget.set_output_root(root)

    def queue_job_on_current_tab(self, workflow_name, workflow, count):
        """
        Queue a job on the currently selected server tab.

        Args:
            workflow_name (str): The name of the workflow to queue
            workflow: The workflow object to execute
            count (int): The number of times to run the workflow
        """
        current_index = self.tab_widget.currentIndex()
        if current_index != -1:
            server_address = list(self._server_queue_widgets.keys())[current_index]
            self.queue_job(server_address, workflow_name, workflow, count)

    def queue_job(self, server_address, workflow_name, workflow, count):
        """
        Queue a job on a specific server.

        Args:
            server_address (str): The address of the server
            workflow_name (str): The name of the workflow to queue
            workflow: The workflow object to execute
            count (int): The number of times to run the workflow
        """
        if server_address in self._server_queue_widgets:
            self._server_queue_widgets[server_address].queue_job(
                workflow_name, workflow, count
            )

    def get_queue_widget(self, server_address):
        """
        Get the QueueWidget instance for a specific server.

        Args:
            server_address (str): The address of the server

        Returns:
            QueueWidget: The queue widget for the specified server, or None if not found
        """
        return self._server_queue_widgets.get(server_address)

    def get_all_queue_widgets(self):
        """
        Get all QueueWidget instances.

        Returns:
            dict: A dictionary mapping server addresses to QueueWidget instances
        """
        return self._server_queue_widgets

    def _format_tab_name(self, server_address):
        """
        Format a server address for display as a tab name.

        Args:
            server_address (str): The server address

        Returns:
            str: Formatted tab name
        """
        # Remove port if it's the default (8188)
        if ":8188" in server_address:
            return server_address.replace(":8188", "")
        return server_address

    def connect_signals(self, target):
        """
        Connect signals from all queue widgets to the target object.

        Args:
            target: The target object to connect signals to
        """
        for queue_widget in self._server_queue_widgets.values():
            queue_widget.new_file.connect(target.got_new_file)
            queue_widget.show_file.connect(target.got_show_file)
            queue_widget.reload_job.connect(target._reload_job)
            queue_widget.new_pil_image.connect(target.got_new_image)
            # Connect status_update signals from queue widgets to this widget
            queue_widget.status_update.connect(self.status_update)

    def clear_history(self):
        """
        Clear the history for all queue widgets.
        """
        for queue_widget in self._server_queue_widgets.values():
            queue_widget.clear_history()
