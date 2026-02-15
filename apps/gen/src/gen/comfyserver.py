import json
import uuid
from urllib.parse import urlencode

import urllib3
from PySide6.QtWebSockets import QWebSocket
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox
from urllib3 import encode_multipart_formdata

class comfyServer(QWebSocket):
    def __init__(self, server_address="127.0.0.1:8188"):
        super().__init__()
        self._server_address = server_address
        self._client_id = str(uuid.uuid4())
        self._connected = False

        # Store messages for processing
        self._message_queue = []

        # Connect signals
        self.connected.connect(self._on_connected)
        self.disconnected.connect(self._on_disconnected)
        self.errorOccurred.connect(self._on_error)

        self.timeout_timer = QTimer()
        # Set a 5-second timeout
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.timeout.connect(self.on_timeout)
        self.timeout_timer.start(7000)

        # Open WebSocket connection
        url = f"ws://{server_address}/ws?clientId={self._client_id}"
        self.open(url)

    def on_timeout(self):
        # Notify the user that the server couldn't be reached.
        self._connected = False
        message = (
            f"Could not reach the Comfy server at '{self._server_address}'.\n\n"
            "Please check the server address and ensure the Comfy server is running."
        )
        try:
            QMessageBox.critical(None, "Comfy Server Connection Error", message)
        except Exception:
            # If for some reason the GUI dialog cannot be shown (no GUI available),
            # fall back to printing the message to stdout/stderr.
            print(message)

    def _on_connected(self):
        """Handle WebSocket connection established."""
        self.timeout_timer.stop()
        self._connected = True

    def _on_disconnected(self):
        """Handle WebSocket disconnection."""
        self._connected = False

    def _on_error(self, error):
        """Handle WebSocket errors."""
        error_string = self.errorString()
        print(f"WebSocket error: {error_string}")

    def is_connected(self):
        """Check if WebSocket is connected."""
        return self._connected

    def close_websocket_connection(self):
        """Close the WebSocket connection."""
        self.close()

    def queue_prompt(self, job):
        p = {"prompt": job.get_workflow_for_submission(self), "client_id": self._client_id}
        headers = {"Content-Type": "application/json"}
        data = json.dumps(p).encode("utf-8")
        req = urllib3.PoolManager().request(
            "POST",
            "http://{}/prompt".format(self._server_address),
            body=data,
            headers=headers,
        )
        return json.loads(req.data)

    def get_system_stats(self): 
        if self.is_connected():
            req = urllib3.PoolManager().request(
                "GET", "http://{}/system_stats".format(self._server_address)
            )
            return json.loads(req.data)
        return {"Error:": "not connected yet"}
    
    def cancel_prompt(self, prompt_id):
        p = {"prompt_id": prompt_id, "client_id": self._client_id}
        headers = {"Content-Type": "application/json"}
        data = json.dumps(p).encode("utf-8")
        req = urllib3.PoolManager().request(
            "POST",
            "http://{}/interrupt".format(self._server_address),
            body=data,
            headers=headers,
        )
        return req.data

    def get_history(self, prompt_id):
        req = urllib3.PoolManager().request(
            "GET", "http://{}/history/{}".format(self._server_address, prompt_id)
        )
        return json.loads(req.data)

    def get_results(self, prompt_id, allow_preview=False):
        results = []

        history = self.get_history(prompt_id)[prompt_id]
        for node_id in history["outputs"]:
            node_output = history["outputs"][node_id]
            output_data = {}
            if "images" in node_output:
                for image in node_output["images"]:
                    if allow_preview and image["type"] == "temp":
                        preview_data = self.get_result(
                            image["filename"], image["subfolder"], image["type"]
                        )
                        output_data["image_data"] = preview_data
                    if image["type"] == "output":
                        image_data = self.get_result(
                            image["filename"], image["subfolder"], image["type"]
                        )
                        output_data["image_data"] = image_data
                    output_data["file_name"] = image["filename"]
                    output_data["type"] = image["type"]
                    results.append(output_data)
            # Handle "gifs" from Video Combine node
            if "gifs" in node_output:
                for video in node_output["gifs"]:
                    if allow_preview and video["type"] == "temp":
                        preview_data = self.get_result(
                            video["filename"], video["subfolder"], video["type"]
                        )
                        output_data["video_data"] = preview_data
                    if video["type"] == "output":
                        video_data = self.get_result(
                            video["filename"], video["subfolder"], video["type"]
                        )
                        output_data["video_data"] = video_data
                    output_data["file_name"] = video["filename"]
                    output_data["type"] = video["type"]
                    output_data["format"] = video.get("format", "")
                    output_data["frame_rate"] = video.get("frame_rate", 0)
                    output_data["fullpath"] = video.get("fullpath", "")
                    results.append(output_data)

        return results

    def get_result(self, filename, subfolder, folder_type):
        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url_values = urlencode(data)
        req = urllib3.PoolManager().request(
            "GET", "http://{}/view?{}".format(self._server_address, url_values)
        )
        return req.data

    def get_object_info(self, node_class):
        req = urllib3.PoolManager().request(
            "GET", "http://{}/object_info/{}".format(self._server_address, node_class)
        )
        return json.loads(req.data)

    def upload_image(self, input_path, name, image_type="input", overwrite=False):
        with open(input_path, "rb") as file:
            file_data = file.read()
            # Build multipart form data
            fields = {
                "image": (name, file_data, "image/png"),
                "type": image_type,
                "overwrite": str(overwrite).lower(),
            }

            # Encode the multipart form data
            data, content_type = encode_multipart_formdata(fields)

            headers = {"Content-Type": content_type}

            req = urllib3.PoolManager().request(
                "POST",
                "http://{}/upload/image".format(self._server_address),
                body=data,
                headers=headers,
            )
            return json.loads(req.data)

    def upload_video(self, input_path, name, image_type="input", overwrite=False):
        with open(input_path, "rb") as file:
            file_data = file.read()
            # Build multipart form data
            fields = {
                "image": (name, file_data, "video/mp4"),
                "type": image_type,
                "overwrite": str(overwrite).lower(),
            }

            # Encode the multipart form data
            data, content_type = encode_multipart_formdata(fields)

            headers = {"Content-Type": content_type}

            req = urllib3.PoolManager().request(
                "POST",
                "http://{}/upload/image".format(self._server_address),
                body=data,
                headers=headers,
            )
            return json.loads(req.data)

    def get_all_models_available(self):
        results = []
        try:
            req = urllib3.PoolManager().request(
                "GET",
                "http://{}/models".format(self._server_address),
            )
            subdirs = json.loads(req.data)

            subdirs_to_check = subdirs
            for subdir in subdirs_to_check:
                if subdir in subdirs:
                    req = urllib3.PoolManager().request(
                        "GET",
                        "http://{}/models/{}".format(self._server_address, subdir),
                    )
                results = results + json.loads(req.data)

            return results
        except Exception as e:
            print(f"Error checking model availability: {e}")
            return False

    def get_loras_available(self):
        results = []
        try:
            req = urllib3.PoolManager().request(
                "GET",
                "http://{}/models/loras".format(self._server_address),
            )
            return json.loads(req.data)
        except Exception as e:
            print(f"Error checking model availability: {e}")
            return False
