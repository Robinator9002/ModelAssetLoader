# backend/core/ui_management/installation_manager.py
import asyncio
import logging
import pathlib
from typing import Optional, Dict, List

from ..constants.constants import UI_REPOSITORIES, UiNameType
from ..file_management.download_tracker import download_tracker
from .ui_registry import UiRegistry
from . import ui_installer

# --- NEW: Import custom error classes for standardized handling ---
from core.errors import MalError, OperationFailedError, BadRequestError

logger = logging.getLogger(__name__)


# --- Helper Functions ---


def _format_bytes(size_bytes: int) -> str:
    """A helper utility to format a size in bytes to a human-readable string."""
    if size_bytes is None or size_bytes == 0:
        return ""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024**2:
        return f"{size_bytes/1024**2:.1f} MB"
    if size_bytes < 1024**3:
        return f"{size_bytes/1024**3:.2f} GB"
    return f"{size_bytes/1024**3:.2f} GB"  # Fallback for very large sizes


class InstallationManager:
    """
    Manages the complex, multi-step workflows for installing and repairing UI environments.

    This class was refactored from the original UiManager to encapsulate all logic
    related to setting up a new UI from scratch or fixing an existing one. It
    orchestrates calls to the `ui_installer` module and provides detailed progress
    updates via the global `download_tracker`.
    """

    def __init__(self, ui_registry: UiRegistry):
        """
        Initializes the InstallationManager.

        Args:
            ui_registry: An instance of UiRegistry to register new installations upon completion.
        """
        self.ui_registry = ui_registry
        # Stores live process objects for installations/repairs to allow for cancellation.
        self.active_tasks: Dict[str, asyncio.subprocess.Process] = {}
        logger.info("InstallationManager initialized.")

    # --- Public Methods for Installation & Repair ---

    def start_install(self, ui_name: UiNameType, install_path: pathlib.Path, task_id: str):
        """
        Starts the UI installation process as a background asyncio task.
        """
        task = asyncio.create_task(self._install_ui_environment(ui_name, install_path, task_id))
        download_tracker.start_tracking(task_id, "UI Installation", ui_name, task)

    def start_repair(
        self, ui_name: UiNameType, path: pathlib.Path, issues_to_fix: List[str], task_id: str
    ):
        """
        Starts the UI repair and adoption process as a background asyncio task.
        """
        task = asyncio.create_task(self._run_repair_process(ui_name, path, issues_to_fix, task_id))
        download_tracker.start_tracking(task_id, "UI Adoption Repair", ui_name, task)

    async def cancel_task(self, task_id: str):
        """
        Cancels a running installation or repair task by terminating its subprocess.
        @refactor: This method should raise OperationFailedError if cancellation fails.
        """
        process = self.active_tasks.get(task_id)
        if process:
            logger.info(
                f"Terminating process for installation/repair task {task_id} (PID: {process.pid})."
            )
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()
                # --- NEW: Raise OperationFailedError if process needs to be killed ---
                raise OperationFailedError(
                    operation_name=f"Cancel task {task_id}",
                    original_exception=TimeoutError(
                        f"Process {process.pid} did not terminate gracefully and was killed."
                    ),
                )
            except Exception as e:
                # --- NEW: Raise OperationFailedError for other termination issues ---
                raise OperationFailedError(
                    operation_name=f"Cancel task {task_id}", original_exception=e
                )
        else:
            # If the process hasn't been created yet, we can cancel via the tracker.
            await download_tracker.cancel_and_remove(task_id)
            # --- NEW: Consider if this should raise an error if task_id is not found in tracker ---
            # For now, it silently succeeds if not found, which might be acceptable for cancellation.

    # --- Core Workflow Implementations ---

    async def _install_ui_environment(
        self, ui_name: UiNameType, install_path: pathlib.Path, task_id: str
    ):
        """The core async method that orchestrates the complete installation of a new UI."""
        await asyncio.sleep(0.1)  # Allow tracker to register the task
        ui_info = UI_REPOSITORIES.get(ui_name)
        if not ui_info:
            # --- REFACTOR: Raise BadRequestError for unknown UI type ---
            await download_tracker.fail_download(task_id, f"Unknown UI '{ui_name}'.")
            raise BadRequestError(f"UI type '{ui_name}' is not recognized.")

        def process_created_cb(process: asyncio.subprocess.Process):
            self.active_tasks[task_id] = process

        async def streamer(line: str):
            logger.debug(f"[{task_id}:install] {line}")

        try:
            requirements_file = ui_info.get("requirements_file")
            if not requirements_file:
                # --- REFACTOR: Raise OperationFailedError for missing config ---
                raise OperationFailedError(
                    operation_name="UI Installation Configuration",
                    original_exception=ValueError(f"No 'requirements_file' defined for {ui_name}."),
                )

            await download_tracker.update_task_progress(
                task_id, 0, f"Cloning {ui_name} repository..."
            )
            # --- REFACTOR: ui_installer.clone_repo will raise MalError directly ---
            await ui_installer.clone_repo(ui_info["git_url"], install_path, streamer)

            await download_tracker.update_task_progress(
                task_id, 15.0, "Creating virtual environment..."
            )
            # --- REFACTOR: ui_installer.create_venv will raise MalError directly ---
            await ui_installer.create_venv(install_path, streamer)

            await download_tracker.update_task_progress(task_id, 25.0, "Installing dependencies...")
            # --- REFACTOR: ui_installer.install_dependencies will raise MalError directly ---
            await ui_installer.install_dependencies(
                install_path,
                requirements_file,
                streamer,
                lambda *args: self._pip_progress_callback(task_id, *args),
                ui_info.get("extra_packages"),
                process_created_cb,
            )

            await download_tracker.update_task_progress(task_id, 90.0, "Finalizing installation...")
            # --- REFACTOR: ui_registry.add_installation will raise MalError directly ---
            self.ui_registry.add_installation(ui_name, install_path)
            await download_tracker.complete_download(task_id, f"Successfully installed {ui_name}.")
        except asyncio.CancelledError:
            await download_tracker.fail_download(
                task_id, "Installation was cancelled by user.", cancelled=True
            )
        # --- REFACTOR: Catch MalError first, then generic Exception ---
        except MalError as e:
            logger.error(
                f"Installation process for {ui_name} failed with MalError: {e.message}",
                exc_info=False,
            )
            await download_tracker.fail_download(task_id, e.message)
        except Exception as e:
            logger.critical(
                f"An unhandled exception occurred during installation for {ui_name}!", exc_info=True
            )
            await download_tracker.fail_download(
                task_id, f"A critical internal error occurred: {e}"
            )
        finally:
            self.active_tasks.pop(task_id, None)

    async def _run_repair_process(
        self, ui_name: UiNameType, path: pathlib.Path, issues_to_fix: List[str], task_id: str
    ):
        """The core async method that performs the repair actions for UI adoption."""
        await asyncio.sleep(0.1)
        ui_info = UI_REPOSITORIES.get(ui_name)
        if not ui_info:
            # --- REFACTOR: Raise BadRequestError for unknown UI type ---
            await download_tracker.fail_download(task_id, f"Unknown UI '{ui_name}'.")
            raise BadRequestError(f"UI type '{ui_name}' is not recognized.")

        def process_created_cb(process: asyncio.subprocess.Process):
            self.active_tasks[task_id] = process

        async def streamer(line: str):
            logger.debug(f"[{task_id}:repair] {line}")

        try:
            if "VENV_MISSING" in issues_to_fix:
                await download_tracker.update_task_progress(
                    task_id, 10, "Creating virtual environment..."
                )
                # --- REFACTOR: ui_installer.create_venv will raise MalError directly ---
                await ui_installer.create_venv(path, streamer)

            if any(
                code in issues_to_fix
                for code in ["VENV_DEPS_INCOMPLETE", "VENV_INCOMPLETE", "VENV_MISSING"]
            ):
                await download_tracker.update_task_progress(
                    task_id, 50, "Installing dependencies..."
                )
                # --- REFACTOR: ui_installer.install_dependencies will raise MalError directly ---
                await ui_installer.install_dependencies(
                    path,
                    ui_info["requirements_file"],
                    streamer,
                    lambda *args: self._pip_progress_callback(task_id, *args),
                    ui_info.get("extra_packages"),
                    process_created_cb,
                )

            await download_tracker.update_task_progress(task_id, 95, "Finalizing adoption...")
            # --- REFACTOR: ui_registry.add_installation will raise MalError directly ---
            self.ui_registry.add_installation(ui_name, path)
            await download_tracker.complete_download(
                task_id, f"Successfully repaired and adopted {ui_name}."
            )
        except asyncio.CancelledError:
            await download_tracker.fail_download(
                task_id, "Repair was cancelled by user.", cancelled=True
            )
        # --- REFACTOR: Catch MalError first, then generic Exception ---
        except MalError as e:
            logger.error(
                f"Repair process for {ui_name} failed with MalError: {e.message}", exc_info=False
            )
            await download_tracker.fail_download(task_id, e.message)
        except Exception as e:
            logger.critical(
                f"An unhandled exception occurred during repair for {ui_name}!", exc_info=True
            )
            await download_tracker.fail_download(
                task_id, f"A critical internal error occurred: {e}"
            )
        finally:
            self.active_tasks.pop(task_id, None)

    # --- Progress Reporting ---

    async def _pip_progress_callback(
        self,
        task_id: str,
        phase: ui_installer.PipPhase,
        processed: int,
        total: int,
        item_name: str,
        item_size: Optional[int],
    ):
        """Translates structured pip progress into frontend status updates via the tracker."""
        collecting_start, collecting_range = 25.0, 50.0
        installing_start, installing_range = 75.0, 15.0
        current_progress, status_text = 0.0, ""

        if phase == "collecting":
            if total == -1:  # Dry run analysis phase
                phase_progress = collecting_range * (1 - 1 / (processed + 1))
                current_progress = collecting_start + phase_progress
                status_text = item_name
            else:  # Actual download phase
                phase_percent = (processed / total) * collecting_range if total > 0 else 0
                current_progress = collecting_start + phase_percent
                size_str = f"({_format_bytes(item_size)})" if item_size else ""
                status_text = f"Collecting: {item_name} {size_str}".strip()
        elif phase == "installing":
            phase_percent = (processed / total) * installing_range if total > 0 else 0
            current_progress = installing_start + phase_percent
            status_text = f"Installing: {item_name}"

        await download_tracker.update_task_progress(
            task_id, progress=min(current_progress, 90.0), status_text=status_text
        )
