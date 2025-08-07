# backend/core/file_management/path_resolver.py
import logging
import os
import pathlib
from typing import Optional

from .config_manager import ConfigManager
from ..constants.constants import KNOWN_UI_PROFILES, ModelType

# --- NEW: Import custom error classes for standardized handling (global import) ---
from core.errors import MalError, OperationFailedError, BadRequestError

logger = logging.getLogger(__name__)


class PathResolver:
    """Resolves target directories and final file paths for models based on the current configuration."""

    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager

    def _get_target_directory(
        self, model_type: ModelType, custom_sub_path: Optional[str] = None
    ) -> pathlib.Path:  # --- REFACTOR: Return type is now always Path, raises on failure ---
        """
        (Internal) Determines the base target directory for a given model type.

        Raises:
            BadRequestError: If the base path is not configured, or the relative path
                             is invalid (absolute, contains '..', or escapes the base path).
            OperationFailedError: For unexpected errors during path resolution.
        """
        if not self.config.base_path:
            logger.warning("Cannot get target directory: base_path is not configured.")
            # --- REFACTOR: Raise BadRequestError ---
            raise BadRequestError(
                message="Base path is not configured. Cannot resolve target directory."
            )

        if custom_sub_path:
            relative_path_str = custom_sub_path
        elif self.config.ui_profile == "Custom":
            relative_path_str = (
                self.config.custom_model_type_paths.get(  # --- FIX: Use custom_model_type_paths ---
                    str(model_type), str(model_type)
                )
            )
        elif self.config.ui_profile in KNOWN_UI_PROFILES:
            profile_paths = KNOWN_UI_PROFILES.get(self.config.ui_profile, {})
            relative_path_str = profile_paths.get(str(model_type), str(model_type))
        else:
            relative_path_str = str(model_type)

        try:
            normalized_path = os.path.normpath(relative_path_str)
            if os.path.isabs(normalized_path) or ".." in normalized_path.split(os.sep):
                logger.error(f"Security: Invalid relative path '{relative_path_str}'. Denying.")
                # --- REFACTOR: Raise BadRequestError ---
                raise BadRequestError(
                    message=f"Invalid relative path '{relative_path_str}'. Absolute paths or directory traversal are not allowed."
                )

            target_dir = (self.config.base_path / normalized_path).resolve()
            resolved_base_path = self.config.base_path.resolve()  # Resolve base path for comparison

            # Ensure the final path is still a child of the base path
            if not str(target_dir).startswith(
                str(resolved_base_path)
            ):  # --- FIX: Compare resolved paths as strings ---
                logger.error(
                    f"Security: Resolved path '{target_dir}' is outside base path. Denying."
                )
                # --- REFACTOR: Raise BadRequestError ---
                raise BadRequestError(
                    message=f"Resolved target directory '{relative_path_str}' is outside the configured base path."
                )

            return target_dir
        except MalError:  # Re-raise our custom errors directly
            raise
        except Exception as e:
            logger.error(
                f"Error resolving target directory for '{relative_path_str}': {e}",
                exc_info=True,
            )
            # --- REFACTOR: Raise OperationFailedError ---
            raise OperationFailedError(
                operation_name=f"Resolve target directory for '{relative_path_str}'",
                original_exception=e,
                message=f"An unexpected error occurred while resolving the target directory for '{relative_path_str}'.",
            ) from e

    def resolve_final_save_path(
        self,
        repo_filename: str,
        model_type: ModelType,
        custom_sub_path: Optional[str] = None,
    ) -> pathlib.Path:  # --- REFACTOR: Return type is now always Path, raises on failure ---
        """
        Resolves the final, absolute path where a downloaded file should be saved.
        This is the main public method for this class.

        Raises:
            BadRequestError: If the base path is not configured, or the target directory path is invalid.
            OperationFailedError: For unexpected errors during path resolution.
        """
        try:
            # 1. Get the base directory (e.g., ".../models/checkpoints")
            # This call will now raise BadRequestError or OperationFailedError on failure.
            target_dir = self._get_target_directory(model_type, custom_sub_path)
            # No need for "if not target_dir:" check, as _get_target_directory now raises.

            # 2. Sanitize the filename based on the model type.
            # For 'diffusers', we keep the internal structure.
            # For everything else, we take only the filename to prevent nested directories.
            if model_type == "diffusers":
                sanitized_filename = repo_filename.replace("\\", "/")
            else:
                sanitized_filename = os.path.basename(repo_filename)

            logger.info(
                f"Path resolution for type '{model_type}': '{repo_filename}' -> '{sanitized_filename}'"
            )

            # 3. Combine them to get the final, absolute path
            final_path = target_dir / sanitized_filename

            return final_path
        except MalError:  # Re-raise our custom errors directly
            raise
        except Exception as e:
            logger.critical(
                f"An unhandled exception occurred during final save path resolution: {e}",
                exc_info=True,
            )
            raise OperationFailedError(
                operation_name=f"Resolve final save path for '{repo_filename}' (type: {model_type})",
                original_exception=e,
                message=f"An unexpected error occurred while resolving the final save path for '{repo_filename}'.",
            ) from e
