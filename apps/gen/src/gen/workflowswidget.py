"""
Jobs widget for the Dueser application.
Contains a QTabWidget with Workflows and Settings tabs.
"""

import copy
import json
import os

from core.metadatahandler import MetadataHandler
from core.utils import check_int
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QImage, QPixmap, QTextOption
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSlider,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .comfyserver import comfyServer


class NodeWidget(QWidget):
    """
    Widget representing a single GUI node.

    This is a placeholder class that can be extended to create
    specific widgets for different node types.
    """

    def __init__(self, id, node_data):
        super().__init__()
        self.node_data = node_data
        self.id = id
        self._type = None

        if "inputs" not in node_data or "title" not in node_data["inputs"]:
            return

        inputs = node_data["inputs"]
        self._value = inputs["value"]
        self.setAcceptDrops(False)

        # Traverse settings_list to build the widget
        # Create a label with the title value
        title_label = QLabel(str(inputs["title"]))
        title_label.setStyleSheet("font-size: 14px;")
        if "view_type" in inputs and inputs["view_type"] == "slider":
            self._type = "slider"
            layout = QVBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            hlayout = QHBoxLayout()
            hlayout.setContentsMargins(0, 0, 0, 0)
            hlayout.addWidget(title_label)
            # Create a slider widget
            # Get slider parameters
            min_val = float(inputs["min"]) if "min" in inputs else 0
            max_val = float(inputs["view_max"]) if "view_max" in inputs else 100
            step = float(inputs["step"]) if "step" in inputs else 1
            current_val = float(inputs["value"]) if "value" in inputs else min_val

            num_steps = round((max_val - min_val) / step)
            # Create the slider
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setMinimum(0)
            slider.setMaximum(num_steps)
            slider.setValue(int((current_val - min_val) / step))
            slider.setSingleStep(1)
            slider.setPageStep(10)

            # Create a label to display the current value
            value_label = QLabel(str(current_val))
            value_label.setStyleSheet("font-size: 14px;")
            self._set_slider_value(slider.value(), min_val, step, value_label)

            # Connect slider value changes to update the label and self._value
            slider.valueChanged.connect(
                lambda idx: self._set_slider_value(idx, min_val, step, value_label)
            )

            # Add widgets to layout
            hlayout.addWidget(value_label)
            layout.addLayout(hlayout)
            layout.addWidget(slider)
            self.setLayout(layout)

        if "view_type" in inputs and inputs["view_type"] == "seed":
            # Create a simple layout with node information
            self._type = "seed"
            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(title_label)

            # Add an int input text box to the right of the title_label
            from PySide6.QtWidgets import QLineEdit

            # Get the current value
            current_val = int(inputs["value"]) if "value" in inputs else 0

            # Create a line edit for integer input
            int_input = QLineEdit(str(current_val))
            int_input.setFixedWidth(180)
            int_input.setAlignment(Qt.AlignmentFlag.AlignRight)
            int_input.setStyleSheet("font-size: 14px;")

            # Connect text changes to update self._value
            int_input.textChanged.connect(lambda text: self._set_int_value(text))

            # Add widgets to layout
            layout.addWidget(int_input)

            # Add a reset button to the right of the int_input
            reset_button = QPushButton("↻")
            reset_button.setFixedSize(27, 27)
            reset_button.setStyleSheet("font-size: 21px; padding: 0;")
            reset_button.clicked.connect(lambda: self._reset_seed_value(int_input))
            layout.addWidget(reset_button)

            self.setLayout(layout)

        if node_data["class_type"] == "SwarmInputText":
            # Add a multi-line text box under the title_label that grows as needed
            self._type = inputs["view_type"]
            layout = QVBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(title_label)

            # Get the current value
            current_val = inputs["value"] if "value" in inputs else ""

            # Create a text edit with word wrap
            text_edit = QTextEdit(str(current_val))
            text_edit.setStyleSheet("font-size: 14px;")
            text_edit.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
            text_edit.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
            )

            # Connect text changes to update self._value
            text_edit.textChanged.connect(
                lambda widget=self: setattr(widget, "_value", text_edit.toPlainText())
            )

            # Add widget to layout
            layout.addWidget(text_edit)
            self.setLayout(layout)

        if node_data["class_type"] == "SwarmInputDropdown":
            # Create a dropdown menu selection
            self._type = "dropdown"
            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)

            # Create a label with the title value
            title_label = QLabel(str(inputs["title"]))
            title_label.setStyleSheet("font-size: 14px;")
            layout.addWidget(title_label)

            # Create a combo box
            combo_box = QComboBox()
            combo_box.setStyleSheet("font-size: 14px;")

            # Populate with options from node_data
            if "options" in node_data and node_data["options"]:
                for option in node_data["options"]:
                    combo_box.addItem(str(option))

            # Set current value if it exists
            if "value" in inputs:
                current_value = str(inputs["value"])
                index = combo_box.findText(current_value)
                if index >= 0:
                    combo_box.setCurrentIndex(index)
                else:
                    self._value = node_data["options"][0]

            # Connect selection changes to update self._value
            combo_box.currentTextChanged.connect(
                lambda text, widget=self: setattr(widget, "_value", text)
            )

            # Add combo box to layout
            layout.addWidget(combo_box)
            self.setLayout(layout)

        if node_data["class_type"] == "SwarmInputImage":
            # Create a horizontal layout with title, button, filename on left and thumbnail on right
            self._type = "image"
            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(10)

            # Set dark grey background for this widget
            # self.setStyleSheet("background-color: #333333;")
            # self.setStyleSheet("border: 1px solid #bbb;")

            # Left side - vertical layout for title, button, filename, and dimensions
            left_layout = QVBoxLayout()
            left_layout.setContentsMargins(0, 0, 0, 0)
            left_layout.setSpacing(5)

            # Create a label with the title value
            title_label = QLabel(str(inputs["title"]))
            title_label.setStyleSheet("font-size: 14px;")
            left_layout.addWidget(title_label)

            # Create a "Choose File" button
            choose_file_button = QPushButton("Choose File")
            choose_file_button.setStyleSheet("font-size: 14px;")
            choose_file_button.clicked.connect(lambda: self._choose_image_file())
            left_layout.addWidget(choose_file_button)

            # Create a label to display the filename
            self._filename_label = QLabel("")
            self._filename_label.setStyleSheet("font-size: 12px; color: gray;")
            left_layout.addWidget(self._filename_label)

            # Create a label to display image dimensions
            self._dimensions_label = QLabel("")
            self._dimensions_label.setStyleSheet("font-size: 12px; color: gray;")
            left_layout.addWidget(self._dimensions_label)

            # Right side - thumbnail
            self._thumbnail_label = QLabel()
            self._thumbnail_label.setFixedSize(128, 128)
            self._thumbnail_label.setStyleSheet(
                "border: 1px solid #000; color: red; font-size: 10px;"
            )

            # Add left and right to main layout
            layout.addLayout(left_layout)
            layout.addWidget(self._thumbnail_label)
            layout.setStretch(0, 0)  # Don't stretch left side
            layout.setStretch(1, 1)  # Let thumbnail take remaining space

            # Set initial value if it exists
            if "image" in inputs and len(inputs["image"]):
                self._value = inputs["image"]
                # Try to load and display the thumbnail
                self._load_thumbnail(inputs["image"])

            self.setLayout(layout)

            # Enable drag and drop for this widget
            self.setAcceptDrops(True)

    def _set_int_value(self, text):
        if text is not None and len(text) > 0 and check_int(text):
            self._value = int(text)

    def _reset_seed_value(self, line_edit):
        """Reset the seed value to -1."""
        line_edit.setText("-1")
        self._value = -1

    def _set_slider_value(self, idx, min_val, step, label):
        val = min_val + idx * step
        if self.node_data["class_type"] == "SwarmInputInteger":
            label.setText(str(int(val)))
            self._value = val
        else:
            label.setText(str(round(val, 8)))
            self._value = round(val, 8)

    def _choose_image_file(self):
        """Open a file dialog to select an image file."""
        # Open file dialog to select an image file
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image File",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.webp)",
        )

        if file_path:
            # Set the value to the file path
            self._value = file_path
            # Update the filename label
            self._filename_label.setText(os.path.basename(file_path))
            # Load and display the thumbnail
            self._load_thumbnail(file_path)

    def _load_thumbnail(self, file_path):
        """Load and display a thumbnail of the image."""
        try:
            # Load the image
            if len(file_path) > 0 and os.path.exists(file_path):
                image = QImage(file_path)
                if image.isNull():
                    raise ValueError("Could not load image")

                # Get image dimensions
                width = image.width()
                height = image.height()

                # Update dimensions label
                if hasattr(self, "_dimensions_label"):
                    self._dimensions_label.setText(f"{width} × {height} px")

                # Scale to 128x128 while maintaining aspect ratio
                pixmap = QPixmap.fromImage(image).scaled(
                    128,
                    128,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

                # Display the thumbnail
                self._thumbnail_label.setPixmap(pixmap)
        except Exception as e:
            print(f"Error loading thumbnail: {e}")
            # Show error message in the thumbnail area
            self._thumbnail_label.setText("Invalid Image")
            # Clear dimensions if error occurs
            if hasattr(self, "_dimensions_label"):
                self._dimensions_label.setText("")

    def get_value(self):
        if self._type is None:
            return
        return self._value

    def dragEnterEvent(self, event):
        """Handle drag enter event."""
        if self._type == "image":
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Handle drop event."""
        if self._type == "image":
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
                # Handle the dropped files
                self.handle_drop_data(event.mimeData())
        else:
            event.ignore()

    def handle_drop_data(self, mime_data):
        """Handle dropped data.

        Args:
            mime_data: QMimeData containing the dropped data
        """
        if mime_data.hasUrls():
            urls = mime_data.urls()
            if urls:
                # Get the first URL
                url = urls[0]
                # Convert to local file path
                file_path = url.toLocalFile()
                # Check if it's an image file
                if file_path.lower().endswith(
                    (".png", ".jpg", ".jpeg", ".bmp", ".webp")
                ):
                    # Set the value to the file path
                    self._value = file_path
                    # Update the filename label
                    self._filename_label.setText(os.path.basename(file_path))
                    # Load and display the thumbnail
                    self._load_thumbnail(file_path)


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
        # self._comfy_server = None

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
            root = QTreeWidgetItem(
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
                        file_item = QTreeWidgetItem(self.workflows_tree, [filename])
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
                dir_item = QTreeWidgetItem(self.workflows_tree, [dirname])
            else:
                dir_item = QTreeWidgetItem(parent_item, [dirname])

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
                file_item = QTreeWidgetItem(item, [filename])
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
                return json.load(f)

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
            gui_nodes.items(),
            key=lambda item: item[1].get("order_priority", 0)
        )
        
        for id, node in sorted_gui_nodes:
            node_widget = NodeWidget(id, node)
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
        # Load the workflow by name from the job
        if hasattr(job, "workflow_name"):
            self._load_workflow_by_name(job.workflow_name)

        # Import settings from the job's workflow data
        if hasattr(job, "_workflow") and hasattr(self, "_node_widgets"):
            # Update each node widget with values from the job's workflow
            for node_widget in self._node_widgets:
                if not hasattr(node_widget, "id"):
                    continue

                node_id = node_widget.id
                if node_id in job._workflow:
                    node_data = job._workflow[node_id]

                    # Get the value from the workflow
                    if node_data["class_type"] == "SwarmInputImage":
                        value = node_data["inputs"].get("image")
                    else:
                        value = node_data["inputs"].get("value")

                    # Update the node widget with the value
                    if value is not None:
                        self._set_node_widget_value(node_widget, value)

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
                self._set_node_widget_value(node_widget, value)

    def _set_node_widget_value(self, node_widget, value):
        """Set the value of a NodeWidget based on its type.

        Args:
            node_widget: The NodeWidget to update
            value: The value to set
        """
        if not hasattr(node_widget, "_type") or node_widget._type is None:
            return

        try:
            if node_widget._type == "slider":
                # For sliders, we need to find the slider widget and set its value
                # This is a bit hacky but works with the current implementation
                layout = node_widget.layout()
                if layout:
                    # Find the slider widget (it's the last widget in the layout)
                    for i in range(layout.count()):
                        item = layout.itemAt(i)
                        if item and hasattr(item, "widget"):
                            widget = item.widget()
                            if isinstance(widget, QSlider):
                                # Convert the value to the slider's range
                                inputs = node_widget.node_data.get("inputs", {})
                                min_val = float(inputs.get("min", 0))
                                step = float(inputs.get("step", 1))
                                max_val = float(inputs.get("view_max", 100))

                                # Try to convert the value to a number
                                try:
                                    numeric_value = float(value)
                                    # Clamp the value to the slider range
                                    numeric_value = max(
                                        min_val, min(numeric_value, max_val)
                                    )
                                    # Calculate slider position
                                    slider_pos = int((numeric_value - min_val) / step)
                                    widget.setValue(slider_pos)
                                    # Update the display label
                                    for j in range(layout.count()):
                                        label_item = layout.itemAt(j)
                                        if label_item and hasattr(label_item, "widget"):
                                            label_widget = label_item.widget()
                                            if (
                                                isinstance(label_widget, QLabel)
                                                and j > 0
                                            ):  # Skip title label
                                                label_widget.setText(
                                                    str(round(numeric_value, 8))
                                                )
                                                break
                                except (ValueError, TypeError):
                                    pass
                                break

            elif node_widget._type == "seed":
                # For seed inputs, find the QLineEdit widget
                layout = node_widget.layout()
                if layout:
                    for i in range(layout.count()):
                        item = layout.itemAt(i)
                        if item and hasattr(item, "widget"):
                            widget = item.widget()
                            if isinstance(widget, QLineEdit):
                                widget.setText(str(value))
                                break

            elif node_widget._type == "text" or node_widget._type == "prompt":
                # For text inputs (SwarmInputText), find the QTextEdit widget
                layout = node_widget.layout()
                if layout:
                    for i in range(layout.count()):
                        item = layout.itemAt(i)
                        if item and hasattr(item, "widget"):
                            widget = item.widget()
                            if isinstance(widget, QTextEdit):
                                widget.setPlainText(str(value))
                                break

            elif node_widget._type == "dropdown":
                # For dropdown inputs, find the QComboBox widget
                layout = node_widget.layout()
                if layout:
                    for i in range(layout.count()):
                        item = layout.itemAt(i)
                        if item and hasattr(item, "widget"):
                            widget = item.widget()
                            if isinstance(widget, QComboBox):
                                # Find the text in the dropdown
                                index = widget.findText(str(value))
                                if index >= 0:
                                    widget.setCurrentIndex(index)
                                break

            elif node_widget._type == "image":
                image_path = str(value)

                # If the image path is not a full path, try to find it
                if not os.path.isabs(image_path):
                    # 1) Check current directory
                    if os.path.exists(image_path):
                        image_path = os.path.abspath(image_path)
                    # 2) Check output_root
                    elif hasattr(self, "_output_root") and len(self._output_root) > 0:
                        output_path = os.path.join(self._output_root, image_path)
                        if os.path.exists(output_path):
                            image_path = output_path
                        elif len(image_path) >= 8:
                            # 3) Check output_root/<year>-<mount>-<day> from first 8 characters of the filename
                            dir_name = (
                                f"{image_path[:4]}-{image_path[4:6]}-{image_path[6:8]}"
                            )
                            output_subdir_path = os.path.join(
                                self._output_root, dir_name, image_path
                            )
                            if os.path.exists(output_subdir_path):
                                image_path = output_subdir_path

                    # If still not found, open a file dialog to look for it
                    if not os.path.exists(image_path):
                        file_path, _ = QFileDialog.getOpenFileName(
                            self,
                            "Select Image File",
                            "",
                            "Image Files (*.png *.jpg *.jpeg *.bmp *.webp)",
                        )
                        if file_path:
                            image_path = file_path

                # For image inputs, update the file path and thumbnail
                value = image_path
                node_widget._value = image_path
                if hasattr(node_widget, "_filename_label"):
                    node_widget._filename_label.setText(os.path.basename(image_path))
                if hasattr(node_widget, "_load_thumbnail") and os.path.exists(
                    image_path
                ):
                    node_widget._load_thumbnail(image_path)

            # Update the internal value
            node_widget._value = value

        except Exception as e:
            print(f"Error setting node widget value: {e}")

    def dragEnterEvent(self, event):
        """Handle drag enter event for the settings tab."""
        # Check if we have URLs (files being dragged)
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Handle drop event for the settings tab."""
        # Check if we have URLs and if we're on the settings tab
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            # Handle the dropped files
            self.handle_drop_data(event.mimeData())
        else:
            event.ignore()

    def handle_drop_data(self, mime_data):
        """Handle dropped data on the settings tab.

        Args:
            mime_data: QMimeData containing the dropped data
        """
        if mime_data.hasUrls():
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
            else:
                workflow[id]["inputs"]["value"] = node_widget.get_value()
        return workflow
