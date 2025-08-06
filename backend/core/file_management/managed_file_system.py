# backend/core/file_management/managed_file_system.py
import logging
import pathlib
import asyncio
import os
import shutil
from typing import Dict, Any, Optional, List

from .config_manager import ConfigManager
from ..constants.constants import MODEL_FILE_EXTENSIONS

logger = logging.getLogger(__name__)


class ManagedFileSystem:
    """
    Handles all direct interactions with the managed file system.

    This class is responsible for resolving paths, listing files and directories,
    and performing file operations like deletion and reading for previews. It
    encapsulates the logic that was previously in the FileManager, creating a
    clear separation of concerns by focusing solely on filesystem interactions.
    """

    def __init__(self, config_manager: ConfigManager):
        """
        Initializes the ManagedFileSystem with a configuration manager.

        Args:
            config_manager: An instance of ConfigManager to get the base_path
                            and other configuration details needed for path resolution.
        """
        self.config = config_manager

    # --- Path Resolution & Validation ---

    def _resolve_and_validate_path(
        self, relative_path_str: Optional[str]
    ) -> Optional[pathlib.Path]:
        """
        Resolves a relative path against the base_path and validates its safety.

        This is a critical security function that ensures file operations do not
        escape the managed base directory, preventing directory traversal attacks.

        Args:
            relative_path_str: The user-provided relative path.

        Returns:
            A resolved, validated pathlib.Path object, or None if invalid.
        """
        if not self.config.base_path:
            return None
        if not relative_path_str:
            return self.config.base_path

        clean_path_str = os.path.normpath(relative_path_str.strip())
        if os.path.isabs(clean_path_str) or ".." in clean_path_str.split(os.sep):
            return None
        try:
            absolute_path = (self.config.base_path / clean_path_str).resolve()
            # Ensure the final path is still a child of the base path
            if (
                self.config.base_path.resolve() not in absolute_path.parents
                and absolute_path != self.config.base_path.resolve()
            ):
                return None
            return absolute_path
        except Exception:
            return None

    # --- File & Directory Listing Logic ---

    def _has_models_recursive(self, directory: pathlib.Path) -> bool:
        """
        Checks if a directory or any of its subdirectories contain model files.
        This is used in 'models' view mode to only show relevant folders.
        """
        try:
            for entry in os.scandir(directory):
                if entry.is_file(follow_symlinks=False):
                    if any(entry.name.lower().endswith(ext) for ext in MODEL_FILE_EXTENSIONS):
                        return True
                elif entry.is_dir(follow_symlinks=False):
                    if self._has_models_recursive(pathlib.Path(entry.path)):
                        return True
        except (PermissionError, FileNotFoundError):
            return False
        return False

    def _get_directory_contents(self, directory: pathlib.Path, mode: str) -> List[Dict[str, Any]]:
        """
        Scans a single directory and returns a list of its contents, formatted for the API.
        """
        items = []
        for p in directory.iterdir():
            # In automatic mode, skip scanning the 'venv' directory for performance.
            if (
                self.config.config_mode == "automatic"
                and p.is_dir()
                and p.name == "venv"
                and p.parent == self.config.base_path
            ):
                logger.debug("Skipping 'venv' directory in automatic mode.")
                continue

            try:
                is_dir = p.is_dir()
                item_data = {
                    "name": p.name,
                    "path": str(p.relative_to(self.config.base_path)),
                    "item_type": "directory" if is_dir else "file",
                    "size": p.stat().st_size if not is_dir else None,
                    "last_modified": p.stat().st_mtime,
                }
                if mode == "models":
                    if is_dir:
                        if self._has_models_recursive(p):
                            items.append(item_data)
                    elif any(p.name.lower().endswith(ext) for ext in MODEL_FILE_EXTENSIONS):
                        items.append(item_data)
                else:  # 'explorer' mode
                    items.append(item_data)
            except (FileNotFoundError, PermissionError):
                continue
        return items

    def list_managed_files(
        self, relative_path_str: Optional[str], mode: str = "explorer"
    ) -> Dict[str, Any]:
        """
        Public method to list files in the managed path.

        Includes smart navigation for 'models' mode, automatically drilling down
        into single-directory folders to improve user experience.
        """
        current_path = self._resolve_and_validate_path(relative_path_str)
        if not current_path or not current_path.is_dir():
            return {"path": relative_path_str, "items": []}

        if mode == "models":
            # Smart drill-down logic
            for _ in range(10):  # Max depth to prevent infinite loops
                items = self._get_directory_contents(current_path, mode="models")
                if len(items) == 1 and items[0]["item_type"] == "directory":
                    new_path_str = items[0]["path"]
                    resolved_new_path = self._resolve_and_validate_path(new_path_str)
                    if resolved_new_path:
                        current_path = resolved_new_path
                    else:
                        break
                else:
                    break

        final_items = self._get_directory_contents(current_path, mode)
        final_items.sort(key=lambda x: (x["item_type"] != "directory", x["name"].lower()))

        final_relative_path = (
            str(current_path.relative_to(self.config.base_path))
            if current_path != self.config.base_path
            else None
        )
        if final_relative_path == ".":
            final_relative_path = None

        return {"path": final_relative_path, "items": final_items}

    # --- File Operations ---

    async def delete_managed_item(self, relative_path_str: str) -> Dict[str, Any]:
        """Asynchronously deletes a file or directory within the managed base path."""
        target_path = self._resolve_and_validate_path(relative_path_str)
        if not target_path or not target_path.exists():
            return {"success": False, "error": "Path not found."}
        if target_path == self.config.base_path:
            return {"success": False, "error": "Cannot delete the root directory."}
        try:
            if target_path.is_dir():
                await asyncio.to_thread(shutil.rmtree, target_path)
            else:
                await asyncio.to_thread(os.remove, target_path)
            return {"success": True, "message": "Item deleted successfully."}
        except Exception as e:
            logger.error(f"Failed to delete '{target_path}': {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def get_file_preview(self, relative_path_str: str) -> Dict[str, Any]:
        """Asynchronously gets the content of a text file for previewing."""
        target_path = self._resolve_and_validate_path(relative_path_str)
        if not target_path or not target_path.is_file():
            return {"success": False, "error": "The specified path is not a valid file."}

        allowed_extensions = {".txt", ".md", ".json", ".yaml", ".yml", ".py"}
        if target_path.suffix.lower() not in allowed_extensions:
            return {"success": False, "error": "Preview is not allowed for this file type."}

        if target_path.stat().st_size > 1024 * 1024:
            return {"success": False, "error": "File is too large to preview (> 1MB)."}

        try:
            content = await asyncio.to_thread(target_path.read_text, encoding="utf-8")
            return {"success": True, "path": relative_path_str, "content": content}
        except Exception as e:
            logger.error(f"Failed to read file for preview '{target_path}': {e}", exc_info=True)
            return {"success": False, "error": f"Could not read file: {e}"}
