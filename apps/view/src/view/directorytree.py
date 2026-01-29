"""Directory tree widget for browsing file system.

This module provides a customizable directory tree widget that supports
folder navigation, filtering, and key-based navigation between folders.
"""

import os

from core.utils import is_directory_empty
from PySide6.QtCore import QDir, QPersistentModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import QFileSystemModel, QTreeView


class FileProxyModel(QSortFilterProxyModel):
    """Custom proxy model for filtering directory tree items.

    This model filters out sibling directories when a specific directory
    is selected, providing a cleaner navigation experience by showing only
    the selected directory and its children.
    """

    def setIndexPath(self, index):
        """Set the current index path for filtering.

        This method sets the reference index for filtering and invalidates
        the filter to trigger a re-evaluation of which rows should be shown.

        Args:
            index: The index to use as the reference point for filtering.
        """
        self._index_path = index
        self.invalidateFilter()

    def filterAcceptsRow(self, sourceRow, sourceParent):
        """Filter rows to show only the selected directory and its children.

        This method implements the filtering logic to hide sibling directories
        at the same level as the selected directory, creating a focused view
        of the directory hierarchy.

        Args:
            sourceRow: The row index in the source model.
            sourceParent: The parent index in the source model.

        Returns:
            bool: True if the row should be shown, False otherwise.
        """
        if hasattr(self, "_index_path"):
            ix = self.sourceModel().index(sourceRow, 0, sourceParent)
            if self._index_path.parent() == sourceParent and self._index_path != ix:
                return False
        return super(FileProxyModel, self).filterAcceptsRow(sourceRow, sourceParent)


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
        # self._file_system_model.setFilter(QDir.Filter.AllDirs)

        self._proxy = FileProxyModel(self)
        self._proxy.setSourceModel(self._file_system_model)
        self.setModel(self._proxy)

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

    def get_file_system_model(self) -> "QFileSystemModel":
        """Get the file system model.

        Returns:
            QFileSystemModel: The file system model.
        """
        return self._file_system_model

    def get_root_folder(self):
        return self._root_folder

    def open_root_folder(self, folder_path: str) -> None:
        """Open a folder from a given path.

        Args:
            folder_path (str): Path to the folder to open.
        """
        self._root_folder = folder_path

        # Check if the path is a valid directory
        if os.path.isdir(folder_path):
            parent_dir = os.path.abspath(os.path.join(folder_path, os.pardir))
            # Set the root path to the parent directory
            self._file_system_model.setRootPath(parent_dir)

            # Set root index to show the folder and its children
            folder_index = self._file_system_model.index(folder_path)

            self._proxy.setIndexPath(QPersistentModelIndex(folder_index))
            self.setRootIndex(
                self._proxy.mapFromSource(self._file_system_model.index(parent_dir))
            )

            # Find and expand the specific folder
            if folder_index.isValid():
                proxy_folder_index = self._proxy.mapFromSource(folder_index)
                # Expand all directories under the root
                self._expand_all_directories(proxy_folder_index)
                # Select the folder
                self.setCurrentIndex(proxy_folder_index)
                # Scroll to make it visible
                self.scrollTo(proxy_folder_index)
                # Fire the clicked signal
                self.clicked.emit(proxy_folder_index)

    def _expand_all_directories(self, index):
        """Recursively expand all directories starting from the given index."""
        # Expand the current index
        self.setExpanded(index, True)

        # Iterate through all children
        source_index = self._proxy.mapToSource(index)
        for row in range(self._file_system_model.rowCount(source_index)):
            child_index = self._file_system_model.index(row, 0, source_index)
            # If the child is a directory, expand it
            if self._file_system_model.isDir(child_index):
                self._expand_all_directories(self._proxy.mapFromSource(child_index))

    def get_selected_folder_path(self) -> str:
        """Get the path of the currently selected folder.

        Returns:
            str: Path to the selected folder, or empty string if none selected.
        """
        index = self.currentIndex()
        if index.isValid():
            return self._file_system_model.filePath(self._proxy.mapToSource(index))
        return ""

    def get_folder_path_from_index(self, index) -> str:
        """Get the path for the index.

        Args:
            index: The model index to get the path for.

        Returns:
            str: Path to the selected folder, or empty string if none selected.
        """
        if index.isValid():
            return self._file_system_model.filePath(self._proxy.mapToSource(index))
        return ""

    def navigate_to_previous_folder(self):
        """Navigate to the previous folder in the directory tree."""
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

        # If we're at root level, try to select the previous sibling
        if not parent_index.isValid():
            parent_index = root_index

        # Get the row of the current index
        current_row = current_index.row()

        # Try to select the previous sibling
        prev_row = current_row - 1
        model_parent_index = self._proxy.mapToSource(parent_index)
        if prev_row >= 0 and prev_row < self._file_system_model.rowCount(
            model_parent_index
        ):
            prev_index = self._file_system_model.index(prev_row, 0, model_parent_index)

            # If it's a directory, select it
            if self._file_system_model.isDir(prev_index):
                proxy_prev_index = self._proxy.mapFromSource(prev_index)
                self.setCurrentIndex(proxy_prev_index)
                self.scrollTo(proxy_prev_index)
                # Fire the clicked signal
                self.clicked.emit(proxy_prev_index)
                return proxy_prev_index

        # If we're at the start of the current level, try to go to parent's previous sibling
        # or recursively check parent levels
        def find_previous_folder(index):
            """Recursively find the previous folder at any level."""
            while index.isValid():
                parent = index.parent()
                parent_row = index.row()

                # Try to find previous sibling at current level
                if parent.isValid():
                    prev_sibling_row = parent_row - 1
                    if (
                        prev_sibling_row >= 0
                        and prev_sibling_row < self._file_system_model.rowCount(parent)
                    ):
                        prev_sibling = self._file_system_model.index(
                            prev_sibling_row, 0, parent
                        )
                        if self._file_system_model.isDir(prev_sibling):
                            return prev_sibling

                # Move up to parent
                index = parent

            return None

        # Try to find previous folder
        prev_folder = find_previous_folder(model_parent_index)
        if prev_folder and prev_folder.isValid():
            proxy_prev_index = self._proxy.mapFromSource(prev_folder)
            self.setCurrentIndex(proxy_prev_index)
            self.scrollTo(proxy_prev_index)
            # Fire the clicked signal
            self.clicked.emit(proxy_prev_index)
            return proxy_prev_index

        return None

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
        model_parent_index = self._proxy.mapToSource(parent_index)
        if next_row < self._file_system_model.rowCount(model_parent_index):
            next_index = self._file_system_model.index(next_row, 0, model_parent_index)

            # If it's a directory, select it
            if self._file_system_model.isDir(next_index):
                proxy_next_index = self._proxy.mapFromSource(next_index)
                self.setCurrentIndex(proxy_next_index)
                self.scrollTo(proxy_next_index)
                # Fire the clicked signal
                self.clicked.emit(proxy_next_index)
                return proxy_next_index

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
                        next_sibling = self._file_system_model.index(
                            next_sibling_row, 0, parent
                        )
                        if self._file_system_model.isDir(next_sibling):
                            return next_sibling

                # Move up to parent
                index = parent

            return None

        # Try to find next folder
        next_index = find_next_folder(model_parent_index)
        if next_index and next_index.isValid():
            proxy_next_index = self._proxy.mapFromSource(next_index)
            self.setCurrentIndex(proxy_next_index)
            self.scrollTo(proxy_next_index)
            # Fire the clicked signal
            self.clicked.emit(proxy_next_index)
            return proxy_next_index

        return None

    def prune_empty_directories(self, root_folder: str) -> int:
        """Recursively remove empty directories below the root folder using depth-first approach.

        This method:
        1. Processes subdirectories first (depth-first)
        2. Checks if each directory is empty after processing its children
        3. Removes Swarm metadata files (.ldb files) before removing directories
        4. Removes empty directories
        5. Returns the count of removed directories

        Args:
            root_folder (str): Path to the root folder to start pruning from.

        Returns:
            int: Number of directories removed.

        Note:
            This operation is irreversible. Use with caution.
        """
        if not os.path.isdir(root_folder):
            return 0

        removed_count = 0

        def _prune_recursive(directory):
            """Recursively prune empty directories using depth-first approach.

            This inner function implements the depth-first traversal:
            - Processes all children first
            - Then checks if the current directory is empty
            - Removes it if empty
            """
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
            if is_directory_empty(directory):
                try:
                    # Remove swarm metadata files before removing the directory
                    for ldb_file in ["swarm_metadata.ldb", "swarm_metadata-log.ldb"]:
                        ldb_path = os.path.join(directory, ldb_file)
                        if os.path.exists(ldb_path):
                            try:
                                os.remove(ldb_path)
                            except (OSError, PermissionError) as e:
                                print(f"Error removing {ldb_file} in {directory}: {e}")

                    # Remove the now-empty directory
                    os.rmdir(directory)
                    removed_count += 1
                except (OSError, PermissionError) as e:
                    print(f"Error removing directory {directory}: {e}")

        # Start the recursive pruning
        _prune_recursive(root_folder)

        return removed_count

    def keyPressEvent(self, event):
        """Handle key press events.

        Args:
            event: QKeyEvent
        """
        # Handle W key for navigating to previous folder
        if event.key() == Qt.Key.Key_W:
            self.navigate_to_previous_folder()
        # Handle S key for navigating to next folder
        elif event.key() == Qt.Key.Key_S:
            self.navigate_to_next_folder()
        else:
            # Call parent class handler for other keys
            super().keyPressEvent(event)
