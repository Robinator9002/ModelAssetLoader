# backend/core/file_manager.py
import logging
import pathlib
import asyncio # Import asyncio
from typing import Dict, Any, Optional

from fastapi import BackgroundTasks

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

    def start_download_model_file(
        self,
        # background_tasks is no longer needed here
        source: str,
        repo_id: str,
        filename: str,
        model_type: ModelType,
        custom_sub_path: Optional[str] = None,
        revision: Optional[str] = None
    ) -> Dict[str, Any]:
        if source != 'huggingface':
            return {"success": False, "error": f"Source '{source}' is not supported for downloads."}

        if not self.base_path:
            return {"success": False, "error": "Base path is not configured. Please configure it first."}

        final_save_path = self.paths.resolve_final_save_path(filename, model_type, custom_sub_path)
        if not final_save_path:
            return {"success": False, "error": f"Could not resolve a valid save path for model type '{model_type}'."}

        # Create the download task
        download_task = asyncio.create_task(
            self.downloader.download_model_file(
                # download_id will be assigned by the tracker
                download_id="", # Placeholder, will be replaced by tracker
                repo_id=repo_id,
                hf_filename=filename,
                target_directory=final_save_path.parent,
                target_filename_override=final_save_path.name,
                revision=revision
            )
        )
        
        # Register the task with the tracker
        status = download_tracker.start_tracking(
            repo_id=repo_id,
            filename=final_save_path.name,
            task=download_task
        )
        
        # Now, update the task with the real download_id
        # This is a bit of a workaround to avoid circular dependencies
        # A better way might be to pass a future/queue to the task
        # But for now, we can patch the coroutine's arguments.
        # Let's refine the downloader to accept the ID directly.
        # Re-creating the task with the correct ID is cleaner.
        download_task.cancel() # Cancel the placeholder task
        
        final_task = asyncio.create_task(
            self.downloader.download_model_file(
                download_id=status.download_id, # Use the real ID
                repo_id=repo_id,
                hf_filename=filename,
                target_directory=final_save_path.parent,
                target_filename_override=final_save_path.name,
                revision=revision
            )
        )
        status.task = final_task # Update the status with the correct task

        logger.info(f"Queued download {status.download_id} for '{filename}' -> '{final_save_path}' as a background task.")
        return {"success": True, "message": "Download started.", "download_id": status.download_id}

    async def dismiss_download(self, download_id: str):
        """Cancels a running download or removes a finished one."""
        logger.info(f"Dismiss request received for download {download_id}. Attempting to cancel and remove.")
        await download_tracker.cancel_and_remove(download_id)

    def list_host_directories(self, path_to_scan_str: Optional[str] = None, max_depth: int = 1) -> Dict[str, Any]:
        return self.scanner.list_host_directories(path_to_scan_str, max_depth)