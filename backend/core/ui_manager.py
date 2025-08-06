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
from . import ui_operator

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

    def __init__(self):
        """
        Initializes the UiManager and its specialized sub-managers.
        """
        # The single source of truth for installation paths.
        self.registry = UiRegistry()

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
        self.installation_manager.start_install(ui_name, install_path, task_id)

    def run_ui(self, ui_name: UiNameType, task_id: str):
        """Delegates the start of a UI process to the ProcessManager."""
        self.process_manager.start_process(ui_name, task_id)

    async def stop_ui(self, task_id: str):
        """Delegates stopping a UI process to the ProcessManager."""
        await self.process_manager.stop_process(task_id)

    async def cancel_ui_task(self, task_id: str):
        """Delegates cancellation of an install/repair task to the InstallationManager."""
        await self.installation_manager.cancel_task(task_id)

    async def delete_environment(self, ui_name: UiNameType) -> bool:
        """
        Deletes a UI environment's directory and removes it from the registry.
        This involves a call to the low-level operator and the registry.
        """
        install_path = self.registry.get_path(ui_name)
        if not install_path:
            return False

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
            await self.stop_ui(running_task_id)
            # Give a moment for the process to terminate.
            await asyncio.sleep(1)

        if await ui_operator.delete_ui_environment(install_path):
            self.registry.remove_installation(ui_name)
            return True
        return False

    # --- Adoption Workflow ---
    # The analysis is a direct operation, while repair and finalization are delegated.

    async def analyze_adoption_candidate(
        self, ui_name: UiNameType, path: pathlib.Path
    ) -> AdoptionAnalysisResult:
        """
        Analyzes a directory to determine if it's a valid, adoptable UI installation.
        This logic is self-contained in the UiAdopter and doesn't require a manager.
        """
        adopter = UiAdopter(ui_name, path)
        return await adopter.analyze()

    def repair_and_adopt_ui(
        self, ui_name: UiNameType, path: pathlib.Path, issues_to_fix: List[str], task_id: str
    ):
        """Delegates the start of a repair process to the InstallationManager."""
        self.installation_manager.start_repair(ui_name, path, issues_to_fix, task_id)

    def finalize_adoption(self, ui_name: UiNameType, path: pathlib.Path) -> bool:
        """
        Directly adopts a UI by adding it to the registry without repairs.
        This is a simple registry operation.
        """
        try:
            self.registry.add_installation(ui_name, path)
            return True
        except Exception as e:
            logger.error(f"Failed to finalize adoption for {ui_name}: {e}", exc_info=True)
            return False
