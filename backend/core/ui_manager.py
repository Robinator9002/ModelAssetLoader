# backend/core/ui_manager.py
import asyncio
import logging
import pathlib
from typing import Optional, Dict, List, Any, Tuple

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
        adopted_path_str = self.config.adopted_ui_paths.get(ui_name)
        if adopted_path_str:
            return pathlib.Path(adopted_path_str)
        if self.config.base_path:
            return self.config.base_path / "managed_uis" / ui_name
        return None

    async def get_all_statuses(self) -> List[ManagedUiStatus]:
        """
        Checks the local environment for all known UIs and returns their status.
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

    async def _monitor_and_stream_process(
        self, process: asyncio.subprocess.Process, task_id: str
    ) -> Tuple[int, str]:
        """
        Monitors a process, streams its output to the tracker, and returns the exit code and combined output.
        """
        output_lines = []

        async def read_stream(stream, stream_name):
            while not stream.at_eof():
                line_bytes = await stream.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace").strip()
                output_lines.append(f"[{stream_name}] {line}")
                # Stream every line to the frontend via the tracker's log mechanism
                await self._stream_progress_to_tracker(task_id, line)

        # Run stream readers concurrently
        await asyncio.gather(
            read_stream(process.stdout, "stdout"), read_stream(process.stderr, "stderr")
        )

        # Wait for the process to terminate and get the exit code
        await process.wait()
        return_code = process.returncode
        combined_output = "\n".join(output_lines)
        logger.info(
            f"Process {process.pid} (task {task_id}) finished with exit code {return_code}."
        )
        return return_code, combined_output

    async def install_ui_environment(
        self, ui_name: UiNameType, base_install_path: pathlib.Path, task_id: str
    ):
        """Manages the full installation process for a given UI with stage-based progress."""
        ui_info = await self._get_ui_info(ui_name, task_id)
        if not ui_info:
            return

        target_dir = base_install_path / ui_name
        git_url = ui_info["git_url"]
        req_file = ui_info.get("requirements_file")

        if not req_file:
            error_message = (
                f"Installation failed: 'requirements_file' not defined for {ui_name} in constants."
            )
            logger.error(error_message)
            await download_tracker.fail_download(task_id, error_message)
            return

        # Define progress percentages for each major stage
        CLONE_PROGRESS_END = 15.0
        VENV_PROGRESS_END = 25.0
        PIP_INSTALL_END = 95.0

        try:
            streamer = lambda line: self._stream_progress_to_tracker(task_id, line)

            # Stage 1: Git Clone
            await download_tracker.update_task_progress(task_id, 0, f"Cloning {ui_name}...")
            if not await ui_installer.clone_repo(git_url, target_dir, streamer):
                raise RuntimeError(f"Failed to clone repository for {ui_name}.")

            # Stage 2: Create Venv
            await download_tracker.update_task_progress(
                task_id, CLONE_PROGRESS_END, "Creating virtual environment..."
            )
            if not await ui_installer.create_venv(target_dir, streamer):
                raise RuntimeError(f"Failed to create venv for {ui_name}.")

            # Stage 3: Pip Install
            await download_tracker.update_task_progress(
                task_id, VENV_PROGRESS_END, "Installing dependencies (this may take a while)..."
            )
            if not await ui_installer.install_dependencies(target_dir, req_file, streamer):
                raise RuntimeError(f"Failed to install dependencies for {ui_name}.")

            # Finalization
            await download_tracker.update_task_progress(
                task_id, PIP_INSTALL_END, "Finalizing installation..."
            )
            await download_tracker.complete_download(task_id, str(target_dir))

        except Exception as e:
            error_message = f"Installation failed for {ui_name}: {e}"
            logger.error(error_message, exc_info=True)
            await download_tracker.fail_download(task_id, error_message)

    async def delete_environment(self, ui_name: UiNameType) -> bool:
        """Deletes a UI environment, whether adopted or managed."""
        target_dir = self._get_install_path_for_ui(ui_name)
        if not target_dir:
            logger.error(f"Cannot delete {ui_name}, path could not be determined.")
            return False

        logger.info(f"Request to delete environment for '{ui_name}' at '{target_dir}'.")
        if self.config.adopted_ui_paths.get(ui_name):
            logger.info(f"'{ui_name}' is an adopted UI. Removing from configuration only.")
            del self.config.adopted_ui_paths[ui_name]
            self.config._save_config()
            return True
        else:
            return await ui_operator.delete_ui_environment(target_dir)

    def run_ui(self, ui_name: UiNameType, task_id: str):
        """Creates a background task to start and manage a UI process."""
        download_tracker.start_tracking(
            download_id=task_id,
            repo_id=f"UI Process",
            filename=ui_name,
            task=asyncio.create_task(self._run_and_manage_process(ui_name, task_id)),
        )

    async def _run_and_manage_process(self, ui_name: UiNameType, task_id: str):
        """(Internal) Helper that contains the full lifecycle of running a process."""
        process = None
        try:
            if task_id in self.running_processes:
                raise RuntimeError(f"Task ID '{task_id}' is already in use.")

            ui_info = await self._get_ui_info(ui_name, task_id)
            if not ui_info:
                return

            target_dir = self._get_install_path_for_ui(ui_name)
            if not target_dir or not target_dir.is_dir():
                raise RuntimeError(
                    f"Cannot run {ui_name}. Installation directory not found at '{target_dir}'."
                )

            start_script = ui_info.get("start_script")
            if not start_script:
                raise RuntimeError(f"No 'start_script' defined for {ui_name} in constants.py.")

            # Get the process object from the operator
            process, error_msg = await ui_operator.run_ui(target_dir, start_script)
            if not process:
                raise RuntimeError(error_msg or "UI process failed to start for an unknown reason.")

            # From this point, the process has started successfully on the OS level.
            self.running_processes[task_id] = process
            self.running_ui_tasks[ui_name] = task_id
            logger.info(f"Process {process.pid} for task '{task_id}' ({ui_name}) is managed.")
            await download_tracker.update_task_progress(
                task_id, 5, status_text="Process is running...", new_status="running"
            )

            # Now, monitor the process, stream its output, and get the final result.
            return_code, combined_output = await self._monitor_and_stream_process(process, task_id)

            # Process has finished. Update tracker based on its exit code.
            if return_code == 0:
                await download_tracker.complete_download(
                    task_id, f"{ui_name} process finished cleanly."
                )
            else:
                error_details = f"{ui_name} process stopped or exited with code {return_code}.\n\nOutput:\n{combined_output}"
                await download_tracker.fail_download(task_id, error_details, cancelled=True)

        except asyncio.CancelledError:
            logger.warning(
                f"UI process task '{task_id}' was cancelled by the user (e.g., via stop button)."
            )
            if process:
                process.kill()  # Ensure it's killed if the managing task is cancelled.
            # The fail_download will be handled by the stop_ui method logic
            raise
        except Exception as e:
            logger.error(f"Error in UI process task '{task_id}': {e}", exc_info=True)
            await download_tracker.fail_download(task_id, f"ERROR: {e}")
        finally:
            # Clean up state regardless of how the process ended.
            self.running_processes.pop(task_id, None)
            if ui_name in self.running_ui_tasks and self.running_ui_tasks[ui_name] == task_id:
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
        except asyncio.TimeoutError:
            logger.warning(f"Process {process.pid} did not terminate gracefully. Killing.")
            process.kill()
        except Exception as e:
            logger.error(f"Error terminating process {process.pid}: {e}", exc_info=True)
            process.kill()  # Force kill on error

    async def validate_ui_path(self, path_str: str) -> Dict[str, Any]:
        """Validates if a given path points to a known and valid UI installation."""
        try:
            path = pathlib.Path(path_str).resolve(strict=True)
            ui_name, error = await ui_operator.validate_git_repo(path)
            if error:
                return {"success": False, "error": error}
            return {"success": True, "ui_name": ui_name}
        except FileNotFoundError:
            return {"success": False, "error": "The specified path does not exist."}
        except Exception as e:
            logger.error(f"Unexpected error during path validation: {e}", exc_info=True)
            return {"success": False, "error": "An unexpected server error occurred."}

    async def adopt_ui_environment(
        self, ui_name: UiNameType, path_str: str, should_backup: bool, task_id: str
    ):
        """Manages the full adoption process for an existing UI installation."""
        try:
            await download_tracker.update_task_progress(
                task_id, 0, f"Starting adoption for {ui_name}..."
            )
            path = pathlib.Path(path_str)
            streamer = lambda line: self._stream_progress_to_tracker(task_id, line)

            # --- Backup Step (if selected) ---
            backup_path = None
            if should_backup:
                await download_tracker.update_task_progress(task_id, 10, f"Backing up {ui_name}...")
                backup_path = await ui_operator.backup_ui_environment(path, streamer)
                if not backup_path:
                    raise RuntimeError("Backup process failed. Aborting adoption.")
                await download_tracker.update_task_progress(task_id, 40, "Backup complete.")
            else:
                await download_tracker.update_task_progress(task_id, 40, "Skipping backup.")

            # --- Configuration Step ---
            await download_tracker.update_task_progress(
                task_id, 50, f"Registering '{ui_name}' in configuration..."
            )
            success, msg = self.config.add_adopted_ui_path(ui_name, str(path))
            if not success:
                raise RuntimeError(f"Failed to update configuration: {msg}")
            await streamer("Configuration updated successfully.")

            # --- NEW: Dependency Repair Step ---
            await download_tracker.update_task_progress(
                task_id, 60, "Verifying and repairing dependencies..."
            )
            ui_info = await self._get_ui_info(ui_name, task_id)
            if not ui_info or not ui_info.get("requirements_file"):
                raise RuntimeError(
                    f"No requirements file defined for {ui_name}, cannot repair environment."
                )

            req_file = ui_info["requirements_file"]
            if not await ui_installer.install_dependencies(path, req_file, streamer):
                # This is a non-fatal error. The UI is adopted, but we must warn the user.
                await streamer(
                    f"WARNING: Could not install/verify dependencies from {req_file}. The UI may not start correctly."
                )
            else:
                await streamer("Dependencies verified successfully.")

            # --- Finalization ---
            await download_tracker.update_task_progress(task_id, 95, "Finalizing adoption...")
            final_message = f"Successfully adopted and verified {ui_name}."
            if backup_path:
                final_message += f" Backup created at: {backup_path}"

            await download_tracker.complete_download(task_id, final_message)

        except Exception as e:
            error_message = f"Adoption failed for {ui_name}: {e}"
            logger.error(error_message, exc_info=True)
            await download_tracker.fail_download(task_id, error_message)
