# backend/core/file_manager.py
import logging
import pathlib
import asyncio
import uuid
import os
import shutil
from typing import Dict, Any, Optional, List, Tuple

# --- MODIFIED: Import UiRegistry to pass it down ---
from .ui_management.ui_registry import UiRegistry
from .file_management.config_manager import ConfigManager
from .file_management.path_resolver import PathResolver
from .file_management.model_downloader import ModelDownloader
from .file_management.host_scanner import HostScanner
from .file_management.download_tracker import download_tracker
from .constants.constants import (
    ModelType,
    UiProfileType,
    ColorThemeType,
    MODEL_FILE_EXTENSIONS,
)

logger = logging.getLogger(__name__)


class FileManager:
    """
    Acts as a high-level orchestrator for all file and model management operations.
    """

    def __init__(self):
        """
        Initializes all the specialized manager components in the correct order,
        ensuring dependencies like UiRegistry are passed correctly.
        """
        # 1. Create the single source of truth for UI paths.
        self.ui_registry = UiRegistry()
        # 2. Give the ConfigManager access to it.
        self.config = ConfigManager(ui_registry=self.ui_registry)
        # 3. The rest of the components can now be initialized.
        self.paths = PathResolver(self.config)
        self.downloader = ModelDownloader()
        self.scanner = HostScanner()
        logger.info(
            f"FileManager initialized. Profile: '{self.config.ui_profile}', Base Path: '{self.config.base_path}'."
        )

    @property
    def base_path(self) -> Optional[pathlib.Path]:
        """Returns the dynamically resolved base path from the config manager."""
        return self.config.base_path

    def get_current_configuration(self) -> Dict[str, Any]:
        """Gets the full, current application configuration."""
        return self.config.get_current_configuration()

    def configure_paths(
        self,
        base_path_str: Optional[str],
        profile: Optional[UiProfileType],
        custom_model_type_paths: Optional[Dict[str, str]] = None,
        color_theme: Optional[ColorThemeType] = None,
        config_mode: Optional[str] = None,
        automatic_mode_ui: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Configures the application paths and settings."""
        changed, message = self.config.update_configuration(
            base_path_str,
            profile,
            custom_model_type_paths,
            color_theme,
            config_mode,
            automatic_mode_ui,
        )
        success = "failed" not in message
        return success, message

    def start_download_model_file(
        self,
        source: str,
        repo_id: str,
        filename: str,
        model_type: ModelType,
        custom_sub_path: Optional[str] = None,
        revision: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Starts a model file download as a background task."""
        if source != "huggingface":
            return {
                "success": False,
                "error": f"Source '{source}' is not supported for downloads.",
            }
        if not self.base_path:
            return {
                "success": False,
                "error": "Base path is not configured. Please configure it first.",
            }
        final_save_path = self.paths.resolve_final_save_path(filename, model_type, custom_sub_path)
        if not final_save_path:
            return {
                "success": False,
                "error": f"Could not resolve a valid save path for model type '{model_type}'.",
            }
        download_id = str(uuid.uuid4())
        download_task = asyncio.create_task(
            self.downloader.download_model_file(
                download_id=download_id,
                repo_id=repo_id,
                hf_filename=filename,
                target_directory=final_save_path.parent,
                target_filename_override=final_save_path.name,
                revision=revision,
            )
        )
        download_tracker.start_tracking(
            download_id=download_id,
            repo_id=repo_id,
            filename=final_save_path.name,
            task=download_task,
        )
        logger.info(
            f"Queued download {download_id} for '{filename}' -> '{final_save_path}' as a background task."
        )
        return {
            "success": True,
            "message": "Download started.",
            "download_id": download_id,
        }

    async def cancel_download(self, download_id: str):
        """Requests cancellation of a running download task."""
        logger.info(f"Cancel request received for download {download_id}.")
        await download_tracker.cancel_and_remove(download_id)

    # --- NEW Method ---
    async def dismiss_download(self, download_id: str):
        """
        Removes a finished (completed, failed, or cancelled) task from the tracker.
        This method is called by the new API endpoint in main.py. It acts as a
        pass-through to the specialized download_tracker singleton.
        """
        logger.info(f"Dismiss request received for download {download_id}.")
        await download_tracker.remove_download(download_id)

    def list_host_directories(
        self, path_to_scan_str: Optional[str] = None, max_depth: int = 1
    ) -> Dict[str, Any]:
        """Lists directories on the host system."""
        return self.scanner.list_host_directories(path_to_scan_str, max_depth)

    def _resolve_and_validate_path(
        self, relative_path_str: Optional[str]
    ) -> Optional[pathlib.Path]:
        """Resolves a relative path against the base_path and validates it."""
        if not self.base_path:
            return None
        if not relative_path_str:
            return self.base_path
        clean_path_str = os.path.normpath(relative_path_str.strip())
        if os.path.isabs(clean_path_str) or ".." in clean_path_str.split(os.sep):
            return None
        try:
            absolute_path = (self.base_path / clean_path_str).resolve()
            # --- COMMENT: Enhanced security check explanation ---
            # This check ensures that the fully resolved path is still a child of
            # the configured base_path. This prevents escaping the intended
            # directory via symlinks or other filesystem tricks.
            if (
                self.base_path.resolve() not in absolute_path.parents
                and absolute_path != self.base_path.resolve()
            ):
                return None
            return absolute_path
        except Exception:
            return None

    def _has_models_recursive(self, directory: pathlib.Path) -> bool:
        """Checks if a directory or its subdirectories contain model files."""
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
        """Gets the contents of a directory, filtered by mode."""
        items = []
        for p in directory.iterdir():
            # In automatic mode, skip scanning the 'venv' directory at the root
            # of the base path to improve performance and avoid irrelevant results.
            if (
                self.config.config_mode == "automatic"
                and p.is_dir()
                and p.name == "venv"
                and p.parent == self.base_path
            ):
                logger.debug("Skipping 'venv' directory at base path root in automatic mode.")
                continue

            try:
                is_dir = p.is_dir()
                item_data = {
                    "name": p.name,
                    "path": str(p.relative_to(self.base_path)),
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
        """Lists files in the managed path, with smart navigation for 'models' mode."""
        current_path = self._resolve_and_validate_path(relative_path_str)
        if not current_path or not current_path.is_dir():
            return {"path": relative_path_str, "items": []}

        if mode == "models":
            # Smart drill-down for models view: if a directory contains only one
            # other directory, automatically navigate into it.
            for _ in range(10):  # Max drill-down depth to prevent infinite loops
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
            str(current_path.relative_to(self.base_path))
            if current_path != self.base_path
            else None
        )
        if final_relative_path == ".":
            final_relative_path = None

        return {"path": final_relative_path, "items": final_items}

    def delete_managed_item(self, relative_path_str: str) -> Dict[str, Any]:
        """Deletes a file or directory within the managed base path."""
        target_path = self._resolve_and_validate_path(relative_path_str)
        if not target_path or not target_path.exists():
            return {"success": False, "error": "Path not found."}
        if target_path == self.base_path:
            return {"success": False, "error": "Cannot delete the root directory."}
        try:
            if target_path.is_dir():
                shutil.rmtree(target_path)
            else:
                os.remove(target_path)
            return {"success": True, "message": "Item deleted successfully."}
        except Exception as e:
            logger.error(f"Failed to delete '{target_path}': {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def get_file_preview(self, relative_path_str: str) -> Dict[str, Any]:
        """Gets the content of a text file for previewing."""
        target_path = self._resolve_and_validate_path(relative_path_str)
        if not target_path or not target_path.is_file():
            return {"success": False, "error": "The specified path is not a valid file."}

        allowed_extensions = {".txt", ".md", ".json", ".yaml", ".yml", ".py"}
        if target_path.suffix.lower() not in allowed_extensions:
            return {"success": False, "error": "Preview is not allowed for this file type."}

        # Limit preview size to 1MB to prevent performance issues.
        if target_path.stat().st_size > 1024 * 1024:
            return {"success": False, "error": "File is too large to preview (> 1MB)."}

        try:
            content = target_path.read_text(encoding="utf-8")
            return {"success": True, "path": relative_path_str, "content": content}
        except Exception as e:
            logger.error(f"Failed to read file for preview '{target_path}': {e}", exc_info=True)
            return {"success": False, "error": f"Could not read file: {e}"}
