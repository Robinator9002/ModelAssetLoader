# backend/core/ui_manager.py
import asyncio
import logging
import pathlib
from typing import Optional, Dict, List

from .constants.constants import UI_REPOSITORIES, UiNameType
from .ui_management import ui_installer, ui_operator
from .file_management.download_tracker import download_tracker, BroadcastCallable
from .file_management.config_manager import ConfigManager
from backend.api.models import ManagedUiStatus

logger = logging.getLogger(__name__)


class UiManager:
    """
    Orchestrates the installation, execution, and management of different AI UIs.
    """

    # --- PHASE 1: MODIFICATION ---
    def __init__(
        self,
        config_manager: ConfigManager,
        broadcast_callback: Optional[BroadcastCallable] = None,
    ):
        """Initializes the UiManager with a reference to the configuration."""
        self.config = config_manager
        self.broadcast_callback = broadcast_callback
        self.running_processes: Dict[str, asyncio.subprocess.Process] = {}
        self.running_ui_tasks: Dict[UiNameType, str] = {}
        logger.info("UiManager initialized.")

    def _get_install_path_for_ui(self, ui_name: UiNameType) -> Optional[pathlib.Path]:
        """
        (Internal) Determines the correct installation path for a UI,
        checking adopted paths first, then default managed paths.
        """
        # 1. Check for a specific, user-provided "adopted" path.
        adopted_path_str = self.config.adopted_ui_paths.get(ui_name)
        if adopted_path_str:
            return pathlib.Path(adopted_path_str)

        # 2. If not adopted, check the default M.A.L. installation location.
        if self.config.base_path:
            return self.config.base_path / "managed_uis" / ui_name

        # 3. If no base path is set and it's not adopted, we don't know where it is.
        return None

    # --- PHASE 1: REFACTOR ---
    async def get_all_statuses(self) -> List[ManagedUiStatus]:
        """
        Checks the local environment for all known UIs and returns their status,
        now aware of both adopted and managed installations.
        """
        statuses: List[ManagedUiStatus] = []
        for ui_name in UI_REPOSITORIES:
            install_path = self._get_install_path_for_ui(ui_name)
            is_installed = install_path is not None and install_path.is_dir()

            running_task_id = self.running_ui_tasks.get(ui_name)
            is_running = running_task_id is not None

            statuses.append(
                ManagedUiStatus(
                    ui_name=ui_name,
                    is_installed=is_installed,
                    is_running=is_running,
                    install_path=str(install_path) if is_installed else None,
                    running_task_id=running_task_id,
                )
            )
        return statuses

    async def _get_ui_info(self, ui_name: UiNameType, task_id: str) -> Optional[dict]:
        """(Internal) Safely gets UI info and fails the task if not found."""
        ui_info = UI_REPOSITORIES.get(ui_name)
        if not ui_info:
            logger.error(f"Unknown UI '{ui_name}'. Cannot proceed.")
            await download_tracker.fail_download(
                task_id, f"Unknown UI '{ui_name}'. Action aborted."
            )
        return ui_info

    async def _stream_progress_to_tracker(self, task_id: str, line: str):
        """(Internal) Formats and sends log messages via the broadcast callback."""
        logger.info(f"[{task_id}] {line}")
        if self.broadcast_callback:
            await self.broadcast_callback({"type": "log", "task_id": task_id, "message": line})

    # --- PHASE 1: REFACTOR ---
    async def install_ui_environment(
        self, ui_name: UiNameType, base_install_path: pathlib.Path, task_id: str
    ):
        """
        Manages the full installation process for a given UI with granular progress.
        This method is now only for M.A.L.-managed installations.
        """
        ui_info = await self._get_ui_info(ui_name, task_id)
        if not ui_info:
            return

        # The install path is always the default managed path for this function.
        target_dir = base_install_path / ui_name
        git_url = ui_info["git_url"]
        req_file = ui_info.get("requirements_file")  # Use .get for safety

        if not req_file:
            error_message = (
                f"Installation failed: 'requirements_file' not defined for {ui_name} in constants."
            )
            logger.error(error_message)
            await download_tracker.fail_download(task_id, error_message)
            return

        # --- Define progress allocation for each step ---
        CLONE_PROGRESS_END = 15
        VENV_PROGRESS_END = 25
        PIP_INSTALL_START = VENV_PROGRESS_END
        PIP_INSTALL_END = 95

        try:
            streamer = lambda line: self._stream_progress_to_tracker(task_id, line)

            # --- Step 1: Cloning ---
            logger.info(f"Step 1/3: Cloning {ui_name}...")
            await download_tracker.update_progress(task_id, 0, 100)
            if not await ui_installer.clone_repo(git_url, target_dir, streamer):
                raise RuntimeError(f"Failed to clone repository for {ui_name}.")
            await download_tracker.update_progress(task_id, CLONE_PROGRESS_END, 100)

            # --- Step 2: Creating venv ---
            logger.info(f"Step 2/3: Creating venv for {ui_name}...")
            if not await ui_installer.create_venv(target_dir, streamer):
                raise RuntimeError(f"Failed to create venv for {ui_name}.")
            await download_tracker.update_progress(task_id, VENV_PROGRESS_END, 100)

            # --- Step 3: Installing Dependencies (with granular progress) ---
            logger.info(f"Step 3/3: Installing dependencies for {ui_name}...")

            async def pip_progress_callback(processed: int, total: int):
                """Calculates and reports progress for the pip install step."""
                if total == 0:
                    return
                pip_progress_fraction = processed / total
                overall_progress = PIP_INSTALL_START + (
                    pip_progress_fraction * (PIP_INSTALL_END - PIP_INSTALL_START)
                )
                await download_tracker.update_progress(task_id, int(overall_progress), 100)

            if not await ui_installer.install_dependencies(
                target_dir, req_file, streamer, pip_progress_callback
            ):
                raise RuntimeError(f"Failed to install dependencies for {ui_name}.")

            # --- Finalization ---
            logger.info(f"Successfully installed {ui_name} at {target_dir}")
            await download_tracker.complete_download(task_id, str(target_dir))

        except Exception as e:
            error_message = f"Installation failed for {ui_name}: {e}"
            logger.error(error_message, exc_info=True)
            await download_tracker.fail_download(task_id, error_message)

    # --- PHASE 1: REFACTOR ---
    async def delete_environment(self, ui_name: UiNameType) -> bool:
        """Deletes a UI environment, whether adopted or managed."""
        target_dir = self._get_install_path_for_ui(ui_name)
        if not target_dir:
            logger.error(f"Cannot delete {ui_name}, path could not be determined.")
            return False

        logger.info(f"Request to delete environment for '{ui_name}' at '{target_dir}'.")
        # For adopted UIs, we only remove it from our config, we DO NOT delete the files.
        if self.config.adopted_ui_paths.get(ui_name):
            logger.info(f"'{ui_name}' is an adopted UI. Removing from configuration only.")
            del self.config.adopted_ui_paths[ui_name]
            self.config._save_config()  # Use internal save method
            return True
        else:
            # For managed UIs, we delete the whole directory.
            return await ui_operator.delete_ui_environment(target_dir)

    # --- PHASE 1: REFACTOR ---
    async def run_ui(self, ui_name: UiNameType, task_id: str):
        """Starts a UI as a managed background process from its correct location."""
        if task_id in self.running_processes:
            await self._stream_progress_to_tracker(
                task_id, f"ERROR: Task ID '{task_id}' is already in use."
            )
            return

        ui_info = await self._get_ui_info(ui_name, task_id)
        if not ui_info:
            return

        target_dir = self._get_install_path_for_ui(ui_name)
        if not target_dir or not target_dir.is_dir():
            error_msg = f"ERROR: Cannot run {ui_name}. Installation directory not found."
            await self._stream_progress_to_tracker(task_id, error_msg)
            await download_tracker.fail_download(task_id, error_msg)
            return

        start_script = ui_info.get("start_script")
        if not start_script:
            error_msg = f"ERROR: No 'start_script' defined for {ui_name} in constants.py."
            await self._stream_progress_to_tracker(task_id, error_msg)
            await download_tracker.fail_download(task_id, error_msg)
            return

        streamer = lambda line: self._stream_progress_to_tracker(task_id, line)

        await download_tracker.start_tracking(
            download_id=task_id,
            repo_id=f"UI Process",
            filename=ui_name,
            task=asyncio.create_task(
                self._run_and_manage_process(ui_name, target_dir, start_script, task_id, streamer)
            ),
        )

    async def _run_and_manage_process(
        self,
        ui_name: UiNameType,
        target_dir: pathlib.Path,
        start_script: str,
        task_id: str,
        streamer: BroadcastCallable,
    ):
        """(Internal) Helper to contain the full lifecycle of running a process."""
        try:
            process = await ui_operator.run_ui(target_dir, start_script, streamer)
            if not process:
                raise RuntimeError("UI process failed to start. Check logs for details.")

            self.running_processes[task_id] = process
            self.running_ui_tasks[ui_name] = task_id
            logger.info(
                f"Process {process.pid} for task '{task_id}' ({ui_name}) is now being managed."
            )

            # Mark the process as "running" in the tracker
            status = download_tracker.active_downloads.get(task_id)
            if status:
                status.status = "downloading"  # Using 'downloading' to show activity
                await download_tracker._broadcast({"type": "update", "data": status.to_dict()})

            await process.wait()
            logger.info(f"Process for task '{task_id}' ({ui_name}) has terminated.")
            await download_tracker.complete_download(task_id, f"{ui_name} process finished.")

        except Exception as e:
            error_msg = f"ERROR: {e}"
            logger.error(
                f"Failed to run or manage process for task '{task_id}': {e}", exc_info=True
            )
            await download_tracker.fail_download(task_id, error_msg)
        finally:
            self.running_processes.pop(task_id, None)
            self.running_ui_tasks.pop(ui_name, None)

    async def stop_ui(self, task_id: str):
        """Stops a running UI process."""
        if task_id not in self.running_processes:
            logger.warning(f"Request to stop task '{task_id}', but it is not running.")
            return

        process = self.running_processes[task_id]
        logger.info(f"Stopping process {process.pid} for task '{task_id}'...")
        try:
            process.terminate()
            await asyncio.wait_for(process.wait(), timeout=10.0)
            logger.info(f"Process {process.pid} terminated successfully.")
        except asyncio.TimeoutError:
            logger.warning(f"Process {process.pid} did not terminate gracefully. Killing it.")
            process.kill()
        except Exception as e:
            logger.error(f"Error terminating process {process.pid}: {e}", exc_info=True)
            process.kill()
        finally:
            # The lifecycle management will handle the final cleanup.
            # We can send a final message to the tracker.
            await download_tracker.cancel_and_remove(task_id, "Process stopped by user.")
