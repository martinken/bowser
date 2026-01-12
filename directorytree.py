"""Directory tree widget for browsing file system."""

from PySide6.QtCore import QDir, Qt
from PySide6.QtWidgets import QFileSystemModel, QTreeView


class DirectoryTree(QTreeView):
    """A custom directory tree widget for browsing and selecting folders."""

    def __init__(self, parent=None):
        """Initialize the DirectoryTree widget.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        
        # Create file system model for the directory tree
        self._file_system_model = QFileSystemModel()
        self._file_system_model.setRootPath("")
        self._file_system_model.setFilter(
            QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot
        )
        self.setModel(self._file_system_model)

        # Configure the tree view
        self.setHeaderHidden(True)
        self.setMinimumWidth(100)

        # Hide all columns except the name column
        self.setColumnHidden(1, True)  # Hide size column
        self.setColumnHidden(2, True)  # Hide type column
        self.setColumnHidden(3, True)  # Hide date

        # Hide the header
        self.header().hide()

        # Set column width for the name column
        self.setColumnWidth(0, 80)

    def get_file_system_model(self):
        """Get the file system model.

        Returns:
            QFileSystemModel: The file system model.
        """
        return self._file_system_model

    def open_root_folder(self, folder_path):
        """Open a folder from a given path.

        Args:
            folder_path (str): Path to the folder to open.
        """
        # Check if the path is a valid directory
        import os
        if os.path.isdir(folder_path):
            # Set the root path of the file system model to the selected folder
            self._file_system_model.setRootPath(folder_path)
            # Expand the root item
            self.setRootIndex(
                self._file_system_model.index(folder_path)
            )
            # Expand all directories under the root
            self._expand_all_directories(self.rootIndex())

    def _expand_all_directories(self, index):
        """Recursively expand all directories starting from the given index."""
        # Expand the current index
        self.setExpanded(index, True)

        # Iterate through all children
        for row in range(self._file_system_model.rowCount(index)):
            child_index = self._file_system_model.index(row, 0, index)
            # If the child is a directory, expand it
            if self._file_system_model.isDir(child_index):
                self._expand_all_directories(child_index)

    def get_selected_folder_path(self):
        """Get the path of the currently selected folder.

        Returns:
            str: Path to the selected folder, or empty string if none selected.
        """
        index = self.currentIndex()
        if index.isValid():
            return self._file_system_model.filePath(index)
        return ""

    def navigate_to_next_folder(self):
        """Navigate to the next folder in the directory tree."""
        # Get the current root folder
        root_path = self._file_system_model.rootPath()
        if not root_path:
            return
        
        # Get the current root index
        root_index = self.rootIndex()
        if not root_index.isValid():
            return
        
        # Find the currently selected index
        current_index = self.currentIndex()
        
        # If no selection, start from the root
        if not current_index.isValid():
            current_index = root_index
        
        # Get the parent of the current index
        parent_index = current_index.parent()
        
        # If we're at root level, try to select the next sibling
        if not parent_index.isValid():
            parent_index = root_index
        
        # Get the row of the current index
        current_row = current_index.row()
        
        # Try to select the next sibling
        next_row = current_row + 1
        if next_row < self._file_system_model.rowCount(parent_index):
            next_index = self._file_system_model.index(next_row, 0, parent_index)
            
            # If it's a directory, select it
            if self._file_system_model.isDir(next_index):
                self.setCurrentIndex(next_index)
                self.scrollTo(next_index)
                return next_index
        
        # If we're at the end of the current level, try to go to parent's next sibling
        # or recursively check parent levels
        def find_next_folder(index):
            """Recursively find the next folder at any level."""
            while index.isValid():
                parent = index.parent()
                parent_row = index.row()
                
                # Try to find next sibling at current level
                if parent.isValid():
                    next_sibling_row = parent_row + 1
                    if next_sibling_row < self._file_system_model.rowCount(parent):
                        next_sibling = self._file_system_model.index(next_sibling_row, 0, parent)
                        if self._file_system_model.isDir(next_sibling):
                            return next_sibling
                
                # Move up to parent
                index = parent
            
            return None
        
        # Try to find next folder
        next_folder = find_next_folder(parent_index)
        if next_folder and next_folder.isValid():
            self.setCurrentIndex(next_folder)
            self.scrollTo(next_folder)
            return next_folder
        
        return None

    def prune_empty_directories(self, root_folder):
        """Recursively remove empty directories below the root folder using depth-first approach.

        Args:
            root_folder (str): Path to the root folder to start pruning from.

        Returns:
            int: Number of directories removed.
        """
        import os
        
        if not os.path.isdir(root_folder):
            return 0

        removed_count = 0

        def _is_directory_empty(directory):
            """Check if a directory is empty (no files or subdirectories)."""
            try:
                # Check if directory exists and is readable
                if not os.path.exists(directory):
                    return True

                # List all entries in the directory
                with os.scandir(directory) as entries:
                    for entry in entries:
                        # Skip special directories
                        if entry.name.startswith(".") and entry.is_dir():
                            continue
                        # Skip swarm metadata files
                        if entry.name in [
                            "swarm_metadata.ldb",
                            "swarm_metadata-log.ldb",
                        ]:
                            continue
                        return False
                return True
            except (OSError, PermissionError):
                # If we can't access the directory, consider it non-empty
                return False

        def _prune_recursive(directory):
            """Recursively prune empty directories using depth-first approach."""
            nonlocal removed_count

            # Get all subdirectories
            try:
                entries = list(os.scandir(directory))
            except (OSError, PermissionError):
                return

            # Process subdirectories first (depth-first)
            for entry in entries:
                if entry.is_dir() and not entry.name.startswith("."):
                    _prune_recursive(entry.path)

            # After processing subdirectories, check if current directory is empty
            if _is_directory_empty(directory):
                try:
                    # Remove swarm metadata files before removing the directory
                    for ldb_file in ["swarm_metadata.ldb", "swarm_metadata-log.ldb"]:
                        ldb_path = os.path.join(directory, ldb_file)
                        if os.path.exists(ldb_path):
                            try:
                                # os.remove(ldb_path)
                                print(f"remove {ldb_path}")
                            except (OSError, PermissionError) as e:
                                print(f"Error removing {ldb_file} in {directory}: {e}")

                    # Remove the now-empty directory
                    # os.rmdir(directory)
                    print(f"remove {directory}")
                    removed_count += 1
                except (OSError, PermissionError) as e:
                    print(f"Error removing directory {directory}: {e}")

        # Start the recursive pruning
        _prune_recursive(root_folder)

        return removed_count
