# backend/core/file_manager.py
import logging
import pathlib
import asyncio
import uuid
from typing import Dict, Any, Optional, List, Tuple

# --- Refactored Imports ---
# Import the new, specialized class for filesystem operations.
from .file_management.managed_file_system import ManagedFileSystem
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
)

# --- NEW: Import custom error classes for standardized handling ---
from core.errors import MalError, OperationFailedError, BadRequestError, EntityNotFoundError

logger = logging.getLogger(__name__)


class FileManager:
    """
    Acts as a high-level orchestrator for all file and model management operations.

    @refactor This class has been refactored to follow the Single Responsibility
    Principle more closely. It no longer contains low-level file system logic.
    Instead, it instantiates and delegates all file browsing, deletion, and
    previewing tasks to the specialized `ManagedFileSystem` class. Its primary
    role is now to coordinate between its various specialized sub-managers.
    """

    def __init__(self, ui_registry: UiRegistry):
        """
        Initializes all the specialized manager components, including the new
        ManagedFileSystem for direct file operations.
        """
        # 1. Create the single source of truth for UI paths.
        self.ui_registry = ui_registry
        # 2. Initialize the configuration manager, giving it access to the registry.
        self.config = ConfigManager(ui_registry=self.ui_registry)
        # 3. Initialize all other specialized managers.
        self.paths = PathResolver(self.config)
        self.downloader = ModelDownloader()
        self.scanner = HostScanner()
        # 4. NEW: Instantiate the dedicated filesystem manager.
        self.fs = ManagedFileSystem(self.config)

        logger.info(
            f"FileManager initialized. Profile: '{self.config.ui_profile}', Base Path: '{self.config.base_path}'."
        )

    @property
    def base_path(self) -> Optional[pathlib.Path]:
        """Returns the dynamically resolved base path from the config manager."""
        return self.config.base_path

    # --- Configuration Management ---
    # These methods are high-level and correctly belong here.

    def get_current_configuration(self) -> Dict[str, Any]:
        """Gets the full, current application configuration."""
        # This method is expected to always succeed in returning a configuration.
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
        """
        Configures the application paths and settings by delegating to the ConfigManager.
        @refactor: This method still returns a success boolean and message for now.
        It will be refactored to raise exceptions directly once ConfigManager.update_configuration
        is updated to raise MalError.
        """
        changed, message = self.config.update_configuration(
            base_path_str,
            profile,
            custom_model_type_paths,
            color_theme,
            config_mode,
            automatic_mode_ui,
        )
        # For now, retain the success check. Once ConfigManager raises errors, this will change.
        success = "failed" not in message
        return success, message

    # --- Download Orchestration ---
    # These methods coordinate between PathResolver, ModelDownloader, and DownloadTracker.

    def start_download_model_file(
        self,
        source: str,
        repo_id: str,
        filename: str,
        model_type: ModelType,
        custom_sub_path: Optional[str] = None,
        revision: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Starts a model file download as a background task.
        @refactor: This method now raises BadRequestError instead of returning error dictionaries.
        """
        if source != "huggingface":
            raise BadRequestError(message=f"Source '{source}' is not supported for downloads.")
        if not self.base_path:
            raise BadRequestError(
                message="Base path is not configured. Please configure it before downloading."
            )

        final_save_path = self.paths.resolve_final_save_path(filename, model_type, custom_sub_path)
        if not final_save_path:
            raise OperationFailedError(
                operation_name="Resolve Download Path",
                original_exception=Exception(
                    f"Could not resolve save path for model type '{model_type}' and filename '{filename}'."
                ),
            )

        download_id = str(uuid.uuid4())
        download_task = asyncio.create_task(
            # The downloader.download_model_file method will be refactored to raise MalError directly.
            # This call here will then propagate that error up if it's not handled within the task itself.
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
        logger.info(f"Queued download {download_id} for '{filename}' -> '{final_save_path}'.")
        # Return a success dictionary as this is a background task initiation,
        # and the actual download success/failure is tracked via download_tracker.
        return {"success": True, "message": "Download started.", "download_id": download_id}

    async def cancel_download(self, download_id: str):
        """Requests cancellation of a running download task."""
        logger.info(f"Cancel request received for download {download_id}.")
        await download_tracker.cancel_and_remove(download_id)

    async def dismiss_download(self, download_id: str):
        """Removes a finished task from the tracker."""
        logger.info(f"Dismiss request received for download {download_id}.")
        await download_tracker.remove_download(download_id)

    # --- Host Scanning ---
    # This method simply delegates to the HostScanner.

    async def list_host_directories(
        self, path_to_scan_str: Optional[str] = None, max_depth: int = 1
    ) -> Dict[str, Any]:
        """
        Asynchronously lists directories on the host system.
        @refactor: This method now directly returns the result of the scanner,
        assuming the scanner will raise MalError on failure.
        """
        # The scanner.list_host_directories method will be refactored to raise MalError
        # (e.g., BadRequestError if path is invalid, OperationFailedError for other issues).
        # This method will then simply return its result, letting errors bubble up.
        return await self.scanner.list_host_directories(path_to_scan_str, max_depth)

    # --- DELEGATED FILE SYSTEM OPERATIONS ---
    # All the following methods now delegate their calls to the new ManagedFileSystem instance.
    # This cleans up FileManager and centralizes the file logic.

    def list_managed_files(
        self, relative_path_str: Optional[str], mode: str = "explorer"
    ) -> Dict[str, Any]:
        """
        Delegates the listing of managed files to the filesystem manager.
        @refactor: This method now directly returns the result of the filesystem manager,
        assuming the filesystem manager will raise MalError on failure.
        """
        # The fs.list_managed_files method will be refactored to raise MalError
        # (e.g., BadRequestError for invalid paths, OperationFailedError for other issues).
        return self.fs.list_managed_files(relative_path_str, mode)

    async def delete_managed_item(self, relative_path_str: str) -> Dict[str, Any]:
        """
        Delegates the deletion of a managed item to the filesystem manager.
        @refactor: This method now directly returns the result of the filesystem manager,
        assuming the filesystem manager will raise MalError on failure.
        """
        # The fs.delete_managed_item method will be refactored to raise MalError
        # (e.g., EntityNotFoundError if item not found, OperationFailedError for deletion issues).
        return await self.fs.delete_managed_item(relative_path_str)

    async def get_file_preview(self, relative_path_str: str) -> Dict[str, Any]:
        """
        Delegates fetching a file preview to the filesystem manager.
        @refactor: This method now directly returns the result of the filesystem manager,
        assuming the filesystem manager will raise MalError on failure.
        """
        # The fs.get_file_preview method will be refactored to raise MalError
        # (e.g., EntityNotFoundError if file not found, BadRequestError if not a text file).
        return await self.fs.get_file_preview(relative_path_str)
