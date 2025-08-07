# backend/core/file_management/managed_file_system.py
import logging
import pathlib
import asyncio
import os
import shutil
from typing import Dict, Any, Optional, List

from .config_manager import ConfigManager
from ..constants.constants import MODEL_FILE_EXTENSIONS

# --- NEW: Import custom error classes for standardized handling (global import) ---
from core.errors import MalError, OperationFailedError, BadRequestError, EntityNotFoundError

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
    ) -> pathlib.Path:  # --- REFACTOR: Return type is now always Path, raises on failure ---
        """
        Resolves a relative path against the base_path and validates its safety.

        This is a critical security function that ensures file operations do not
        escape the managed base directory, preventing directory traversal attacks.

        Args:
            relative_path_str: The user-provided relative path.

        Returns:
            A resolved, validated pathlib.Path object.

        Raises:
            BadRequestError: If the base path is not configured, or the relative path
                             is invalid (absolute, contains '..', or escapes the base path).
            OperationFailedError: For unexpected errors during path resolution.
        """
        if not self.config.base_path:
            # --- REFACTOR: Raise BadRequestError ---
            raise BadRequestError(message="Base path is not configured for file operations.")

        # If no relative path is provided, refer to the base path itself.
        if not relative_path_str:
            return self.config.base_path

        clean_path_str = os.path.normpath(relative_path_str.strip())

        # Security check: Prevent absolute paths or directory traversal attempts
        if os.path.isabs(clean_path_str) or ".." in clean_path_str.split(os.sep):
            logger.error(f"Security: Invalid relative path '{relative_path_str}'. Denying.")
            # --- REFACTOR: Raise BadRequestError ---
            raise BadRequestError(
                message=f"Invalid path '{relative_path_str}'. Absolute paths or directory traversal are not allowed."
            )

        try:
            absolute_path = (self.config.base_path / clean_path_str).resolve()
            resolved_base_path = self.config.base_path.resolve()

            # Ensure the final path is still a child of the base path (after resolving symlinks, etc.)
            if (
                resolved_base_path not in absolute_path.parents
                and absolute_path != resolved_base_path
            ):
                logger.error(
                    f"Security: Resolved path '{absolute_path}' is outside base path '{resolved_base_path}'. Denying."
                )
                # --- REFACTOR: Raise BadRequestError ---
                raise BadRequestError(
                    message=f"Resolved path '{relative_path_str}' is outside the managed base directory."
                )
            return absolute_path
        except MalError:  # Re-raise our custom errors directly
            raise
        except Exception as e:
            # Catch any other unexpected errors during path resolution (e.g., invalid characters that pathlib can't handle)
            logger.error(
                f"Error resolving target path for '{relative_path_str}': {e}",
                exc_info=True,
            )
            # --- REFACTOR: Raise OperationFailedError ---
            raise OperationFailedError(
                operation_name=f"Resolve and validate path '{relative_path_str}'",
                original_exception=e,
                message=f"An unexpected error occurred while resolving path '{relative_path_str}'.",
            ) from e

    # --- File & Directory Listing Logic ---

    def _has_models_recursive(self, directory: pathlib.Path) -> bool:
        """
        Checks if a directory or any of its subdirectories contain model files.
        This is used in 'models' view mode to only show relevant folders.
        @refactor: No change to error handling here, as returning False on permission/not found is acceptable.
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
            # Log but don't re-raise, as this is a recursive helper;
            # the parent listing function will handle overall directory access issues.
            logger.debug(
                f"Permission or file not found error in _has_models_recursive for {directory}"
            )
            return False
        except Exception as e:
            logger.warning(
                f"Unexpected error in _has_models_recursive for {directory}: {e}", exc_info=True
            )
            return False
        return False

    def _get_directory_contents(self, directory: pathlib.Path, mode: str) -> List[Dict[str, Any]]:
        """
        Scans a single directory and returns a list of its contents, formatted for the API.
        @refactor: Now raises OperationFailedError for critical directory access issues.
        """
        items = []
        try:
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
                except (FileNotFoundError, PermissionError) as e:
                    # Log but don't re-raise for individual file access issues within a directory,
                    # as the goal is to list as much as possible.
                    logger.debug(f"Skipping inaccessible item {p}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"Unexpected error processing item {p}: {e}", exc_info=True)
                    continue
        except (PermissionError, FileNotFoundError) as e:
            # --- REFACTOR: Raise OperationFailedError for critical directory access issues ---
            raise OperationFailedError(
                operation_name=f"List contents of directory '{directory}'",
                original_exception=e,
                message=f"Could not read directory '{directory}' due to permissions or missing directory.",
            ) from e
        except Exception as e:
            logger.critical(
                f"An unhandled exception occurred during directory listing for {directory}: {e}",
                exc_info=True,
            )
            raise OperationFailedError(
                operation_name=f"List contents of directory '{directory}'",
                original_exception=e,
                message=f"An unexpected error occurred while listing directory '{directory}'.",
            ) from e

        return items

    def list_managed_files(
        self, relative_path_str: Optional[str], mode: str = "explorer"
    ) -> Dict[str, Any]:
        """
        Public method to list files in the managed path.

        Includes smart navigation for 'models' mode, automatically drilling down
        into single-directory folders to improve user experience.
        @refactor: Now raises BadRequestError or OperationFailedError on failure.
        """
        try:
            current_path = self._resolve_and_validate_path(relative_path_str)
            if not current_path.is_dir():
                # --- REFACTOR: Raise BadRequestError if resolved path is not a directory ---
                raise BadRequestError(
                    f"The specified path '{relative_path_str}' is not a directory."
                )

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
                            break  # Break if new path is invalid after resolution
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
        except MalError:  # Re-raise our custom errors directly
            raise
        except Exception as e:
            logger.critical(
                f"An unhandled exception occurred during managed file listing: {e}", exc_info=True
            )
            raise OperationFailedError(
                operation_name=f"List managed files at '{relative_path_str}'",
                original_exception=e,
                message=f"An unexpected internal error occurred while listing files.",
            ) from e

    # --- File Operations ---

    async def delete_managed_item(
        self, relative_path_str: str
    ) -> (
        None
    ):  # --- REFACTOR: Changed return type from Dict[str, Any] to None, will raise on failure ---
        """
        Asynchronously deletes a file or directory within the managed base path.
        @refactor: Now raises EntityNotFoundError, BadRequestError, or OperationFailedError on failure.
        """
        target_path = self._resolve_and_validate_path(relative_path_str)
        # _resolve_and_validate_path now raises BadRequestError if base_path is not configured or path is invalid.

        if not target_path.exists():
            # --- REFACTOR: Raise EntityNotFoundError ---
            raise EntityNotFoundError(
                entity_name="File or Directory",
                entity_id=str(target_path),
                message=f"Path '{relative_path_str}' not found.",
            )
        if target_path == self.config.base_path:
            # --- REFACTOR: Raise BadRequestError ---
            raise BadRequestError(message="Cannot delete the root managed directory.")

        try:
            if target_path.is_dir():
                await asyncio.to_thread(shutil.rmtree, target_path)
            else:
                await asyncio.to_thread(os.remove, target_path)
            logger.info(f"Successfully deleted '{target_path}'.")
            # --- REFACTOR: No return needed on success ---
        except OSError as e:  # --- REFACTOR: Catch specific OSError for file system ops ---
            error_msg = f"Failed to delete '{target_path}': {e}"
            logger.error(error_msg, exc_info=True)
            # --- REFACTOR: Raise OperationFailedError ---
            raise OperationFailedError(
                operation_name=f"Delete managed item '{relative_path_str}'",
                original_exception=e,
                message=error_msg,
            ) from e
        except Exception as e:
            logger.critical(
                f"An unhandled exception occurred during deletion of '{target_path}': {e}",
                exc_info=True,
            )
            raise OperationFailedError(
                operation_name=f"Delete managed item '{relative_path_str}'",
                original_exception=e,
                message=f"An unexpected error occurred while deleting '{relative_path_str}'.",
            ) from e

    async def get_file_preview(
        self, relative_path_str: str
    ) -> Dict[
        str, Any
    ]:  # --- REFACTOR: Return type remains Dict[str, Any], will raise on failure ---
        """
        Asynchronously gets the content of a text file for previewing.
        @refactor: Now raises EntityNotFoundError, BadRequestError, or OperationFailedError on failure.
        """
        target_path = self._resolve_and_validate_path(relative_path_str)
        # _resolve_and_validate_path now raises BadRequestError if base_path is not configured or path is invalid.

        if not target_path.is_file():
            # --- REFACTOR: Raise EntityNotFoundError ---
            raise EntityNotFoundError(
                entity_name="File",
                entity_id=str(target_path),
                message=f"The specified path '{relative_path_str}' is not a valid file.",
            )

        allowed_extensions = {".txt", ".md", ".json", ".yaml", ".yml", ".py"}
        if target_path.suffix.lower() not in allowed_extensions:
            # --- REFACTOR: Raise BadRequestError ---
            raise BadRequestError(
                message=f"Preview is not allowed for file type '{target_path.suffix}'."
            )

        if target_path.stat().st_size > 1024 * 1024:
            # --- REFACTOR: Raise BadRequestError ---
            raise BadRequestError(
                message=f"File is too large to preview (> 1MB): '{relative_path_str}'."
            )

        try:
            content = await asyncio.to_thread(target_path.read_text, encoding="utf-8")
            return {"success": True, "path": relative_path_str, "content": content}
        except OSError as e:  # --- REFACTOR: Catch specific OSError for file read ops ---
            error_msg = f"Failed to read file for preview '{target_path}': {e}"
            logger.error(error_msg, exc_info=True)
            # --- REFACTOR: Raise OperationFailedError ---
            raise OperationFailedError(
                operation_name=f"Read file for preview '{relative_path_str}'",
                original_exception=e,
                message=error_msg,
            ) from e
        except Exception as e:
            logger.critical(
                f"An unhandled exception occurred during file preview of '{target_path}': {e}",
                exc_info=True,
            )
            raise OperationFailedError(
                operation_name=f"Read file for preview '{relative_path_str}'",
                original_exception=e,
                message=f"An unexpected error occurred while previewing '{relative_path_str}'.",
            ) from e
