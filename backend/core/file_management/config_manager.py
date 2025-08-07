# backend/core/file_management/config_manager.py
import json
import logging
import pathlib
from typing import Dict, Any, Optional, Literal

from ..ui_management.ui_registry import UiRegistry
from ..constants.constants import (
    CONFIG_FILE_PATH,
    UiProfileType,
    ColorThemeType,
    UiNameType,
)
from core.errors import MalError, OperationFailedError, BadRequestError

ConfigurationMode = Literal["automatic", "manual"]
logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Handles loading, saving, and managing the application's configuration,
    now using UiRegistry to resolve paths in 'automatic' mode via installation IDs.
    """

    def __init__(self, ui_registry: UiRegistry):
        """
        Initializes the ConfigManager and loads the existing configuration.

        Args:
            ui_registry: An instance of UiRegistry to resolve UI paths.
        """
        self.ui_registry = ui_registry
        self._manual_base_path: Optional[pathlib.Path] = None
        # --- REFACTOR: This now stores the unique installation_id (a string) ---
        self.automatic_mode_ui_id: Optional[str] = None
        self.ui_profile: Optional[UiProfileType] = None
        self.custom_model_type_paths: Dict[str, str] = {}
        self.color_theme: ColorThemeType = "dark"
        self.config_mode: ConfigurationMode = "automatic"
        self._load_config()

    @property
    def base_path(self) -> Optional[pathlib.Path]:
        """
        Dynamically determines the base path for model storage based on the current mode.
        """
        if self.config_mode == "automatic":
            if self.automatic_mode_ui_id:
                # --- REFACTOR: Use the stored ID to get installation details from the registry ---
                installation = self.ui_registry.get_installation(self.automatic_mode_ui_id)
                if installation and "path" in installation:
                    return pathlib.Path(installation["path"])
                else:
                    logger.warning(
                        f"Automatic mode UI ID '{self.automatic_mode_ui_id}' not found in registry. Base path is unavailable."
                    )
                    # If the configured ID is invalid, clear it to prevent further errors.
                    self.automatic_mode_ui_id = None
                    self._save_config()
                    return None
            return None
        # In manual mode, the logic remains the same.
        return self._manual_base_path

    def _load_config(self):
        """
        Loads configuration from the JSON file if it exists.
        """
        if not CONFIG_FILE_PATH.exists():
            logger.info("Configuration file not found. Using default settings.")
            return

        try:
            with open(CONFIG_FILE_PATH, "r") as f:
                config_data = json.load(f)

            self.ui_profile = config_data.get("ui_profile")
            self.custom_model_type_paths = config_data.get("custom_model_type_paths", {})
            self.color_theme = config_data.get("color_theme", "dark")
            self.config_mode = config_data.get("config_mode", "automatic")
            # --- REFACTOR: Load the installation ID ---
            self.automatic_mode_ui_id = config_data.get("automatic_mode_ui")

            base_path_str = config_data.get("base_path")
            if base_path_str:
                self._manual_base_path = pathlib.Path(base_path_str)

            logger.info(f"Configuration loaded from {CONFIG_FILE_PATH}")

        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Error reading configuration file: {e}. Using defaults.")
            self._reset_to_defaults()
        except Exception as e:
            logger.critical(
                f"An unhandled exception occurred during config loading: {e}", exc_info=True
            )
            self._reset_to_defaults()

    def _save_config(self):
        """
        Saves the current configuration to the JSON file.
        """
        try:
            CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
            config_data = {
                # The saved 'base_path' is now only for manual mode persistence.
                # The effective base_path is always calculated dynamically.
                "base_path": str(self._manual_base_path) if self._manual_base_path else None,
                "ui_profile": self.ui_profile,
                "custom_model_type_paths": self.custom_model_type_paths,
                "color_theme": self.color_theme,
                "config_mode": self.config_mode,
                # --- REFACTOR: Save the installation ID ---
                "automatic_mode_ui": self.automatic_mode_ui_id,
            }

            with open(CONFIG_FILE_PATH, "w") as f:
                json.dump(config_data, f, indent=4)
            logger.info(f"Configuration saved to {CONFIG_FILE_PATH}")
        except IOError as e:
            logger.error(f"Error saving configuration file: {e}", exc_info=True)
        except Exception as e:
            logger.critical(
                f"An unhandled exception occurred during config saving: {e}", exc_info=True
            )

    def _reset_to_defaults(self):
        """Resets the configuration to a clean default state."""
        self._manual_base_path = None
        self.automatic_mode_ui_id = None
        self.ui_profile = None
        self.custom_model_type_paths = {}
        self.color_theme = "dark"
        self.config_mode = "automatic"

    def get_current_configuration(self) -> Dict[str, Any]:
        """Returns the current configuration state as a dictionary for the API."""
        return {
            "base_path": str(self.base_path) if self.base_path else None,
            "ui_profile": self.ui_profile,
            "custom_model_type_paths": self.custom_model_type_paths,
            "color_theme": self.color_theme,
            "config_mode": self.config_mode,
            "automatic_mode_ui": self.automatic_mode_ui_id,
        }

    def update_configuration(
        self,
        base_path_str: Optional[str],
        profile: Optional[UiProfileType],
        custom_model_type_paths: Optional[Dict[str, str]],
        color_theme: Optional[ColorThemeType],
        config_mode: Optional[ConfigurationMode],
        # --- REFACTOR: This now accepts the installation_id string ---
        automatic_mode_ui: Optional[str],
    ):
        """
        Updates and saves the configuration based on user input.
        Raises BadRequestError for invalid input.
        """
        changed = False

        if config_mode and config_mode != self.config_mode:
            self.config_mode = config_mode
            changed = True

        if self.config_mode == "automatic":
            # --- REFACTOR: Update the installation ID ---
            if automatic_mode_ui != self.automatic_mode_ui_id:
                self.automatic_mode_ui_id = automatic_mode_ui
                self._manual_base_path = None  # Clear manual path when switching to auto
                changed = True
        else:  # Manual mode
            new_manual_path = pathlib.Path(base_path_str) if base_path_str else None
            if new_manual_path != self._manual_base_path:
                if new_manual_path and not new_manual_path.is_dir():
                    raise BadRequestError(
                        message=f"The provided base path '{new_manual_path}' is not a valid directory."
                    )
                self._manual_base_path = new_manual_path
                self.automatic_mode_ui_id = None  # Clear auto UI when switching to manual
                changed = True

        if profile != self.ui_profile:
            self.ui_profile = profile
            changed = True

        if (
            custom_model_type_paths is not None
            and custom_model_type_paths != self.custom_model_type_paths
        ):
            self.custom_model_type_paths = custom_model_type_paths
            changed = True

        if color_theme and color_theme != self.color_theme:
            self.color_theme = color_theme
            changed = True

        if changed:
            try:
                self._save_config()
            except Exception as e:
                raise OperationFailedError(
                    operation_name="Save Configuration",
                    original_exception=e,
                    message="Failed to save configuration after update.",
                ) from e
