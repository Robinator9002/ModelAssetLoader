# backend/core/file_management/path_resolver.py
import logging
import os
import pathlib
from typing import Optional

from .config_manager import ConfigManager
from .constants import KNOWN_UI_PROFILES, ModelType

logger = logging.getLogger(__name__)

class PathResolver:
    """Resolves target directories and final file paths for models based on the current configuration."""
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager

    def _get_target_directory(self, model_type: ModelType, custom_sub_path: Optional[str] = None) -> Optional[pathlib.Path]:
        """
        (Internal) Determines the base target directory for a given model type.
        """
        if not self.config.base_path:
            logger.warning("Cannot get target directory: base_path is not configured.")
            return None

        if custom_sub_path:
            relative_path_str = custom_sub_path
        elif self.config.ui_profile == "Custom":
            relative_path_str = self.config.custom_paths.get(str(model_type), str(model_type))
        elif self.config.ui_profile in KNOWN_UI_PROFILES:
            profile_paths = KNOWN_UI_PROFILES.get(self.config.ui_profile, {})
            relative_path_str = profile_paths.get(str(model_type), str(model_type))
        else:
            relative_path_str = str(model_type)

        try:
            normalized_path = os.path.normpath(relative_path_str)
            if os.path.isabs(normalized_path) or ".." in normalized_path.split(os.sep):
                logger.error(f"Security: Invalid relative path '{relative_path_str}'. Denying.")
                return None

            target_dir = (self.config.base_path / normalized_path).resolve()

            if not str(target_dir).startswith(str(self.config.base_path.resolve())):
                logger.error(f"Security: Resolved path '{target_dir}' is outside base path. Denying.")
                return None

            return target_dir
        except Exception as e:
            logger.error(f"Error resolving target directory for '{relative_path_str}': {e}", exc_info=True)
            return None

    def resolve_final_save_path(
        self,
        repo_filename: str,
        model_type: ModelType,
        custom_sub_path: Optional[str] = None
    ) -> Optional[pathlib.Path]:
        """
        Resolves the final, absolute path where a downloaded file should be saved.
        This is the main public method for this class.
        """
        # 1. Get the base directory (e.g., ".../models/checkpoints")
        target_dir = self._get_target_directory(model_type, custom_sub_path)
        if not target_dir:
            return None

        # 2. Sanitize the filename based on the model type.
        # For 'diffusers', we keep the internal structure.
        # For everything else, we take only the filename to prevent nested directories.
        if model_type == 'diffusers':
            sanitized_filename = repo_filename.replace("\\", "/")
        else:
            sanitized_filename = os.path.basename(repo_filename)
        
        logger.info(f"Path resolution for type '{model_type}': '{repo_filename}' -> '{sanitized_filename}'")

        # 3. Combine them to get the final, absolute path
        final_path = target_dir / sanitized_filename
        
        return final_path
