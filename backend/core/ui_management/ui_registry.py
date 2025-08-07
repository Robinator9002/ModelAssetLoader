# backend/core/ui_management/ui_registry.py
import json
import logging
import pathlib
from typing import Dict, Optional

# Note: Using a relative import to get to the constants file.
# This assumes a standard project structure.
from ..constants.constants import CONFIG_FILE_DIR, UiNameType

# --- NEW: Import custom error classes for standardized handling (global import) ---
# Although not directly used for raising errors within this file's current logic,
# it's good practice for consistency and future expansion.
from core.errors import MalError, OperationFailedError, BadRequestError, EntityNotFoundError


logger = logging.getLogger(__name__)

# Define the path for our new registry file within the existing config directory.
INSTALLATIONS_FILE_PATH = CONFIG_FILE_DIR / "ui_installations.json"


class UiRegistry:
    """
    Manages the persistent registry of UI installations.

    This class reads from and writes to 'ui_installations.json' to keep track
    of where each UI environment (default or custom) is installed. It acts as
    the single source of truth for UI locations.
    """

    def __init__(self):
        """Initializes the registry by loading data from the file."""
        self._installations: Dict[UiNameType, str] = self._load_installations()
        logger.info(
            f"UI Registry initialized with {len(self._installations)} registered installations."
        )

    def _load_installations(self) -> Dict[UiNameType, str]:
        """
        Loads the installation paths from the JSON file.
        If the file doesn't exist or is corrupt, it returns an empty dictionary.
        @refactor: No change to error handling here, as graceful recovery (empty dict) is desired.
        """
        if not INSTALLATIONS_FILE_PATH.exists():
            logger.info("ui_installations.json not found. A new one will be created if needed.")
            return {}
        try:
            with open(INSTALLATIONS_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Basic validation to ensure the loaded data is a dictionary.
                if isinstance(data, dict):
                    return data
                logger.warning(
                    "ui_installations.json is malformed. Starting with an empty registry."
                )
                return {}
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading UI installations file: {e}", exc_info=True)
            return {}

    def _save_installations(self):
        """
        Saves the current state of the installation paths to the JSON file.
        @refactor: No change to error handling here, as logging the failure is sufficient.
        """
        try:
            # Ensure the parent config directory exists.
            CONFIG_FILE_DIR.mkdir(exist_ok=True)
            with open(INSTALLATIONS_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(self._installations, f, indent=4)
        except IOError as e:
            logger.error(f"Error saving UI installations file: {e}", exc_info=True)

    def add_installation(self, ui_name: UiNameType, install_path: pathlib.Path):
        """
        Adds or updates the installation path for a given UI and saves the registry.
        The path is stored as an absolute, resolved string.
        @refactor: This method relies on _save_installations for error handling.
        Any path resolution errors (e.g., OSError from .resolve()) will propagate
        to the caller (UiManager.finalize_adoption), which is already set to catch them.
        """
        logger.info(f"Registering installation for '{ui_name}' at path: '{install_path.resolve()}'")
        self._installations[ui_name] = str(install_path.resolve())
        self._save_installations()

    def remove_installation(self, ui_name: UiNameType):
        """
        Removes an installation record for a given UI and saves the registry.
        @refactor: This method relies on _save_installations for error handling.
        """
        if ui_name in self._installations:
            logger.info(f"Unregistering installation for '{ui_name}'.")
            del self._installations[ui_name]
            self._save_installations()
        else:
            logger.warning(
                f"Attempted to unregister '{ui_name}', but it was not found in the registry."
            )

    def get_path(self, ui_name: UiNameType) -> Optional[pathlib.Path]:
        """
        Retrieves the installation path for a specific UI as a pathlib.Path object.
        Returns None if the UI is not registered.
        """
        path_str = self._installations.get(ui_name)
        return pathlib.Path(path_str) if path_str else None

    def get_all_paths(self) -> Dict[UiNameType, pathlib.Path]:
        """
        Gets a dictionary of all registered UI names and their corresponding
        pathlib.Path objects.
        """
        return {ui_name: pathlib.Path(path) for ui_name, path in self._installations.items()}
