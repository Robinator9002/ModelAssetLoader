# backend/core/file_manager.py
import logging
import pathlib
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
        """Provides direct access to the configured base_path."""
        return self.config.base_path

    def get_current_configuration(self) -> Dict[str, Any]:
        """Returns the current live configuration from the ConfigManager."""
        return self.config.get_current_configuration()

    def configure_paths(
        self,
        base_path_str: Optional[str],
        profile: Optional[UiProfileType],
        custom_model_type_paths: Optional[Dict[str, str]] = None,
        color_theme: Optional[ColorThemeType] = None
    ) -> Dict[str, Any]:
        """Delegates configuration updates to the ConfigManager."""
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
        background_tasks: BackgroundTasks,
        source: str, # REFACTOR: Added source to make it extensible
        repo_id: str,
        filename: str,
        model_type: ModelType,
        custom_sub_path: Optional[str] = None,
        revision: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Initiates a download as a background task and returns immediately.
        """
        # REFACTOR: Check for supported sources. Currently only Hugging Face is implemented.
        if source != 'huggingface':
            return {"success": False, "error": f"Source '{source}' is not supported for downloads."}

        if not self.base_path:
            return {"success": False, "error": "Base path is not configured. Please configure it first."}

        target_dir = self.paths.get_target_directory(model_type, custom_sub_path)
        if not target_dir:
            return {"success": False, "error": f"Could not resolve target directory for model type '{model_type}'."}
            
        # Register the download with the tracker to get a unique ID
        status = download_tracker.start_tracking(repo_id=repo_id, filename=filename)
        
        # Add the download process to run in the background
        # The downloader itself is currently HF-specific, but this layer is now ready for more.
        background_tasks.add_task(
            self.downloader.download_model_file,
            download_id=status.download_id,
            repo_id=repo_id,
            hf_filename=filename,
            target_directory=target_dir,
            revision=revision
        )

        logger.info(f"Queued download {status.download_id} for '{filename}' as a background task.")
        return {"success": True, "message": "Download started.", "download_id": status.download_id}

    def list_host_directories(self, path_to_scan_str: Optional[str] = None, max_depth: int = 1) -> Dict[str, Any]:
        """Delegates directory scanning on the host to the HostScanner."""
        return self.scanner.list_host_directories(path_to_scan_str, max_depth)

    def list_managed_directory_contents(self, relative_path_str: Optional[str] = None, depth: int = 1) -> Dict[str, Any]:
        """
        Lists contents of a directory within the managed base_path.
        """
        if not self.base_path:
            return {"success": False, "error": "Base path is not configured."}

        try:
            scan_root = self.base_path.resolve()
            scan_path = scan_root
            if relative_path_str:
                scan_path = (scan_root / relative_path_str).resolve()
            if not str(scan_path).startswith(str(scan_root)):
                logger.error(f"Security violation: Attempt to list '{scan_path}' outside of base path '{scan_root}'.")
                return {"success": False, "error": "Path is outside the managed directory."}
        except Exception as e:
            return {"success": False, "error": f"Invalid path specified: {e}"}

        logger.info(f"Listing managed directory contents for '{scan_path}', depth {depth}")
        return self.scanner.list_host_directories(str(scan_path), depth)
