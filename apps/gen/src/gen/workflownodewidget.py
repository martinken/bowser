"""
Workflow Node Widget for the bowser-gen application.

This module contains the WorkflowNodeWidget class which represents
a single GUI node in a workflow.
"""

import os
import cv2
import numpy as np
from core.utils import check_int, get_swarm_preview_path, is_video_file, numpy_to_qimage
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QTextOption
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

class WorkflowNodeWidget(QWidget):
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
        self.input_width = 0
        self.input_height = 0

        # have to have class_type
        if "class_type" not in node_data:
            return

        self.setAcceptDrops(False)

        if self.node_data["class_type"] == "SwarmLoraLoader":
            # Create a button that when pressed opens a lora selection dialog
            self._type = "lora"
            layout = QVBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            
            # Create a horizontal layout for title and button
            hlayout = QHBoxLayout()
            hlayout.setContentsMargins(0, 0, 0, 0)
            
            # Create a label with the title value
            title_label = QLabel(str(self.node_data["_meta"]["title"]))
            title_label.setStyleSheet("font-size: 14px;")
            hlayout.addWidget(title_label)
            
            # Create a button to open the lora selection dialog
            select_lora_button = QPushButton("Select LoRAs...")
            select_lora_button.setStyleSheet("font-size: 14px;")
            select_lora_button.clicked.connect(lambda: self._open_lora_dialog())
            hlayout.addWidget(select_lora_button)
            
            # Add horizontal layout to main layout
            layout.addLayout(hlayout)
            
            # Create a label to display the current selection
            self._lora_selection_label = QLabel("")
            self._lora_selection_label.setStyleSheet("font-size: 12px; color: gray;")
            layout.addWidget(self._lora_selection_label)
            
            self.setLayout(layout)
            return

        if "inputs" not in node_data or "title" not in node_data["inputs"]:
            return

        inputs = node_data["inputs"]
        self._value = inputs["value"]

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
            text_edit.setFixedHeight(109)  # Start with a fixed height, 5 lines

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

        if (
            node_data["class_type"] == "SwarmInputImage"
            or node_data["class_type"] == "SwarmInputVideo"
        ):
            # Create a horizontal layout with title, button, filename on left and thumbnail on right
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
                self._type = "image"
                self._value = inputs["image"]
                # Try to load and display the thumbnail
                self._load_thumbnail(inputs["image"])
                choose_file_button.clicked.connect(lambda: self._choose_image_file())

            if "video" in inputs and len(inputs["video"]):
                self._type = "video"
                self._value = inputs["video"]
                # Try to load and display the thumbnail
                self._load_thumbnail(inputs["video"])
                choose_file_button.clicked.connect(lambda: self._choose_video_file())

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

    def _choose_video_file(self):
        """Open a file dialog to select an video file."""
        # Open file dialog to select an video file
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            "",
            "Video Files (*.mov *.mp4)",
        )

        if file_path:
            # Set the value to the file path
            self._value = file_path
            # Update the filename label
            self._filename_label.setText(os.path.basename(file_path))
            # Load and display the thumbnail
            self._load_thumbnail(file_path)

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
        if len(file_path) <= 0 or not os.path.exists(file_path):
            return

        image = None
        try:
            # Load the image
            if is_video_file(file_path):
                preview_path = get_swarm_preview_path(file_path)
                if len(preview_path) > 0 and os.path.exists(preview_path):
                    image = QImage(preview_path)
                    if image.isNull():
                        raise ValueError("Could not load image")
                else:
                    # Use cv2 to grab first frame from the video
                    # Open the video file
                    cap = cv2.VideoCapture(file_path)
                    if cap.isOpened():
                        # Read the first frame
                        ret, frame = cap.read()
                        cap.release()
                        if ret and frame is not None:
                            image = numpy_to_qimage(frame)
            else:
                image = QImage(file_path)
                if image.isNull():
                    raise ValueError("Could not load image")

            if image is None:
                return

            # Get image dimensions
            self.input_width = image.width()
            self.input_height = image.height()

            # Update dimensions label
            if hasattr(self, "_dimensions_label"):
                self._dimensions_label.setText(
                    f"{self.input_width} × {self.input_height} px"
                )

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
        if self._type == "image" or self._type == "video":
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Handle drop event."""
        if self._type == "image" or self._type == "video":
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
                # Check if it's an image file or video respectively
                if (
                    self._type == "image"
                    and file_path.lower().endswith(
                        (".png", ".jpg", ".jpeg", ".bmp", ".webp")
                    )
                ) or (
                    self._type == "video"
                    and file_path.lower().endswith((".mp4", ".mov"))
                ):
                    # Set the value to the file path
                    self._value = file_path
                    # Update the filename label
                    self._filename_label.setText(os.path.basename(file_path))
                    # Load and display the thumbnail
                    self._load_thumbnail(file_path)

    def set_node_widget_value(self, value, output_root=""):
        """Set the value of a NodeWidget based on its type.

        Args:
            node_widget: The NodeWidget to update
            value: The value to set
        """
        if not hasattr(self, "_type") or self._type is None:
            return

        try:
            if self._type == "slider":
                # For sliders, we need to find the slider widget and set its value
                # This is a bit hacky but works with the current implementation
                layout = self.layout()
                if layout:
                    # Find the slider widget (it's the last widget in the layout)
                    for i in range(layout.count()):
                        item = layout.itemAt(i)
                        if item and hasattr(item, "widget"):
                            widget = item.widget()
                            if isinstance(widget, QSlider):
                                # Convert the value to the slider's range
                                inputs = self.node_data.get("inputs", {})
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
                                    slider_pos = round((numeric_value - min_val) / step)
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

            elif self._type == "seed":
                # For seed inputs, find the QLineEdit widget
                layout = self.layout()
                if layout:
                    for i in range(layout.count()):
                        item = layout.itemAt(i)
                        if item and hasattr(item, "widget"):
                            widget = item.widget()
                            if isinstance(widget, QLineEdit):
                                widget.setText(str(value))
                                break

            elif self.node_data["class_type"] == "SwarmInputText":
                # For text inputs (SwarmInputText), find the QTextEdit widget
                layout = self.layout()
                if layout:
                    for i in range(layout.count()):
                        item = layout.itemAt(i)
                        if item and hasattr(item, "widget"):
                            widget = item.widget()
                            if isinstance(widget, QTextEdit):
                                widget.setPlainText(str(value))
                                break

            elif self._type == "dropdown":
                # For dropdown inputs, find the QComboBox widget
                layout = self.layout()
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

            elif self._type == "image" or self._type == "video":
                image_path = str(value)

                # If the image path is not a full path, try to find it
                if not os.path.isabs(image_path):
                    # 1) Check current directory
                    if os.path.exists(image_path):
                        image_path = os.path.abspath(image_path)
                    # 2) Check output_root
                    elif hasattr(self, "_output_root") and len(output_root) > 0:
                        output_path = os.path.join(output_root, image_path)
                        if os.path.exists(output_path):
                            image_path = output_path
                        elif len(image_path) >= 8:
                            # 3) Check output_root/<year>-<mount>-<day> from first 8 characters of the filename
                            dir_name = (
                                f"{image_path[:4]}-{image_path[4:6]}-{image_path[6:8]}"
                            )
                            output_subdir_path = os.path.join(
                                output_root, dir_name, image_path
                            )
                            if os.path.exists(output_subdir_path):
                                image_path = output_subdir_path

                    # If still not found leave blank
                    if not os.path.exists(image_path):
                        return

                # For image inputs, update the file path and thumbnail
                value = image_path
                self._value = image_path
                if hasattr(self, "_filename_label"):
                    self._filename_label.setText(os.path.basename(image_path))
                if hasattr(self, "_load_thumbnail") and os.path.exists(
                    image_path
                ):
                    self._load_thumbnail(image_path)

            # Update the internal value
            self._value = value

        except Exception as e:
            print(f"Error setting node widget value: {e}")

    def _open_lora_dialog(self):
        """Open the Lora selection dialog."""
        dialog = LoraSelectionDialog(self.node_data.get("options", []), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Get the selected loras with their strengths
            loras = dialog.get_selected_loras()
            # Store the value as a list of dictionaries
            self._value = loras
            # Update the display label
            if loras:
                display_text = ", ".join([f"{name}({strength})" for name, strength in loras.items()])
                self._lora_selection_label.setText(display_text)
            else:
                self._lora_selection_label.setText("")


class LoraSelectionDialog(QDialog):
    """
    Dialog for selecting LoRAs with their strengths.
    """

    def __init__(self, available_loras, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select LoRAs")
        self.setMinimumWidth(600)
        self.setMinimumHeight(700)
        
        self.available_loras = available_loras or []
        self.selected_loras = []
        
        # Main layout
        main_layout = QVBoxLayout()
        
        # Search box
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        search_label.setStyleSheet("font-size: 14px;")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter by name...")
        self.search_edit.setStyleSheet("font-size: 14px;")
        self.search_edit.textChanged.connect(self._filter_loras)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit)
        main_layout.addLayout(search_layout)
        
        # Active LoRAs section
        active_layout = QVBoxLayout()
        active_label = QLabel("Active LoRAs:")
        active_label.setStyleSheet("font-size: 14px;")
        active_layout.addWidget(active_label)
        
        # Scroll area for active loras - fixed height for 3 loras
        self.active_scroll = QScrollArea()
        self.active_scroll.setWidgetResizable(True)
        self.active_scroll.setFixedHeight(90)  # Height for approximately 3 loras
        
        self.active_widget = QWidget()
        self.active_layout = QVBoxLayout()
        self.active_layout.setContentsMargins(0, 0, 0, 0)
        self.active_layout.setSpacing(0)
        self.active_widget.setLayout(self.active_layout)
        self.active_scroll.setWidget(self.active_widget)
        
        active_layout.addWidget(self.active_scroll)
        main_layout.addLayout(active_layout)
        
        # Available LoRAs section - takes remaining space
        available_layout = QVBoxLayout()
        available_label = QLabel("Available LoRAs:")
        available_label.setStyleSheet("font-size: 14px;")
        available_layout.addWidget(available_label)
        
        # List widget for available loras
        self.lora_list = QListWidget()
        self.lora_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.lora_list.setStyleSheet("font-size: 14px;")
        self.lora_list.itemDoubleClicked.connect(self._add_lora)
        
        # Populate the list
        self._populate_lora_list()
        
        available_layout.addWidget(self.lora_list)
        main_layout.addLayout(available_layout)
        
        # Set stretch factors so available loras take remaining space
        main_layout.setStretch(2, 1)  # The available loras section takes remaining space
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
        
        self.setLayout(main_layout)

    def _populate_lora_list(self):
        """Populate the list of available loras."""
        self.lora_list.clear()
        for lora in self.available_loras:
            self.lora_list.addItem(lora)

    def _filter_loras(self, text):
        """Filter the lora list based on search text."""
        filter_text = text.lower()
        for i in range(self.lora_list.count()):
            item = self.lora_list.item(i)
            if filter_text in item.text().lower():
                item.setHidden(False)
            else:
                item.setHidden(True)

    def _add_lora(self, item):
        """Add a lora to the active list."""
        lora_name = item.text()
        
        # Check if already active
        for active_lora in self.selected_loras:
            if active_lora["name"] == lora_name:
                # Remove if already active
                self.selected_loras.remove(active_lora)
                self._update_active_list()
                return
        
        # Add new lora with default strength of 1.0
        self.selected_loras.append({"name": lora_name, "strength": 1.0})
        self._update_active_list()

    def _update_active_list(self):
        """Update the display of active loras."""
        # Clear existing items
        while self.active_layout.count():
            item = self.active_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        
        # Add each active lora
        for lora in self.selected_loras:
            lora_widget = QWidget()
            lora_layout = QHBoxLayout()
            lora_layout.setContentsMargins(0, 0, 0, 0)
            
            # Lora name
            name_label = QLabel(lora["name"])
            name_label.setStyleSheet("font-size: 14px;")
            lora_layout.addWidget(name_label)
            
            # Strength input
            strength_edit = QLineEdit(str(lora["strength"]))
            strength_edit.setFixedWidth(80)
            strength_edit.setAlignment(Qt.AlignmentFlag.AlignRight)
            strength_edit.setStyleSheet("font-size: 14px;")
            
            # Store reference to update the strength when text changes
            strength_edit.textChanged.connect(
                lambda text, idx=self.selected_loras.index(lora): 
                    self._update_strength(idx, text)
            )
            
            lora_layout.addWidget(strength_edit)
            
            # Remove button
            remove_button = QPushButton("×")
            remove_button.setFixedSize(27, 27)
            remove_button.setStyleSheet("font-size: 21px; padding: 0;")
            
            # Store reference to remove the correct lora
            remove_button.clicked.connect(
                lambda checked=False, idx=self.selected_loras.index(lora): 
                    self._remove_lora(idx)
            )
            
            lora_layout.addWidget(remove_button)
            lora_widget.setLayout(lora_layout)
            self.active_layout.addWidget(lora_widget)

    def _update_strength(self, idx, text):
        """Update the strength value of an active lora."""
        try:
            value = float(text)
            self.selected_loras[idx]["strength"] = value
        except ValueError:
            pass

    def _remove_lora(self, idx):
        """Remove a lora from the active list."""
        self.selected_loras.pop(idx)
        self._update_active_list()

    def get_selected_loras(self):
        """Get the list of selected loras with their strengths.
        
        Returns:
            Dictionary with lora names as keys and their strengths as values.
        """
        result = {}
        for lora in self.selected_loras:
            result[lora["name"]] = lora["strength"]
        return result
