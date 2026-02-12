"""
Job class for managing workflow execution jobs.
"""
import os
import copy
import time
from random import randint


def get_gpu_from_device_string(device_string):
    """Extract GPU identifier from device string."""
    # Simple extraction - can be enhanced based on actual device string format
    if not device_string:
        return "unknown"
    
    # Try to extract common GPU identifiers
    gpu_identifiers = [
        "3090", "3090ti", "3080ti", "3080", "3070ti", "3070", "3060ti", "3060",
        "4090", "4080", "4070ti", "4070", "4060ti", "4060",
        "2080ti", "2080super", "2080", "2070super", "2070", "2060super", "2060",
        "5090", "5080", "5070", "5060",
        "rx7900xtx", "rx7900xt", "rx7800xt", "rx6950xt", "rx6900xt", "rx6800xt", "rx6800", "rx6700xt",
        "3080laptop", "3070laptop", "4070laptop", "4060laptop"
    ]
    
    for gpu_id in gpu_identifiers:
        if gpu_id.lower() in device_string.lower():
            return gpu_id
    
    return "unknown"

class Job:
    def __init__(self, workflow_name, workflow, count, parent=None):
        self.workflow = workflow
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
                + self.results[0]["start_time"]
            )
        else:
            return self.estimated_runtime

    def compute_ops(self):
        metadata = {}
        width = 1000
        height = 1000
        for id, node in self.workflow.items():
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
                    # Try to extract Frames
                    elif "cfg" in title_lower or "cfgscale" in title_lower:
                        node_metadata["cfg"] = value

                # Only add to metadata_list if we found relevant data
                if node_metadata:
                    metadata.update(node_metadata)

        # Process metadata to extract width and height from aspectratio if needed
        # If width and height are missing, try to extract them from the aspectratio field
        # examples "1M  4:3 1152, 864" would be 1152 width and 864 height
        if metadata.get("width") is None or metadata.get("height") is None:
            aspectratio = metadata.get("aspectratio", "")
            if aspectratio:
                # Try to extract width and height from aspectratioq
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
        cfg = float(metadata.get("cfg", 1.0))
        # when cfg is 1.0 samplers only run once per step at anything higher
        # they run twice, but some workflows only use cfg for one of the
        # samplers in a multisampler setup, so we cap it at 1.6 to avoid
        # massively overestimating runtime for some workflows
        if cfg > 1.0:
            cfg = 1.6
        self.ops = width * height * steps * frames * cfg

    def set_start_time(self, timestamp):
        self.results[self.completions]["start_time"] = timestamp

    def set_end_time(self, timestamp):
        self.results[self.completions]["end_time"] = timestamp
        self.results[self.completions]["elapsed_time"] = round(
            timestamp - self.results[self.completions]["start_time"], 2
        )

    def is_completed(self):
        return self.completions >= self.count

    def _replace_random_syntax(self, text, seed):
        """Replace <random:...> syntax in text with random selections.

        Uses the provided seed for deterministic results.
        Supports:
        - <random:val1, val2, val3> - random selection from list
        - <random:val1|val2|val3> - pipe separator for values with commas
        - <random:1-5> - integer ranges
        - <random:0.8-1.2> - float ranges with decimal precision
        - <random[2-4):val1, val2> - repeat 2-4 times without repetition
        - <random[2-4,):val1, val2> - repeat with comma separator

        Args:
            text (str): Text containing <random:...> patterns
            seed (int): Seed for random number generation

        Returns:
            str: Text with random patterns replaced
        """
        import random
        import re

        # Create a seeded random instance
        rng = random.Random(seed)

        # Pattern to match <random[repeat]:options> or <random:options>
        pattern = r"<random(?:\[(\d+(?:-\d+)?)(,?)\])?:([^>]+)>"

        def replace_match(match):
            repeat_spec = match.group(1)  # e.g., "2" or "2-4"
            comma_sep = match.group(2)  # "," if comma separator requested
            options_str = match.group(3)  # The options list

            # Determine separator (| is preferred if it appears more than ,)
            if options_str.count("|") > options_str.count(","):
                separator = "|"
            else:
                separator = ","

            # Split options
            options = [opt.strip() for opt in options_str.split(separator)]

            # Process each option for ranges
            expanded_options = []
            for opt in options:
                # Check for numeric range (int or float)
                range_match = re.match(r"^(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)$", opt)
                if range_match:
                    start_str, end_str = range_match.groups()

                    # Check if it's a float range
                    if "." in start_str or "." in end_str:
                        # Float range - determine decimal places
                        decimal_places = max(
                            len(start_str.split(".")[-1]) if "." in start_str else 0,
                            len(end_str.split(".")[-1]) if "." in end_str else 0,
                        )
                        start = float(start_str)
                        end = float(end_str)

                        # Generate range with appropriate step
                        step = 10 ** (-decimal_places)
                        current = start
                        while current <= end + step / 2:  # Add small epsilon for float comparison
                            expanded_options.append(f"{current:.{decimal_places}f}")
                            current += step
                    else:
                        # Integer range
                        start = int(start_str)
                        end = int(end_str)
                        expanded_options.extend([str(i) for i in range(start, end + 1)])
                else:
                    expanded_options.append(opt)

            # Determine how many times to repeat
            if repeat_spec:
                if "-" in repeat_spec:
                    min_repeat, max_repeat = map(int, repeat_spec.split("-"))
                    repeat_count = rng.randint(min_repeat, max_repeat)
                else:
                    repeat_count = int(repeat_spec)
            else:
                repeat_count = 1

            # Select random options (without repetition if possible)
            if repeat_count <= len(expanded_options):
                selected = rng.sample(expanded_options, repeat_count)
            else:
                # If more repeats than options, allow repetition
                selected = rng.choices(expanded_options, k=repeat_count)

            # Join with appropriate separator
            if comma_sep:
                return ", ".join(selected)
            else:
                return " ".join(selected)

        # Replace all matches
        result = re.sub(pattern, replace_match, text)
        return result

    def get_workflow_for_submission(self, comfy_server):
        workflow = copy.deepcopy(self.workflow)
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

            # Handle SwarmInputText nodes with view_type of prompt
            if node["class_type"] == "SwarmInputText":
                if node["inputs"].get("view_type") == "prompt" and "value" in node["inputs"]:
                    original_prompt = node["inputs"]["value"]

                    # Perform random replacements using the seed
                    if self.start_seed == -1:
                        self.start_seed = randint(0, 2**63 - 1)
                    modified_prompt = self._replace_random_syntax(original_prompt, self.start_seed + self.completions)
                    # Store the original prompt for reference if different from the modified_prompt
                    if modified_prompt != original_prompt:
                        self.results[self.completions]["original_prompt"] = original_prompt
                    node["inputs"]["value"] = modified_prompt

        self.results[self.completions]["seed"] = self.start_seed + self.completions
        self.results[self.completions]["submitted_workflow"] = workflow

        return workflow

    def add_completion(self):
        self.completions += 1