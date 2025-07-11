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
    Manages the lifecycle of UI environments, including installation, execution,
    and removal, operating on specified paths.
    """

    def __init__(self, broadcast_callback: Optional[BroadcastCallable] = None):
        """
        Initializes the UiManager.

        Args:
            broadcast_callback: An optional async function to broadcast real-time
                                status updates, typically to a WebSocket.
        """
        self.broadcast_callback = broadcast_callback
        self.running_processes: Dict[str, asyncio.subprocess.Process] = {}
        self.running_ui_tasks: Dict[UiNameType, str] = {}
        logger.info("UiManager initialized.")

    async def get_all_statuses(
        self, managed_ui_paths: Dict[UiNameType, pathlib.Path]
    ) -> List[ManagedUiStatus]:
        """
        Retrieves the current status for all UIs based on provided paths.

        Args:
            managed_ui_paths: A dictionary mapping UI names to their installation paths.
        """
        statuses: List[ManagedUiStatus] = []
        for ui_name, install_path in managed_ui_paths.items():
            is_installed = install_path.is_dir()
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
        """A helper to retrieve UI metadata and handle unknown UI names."""
        ui_info = UI_REPOSITORIES.get(ui_name)
        if not ui_info:
            logger.error(f"Unknown UI '{ui_name}'. Cannot proceed.")
            await download_tracker.fail_download(
                task_id, f"Unknown UI '{ui_name}'. Action aborted."
            )
        return ui_info

    async def _stream_progress_to_tracker(self, task_id: str, line: str):
        """Streams log lines from subprocesses to the frontend via the tracker."""
        if self.broadcast_callback:
            await self.broadcast_callback({"type": "log", "task_id": task_id, "message": line})

    async def install_ui_environment(
        self, ui_name: UiNameType, install_path: pathlib.Path, task_id: str
    ):
        """
        Orchestrates the complete installation of a UI environment into a
        specified target directory.
        """
        ui_info = await self._get_ui_info(ui_name, task_id)
        if not ui_info:
            return

        git_url = ui_info["git_url"]
        req_file = ui_info.get("requirements_file")

        if not req_file:
            msg = f"Installation failed: 'requirements_file' not defined for {ui_name}."
            logger.error(msg)
            await download_tracker.fail_download(task_id, msg)
            return

        # Define progress milestones for a smoother UI experience.
        CLONE_END, VENV_END = 15.0, 25.0
        COLLECT_START, COLLECT_END = 25.0, 70.0
        INSTALL_START, INSTALL_END = 70.0, 95.0
        COLLECT_RANGE = COLLECT_END - COLLECT_START
        INSTALL_RANGE = INSTALL_END - INSTALL_START

        try:
            streamer = lambda line: self._stream_progress_to_tracker(task_id, line)

            await download_tracker.update_task_progress(task_id, 0, f"Cloning {ui_name}...")
            if not await ui_installer.clone_repo(git_url, install_path, streamer):
                raise RuntimeError(f"Failed to clone repository for {ui_name}.")

            await download_tracker.update_task_progress(
                task_id, CLONE_END, "Creating virtual environment..."
            )
            if not await ui_installer.create_venv(install_path, streamer):
                raise RuntimeError(f"Failed to create venv for {ui_name}.")

            async def pip_progress_updater(
                phase: ui_installer.PipPhase, current: int, total: int, status_text: str
            ):
                """Callback to translate pip output into smooth progress bar updates."""
                if phase == "collecting":
                    estimated_total = total * 3 if total > 0 else 1
                    fraction = min(current / estimated_total, 1.0)
                    progress = COLLECT_START + (fraction * COLLECT_RANGE)
                    await download_tracker.update_task_progress(
                        task_id, progress, f"Collecting: {status_text}"
                    )
                elif phase == "installing":
                    fraction = current / total if total > 0 else 0
                    progress = INSTALL_START + (fraction * INSTALL_RANGE)
                    await download_tracker.update_task_progress(task_id, progress, status_text)

            await download_tracker.update_task_progress(
                task_id, VENV_END, "Resolving dependencies..."
            )
            if not await ui_installer.install_dependencies(
                install_path, req_file, streamer, pip_progress_updater
            ):
                raise RuntimeError(f"Failed to install dependencies for {ui_name}.")

            await download_tracker.update_task_progress(
                task_id, INSTALL_END, "Finalizing installation..."
            )
            await download_tracker.complete_download(task_id, str(install_path))

        except Exception as e:
            error_message = f"Installation failed for {ui_name}: {e}"
            logger.error(error_message, exc_info=True)
            await download_tracker.fail_download(task_id, error_message)

    async def delete_environment(self, install_path: pathlib.Path) -> bool:
        """Deletes the UI environment directory at the specified path."""
        return await ui_operator.delete_ui_environment(install_path)

    def run_ui(self, ui_name: UiNameType, install_path: pathlib.Path, task_id: str):
        """Creates a background task to start and manage a UI process from a given path."""
        download_tracker.start_tracking(
            download_id=task_id,
            repo_id="UI Process",
            filename=ui_name,
            task=asyncio.create_task(self._run_and_manage_process(ui_name, install_path, task_id)),
        )

    async def _run_and_manage_process(
        self, ui_name: UiNameType, install_path: pathlib.Path, task_id: str
    ):
        """The core async method that runs a UI process and tracks its lifecycle."""
        process = None
        try:
            ui_info = await self._get_ui_info(ui_name, task_id)
            if not ui_info:
                return

            if not install_path.is_dir():
                raise RuntimeError(f"Installation directory for {ui_name} not found.")

            start_script = ui_info.get("start_script")
            if not start_script:
                raise RuntimeError(f"No 'start_script' defined for {ui_name}.")

            process, error_msg = await ui_operator.run_ui(install_path, start_script)
            if not process:
                raise RuntimeError(error_msg or "UI process failed to start.")

            self.running_processes[task_id] = process
            self.running_ui_tasks[ui_name] = task_id
            await download_tracker.update_task_progress(
                task_id, 5, status_text="Process is running...", new_status="running"
            )

            await process.wait()
            return_code = process.returncode

            if return_code == 0:
                await download_tracker.complete_download(task_id, f"{ui_name} finished.")
            else:
                await download_tracker.fail_download(
                    task_id, f"{ui_name} exited with code {return_code}."
                )
        except Exception as e:
            await download_tracker.fail_download(task_id, str(e))
        finally:
            self.running_processes.pop(task_id, None)
            if self.running_ui_tasks.get(ui_name) == task_id:
                self.running_ui_tasks.pop(ui_name, None)

    async def stop_ui(self, task_id: str):
        """Stops a running UI process by its task ID."""
        process = self.running_processes.get(task_id)
        if not process:
            return

        try:
            logger.info(f"Terminating process {process.pid} for task {task_id}.")
            process.terminate()
            await asyncio.wait_for(process.wait(), timeout=10)
        except asyncio.TimeoutError:
            logger.warning(f"Process {process.pid} did not terminate gracefully. Killing.")
            process.kill()
