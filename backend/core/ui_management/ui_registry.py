# backend/core/ui_management/ui_registry.py
import json
import logging
import pathlib

# --- REFACTOR: Import TypedDict for defining the new data structure ---
from typing import Dict, Optional, TypedDict

from ..constants.constants import CONFIG_FILE_DIR, UiNameType
from core.errors import MalError, OperationFailedError

logger = logging.getLogger(__name__)

INSTALLATIONS_FILE_PATH = CONFIG_FILE_DIR / "ui_installations.json"


# --- REFACTOR: Define a TypedDict for Installation Details ---
# This creates a formal, type-checked structure for each registered UI instance.
# It's the core of the change, allowing us to store more than just a path.
class InstallationDetails(TypedDict):
    """Represents the data stored for a single managed UI installation."""

    ui_name: UiNameType
    display_name: str
    path: str


class UiRegistry:
    """
    Manages the persistent registry of unique UI installations.

    @refactor This class has been significantly reworked. It no longer assumes a
    1-to-1 relationship between a UI type (e.g., 'ComfyUI') and an installation.
    Instead, it now manages a dictionary of unique installation instances,
    each identified by a unique ID. This is the foundational change required
    to support multiple, named instances of the same UI.
    """

    def __init__(self):
        """Initializes the registry by loading data from the file."""
        # --- REFACTOR: The internal dictionary now maps a unique installation_id (str)
        # to the detailed InstallationDetails dictionary. ---
        self._installations: Dict[str, InstallationDetails] = self._load_installations()
        logger.info(
            f"UI Registry initialized with {len(self._installations)} registered installations."
        )

    def _load_installations(self) -> Dict[str, InstallationDetails]:
        """
        Loads the installation data from the JSON file.
        Gracefully handles missing or corrupt files by returning an empty dictionary.
        """
        if not INSTALLATIONS_FILE_PATH.exists():
            return {}
        try:
            with open(INSTALLATIONS_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                # --- REFACTOR: Add more robust validation for the new structure ---
                if isinstance(data, dict) and all(
                    isinstance(k, str) and isinstance(v, dict) and "path" in v and "ui_name" in v
                    for k, v in data.items()
                ):
                    return data
                logger.warning(
                    "ui_installations.json is malformed or uses an old format. Starting fresh."
                )
                return {}
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading UI installations file: {e}", exc_info=True)
            return {}

    def _save_installations(self):
        """Saves the current state of the installation registry to the JSON file."""
        try:
            CONFIG_FILE_DIR.mkdir(exist_ok=True)
            with open(INSTALLATIONS_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(self._installations, f, indent=4)
        except IOError as e:
            logger.error(f"Error saving UI installations file: {e}", exc_info=True)
            # In a production scenario, we might want to raise an OperationFailedError here
            # if saving is absolutely critical. For now, logging is sufficient.

    # --- REFACTOR: `add_installation` now requires more details ---
    def add_installation(
        self,
        installation_id: str,
        ui_name: UiNameType,
        display_name: str,
        install_path: pathlib.Path,
    ):
        """
        Adds or updates an installation instance in the registry.

        Args:
            installation_id: The unique identifier for this instance.
            ui_name: The type of the UI (e.g., 'ComfyUI').
            display_name: The user-provided name for this instance.
            install_path: The absolute path to the installation directory.
        """
        resolved_path_str = str(install_path.resolve())
        logger.info(
            f"Registering installation '{installation_id}' ({display_name}) at path: '{resolved_path_str}'"
        )
        self._installations[installation_id] = {
            "ui_name": ui_name,
            "display_name": display_name,
            "path": resolved_path_str,
        }
        self._save_installations()

    # --- REFACTOR: All public methods now operate on `installation_id` ---
    def remove_installation(self, installation_id: str):
        """Removes an installation record from the registry by its unique ID."""
        if installation_id in self._installations:
            display_name = self._installations[installation_id].get("display_name", installation_id)
            logger.info(f"Unregistering installation '{display_name}' ({installation_id}).")
            del self._installations[installation_id]
            self._save_installations()
        else:
            logger.warning(
                f"Attempted to unregister installation ID '{installation_id}', but it was not found."
            )

    def get_installation(self, installation_id: str) -> Optional[InstallationDetails]:
        """Retrieves the full details for a specific installation instance."""
        return self._installations.get(installation_id)

    def get_all_installations(self) -> Dict[str, InstallationDetails]:
        """
        Gets a dictionary of all registered UI instances, keyed by their unique ID.
        """
        return self._installations.copy()
