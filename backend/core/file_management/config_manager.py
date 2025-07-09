# backend/core/file_management/config_manager.py
import json
import logging
import pathlib
from typing import Dict, Any, Optional, Tuple, Literal

from ..constants.constants import (
    CONFIG_FILE_PATH,
    MANAGED_UIS_ROOT_PATH,
    UiProfileType,
    ColorThemeType,
    UiNameType,
)

# Define the type for configuration mode
ConfigurationMode = Literal["automatic", "manual"]

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Handles loading, saving, and managing the application's configuration,
    supporting both a dynamic 'automatic' mode and a user-defined 'manual' mode.
    """

    def __init__(self):
        """Initializes the ConfigManager and loads the existing configuration."""
        # This holds the user-defined base path for 'manual' mode.
        self._manual_base_path: Optional[pathlib.Path] = None
        # This holds the name of the managed UI selected in 'automatic' mode.
        self.automatic_mode_ui: Optional[UiNameType] = None

        self.ui_profile: Optional[UiProfileType] = None
        self.custom_model_type_paths: Dict[str, str] = {}
        self.color_theme: ColorThemeType = "dark"
        self.config_mode: ConfigurationMode = "automatic"
        self._load_config()

    @property
    def base_path(self) -> Optional[pathlib.Path]:
        """
        Dynamically determines the base path for model storage.

        In 'automatic' mode, it's derived from the selected managed UI's path.
        In 'manual' mode, it's the user-specified path.
        """
        if self.config_mode == "automatic":
            if self.automatic_mode_ui:
                # The base path is the installation directory of the selected UI.
                return MANAGED_UIS_ROOT_PATH / self.automatic_mode_ui
            return None
        # In manual mode, return the explicitly set path.
        return self._manual_base_path

    def _load_config(self):
        """Loads configuration from the JSON file if it exists."""
        if not CONFIG_FILE_PATH.exists():
            logger.info("Configuration file not found. Using default settings.")
            return

        try:
            with open(CONFIG_FILE_PATH, "r") as f:
                config_data = json.load(f)

            # Load settings common to both modes
            self.ui_profile = config_data.get("ui_profile")
            self.custom_model_type_paths = config_data.get("custom_model_type_paths", {})
            self.color_theme = config_data.get("color_theme", "dark")
            self.config_mode = config_data.get("config_mode", "automatic")
            self.automatic_mode_ui = config_data.get("automatic_mode_ui")

            # Load the base path only if it exists (for manual mode persistence)
            base_path_str = config_data.get("base_path")
            if base_path_str:
                self._manual_base_path = pathlib.Path(base_path_str)

            logger.info(f"Configuration loaded from {CONFIG_FILE_PATH}")

        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Error reading configuration file: {e}. Using defaults.")
            self._reset_to_defaults()

    def _save_config(self):
        """Saves the current configuration to the JSON file."""
        CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        config_data = self.get_current_configuration()

        try:
            with open(CONFIG_FILE_PATH, "w") as f:
                json.dump(config_data, f, indent=4)
            logger.info(f"Configuration saved to {CONFIG_FILE_PATH}")
        except IOError as e:
            logger.error(f"Error saving configuration file: {e}")

    def _reset_to_defaults(self):
        """Resets the configuration to a clean default state."""
        self._manual_base_path = None
        self.automatic_mode_ui = None
        self.ui_profile = None
        self.custom_model_type_paths = {}
        self.color_theme = "dark"
        self.config_mode = "automatic"

    def get_current_configuration(self) -> Dict[str, Any]:
        """Returns the current configuration state as a dictionary."""
        # In automatic mode, the saved 'base_path' should be null.
        manual_path_str = str(self._manual_base_path) if self._manual_base_path else None
        base_path_to_save = None if self.config_mode == "automatic" else manual_path_str

        return {
            "base_path": base_path_to_save,
            "ui_profile": self.ui_profile,
            "custom_model_type_paths": self.custom_model_type_paths,
            "color_theme": self.color_theme,
            "config_mode": self.config_mode,
            "automatic_mode_ui": self.automatic_mode_ui,
        }

    def update_configuration(
        self,
        base_path_str: Optional[str],
        profile: Optional[UiProfileType],
        custom_model_type_paths: Optional[Dict[str, str]],
        color_theme: Optional[ColorThemeType],
        config_mode: Optional[ConfigurationMode],
        automatic_mode_ui: Optional[UiNameType],
    ) -> Tuple[bool, str]:
        """
        Updates and saves the configuration based on user input from the settings page.
        """
        changed = False

        # Update Config Mode first, as it affects other logic
        if config_mode and config_mode != self.config_mode:
            self.config_mode = config_mode
            changed = True

        # Handle mode-specific settings
        if self.config_mode == "automatic":
            if automatic_mode_ui != self.automatic_mode_ui:
                self.automatic_mode_ui = automatic_mode_ui
                # Clear manual path when switching to an automatic configuration
                self._manual_base_path = None
                changed = True
        else:  # Manual mode
            new_manual_path = pathlib.Path(base_path_str) if base_path_str else None
            if new_manual_path != self._manual_base_path:
                if new_manual_path and not new_manual_path.is_dir():
                    return (
                        False,
                        f"Error: The provided base path '{new_manual_path}' is not a valid directory.",
                    )
                self._manual_base_path = new_manual_path
                # Clear automatic UI selection when switching to manual
                self.automatic_mode_ui = None
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

        if changed:
            self._save_config()
            return True, "Configuration updated successfully."

        return False, "No changes detected in configuration."
