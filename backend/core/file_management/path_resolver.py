# backend/core/file_management/path_resolver.py
import logging
import os
import pathlib
from typing import Optional

from .config_manager import ConfigManager
from .constants import KNOWN_UI_PROFILES, ModelType

logger = logging.getLogger(__name__)

class PathResolver:
    """Resolves target directories for models based on the current configuration."""
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager

    def get_target_directory(self, model_type: ModelType, custom_sub_path: Optional[str] = None) -> Optional[pathlib.Path]:
        """
        Determines the target directory for a given model type.

        This method centralizes the logic for path resolution, including sanitization
        and security checks to prevent path traversal attacks.

        Returns:
            A pathlib.Path object to the target directory, or None if invalid.
        """
        if not self.config.base_path:
            logger.warning("Cannot get target directory: base_path is not configured.")
            return None

        # Determine the relative path string based on profile or custom input
        if custom_sub_path:
            relative_path_str = custom_sub_path
        elif self.config.ui_profile == "Custom":
            relative_path_str = self.config.custom_paths.get(str(model_type), str(model_type))
        elif self.config.ui_profile in KNOWN_UI_PROFILES:
            profile_paths = KNOWN_UI_PROFILES.get(self.config.ui_profile, {})
            relative_path_str = profile_paths.get(str(model_type), str(model_type))
        else:
            relative_path_str = str(model_type)

        # Sanitize the relative path to prevent security issues
        try:
            # Normalize path separators (e.g., '\' to '/')
            normalized_path = os.path.normpath(relative_path_str)

            # Disallow absolute paths or traversal ('..') in the relative path
            if os.path.isabs(normalized_path) or ".." in normalized_path.split(os.sep):
                logger.error(f"Security: Invalid relative path '{relative_path_str}'. Denying.")
                return None

            # Construct the final path
            target_dir = (self.config.base_path / normalized_path).resolve()

            # Final security check: ensure the resolved path is within the base path
            if not str(target_dir).startswith(str(self.config.base_path.resolve())):
                logger.error(f"Security: Resolved path '{target_dir}' is outside base path. Denying.")
                return None

            return target_dir
        except Exception as e:
            logger.error(f"Error resolving target directory for '{relative_path_str}': {e}", exc_info=True)
            return None
        