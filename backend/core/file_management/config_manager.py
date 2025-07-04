# backend/core/file_management/config_manager.py
import json
import logging
import pathlib
from typing import Dict, Optional, Any

from .constants import CONFIG_FILE_DIR, CONFIG_FILE_PATH, ColorThemeType, UiProfileType

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages loading, saving, and accessing application settings."""

    def __init__(self):
        self.base_path: Optional[pathlib.Path] = None
        self.ui_profile: Optional[UiProfileType] = None
        self.custom_paths: Dict[str, str] = {}
        self.color_theme: ColorThemeType = "dark"

        self._ensure_config_dir_exists()
        self._load_config()

    def _ensure_config_dir_exists(self):
        """Ensures the configuration directory exists."""
        try:
            CONFIG_FILE_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(
                f"Could not create or access config directory {CONFIG_FILE_DIR}: {e}"
            )

    def _load_config(self):
        """Loads configuration from the JSON file if it exists."""
        if not CONFIG_FILE_PATH.exists():
            logger.info(
                f"Config file not found at {CONFIG_FILE_PATH}. Using default state."
            )
            return

        try:
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            # Validate and set base_path
            base_path_str = config_data.get("base_path")
            if base_path_str:
                resolved_path = pathlib.Path(base_path_str).resolve()
                if resolved_path.is_dir():
                    self.base_path = resolved_path
                else:
                    logger.warning(
                        f"Loaded base_path '{base_path_str}' is not a valid directory. Ignoring."
                    )

            self.ui_profile = config_data.get("ui_profile")
            self.custom_paths = config_data.get("custom_paths", {})
            self.color_theme = config_data.get("color_theme", "dark")
            logger.info(f"Configuration loaded from {CONFIG_FILE_PATH}")

        except (json.JSONDecodeError, Exception) as e:
            logger.error(
                f"Error loading config from {CONFIG_FILE_PATH}: {e}. Resetting to defaults.",
                exc_info=True,
            )
            self._initialize_default_state()

    def _save_config(self) -> bool:
        """Saves the current configuration to the JSON file."""
        if not CONFIG_FILE_DIR.is_dir():
            logger.error(
                f"Config directory {CONFIG_FILE_DIR} does not exist. Cannot save."
            )
            return False

        config_data = {
            "base_path": str(self.base_path) if self.base_path else None,
            "ui_profile": self.ui_profile,
            "custom_paths": self.custom_paths,
            "color_theme": self.color_theme,
        }
        try:
            with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4)
            logger.info(f"Configuration saved to {CONFIG_FILE_PATH}")
            return True
        except Exception as e:
            logger.error(
                f"Error saving configuration to {CONFIG_FILE_PATH}: {e}", exc_info=True
            )
            return False

    def _initialize_default_state(self):
        """Resets configuration to a default (empty) state."""
        self.base_path = None
        self.ui_profile = None
        self.custom_paths = {}
        self.color_theme = "dark"

    def get_current_configuration(self) -> Dict[str, Any]:
        """Returns the current live configuration."""
        return {
            "base_path": str(self.base_path) if self.base_path else None,
            "ui_profile": self.ui_profile,
            "custom_model_type_paths": self.custom_paths,
            "color_theme": self.color_theme,
        }

    def update_configuration(
        self,
        base_path_str: Optional[str],
        profile: Optional[UiProfileType],
        custom_model_type_paths: Optional[Dict[str, str]],
        color_theme: Optional[ColorThemeType],
    ) -> tuple[bool, str]:
        """
        Updates configuration fields and saves them.
        Returns a tuple of (config_changed, message).
        """
        config_changed = False
        message = "No changes to configuration."

        # Update Base Path
        if base_path_str is not None:
            if base_path_str == "":  # Explicitly clear path
                if self.base_path is not None:
                    self.base_path = None
                    config_changed = True
            else:
                try:
                    p = pathlib.Path(base_path_str).resolve()
                    if not p.is_dir():
                        p.mkdir(parents=True, exist_ok=True)
                    if self.base_path != p:
                        self.base_path = p
                        config_changed = True
                except Exception as e:
                    error_msg = f"Invalid base path '{base_path_str}': {e}"
                    return False, error_msg

        # Update UI Profile
        if profile is not None and self.ui_profile != profile:
            self.ui_profile = profile
            config_changed = True

        # Update Custom Paths
        if (
            custom_model_type_paths is not None
            and self.custom_paths != custom_model_type_paths
        ):
            self.custom_paths = custom_model_type_paths
            config_changed = True

        # Update Color Theme
        if color_theme is not None and self.color_theme != color_theme:
            self.color_theme = color_theme
            config_changed = True

        if config_changed:
            if self._save_config():
                message = "Configuration updated successfully."
            else:
                message = "Configuration updated in memory, but failed to save to file."
                # The change is still technically a success in memory, but we report the save failure.
                return True, message

        return config_changed, message
