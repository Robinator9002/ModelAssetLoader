# backend/core/ui_management/ui_registry.py
import json
import logging
import pathlib

from typing import Dict, Optional, TypedDict

from ..constants.constants import CONFIG_FILE_DIR, UiNameType
from core.errors import MalError, OperationFailedError, EntityNotFoundError

logger = logging.getLogger(__name__)

INSTALLATIONS_FILE_PATH = CONFIG_FILE_DIR / "ui_installations.json"


class InstallationDetails(TypedDict):
    """Represents the data stored for a single managed UI installation."""

    ui_name: UiNameType
    display_name: str
    path: str


class UiRegistry:
    """
    Manages the persistent registry of unique UI installations.
    """

    def __init__(self):
        """Initializes the registry by loading data from the file."""
        self._installations: Dict[str, InstallationDetails] = self._load_installations()
        logger.info(
            f"UI Registry initialized with {len(self._installations)} registered installations."
        )

    def _load_installations(self) -> Dict[str, InstallationDetails]:
        """
        Loads the installation data from the JSON file.
        """
        if not INSTALLATIONS_FILE_PATH.exists():
            return {}
        try:
            with open(INSTALLATIONS_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
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
            raise OperationFailedError(operation_name="Save UI installations", original_exception=e)

    def add_installation(
        self,
        installation_id: str,
        ui_name: UiNameType,
        display_name: str,
        install_path: pathlib.Path,
    ):
        """
        Adds or updates an installation instance in the registry.
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

    # --- NEW: Method to update an existing installation ---
    def update_installation(
        self,
        installation_id: str,
        new_display_name: Optional[str] = None,
        new_path: Optional[pathlib.Path] = None,
    ):
        """
        Updates the details of an existing installation.

        Args:
            installation_id: The ID of the instance to update.
            new_display_name: The new display name, if provided.
            new_path: The new absolute path, if provided.
        """
        if installation_id not in self._installations:
            raise EntityNotFoundError(entity_name="UI Installation", entity_id=installation_id)

        if new_display_name:
            self._installations[installation_id]["display_name"] = new_display_name
            logger.info(f"Updated display name for '{installation_id}' to '{new_display_name}'.")

        if new_path:
            resolved_path_str = str(new_path.resolve())
            self._installations[installation_id]["path"] = resolved_path_str
            logger.info(f"Updated path for '{installation_id}' to '{resolved_path_str}'.")

        self._save_installations()

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
