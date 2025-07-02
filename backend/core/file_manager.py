# backend/core/file_manager.py
import logging
import pathlib
import asyncio
import uuid
import os
import shutil
from typing import Dict, Any, Optional, List

# Import specialized managers and helpers
from .file_management.config_manager import ConfigManager
from .file_management.path_resolver import PathResolver
from .file_management.model_downloader import ModelDownloader
from .file_management.host_scanner import HostScanner
from .file_management.download_tracker import download_tracker
from .file_management.constants import ModelType, UiProfileType, ColorThemeType

logger = logging.getLogger(__name__)

class FileManager:
    """
    Acts as a high-level orchestrator for all file and model management operations.
    """
    def __init__(self):
        """Initializes all the specialized manager components."""
        self.config = ConfigManager()
        self.paths = PathResolver(self.config)
        self.downloader = ModelDownloader()
        self.scanner = HostScanner()
        logger.info(f"FileManager initialized. Profile: '{self.config.ui_profile}', Base Path: '{self.config.base_path}'.")

    @property
    def base_path(self) -> Optional[pathlib.Path]:
        return self.config.base_path

    # --- Configuration Methods (Unchanged) ---
    def get_current_configuration(self) -> Dict[str, Any]:
        return self.config.get_current_configuration()

    def configure_paths(
        self,
        base_path_str: Optional[str],
        profile: Optional[UiProfileType],
        custom_model_type_paths: Optional[Dict[str, str]] = None,
        color_theme: Optional[ColorThemeType] = None
    ) -> Dict[str, Any]:
        changed, message = self.config.update_configuration(
            base_path_str, profile, custom_model_type_paths, color_theme
        )
        success = "failed" not in message
        response = {
            "success": success,
            "message": message,
            "configured_base_path": str(self.config.base_path) if self.config.base_path else None
        }
        if not success:
            response["error"] = message
        return response

    # --- Download Methods (Unchanged, but cancel/dismiss logic is now split) ---
    def start_download_model_file(
        self,
        source: str,
        repo_id: str,
        filename: str,
        model_type: ModelType,
        custom_sub_path: Optional[str] = None,
        revision: Optional[str] = None
    ) -> Dict[str, Any]:
        # (Code is unchanged)
        if source != 'huggingface':
            return {"success": False, "error": f"Source '{source}' is not supported for downloads."}
        if not self.base_path:
            return {"success": False, "error": "Base path is not configured. Please configure it first."}
        final_save_path = self.paths.resolve_final_save_path(filename, model_type, custom_sub_path)
        if not final_save_path:
            return {"success": False, "error": f"Could not resolve a valid save path for model type '{model_type}'."}
        download_id = str(uuid.uuid4())
        download_task = asyncio.create_task(
            self.downloader.download_model_file(
                download_id=download_id,
                repo_id=repo_id,
                hf_filename=filename,
                target_directory=final_save_path.parent,
                target_filename_override=final_save_path.name,
                revision=revision
            )
        )
        download_tracker.start_tracking(
            download_id=download_id,
            repo_id=repo_id,
            filename=final_save_path.name,
            task=download_task
        )
        logger.info(f"Queued download {download_id} for '{filename}' -> '{final_save_path}' as a background task.")
        return {"success": True, "message": "Download started.", "download_id": download_id}

    # --- NEW: Explicit cancel method ---
    async def cancel_download(self, download_id: str):
        """Requests cancellation of a running download task."""
        logger.info(f"Cancel request received for download {download_id}.")
        # This single tracker method handles cancelling the task if it's running.
        await download_tracker.cancel_and_remove(download_id)

    # --- UPDATED: Dismiss now only handles removal from tracker ---
    async def dismiss_download(self, download_id: str):
        """Removes a finished (completed/error/cancelled) download from the tracker."""
        logger.info(f"Dismiss request received for download {download_id}.")
        # This method is for cleanup after a download is in a final state.
        await download_tracker.remove_download(download_id)

    # --- Host Scanning Methods (Unchanged) ---
    def list_host_directories(self, path_to_scan_str: Optional[str] = None, max_depth: int = 1) -> Dict[str, Any]:
        return self.scanner.list_host_directories(path_to_scan_str, max_depth)

    # --- Local File Management Methods (Unchanged) ---
    def _resolve_and_validate_path(self, relative_path_str: Optional[str]) -> Optional[pathlib.Path]:
        if not self.base_path:
            logger.error("Security check failed: base_path is not configured.")
            return None
        if not relative_path_str:
            return self.base_path
        clean_path_str = os.path.normpath(relative_path_str.strip())
        if os.path.isabs(clean_path_str) or ".." in clean_path_str.split(os.sep):
            logger.warning(f"Security violation: Attempted access to invalid path '{relative_path_str}'.")
            return None
        try:
            absolute_path = (self.base_path / clean_path_str).resolve()
            if self.base_path.resolve() not in absolute_path.parents and absolute_path != self.base_path.resolve():
                 logger.warning(f"Security violation: Path '{absolute_path}' is outside of base path '{self.base_path.resolve()}'.")
                 return None
            return absolute_path
        except Exception as e:
            logger.error(f"Error resolving path '{relative_path_str}': {e}", exc_info=True)
            return None

    def list_managed_files(self, relative_path_str: Optional[str]) -> List[Dict[str, Any]]:
        target_path = self._resolve_and_validate_path(relative_path_str)
        if not target_path or not target_path.is_dir():
            return []
        items = []
        for p in target_path.iterdir():
            try:
                item_type = "directory" if p.is_dir() else "file"
                items.append({
                    "name": p.name,
                    "path": str(p.relative_to(self.base_path)),
                    "item_type": item_type,
                    "size": p.stat().st_size if item_type == "file" else None,
                    "last_modified": p.stat().st_mtime
                })
            except (FileNotFoundError, PermissionError) as e:
                logger.warning(f"Could not access item {p}: {e}")
        items.sort(key=lambda x: (x['item_type'] != 'directory', x['name'].lower()))
        return items

    def delete_managed_item(self, relative_path_str: str) -> Dict[str, Any]:
        target_path = self._resolve_and_validate_path(relative_path_str)
        if not target_path or not target_path.exists():
            return {"success": False, "error": f"Path '{relative_path_str}' not found or is invalid."}
        if target_path == self.base_path.resolve():
            return {"success": False, "error": "Cannot delete the root base directory."}
        try:
            item_name = target_path.name
            if target_path.is_dir():
                shutil.rmtree(target_path)
                logger.info(f"Successfully deleted directory: {target_path}")
                return {"success": True, "message": f"Directory '{item_name}' deleted."}
            else:
                os.remove(target_path)
                logger.info(f"Successfully deleted file: {target_path}")
                return {"success": True, "message": f"File '{item_name}' deleted."}
        except Exception as e:
            logger.error(f"Failed to delete '{target_path}': {e}", exc_info=True)
            return {"success": False, "error": f"Could not delete item: {e}"}

    def get_file_preview(self, relative_path_str: str) -> Dict[str, Any]:
        target_path = self._resolve_and_validate_path(relative_path_str)
        if not target_path or not target_path.is_file():
            return {"success": False, "path": relative_path_str, "error": "File not found or is not a file."}
        allowed_extensions = {".txt", ".md", ".json", ".yaml", ".yml", ".py"}
        if target_path.suffix.lower() not in allowed_extensions:
            return {"success": False, "path": relative_path_str, "error": "File type not allowed for preview."}
        max_size_bytes = 1 * 1024 * 1024
        if target_path.stat().st_size > max_size_bytes:
            return {"success": False, "path": relative_path_str, "error": "File is too large to preview."}
        try:
            content = target_path.read_text(encoding="utf-8")
            return {"success": True, "path": relative_path_str, "content": content}
        except Exception as e:
            logger.error(f"Could not read file preview for '{target_path}': {e}", exc_info=True)
            return {"success": False, "path": relative_path_str, "error": f"Could not read file: {e}"}
