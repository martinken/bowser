"""
Jobs widget for the Dueser application.
Contains a QTabWidget with Workflows and Settings tabs.
"""

import copy
import json
import os
from typing import Optional

from core.metadatahandler import MetadataHandler
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .comfyserver import comfyServer
from .workflownodewidget import WorkflowNodeWidget

class WorkflowsTreeWidgetItem(QTreeWidgetItem):
    """
    Custom QTreeWidgetItem subclass for workflows that adds full_path and is_populated members.

    This item extends QTreeWidgetItem to include additional attributes for managing
    workflow file paths and lazy loading state.
    """

    def __init__(self, parent: QTreeWidget, strings: list[str]):
        super().__init__(parent, strings)
        # Initialize custom attributes
        self.full_path: Optional[str] = None
        self.is_populated: bool = False


class WorkflowsWidget(QWidget):
    """
    Widget containing tabs for managing workflows and settings.
    """

    _comfy_server: comfyServer
    _workflow_data: dict
    _settings_widget: QWidget

    # Signal emitted when a job is queued
    job_queued = Signal(str, dict, int)

    def __init__(self):
        super().__init__()
        self.setMinimumWidth(250)

        # Create main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create tab widget
        self.tab_widget = QTabWidget()

        # Create placeholder widgets for each tab
        self.workflows_tab = QWidget()
        self.settings_tab = QWidget()
        self._settings_layout = QVBoxLayout(self.settings_tab)
        self._settings_layout.setContentsMargins(0, 0, 0, 0)
        self._settings_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Add tabs
        self.tab_widget.addTab(self.workflows_tab, "Workflows")
        self.tab_widget.addTab(self.settings_tab, "Settings")

        # Add tab widget to layout
        layout.addWidget(self.tab_widget)
        self.setLayout(layout)

        # Initialize workflows directory tree
        self._initialize_workflows_tree()

        # Enable drag and drop for the entire widget
        self.setAcceptDrops(True)
        self.settings_tab.setAcceptDrops(True)
        self.workflows_tab.setAcceptDrops(True)

    def set_comfy_server(self, comfy_server):
        self._comfy_server = comfy_server

    def set_output_root(self, root):
        """Set the output root directory for finding image files.

        Args:
            root: Path to the output root directory
        """
        self._output_root = root

    def _initialize_workflows_tree(self):
        """Initialize the directory tree for workflows."""
        # Create tree widget
        self.workflows_tree = QTreeWidget()
        self.workflows_tree.setHeaderHidden(True)
        self.workflows_tree.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        font = QFont()
        font.setPointSize(12)  # Use setPixelSize() for pixel-based sizing
        self.workflows_tree.setFont(font)

        # Connect signals
        self.workflows_tree.itemClicked.connect(self._on_workflow_item_clicked)
        self.workflows_tree.itemExpanded.connect(self._on_item_expanded)

        # Populate tree with workflows directory
        self._populate_workflows_tree()

        # Set tree as workflows tab content
        self.set_workflows_content(self.workflows_tree)

    def _populate_workflows_tree(self):
        """Populate the tree widget with workflows directory structure."""
        # Use the workflows directory from instance variable or default to "workflows"
        workflows_dir = getattr(self, "workflows_directory", "workflows")

        if not os.path.exists(workflows_dir):
            # Create workflows directory if it doesn't exist
            os.makedirs(workflows_dir)
            root_name = (
                os.path.basename(workflows_dir)
                if os.path.basename(workflows_dir)
                else "workflows"
            )
            # Show message directly in tree
            root = QTreeWidgetItem(self.workflows_tree, [f"{root_name} (empty)"])
            root.setChildIndicatorPolicy(
                QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator
            )
            return

        # First pass: find all directories that contain JSON files
        json_dirs = set()

        for dirpath, dirnames, filenames in os.walk(workflows_dir, topdown=False):
            # Check if this directory contains any JSON files
            has_json = any(filename.endswith(".json") for filename in filenames)
            if has_json:
                json_dirs.add(dirpath)

        if not json_dirs:
            # No JSON files found
            root_name = (
                os.path.basename(workflows_dir)
                if os.path.basename(workflows_dir)
                else "workflows"
            )
            # Show message directly in tree
            root = WorkflowsTreeWidgetItem(
                self.workflows_tree, [f"{root_name} (no JSON files)"]
            )
            root.setChildIndicatorPolicy(
                QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator
            )
            return

        # Build the tree structure with only directories containing JSON files
        # but don't add the JSON files yet (lazy loading)
        # Start directly with subdirectories of workflows_dir
        for dirpath, dirnames, filenames in os.walk(workflows_dir):
            # Get relative path
            rel_path = os.path.relpath(dirpath, workflows_dir)

            # Only process directories that contain JSON files
            if dirpath not in json_dirs:
                continue

            # Determine parent item
            if rel_path == ".":
                # This is the workflows_dir itself
                # Add JSON files directly to the tree
                for filename in filenames:
                    if filename.endswith(".json"):
                        file_item = WorkflowsTreeWidgetItem(
                            self.workflows_tree, [filename]
                        )
                        file_item.setChildIndicatorPolicy(
                            QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicatorWhenChildless
                        )
                        # Store full path for loading
                        file_item.full_path = os.path.join(workflows_dir, filename)
                continue

            # Find or create parent item
            parent_path_parts = rel_path.split(os.sep)
            # The parent should be the item above the current directory
            parent_path = os.path.join(workflows_dir, *parent_path_parts[:-1])

            if parent_path == workflows_dir:
                # Parent is the root workflows directory, add directly to tree
                parent_item = None
            else:
                # Find parent in tree
                parent_item = self._find_item_in_tree(
                    self.workflows_tree.invisibleRootItem(), parent_path
                )

            # Add current directory
            dirname = os.path.basename(dirpath)
            if parent_item is None:
                # Add as top-level item
                dir_item = WorkflowsTreeWidgetItem(self.workflows_tree, [dirname])
            else:
                dir_item = WorkflowsTreeWidgetItem(parent_item, [dirname])

            dir_item.setChildIndicatorPolicy(
                QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
            )
            # Store path for lazy loading
            dir_item.full_path = dirpath
            dir_item.is_populated = False

        # No need to expand root since we don't have a root item

    def _find_item_in_tree(self, parent, target_path):
        """Find an item in the tree by its full path."""
        # Check if this parent is the target
        if hasattr(parent, "full_path") and parent.full_path == target_path:
            return parent

        # Search recursively in children
        for i in range(parent.childCount()):
            child = parent.child(i)
            if hasattr(child, "full_path") and child.full_path == target_path:
                return child
            # Recursively search in child's children
            found = self._find_item_in_tree(child, target_path)
            if found:
                return found

        return None

    def _find_or_create_item(self, parent, path_parts):
        """Find or create a tree item for the given path parts."""
        if not path_parts:
            return parent

        # Find child with matching name
        for i in range(parent.childCount()):
            child = parent.child(i)
            if child.text(0) == path_parts[0]:
                return self._find_or_create_item(child, path_parts[1:])

        # Create new item
        new_item = QTreeWidgetItem(parent, [path_parts[0]])
        new_item.setChildIndicatorPolicy(
            QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
        )
        return self._find_or_create_item(new_item, path_parts[1:])

    def _on_item_expanded(self, item):
        """Handle item expansion in the workflows tree (lazy loading)."""
        # Only populate if this item hasn't been populated yet and it's a directory
        if not getattr(item, "is_populated", True):
            self._populate_directory(item)

    def _populate_directory(self, item):
        """Populate a directory item with its JSON files."""
        # Mark as populated to avoid re-populating
        item.is_populated = True

        # Get the full path of this directory
        dir_path = getattr(item, "full_path", None)

        if dir_path is None:
            # This is the root item
            workflows_dir = getattr(self, "workflows_directory", "workflows")
            dir_path = workflows_dir

        # List all JSON files in this directory
        try:
            filenames = os.listdir(dir_path)
            json_files = [f for f in filenames if f.endswith(".json")]

            # Add JSON files as children
            for filename in json_files:
                file_item = WorkflowsTreeWidgetItem(item, [filename])
                file_item.setChildIndicatorPolicy(
                    QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicatorWhenChildless
                )
                # Store full path for loading
                file_item.full_path = os.path.join(dir_path, filename)

        except Exception as e:
            print(f"Error populating directory {dir_path}: {e}")

    def _on_workflow_item_clicked(self, item):
        """Handle item click in the workflows tree."""
        # Check if the clicked item is a JSON file
        if item.childCount() == 0 and item.text(0).endswith(".json"):
            self._workflow_data = self.load_workflow(item)
            # Store the filename without extension for the title
            self._workflow_data_filename = os.path.splitext(item.text(0))[0]
            self._gui_nodes = self.extract_gui_nodes(self._workflow_data)
            self.build_gui_from_nodes(self._gui_nodes)
            # Switch to the Settings tab
            self.tab_widget.setCurrentWidget(self.settings_tab)

    def load_workflow(self, tree_item):
        """
        Load a workflow from the selected JSON file.

        Args:
            tree_item: The QTreeWidgetItem representing the JSON file
        """
        # Get the full path to the JSON file
        file_path = getattr(tree_item, "full_path", None)

        if file_path is None:
            # Fallback to old method if full_path is not set
            workflows_dir = getattr(self, "workflows_directory", "workflows")

            # Build the path by traversing up the tree
            path_parts = []
            current = tree_item
            while current.parent():
                path_parts.insert(0, current.text(0))
                current = current.parent()

            # The parent should be the root workflows item
            root_name = (
                os.path.basename(workflows_dir)
                if os.path.basename(workflows_dir)
                else "workflows"
            )
            if current.text(0) != root_name:
                return {}

            file_path = os.path.join(workflows_dir, *path_parts)

        # Load and parse the JSON file
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                workflow = json.load(f)
                return workflow

        except Exception as e:
            print(f"Error loading workflow {file_path}: {e}")

        return {}

    def _load_workflow_by_name(self, workflow_name):
        """
        Search for a workflow by name in the workflows tree and load it.

        This method searches through all JSON files in the workflows tree
        to find one whose filename (without extension) matches the given
        workflow_name. If found, it loads that workflow and builds the GUI.

        Args:
            workflow_name (str): The name of the workflow to load (without .json extension)
        """
        if not hasattr(self, "workflows_tree"):
            print(
                f"Warning: workflows_tree not initialized, cannot load workflow by name: {workflow_name}"
            )
            return

        # Search through all items in the tree
        root = self.workflows_tree.invisibleRootItem()
        found_item = self._find_workflow_by_name(root, workflow_name)

        if found_item:
            # Load the workflow
            self._workflow_data = self.load_workflow(found_item)
            # Store the filename without extension for the title
            self._workflow_data_filename = workflow_name
            # Extract GUI nodes and build the GUI
            self._gui_nodes = self.extract_gui_nodes(self._workflow_data)
            self.build_gui_from_nodes(self._gui_nodes)
            # Switch to the Settings tab
            self.tab_widget.setCurrentWidget(self.settings_tab)
        else:
            print(f"Warning: Workflow '{workflow_name}' not found in workflows tree")

    def _find_workflow_by_name(self, parent_item, workflow_name):
        """
        Recursively search for a workflow file with the given name.

        Args:
            parent_item: The parent QTreeWidgetItem to search under
            workflow_name (str): The name of the workflow to find (without .json extension)

        Returns:
            QTreeWidgetItem: The found workflow item, or None if not found
        """
        # Check if this item is a JSON file with matching name
        if parent_item.childCount() == 0 and parent_item.text(0).endswith(".json"):
            item_name = os.path.splitext(parent_item.text(0))[0]
            if item_name == workflow_name:
                return parent_item

        # Recursively search in children
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            found = self._find_workflow_by_name(child, workflow_name)
            if found:
                return found

        return None

    def set_workflows_content(self, widget):
        """Replace the placeholder workflows tab content."""
        layout = QVBoxLayout(self.workflows_tab)
        layout.addWidget(widget)

    def set_settings_content(self, widget):
        """Replace the settings tab content."""
        if hasattr(self, "_settings_widget"):
            self._settings_layout.removeWidget(self._settings_widget)
            self._settings_widget.deleteLater()
        self._settings_widget = widget
        self._settings_layout.addWidget(widget)

    def extract_gui_nodes(self, workflow_data):
        """
        Extract GUI nodes from workflow data.

        Traverses all nodes in the workflow data and extracts any nodes whose
        type starts with 'SwarmInput'.

        Args:
            workflow_data: Dictionary containing workflow data with nodes

        Returns:
            List of nodes whose type starts with 'SwarmInput'
        """
        gui_nodes = {}

        # Iterate through all nodes
        for id, node in workflow_data.items():
            # Check if node has a type attribute and if it starts with 'SwarmInput'
            if (
                "class_type" in node
                and node["class_type"].startswith("SwarmInput")
                and not node["class_type"].startswith("SwarmInputGroup")
            ):
                gui_nodes[id] = node
                # find the options for a swarm dropdown
                if node["class_type"] == "SwarmInputDropdown":
                    for id2, node2 in workflow_data.items():
                        for name, input in node2["inputs"].items():
                            if isinstance(input, list) and input[0] == id:
                                # call the server to get the info for that class
                                info = self._comfy_server.get_object_info(
                                    node2["class_type"]
                                )
                                classinfo = info[node2["class_type"]]
                                # extract and store the options
                                options = None
                                if "required" in classinfo["input"]:
                                    options = classinfo["input"]["required"][name]
                                elif "optional" in classinfo["input"]:
                                    options = classinfo["input"]["optional"][name]
                                if options is not None:
                                    if options[0] == "COMBO":
                                        options = options[1]["options"]
                                    else:
                                        options = options[0]
                                node["options"] = options

            # find the options for a swarm lora loader
            elif node["class_type"] == "SwarmLoraLoader":
                loras = self._comfy_server.get_loras_available()
                node["options"] = loras
                gui_nodes[id] = node
                # print(loras)

        return gui_nodes

    def build_gui_from_nodes(self, gui_nodes):
        """
        Build a GUI in the Settings tab using the provided GUI nodes.

        Creates a vertical layout filled with one widget per GUI node.

        Args:
            gui_nodes: List of GUI nodes to display
        """
        # Create a container widget for the settings content
        container = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        # Set size policy to pack widgets at the top
        container.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Minimum,
        )
        # Set stretch to 0 to prevent expanding
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Get the workflow filename from the stored attribute
        workflow_filename = "GUI Configuration"
        if hasattr(self, "_workflow_data_filename"):
            workflow_filename = self._workflow_data_filename

        title = QLabel(workflow_filename)
        title.setStyleSheet("font-weight: bold; font-size: 16px;")
        layout.addWidget(title)
        layout.addSpacing(2)

        # Add a horizontal layout with Queue button and queue count input
        hlayout = QHBoxLayout()
        hlayout.setContentsMargins(0, 0, 0, 0)

        # Create a line edit for queue count
        self._queue_count = QLineEdit("1")
        self._queue_count.setFixedWidth(50)
        self._queue_count.setStyleSheet("font-size: 14px;")

        # Create a Queue button
        queue_button = QPushButton("Queue")
        queue_button.setStyleSheet("font-size: 14px;")

        # Make the button clickable
        queue_button.mousePressEvent = lambda event: self._queue_job(
            int(self._queue_count.text())
        )

        # Add widgets to horizontal layout
        hlayout.addWidget(queue_button)
        hlayout.addWidget(self._queue_count)

        # Add horizontal layout to main layout
        layout.addLayout(hlayout)

        #
        # Create a widget for each GUI node
        self._node_widgets = []
        # Sort gui_nodes by order_priority field if it exists
        sorted_gui_nodes = sorted(
            gui_nodes.items(), key=lambda item: item[1].get("order_priority", 0)
        )

        for id, node in sorted_gui_nodes:
            node_widget = WorkflowNodeWidget(id, node)
            layout.addWidget(node_widget)

            # Add spacing between nodes
            layout.addSpacing(2)
            self._node_widgets.append(node_widget)

        # Set the layout
        container.setLayout(layout)

        # Set the container as the settings tab content
        self.set_settings_content(container)

    def load_workflow_and_settings_from_job(self, job):
        """
        Load a workflow and its settings from a job object.

        This method loads the workflow by name from the job, then imports
        the settings from the job's workflow data into the GUI.

        Args:
            job: A Job object containing workflow_name and _workflow data
        """
        if type(job) is not dict:
            # Load the workflow by name from the job
            if hasattr(job, "workflow_name"):
                self._load_workflow_by_name(job.workflow_name)
            workflow = getattr(job, "workflow", None)
        else:
            if "workflow_name" in job:
                self._load_workflow_by_name(job["workflow_name"])
            workflow = job.get("workflow", None)

        # Import settings from the job's workflow data
        if workflow and hasattr(self, "_node_widgets"):
            # Update each node widget with values from the job's workflow
            for node_widget in self._node_widgets:
                if not hasattr(node_widget, "id"):
                    continue

                node_id = node_widget.id
                if node_id in workflow:
                    node_data = workflow[node_id]

                    # Get the value from the workflow
                    if node_data["class_type"] == "SwarmInputImage":
                        value = node_data["inputs"].get("image")
                    elif node_data["class_type"] == "SwarmInputVideo":
                        value = node_data["inputs"].get("video")
                    else:
                        value = node_data["inputs"].get("value")

                    # Update the node widget with the value
                    if value is not None:
                        node_widget.set_node_widget_value(value, self._output_root)

    def _import_settings_from_dropped_file(self, filename):
        """Import settings from a dropped file and update NodeWidgets.

        This method loads metadata from the dropped file (image or video) using
        the MetadataHandler, extracts relevant values, and updates the corresponding
        NodeWidgets in the GUI with matching values.

        The method attempts to match metadata fields to node widget titles using:
        1. Exact title matching (case-insensitive)
        2. Common field name mappings (seed, steps, cfg, prompt, model, image)

        Args:
            filename: Path to the dropped file
        """
        handler = MetadataHandler()

        # Load metadata from the file
        metadata = handler.load_file_metadata(filename)
        if not metadata or type(metadata) is not dict or "error" in metadata:
            print(f"Error loading metadata from {filename}")
            return

        # flatten the metadata
        extracted_values = MetadataHandler.flatten(metadata)

        # Check if there is a workflow_name value in the metadata
        # If found, search for and load that workflow before proceeding
        # print(extracted_values)
        workflow_name = extracted_values.get("workflow_name")
        if workflow_name and (
            not hasattr(self, "_workflow_data_filename")
            or self._workflow_data_filename != workflow_name
        ):
            self._load_workflow_by_name(workflow_name)

        # if we still do not have widgets then return
        if not hasattr(self, "_node_widgets"):
            return

        # Update NodeWidgets with matching values
        for node_widget in self._node_widgets:
            if not hasattr(node_widget, "node_data"):
                continue

            node_data = node_widget.node_data
            inputs = node_data.get("inputs", {})
            value = MetadataHandler.find_metadata_for_key(
                inputs.get("title", ""), extracted_values
            )
            if value is not None:
                node_widget.set_node_widget_value(value, self._output_root)


    def dragEnterEvent(self, event):
        """Handle drag enter event for the settings tab."""
        # Check if we have URLs (files being dragged) or job widget data
        if event.mimeData().hasUrls() or event.mimeData().hasFormat("application/x-job-widget"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Handle drop event for the settings tab."""
        # Check if we have URLs (files) or job widget data
        if event.mimeData().hasUrls() or event.mimeData().hasFormat("application/x-job-widget"):
            event.acceptProposedAction()
            # Handle the dropped data
            self.handle_drop_data(event.mimeData())
        else:
            event.ignore()

    def handle_drop_data(self, mime_data):
        """Handle dropped data on the settings tab.

        Args:
            mime_data: QMimeData containing the dropped data
        """
        # Check if this is a job widget being dropped
        if mime_data.hasFormat("application/x-job-widget"):
            # Get the job data from the MIME data
            job_data = json.loads(bytes(mime_data.data("application/x-job-widget")).decode('utf-8'))
            self.load_workflow_and_settings_from_job(job_data)
            
        # Check if this is a file being dropped
        elif mime_data.hasUrls():
            urls = mime_data.urls()
            if urls:
                # Get the first URL
                url = urls[0]
                # Convert to local file path
                file_path = url.toLocalFile()
                # Import settings from the dropped file
                self._import_settings_from_dropped_file(file_path)

    def set_workflows_directory(self, directory):
        """Set the workflows directory and repopulate the tree.

        Args:
            directory: Path to the workflows directory
        """
        self.workflows_directory = directory
        # Clear and repopulate the existing tree with the new directory
        if hasattr(self, "workflows_tree"):
            self.workflows_tree.clear()
            self._populate_workflows_tree()
        else:
            # If tree doesn't exist yet, initialize it
            self._initialize_workflows_tree()

    def _queue_job(self, count):
        workflow = self._update_workflow_with_gui_values()

        # print(workflow)
        # Emit the job_queued signal with the workflow data and count
        self.job_queued.emit(self._workflow_data_filename, workflow, count)

    def _update_workflow_with_gui_values(self):
        workflow = copy.deepcopy(self._workflow_data)
        for node_widget in self._node_widgets:
            id = node_widget.id
            if workflow[id]["class_type"] == "SwarmInputImage":
                workflow[id]["inputs"]["image"] = node_widget.get_value()
                workflow[id]["input_width"] = node_widget.input_width
                workflow[id]["input_height"] = node_widget.input_height
            elif workflow[id]["class_type"] == "SwarmInputVideo":
                workflow[id]["inputs"]["video"] = node_widget.get_value()
                workflow[id]["input_width"] = node_widget.input_width
                workflow[id]["input_height"] = node_widget.input_height
            elif workflow[id]["class_type"] == "SwarmLoraLoader":
                value = node_widget.get_value()
                workflow[id]["inputs"]["lora_names"] = list(value.keys())
                workflow[id]["inputs"]["lora_weights"] = list(value.values())
            else:
                workflow[id]["inputs"]["value"] = node_widget.get_value()
        return workflow
