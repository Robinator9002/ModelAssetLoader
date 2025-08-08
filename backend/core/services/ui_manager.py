# backend/core/services/ui_manager.py
import asyncio
import logging
import pathlib
import uuid
from typing import List

from api.models import ManagedUiStatus
from core.constants.constants import UiNameType
from core.ui_management.ui_adopter import UiAdopter, AdoptionAnalysisResult
from core.ui_management.ui_registry import UiRegistry
from core.ui_management.process_manager import ProcessManager
from core.ui_management.installation_manager import InstallationManager
from core.ui_management import ui_operator

from core.errors import MalError, OperationFailedError, BadRequestError, EntityNotFoundError

logger = logging.getLogger(__name__)


class UiManager:
    """
    Acts as a high-level facade for all UI environment management operations.
    It instantiates and delegates all tasks to the specialized sub-managers.
    """

    def __init__(self, ui_registry: UiRegistry):
        self.registry = ui_registry
        self.process_manager = ProcessManager(self.registry)
        self.installation_manager = InstallationManager(self.registry)
        logger.info("UiManager initialized with specialized Process and Installation managers.")

    # --- Status & Information ---

    async def get_all_statuses(self) -> List[ManagedUiStatus]:
        """
        Retrieves the current status for all registered UI environments.
        It combines data from the registry and the process manager.
        """
        statuses: List[ManagedUiStatus] = []
        # --- FIX: Call the new, correct method on the process_manager ---
        running_ui_map = self.process_manager.get_running_tasks_by_installation_id()

        for installation_id, details in self.registry.get_all_installations().items():
            install_path = pathlib.Path(details["path"])
            if not install_path.is_dir():
                logger.warning(
                    f"Path for '{details['display_name']}' ({installation_id}) not found at '{install_path}'. Unregistering."
                )
                self.registry.remove_installation(installation_id)
                continue

            running_task_id = running_ui_map.get(installation_id)
            statuses.append(
                ManagedUiStatus(
                    installation_id=installation_id,
                    display_name=details["display_name"],
                    ui_name=details["ui_name"],
                    is_installed=True,
                    is_running=running_task_id is not None,
                    install_path=str(install_path),
                    running_task_id=running_task_id,
                )
            )
        return statuses

    # --- Delegated Lifecycle Methods ---

    def install_ui_environment(
        self,
        ui_name: UiNameType,
        display_name: str,
        install_path: pathlib.Path,
        task_id: str,
    ):
        installation_id = str(uuid.uuid4())
        # This logic assumes install_path is always provided by the router layer.
        # If it can be None, a default path should be constructed here.
        self.installation_manager.start_install(
            ui_name, install_path, task_id, installation_id, display_name
        )

    # --- FIX: Pass installation_id to the process_manager ---
    def run_ui(self, installation_id: str, task_id: str):
        self.process_manager.start_process(installation_id, task_id)

    async def stop_ui(self, task_id: str):
        await self.process_manager.stop_process(task_id)

    async def cancel_ui_task(self, task_id: str):
        await self.installation_manager.cancel_task(task_id)

    async def delete_environment(self, installation_id: str):
        details = self.registry.get_installation(installation_id)
        if not details:
            raise EntityNotFoundError(entity_name="UI Installation", entity_id=installation_id)

        install_path = pathlib.Path(details["path"])
        # --- FIX: Use the correct method to find the running task ---
        running_task_id = self.process_manager.get_running_tasks_by_installation_id().get(
            installation_id
        )

        if running_task_id:
            logger.warning(
                f"Stopping running process for '{details['display_name']}' before deletion."
            )
            await self.stop_ui(running_task_id)
            await asyncio.sleep(1)

        try:
            await ui_operator.delete_ui_environment(install_path)
            self.registry.remove_installation(installation_id)
        except Exception as e:
            raise OperationFailedError(
                operation_name=f"Delete UI environment '{details['display_name']}'",
                original_exception=e,
            )

    # --- Adoption Workflow ---

    async def analyze_adoption_candidate(
        self, ui_name: UiNameType, path: pathlib.Path
    ) -> AdoptionAnalysisResult:
        adopter = UiAdopter(ui_name, path)
        return await adopter.analyze()

    def repair_and_adopt_ui(
        self,
        ui_name: UiNameType,
        display_name: str,
        path: pathlib.Path,
        issues_to_fix: List[str],
        task_id: str,
    ):
        installation_id = str(uuid.uuid4())
        self.installation_manager.start_repair(
            ui_name, path, issues_to_fix, task_id, installation_id, display_name
        )

    def finalize_adoption(self, ui_name: UiNameType, display_name: str, path: pathlib.Path):
        try:
            installation_id = str(uuid.uuid4())
            self.registry.add_installation(installation_id, ui_name, display_name, path)
        except Exception as e:
            logger.error(f"Failed to finalize adoption for {display_name}: {e}", exc_info=True)
            raise OperationFailedError(
                operation_name=f"Finalize adoption for UI '{display_name}'", original_exception=e
            )
