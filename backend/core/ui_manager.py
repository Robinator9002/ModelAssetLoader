# backend/core/ui_manager.py
import asyncio
import logging
import pathlib
from typing import Optional, Dict, List

from .constants.constants import UI_REPOSITORIES, UiNameType
from .ui_management import ui_installer, ui_operator

# --- NEW IMPORT ---
# We now import the UiRegistry to manage persistent storage of install paths.
from .ui_management.ui_registry import UiRegistry
from .file_management.download_tracker import download_tracker, BroadcastCallable
from backend.api.models import ManagedUiStatus

logger = logging.getLogger(__name__)


class UiManager:
    """
    Manages the lifecycle of UI environments by coordinating with the UI Registry
    for path information and operators for execution.
    """

    def __init__(self, broadcast_callback: Optional[BroadcastCallable] = None):
        """Initializes the UiManager and its connection to the UI Registry."""
        self.broadcast_callback = broadcast_callback
        self.running_processes: Dict[str, asyncio.subprocess.Process] = {}
        self.running_ui_tasks: Dict[UiNameType, str] = {}
        # --- NEW: Instantiate the registry ---
        # The UiManager now has a direct line to our persistent storage.
        self.registry = UiRegistry()
        logger.info("UiManager initialized and connected to UI Registry.")

    async def get_all_statuses(self) -> List[ManagedUiStatus]:
        """
        Retrieves the current status for all UIs based on the registry,
        making it the single source of truth.
        """
        statuses: List[ManagedUiStatus] = []
        # --- MODIFIED: Get all known paths directly from the registry ---
        registered_paths = self.registry.get_all_paths()

        # We check the status of every UI the registry knows about.
        for ui_name, install_path in registered_paths.items():
            is_installed = install_path.is_dir()
            running_task_id = self.running_ui_tasks.get(ui_name)
            is_running = running_task_id is not None

            # If a directory was deleted manually, we should unregister it.
            if not is_installed:
                logger.warning(
                    f"Installation for '{ui_name}' at '{install_path}' not found. Unregistering."
                )
                self.registry.remove_installation(ui_name)
                continue

            statuses.append(
                ManagedUiStatus(
                    ui_name=ui_name,
                    is_installed=is_installed,
                    is_running=is_running,
                    install_path=str(install_path),
                    running_task_id=running_task_id,
                )
            )
        return statuses

    async def _get_ui_info(self, ui_name: UiNameType, task_id: str) -> Optional[dict]:
        """Helper to retrieve UI metadata from constants."""
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
        Orchestrates the installation and, on success, registers the new path.
        """
        ui_info = await self._get_ui_info(ui_name, task_id)
        if not ui_info:
            return

        git_url = ui_info["git_url"]
        req_file = ui_info.get("requirements_file")
        extra_packages = ui_info.get("extra_packages")

        if not req_file:
            msg = f"Installation failed: 'requirements_file' not defined for {ui_name}."
            logger.error(msg)
            await download_tracker.fail_download(task_id, msg)
            return

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
                if phase == "collecting":
                    estimated_total = total * 2 if total > 0 else 1
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
                install_path, req_file, streamer, pip_progress_updater, extra_packages
            ):
                raise RuntimeError(f"Failed to install dependencies for {ui_name}.")

            await download_tracker.update_task_progress(
                task_id, INSTALL_END, "Finalizing installation..."
            )

            # --- MODIFIED: Register the installation on success ---
            # This is the crucial step that records the custom path.
            self.registry.add_installation(ui_name, install_path)
            await download_tracker.complete_download(task_id, str(install_path))

        except Exception as e:
            error_message = f"Installation failed for {ui_name}: {e}"
            logger.error(error_message, exc_info=True)
            await download_tracker.fail_download(task_id, error_message)

    async def delete_environment(self, ui_name: UiNameType) -> bool:
        """Deletes the UI environment folder and removes it from the registry."""
        install_path = self.registry.get_path(ui_name)
        if not install_path:
            logger.warning(f"Cannot delete '{ui_name}', not found in registry.")
            return False

        if await ui_operator.delete_ui_environment(install_path):
            # --- MODIFIED: Unregister on successful deletion ---
            self.registry.remove_installation(ui_name)
            return True
        return False

    def run_ui(self, ui_name: UiNameType, task_id: str):
        """Starts a UI process using its registered path."""
        # --- MODIFIED: Get the path from the registry ---
        install_path = self.registry.get_path(ui_name)
        if not install_path or not install_path.exists():
            # Fail fast if the UI is registered but the path is gone.
            async def fail_task():
                error_msg = f"Installation path for {ui_name} not found or is invalid."
                logger.error(error_msg)
                await download_tracker.fail_download(task_id, error_msg)

            download_tracker.start_tracking(
                download_id=task_id,
                repo_id="UI Process",
                filename=ui_name,
                task=asyncio.create_task(fail_task()),
            )
            return

        # The rest of the function proceeds as before, now with a reliable path.
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

            output_lines = []

            async def read_stream(stream, stream_name):
                while not stream.at_eof():
                    try:
                        line_bytes = await stream.readline()
                        if not line_bytes:
                            break
                        line = line_bytes.decode("utf-8", errors="replace").strip()
                        if line:
                            logger.info(f"[{ui_name}:{stream_name}] {line}")
                            await self._stream_progress_to_tracker(task_id, line)
                            output_lines.append(line)
                    except Exception as e:
                        logger.warning(f"Error reading stream from {ui_name}: {e}")
                        break

            await asyncio.gather(
                read_stream(process.stdout, "stdout"),
                read_stream(process.stderr, "stderr"),
            )

            await process.wait()
            return_code = process.returncode

            if return_code == 0:
                await download_tracker.complete_download(task_id, f"{ui_name} finished.")
            else:
                combined_output = "\n".join(output_lines)
                error_message = f"{ui_name} exited with code {return_code}."
                logger.error(f"{error_message} Full Output:\n{combined_output}")
                await download_tracker.fail_download(
                    task_id, f"{error_message} Check backend logs for details."
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
