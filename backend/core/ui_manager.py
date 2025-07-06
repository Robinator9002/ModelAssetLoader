# backend/core/ui_manager.py
import asyncio
import logging
import pathlib
from typing import Optional, Dict, List

from .constants.constants import UI_REPOSITORIES, UiNameType
from .ui_management import ui_installer, ui_operator
from .file_management.download_tracker import download_tracker, BroadcastCallable
from backend.api.models import ManagedUiStatus

logger = logging.getLogger(__name__)


class UiManager:
    """
    Orchestrates the installation, execution, and management of different AI UIs.
    """

    def __init__(self, broadcast_callback: Optional[BroadcastCallable] = None):
        """Initializes the UiManager."""
        self.broadcast_callback = broadcast_callback
        self.running_processes: Dict[str, asyncio.subprocess.Process] = {}
        self.running_ui_tasks: Dict[UiNameType, str] = {}
        logger.info("UiManager initialized.")

    async def get_all_statuses(
        self, base_install_path: pathlib.Path
    ) -> List[ManagedUiStatus]:
        """Checks the local environment for all known UIs and returns their status."""
        statuses: List[ManagedUiStatus] = []
        for ui_name in UI_REPOSITORIES:
            target_dir = base_install_path / ui_name
            is_installed = target_dir.is_dir()
            running_task_id = self.running_ui_tasks.get(ui_name)
            is_running = running_task_id is not None
            statuses.append(
                ManagedUiStatus(
                    ui_name=ui_name,
                    is_installed=is_installed,
                    is_running=is_running,
                    install_path=str(target_dir) if is_installed else None,
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

    async def install_ui_environment(
        self, ui_name: UiNameType, base_install_path: pathlib.Path, task_id: str
    ):
        """Manages the full installation process for a given UI with granular progress."""
        ui_info = await self._get_ui_info(ui_name, task_id)
        if not ui_info:
            return

        target_dir = base_install_path / ui_name
        git_url = ui_info["git_url"]
        req_file = ui_info["requirements_file"]

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
                if total == 0: return
                # Calculate the progress within the allocated range for pip
                pip_progress_fraction = processed / total
                overall_progress = PIP_INSTALL_START + (pip_progress_fraction * (PIP_INSTALL_END - PIP_INSTALL_START))
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

    async def delete_environment(
        self, ui_name: UiNameType, base_install_path: pathlib.Path
    ) -> bool:
        """Deletes an entire UI environment."""
        target_dir = base_install_path / ui_name
        logger.info(f"Request to delete environment for '{ui_name}' at '{target_dir}'.")
        return await ui_operator.delete_ui_environment(target_dir)

    async def run_ui(self, ui_name: UiNameType, base_install_path: pathlib.Path, task_id: str):
        """Starts a UI as a managed background process."""
        # This method remains unchanged as it doesn't have a progress bar component.
        if task_id in self.running_processes:
            await self._stream_progress_to_tracker(
                task_id, f"ERROR: Task ID '{task_id}' is already in use."
            )
            return

        ui_info = await self._get_ui_info(ui_name, task_id)
        if not ui_info: return

        target_dir = base_install_path / ui_name
        start_script = ui_info.get("start_script")
        if not start_script:
            error_msg = f"ERROR: No 'start_script' defined for {ui_name} in constants.py."
            await self._stream_progress_to_tracker(task_id, error_msg)
            await download_tracker.fail_download(task_id, error_msg)
            return

        streamer = lambda line: self._stream_progress_to_tracker(task_id, line)
        
        await download_tracker.update_progress(task_id, 0, 100, status="downloading")

        process = await ui_operator.run_ui(target_dir, start_script, streamer)

        if process:
            self.running_processes[task_id] = process
            self.running_ui_tasks[ui_name] = task_id
            logger.info(f"Process {process.pid} for task '{task_id}' ({ui_name}) is now being managed.")
            
            asyncio.create_task(self._manage_process_lifecycle(process, task_id, ui_name))
        else:
            error_msg = "ERROR: UI process failed to start. Check logs for details."
            logger.error(f"Failed to start process for task '{task_id}'.")
            await self._stream_progress_to_tracker(task_id, error_msg)
            await download_tracker.fail_download(task_id, error_msg)
            
    async def _manage_process_lifecycle(self, process: asyncio.subprocess.Process, task_id: str, ui_name: UiNameType):
        """(Internal) Waits for a process to end and cleans up resources."""
        await process.wait()
        logger.info(f"Process for task '{task_id}' ({ui_name}) has terminated.")
        self.running_processes.pop(task_id, None)
        self.running_ui_tasks.pop(ui_name, None)
        await download_tracker.complete_download(task_id, f"{ui_name} process finished.")

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
