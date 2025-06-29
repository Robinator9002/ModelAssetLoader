# backend/core/file_manager.py
import logging
from typing import Dict, Any, Optional, List

# --- Import the specialized manager classes ---
# The '.' indicates a relative import from the same package ('core').
from .file_management.config_manager import ConfigManager
from .file_management.path_resolver import PathResolver
from .file_management.model_downloader import ModelDownloader
from .file_management.host_scanner import HostScanner
from .file_management.constants import ModelType, UiProfileType, ColorThemeType

logger = logging.getLogger(__name__)

class FileManager:
    """
    Acts as a high-level orchestrator for all file and model management operations.

    This class delegates tasks to specialized managers for configuration, path resolution,
    downloading, and filesystem scanning, providing a clean public API.
    """
    def __init__(self):
        """Initializes all the specialized manager components."""
        self.config = ConfigManager()
        self.paths = PathResolver(self.config)
        self.downloader = ModelDownloader()
        self.scanner = HostScanner()
        logger.info(f"FileManager initialized with profile '{self.config.ui_profile}' and base path '{self.config.base_path}'.")

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
        """
        Configures application settings by delegating to the ConfigManager.
        """
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
            response["error"] = message # If it failed, message is the error

        return response

    def download_model_file(
        self,
        repo_id: str,
        filename: str,
        model_type: ModelType,
        custom_sub_path: Optional[str] = None,
        revision: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Orchestrates downloading a model file.

        1. Resolves the target directory using the PathResolver.
        2. Delegates the actual download to the ModelDownloader.
        """
        if not self.config.base_path:
            return {"success": False, "error": "Base path is not configured. Please configure it first."}

        # 1. Determine where the file should go.
        target_dir = self.paths.get_target_directory(model_type, custom_sub_path)
        if not target_dir:
            error_msg = f"Could not determine a valid target directory for model type '{model_type}'."
            return {"success": False, "error": error_msg}

        # 2. Delegate the download task.
        return self.downloader.download_model_file(
            repo_id=repo_id,
            hf_filename=filename,
            target_directory=target_dir,
            revision=revision
        )

    def list_host_directories(self, path_to_scan_str: Optional[str] = None, max_depth: int = 1) -> Dict[str, Any]:
        """Delegates directory scanning to the HostScanner."""
        return self.scanner.list_host_directories(path_to_scan_str, max_depth)


    # --- Placeholder methods for future features ---
    # These demonstrate how new features would be integrated into the orchestrated design.

    def list_managed_directory_contents(self, relative_path_str: Optional[str] = None, depth: int = 1) -> Dict[str, Any]:
        """
        (Placeholder) Lists contents of a directory within the managed base_path.
        This would use the HostScanner but be constrained to the base path.
        """
        if not self.config.base_path:
            return {"success": False, "error": "Base path is not configured."}

        scan_path = str(self.config.base_path / (relative_path_str or ""))
        logger.info(f"Placeholder: list_managed_directory_contents for '{scan_path}', depth {depth}")
        # In a full implementation, you'd call self.scanner.list_host_directories(scan_path, depth)
        # and potentially add logic to filter for model files, etc.
        return {"success": True, "data": [], "message": "Functionality not fully implemented."}

    def rescan_base_path_structure(self) -> Dict[str, Any]:
        """
        (Placeholder) Rescans the entire configured base_path structure.
        Useful for refreshing a library view in the UI.
        """
        if not self.config.base_path:
            return {"success": False, "error": "Base path is not configured."}

        logger.info(f"Placeholder: Rescanning structure for base path: {self.config.base_path}")
        # Full implementation would likely call the scanner and update a model database.
        return {"success": True, "message": f"Rescan initiated for {self.config.base_path} (placeholder)."}
