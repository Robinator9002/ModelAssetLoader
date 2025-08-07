# backend/core/ui_management/ui_manager.py
import asyncio
import logging
import pathlib
from typing import List

from api.models import ManagedUiStatus
from .constants.constants import UiNameType
from .ui_management.ui_adopter import UiAdopter, AdoptionAnalysisResult
from .ui_management.ui_registry import UiRegistry
from .ui_management.process_manager import ProcessManager
from .ui_management.installation_manager import InstallationManager
from .ui_management import ui_operator
from .ui_management.ui_registry import UiRegistry

# --- NEW: Import custom error classes for standardized handling ---
from core.errors import MalError, OperationFailedError, BadRequestError, EntityNotFoundError

logger = logging.getLogger(__name__)


class UiManager:
    """
    Acts as a high-level facade for all UI environment management operations.

    @refactor This class has been significantly simplified. It no longer contains
    the complex logic for process management or installation workflows. Instead,
    it instantiates and delegates all tasks to the specialized `ProcessManager`
    and `InstallationManager` classes. Its primary role is to act as a unified
    entry point for the API layer, coordinating between its sub-managers.
    """

    def __init__(self, ui_registry: UiRegistry):
        """
        Initializes the UiManager and its specialized sub-managers.
        """
        # The single source of truth for installation paths.
        self.registry = ui_registry

        # Specialized managers for handling specific responsibilities.
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
        # Get a map of running UIs for quick lookup.
        running_ui_map = {
            ui_name: task_id
            for task_id, (ui_name, pid) in self.process_manager.running_ui_tasks.items()
        }

        for ui_name, install_path in self.registry.get_all_paths().items():
            if not install_path.is_dir():
                logger.warning(
                    f"Path for '{ui_name}' not found at '{install_path}'. Unregistering."
                )
                self.registry.remove_installation(ui_name)
                continue

            running_task_id = running_ui_map.get(ui_name)
            statuses.append(
                ManagedUiStatus(
                    ui_name=ui_name,
                    is_installed=True,
                    is_running=running_task_id is not None,
                    install_path=str(install_path),
                    running_task_id=running_task_id,
                )
            )
        return statuses

    # --- Delegated Lifecycle Methods ---
    # These methods now simply delegate the call to the appropriate manager.

    def install_ui_environment(self, ui_name: UiNameType, install_path: pathlib.Path, task_id: str):
        """Delegates the start of an installation to the InstallationManager."""
        # The InstallationManager.start_install method will be refactored to raise MalError.
        # This method will then simply propagate those errors.
        self.installation_manager.start_install(ui_name, install_path, task_id)

    def run_ui(self, ui_name: UiNameType, task_id: str):
        """Delegates the start of a UI process to the ProcessManager."""
        # The ProcessManager.start_process method will be refactored to raise MalError.
        # This method will then simply propagate those errors.
        self.process_manager.start_process(ui_name, task_id)

    async def stop_ui(self, task_id: str):
        """Delegates stopping a UI process to the ProcessManager."""
        # The ProcessManager.stop_process method will be refactored to raise MalError.
        # This method will then simply propagate those errors.
        await self.process_manager.stop_process(task_id)

    async def cancel_ui_task(self, task_id: str):
        """Delegates cancellation of an install/repair task to the InstallationManager."""
        # The InstallationManager.cancel_task method will be refactored to raise MalError.
        # This method will then simply propagate those errors.
        await self.installation_manager.cancel_task(task_id)

    async def delete_environment(self, ui_name: UiNameType) -> bool:
        """
        Deletes a UI environment's directory and removes it from the registry.
        This involves a call to the low-level operator and the registry.
        @refactor: This method now raises OperationFailedError or EntityNotFoundError
        instead of returning a boolean.
        """
        install_path = self.registry.get_path(ui_name)
        if not install_path:
            # --- REFACTOR: Raise EntityNotFoundError if UI not found ---
            raise EntityNotFoundError(entity_name="UI Environment", entity_id=ui_name)

        # Ensure the process is stopped before deleting the environment.
        running_task_id = next(
            (
                tid
                for tid, (name, pid) in self.process_manager.running_ui_tasks.items()
                if name == ui_name
            ),
            None,
        )
        if running_task_id:
            logger.warning(f"Stopping running process for '{ui_name}' before deletion.")
            # The stop_ui method will be refactored to raise MalError.
            # This call will then propagate that error up.
            await self.stop_ui(running_task_id)
            # Give a moment for the process to terminate.
            await asyncio.sleep(1)

        try:
            # The ui_operator.delete_ui_environment method will be refactored to raise MalError.
            # This call will then propagate that error up.
            if await ui_operator.delete_ui_environment(install_path):
                self.registry.remove_installation(ui_name)
                return True
            else:
                # This else branch should ideally not be reached if ui_operator raises errors.
                # Retained for now, but will be removed once ui_operator is fully refactored.
                raise OperationFailedError(
                    operation_name=f"Delete UI environment '{ui_name}'",
                    original_exception=Exception("Unknown error during UI environment deletion."),
                )
        except MalError:
            # Re-raise our custom errors directly.
            raise
        except Exception as e:
            # Catch any other unexpected errors during deletion and wrap them.
            raise OperationFailedError(
                operation_name=f"Delete UI environment '{ui_name}'", original_exception=e
            )

    # --- Adoption Workflow ---
    # The analysis is a direct operation, while repair and finalization are delegated.

    async def analyze_adoption_candidate(
        self, ui_name: UiNameType, path: pathlib.Path
    ) -> AdoptionAnalysisResult:
        """
        Analyzes a directory to determine if it's a valid, adoptable UI installation.
        This logic is self-contained in the UiAdopter and doesn't require a manager.
        @refactor: This method directly returns the result of UiAdopter,
        assuming UiAdopter will raise MalError on failure.
        """
        adopter = UiAdopter(ui_name, path)
        # The adopter.analyze() method will be refactored to raise MalError.
        # This method will then simply propagate those errors.
        return await adopter.analyze()

    def repair_and_adopt_ui(
        self, ui_name: UiNameType, path: pathlib.Path, issues_to_fix: List[str], task_id: str
    ):
        """Delegates the start of a repair process to the InstallationManager."""
        # The InstallationManager.start_repair method will be refactored to raise MalError.
        # This method will then simply propagate those errors.
        self.installation_manager.start_repair(ui_name, path, issues_to_fix, task_id)

    def finalize_adoption(self, ui_name: UiNameType, path: pathlib.Path) -> bool:
        """
        Directly adopts a UI by adding it to the registry without repairs.
        This is a simple registry operation.
        @refactor: This method now raises OperationFailedError instead of returning a boolean.
        """
        try:
            self.registry.add_installation(ui_name, path)
            return True
        # --- REFACTOR: Catch MalError and re-raise as OperationFailedError ---
        except MalError:
            # If registry.add_installation raises a specific MalError, re-raise it directly.
            raise
        except Exception as e:
            # Catch any other unexpected errors and wrap them in OperationFailedError.
            logger.error(f"Failed to finalize adoption for {ui_name}: {e}", exc_info=True)
            raise OperationFailedError(
                operation_name=f"Finalize adoption for UI '{ui_name}'", original_exception=e
            )
