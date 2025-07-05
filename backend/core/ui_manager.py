# backend/core/ui_manager.py
import asyncio
import logging
import pathlib
from typing import Optional, Dict

# --- Import the building blocks ---

# The "knowledge base" containing Git URLs and other metadata
from .constants.constants import UI_REPOSITORIES, UiNameType

# The specialists for different actions
from .ui_management import ui_installer, ui_operator

# A shared tracker for reporting progress to the frontend
from .file_management.download_tracker import download_tracker, BroadcastCallable

logger = logging.getLogger(__name__)


class UiManager:
    """
    Orchestrates the installation, execution, and management of different AI UIs.

    This class acts as the high-level facade, connecting the API endpoints
    to the low-level installation and operation logic.
    """

    def __init__(self, broadcast_callback: Optional[BroadcastCallable] = None):
        """
        Initializes the UiManager.

        Args:
            broadcast_callback: An async function to broadcast status updates.
        """
        self.broadcast_callback = broadcast_callback
        # --- State management for running processes ---
        # Key: A unique task_id. Value: The running asyncio.subprocess.Process object.
        self.running_processes: Dict[str, asyncio.subprocess.Process] = {}
        logger.info("UiManager initialized.")

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

    # --- Installation ---
    async def install_ui_environment(
        self, ui_name: UiNameType, base_install_path: pathlib.Path, task_id: str
    ):
        """Manages the full installation process for a given UI."""
        ui_info = await self._get_ui_info(ui_name, task_id)
        if not ui_info:
            return

        target_dir = base_install_path / ui_name
        git_url = ui_info["git_url"]
        req_file = ui_info["requirements_file"]

        try:
            # Curry the callback with the task_id
            streamer = lambda line: self._stream_progress_to_tracker(task_id, line)

            logger.info(f"Step 1/3: Cloning {ui_name}...")
            await download_tracker.update_progress(task_id, 0, 100)
            if not await ui_installer.clone_repo(git_url, target_dir, streamer):
                raise RuntimeError(f"Failed to clone repository for {ui_name}.")

            logger.info(f"Step 2/3: Creating venv for {ui_name}...")
            await download_tracker.update_progress(task_id, 33, 100)
            if not await ui_installer.create_venv(target_dir, streamer):
                raise RuntimeError(f"Failed to create venv for {ui_name}.")

            logger.info(f"Step 3/3: Installing dependencies for {ui_name}...")
            await download_tracker.update_progress(task_id, 66, 100)
            if not await ui_installer.install_dependencies(target_dir, req_file, streamer):
                raise RuntimeError(f"Failed to install dependencies for {ui_name}.")

            logger.info(f"Successfully installed {ui_name} at {target_dir}")
            await download_tracker.complete_download(task_id, str(target_dir))

        except Exception as e:
            error_message = f"Installation failed for {ui_name}: {e}"
            logger.error(error_message, exc_info=True)
            await download_tracker.fail_download(task_id, error_message)

    # --- Deletion ---
    async def delete_environment(
        self, ui_name: UiNameType, base_install_path: pathlib.Path
    ) -> bool:
        """Deletes an entire UI environment."""
        target_dir = base_install_path / ui_name
        logger.info(f"Request to delete environment for '{ui_name}' at '{target_dir}'.")
        return await ui_operator.delete_ui_environment(target_dir)

    # --- Execution ---
    async def run_ui(self, ui_name: UiNameType, base_install_path: pathlib.Path, task_id: str):
        """Starts a UI as a managed background process."""
        if task_id in self.running_processes:
            await self._stream_progress_to_tracker(
                task_id, f"ERROR: Task ID '{task_id}' is already in use."
            )
            return

        ui_info = await self._get_ui_info(ui_name, task_id)
        if not ui_info:
            return

        target_dir = base_install_path / ui_name
        start_script = ui_info.get("start_script")
        if not start_script:
            await self._stream_progress_to_tracker(
                task_id, f"ERROR: No 'start_script' defined for {ui_name}."
            )
            return

        streamer = lambda line: self._stream_progress_to_tracker(task_id, line)
        process = await ui_operator.run_ui(target_dir, start_script, streamer)

        if process:
            self.running_processes[task_id] = process
            logger.info(f"Process {process.pid} for task '{task_id}' is now being managed.")
            # Start a separate task to stream the output without blocking
            asyncio.create_task(ui_installer._stream_process(process, streamer))
            # Wait for the process to exit and then clean up
            await process.wait()
            logger.info(f"Process for task '{task_id}' has terminated.")
            self.running_processes.pop(task_id, None)
        else:
            logger.error(f"Failed to start process for task '{task_id}'.")
            await self._stream_progress_to_tracker(task_id, "ERROR: UI process failed to start.")

    async def stop_ui(self, task_id: str):
        """Stops a running UI process."""
        if task_id not in self.running_processes:
            logger.warning(f"Request to stop task '{task_id}', but it is not running.")
            return

        process = self.running_processes[task_id]
        logger.info(f"Stopping process {process.pid} for task '{task_id}'...")
        try:
            process.terminate()
            await process.wait()  # Wait for the process to actually terminate
            logger.info(f"Process {process.pid} terminated successfully.")
        except Exception as e:
            logger.error(f"Error terminating process {process.pid}: {e}", exc_info=True)
            # If terminate fails, be more forceful
            process.kill()
        finally:
            self.running_processes.pop(task_id, None)
