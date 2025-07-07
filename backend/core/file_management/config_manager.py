# backend/core/file_management/config_manager.py
import json
import logging
import pathlib
from typing import Dict, Any, Optional, Tuple, Literal

from ..constants.constants import (
    CONFIG_FILE_PATH,
    KNOWN_UI_PROFILES,
    ModelType,
    UiProfileType,
    ColorThemeType,
    UiNameType,
)

# Define the new type for configuration mode
ConfigurationMode = Literal["automatic", "manual"]

logger = logging.getLogger(__name__)


class ConfigManager:
    """Handles loading, saving, and managing the application's configuration file."""

    def __init__(self):
        self.base_path: Optional[pathlib.Path] = None
        self.ui_profile: Optional[UiProfileType] = None
        self.custom_model_type_paths: Dict[str, str] = {}
        self.color_theme: ColorThemeType = "dark"
        self.config_mode: ConfigurationMode = "automatic"
        # --- PHASE 1: ADDITION ---
        # This new dictionary will store paths to user-provided, "adopted" UI installations.
        # e.g., {"ComfyUI": "/path/to/existing/ComfyUI"}
        self.adopted_ui_paths: Dict[UiNameType, str] = {}
        self._load_config()

    def _load_config(self):
        """Loads configuration from the JSON file if it exists."""
        if not CONFIG_FILE_PATH.exists():
            logger.info("Configuration file not found. Using default settings.")
            return

        try:
            with open(CONFIG_FILE_PATH, "r") as f:
                config_data = json.load(f)

            base_path_str = config_data.get("base_path")
            if base_path_str:
                self.base_path = pathlib.Path(base_path_str)

            self.ui_profile = config_data.get("ui_profile")
            self.custom_model_type_paths = config_data.get("custom_model_type_paths", {})
            self.color_theme = config_data.get("color_theme", "dark")
            self.config_mode = config_data.get("config_mode", "automatic")
            # --- PHASE 1: ADDITION ---
            # Load the adopted UI paths, defaulting to an empty dictionary if not present.
            self.adopted_ui_paths = config_data.get("adopted_ui_paths", {})

            logger.info(f"Configuration loaded from {CONFIG_FILE_PATH}")

        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Error reading configuration file: {e}. Using defaults.")
            self._reset_to_defaults()

    def _save_config(self):
        """Saves the current configuration to the JSON file."""
        CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        # get_current_configuration now includes the new adopted_ui_paths field.
        config_data = self.get_current_configuration()

        try:
            with open(CONFIG_FILE_PATH, "w") as f:
                json.dump(config_data, f, indent=4)
            logger.info(f"Configuration saved to {CONFIG_FILE_PATH}")
        except IOError as e:
            logger.error(f"Error saving configuration file: {e}")

    def _reset_to_defaults(self):
        """Resets the configuration to a default state."""
        self.base_path = None
        self.ui_profile = None
        self.custom_model_type_paths = {}
        self.color_theme = "dark"
        self.config_mode = "automatic"
        # --- PHASE 1: ADDITION ---
        self.adopted_ui_paths = {}

    def get_current_configuration(self) -> Dict[str, Any]:
        """Returns the current configuration as a dictionary."""
        return {
            "base_path": str(self.base_path) if self.base_path else None,
            "ui_profile": self.ui_profile,
            "custom_model_type_paths": self.custom_model_type_paths,
            "color_theme": self.color_theme,
            "config_mode": self.config_mode,
            # --- PHASE 1: ADDITION ---
            "adopted_ui_paths": self.adopted_ui_paths,
        }

    def update_configuration(
        self,
        base_path_str: Optional[str],
        profile: Optional[UiProfileType],
        custom_model_type_paths: Optional[Dict[str, str]],
        color_theme: Optional[ColorThemeType],
        config_mode: Optional[ConfigurationMode],
    ) -> Tuple[bool, str]:
        """Updates and saves the configuration from the main settings page."""
        changed = False

        # Update Base Path
        new_base_path = pathlib.Path(base_path_str) if base_path_str else None
        if new_base_path != self.base_path:
            if new_base_path and not new_base_path.is_dir():
                return (
                    False,
                    f"Error: The provided base path '{new_base_path}' is not a valid directory.",
                )
            self.base_path = new_base_path
            changed = True

        # Update UI Profile
        if profile != self.ui_profile:
            self.ui_profile = profile
            changed = True

        # Update Custom Paths
        if (
            custom_model_type_paths is not None
            and custom_model_type_paths != self.custom_model_type_paths
        ):
            self.custom_model_type_paths = custom_model_type_paths
            changed = True

        # Update Color Theme
        if color_theme and color_theme != self.color_theme:
            self.color_theme = color_theme
            changed = True

        # Update Config Mode
        if config_mode and config_mode != self.config_mode:
            self.config_mode = config_mode
            changed = True

        if changed:
            self._save_config()
            return True, "Configuration updated successfully."

        return False, "No changes detected in configuration."

    # --- PHASE 1: ADDITION ---
    def add_adopted_ui_path(self, ui_name: UiNameType, path_str: str) -> Tuple[bool, str]:
        """
        Adds or updates a single adopted UI path and saves the configuration.
        This provides a dedicated method for the adoption process.
        """
        path = pathlib.Path(path_str)
        if not path.is_dir():
            return False, f"Error: The provided path '{path_str}' is not a valid directory."

        if self.adopted_ui_paths.get(ui_name) == path_str:
            return False, "No change detected for adopted UI path."

        logger.info(f"Adopting UI '{ui_name}' at path '{path_str}'.")
        self.adopted_ui_paths[ui_name] = path_str
        self._save_config()
        return True, f"Successfully adopted {ui_name}."
