# backend/core/ui_manager.py
import asyncio
import logging
import pathlib
from typing import Optional, Dict, List

from backend.api.models import ManagedUiStatus
from backend.core.constants.constants import UI_REPOSITORIES, UiNameType
from backend.core.file_management.download_tracker import download_tracker, BroadcastCallable
from backend.core.ui_management import ui_installer, ui_operator
from backend.core.ui_management.ui_adopter import UiAdopter, AdoptionAnalysisResult
from backend.core.ui_management.ui_registry import UiRegistry


logger = logging.getLogger(__name__)


def _format_bytes(size_bytes: int) -> str:
    """Formats a size in bytes to a human-readable string (KB, MB, GB)."""
    if size_bytes is None:
        return ""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024**2:
        return f"{size_bytes/1024:.1f} KB"
    if size_bytes < 1024**3:
        return f"{size_bytes/1024**2:.1f} MB"
    return f"{size_bytes/1024**3:.2f} GB"


class UiManager:
    """
    Manages the lifecycle of UI environments.

    This class serves as the central orchestrator for installing, running, deleting,
    and adopting UI environments. It coordinates with the UiRegistry for path
    persistence and delegates specific tasks to operators and installers.
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
        self.registry = UiRegistry()
        logger.info("UiManager initialized and connected to UI Registry.")

    async def _stream_progress_to_tracker(self, task_id: str, line: str):
        """
        Helper method to stream raw text updates for detailed logging, without
        affecting the main progress bar or status text.
        """
        logger.debug(f"[{task_id}] STREAM: {line}")

    async def _pip_progress_callback(
        self,
        task_id: str,
        phase: ui_installer.PipPhase,
        processed: int,
        total: int,
        item_name: str,
        item_size: Optional[int],
    ):
        """
        Translates structured progress from the pip installer into a percentage
        and human-readable status for the frontend. This provides a granular,
        two-phase progress update for both collecting and installing dependencies.
        """
        # The overall installation is mapped to a 0-100% scale.
        # We allocate percentages to each major step:
        # 0-15%:    Cloning repository
        # 15-25%:   Creating virtual environment
        # 25-75%:   Collecting dependencies (downloading) (50 percentage points)
        # 75-90%:   Installing dependencies (from cache) (15 percentage points)
        # 90-100%:  Finalizing
        collecting_start_progress = 25.0
        collecting_range = 50.0

        installing_start_progress = collecting_start_progress + collecting_range  # 75.0
        installing_range = 15.0

        current_progress = 0.0
        status_text = ""

        if phase == "collecting":
            # The 'collecting' phase progress is now weighted by download size.
            # 'processed' is the cumulative bytes downloaded, 'total' is the total bytes.
            phase_percent = (processed / total) * collecting_range if total > 0 else 0
            current_progress = collecting_start_progress + phase_percent

            size_str = (
                f"({_format_bytes(item_size)})" if item_size is not None and item_size > 0 else ""
            )
            status_text = f"Collecting: {item_name} {size_str}".strip()

        elif phase == "installing":
            # The 'installing' phase is a simple, count-based simulation after downloads are complete.
            phase_percent = (processed / total) * installing_range if total > 0 else 0
            current_progress = installing_start_progress + phase_percent
            status_text = item_name

        # Clamp progress to the maximum allocated for the dependencies phase.
        final_dependencies_progress = installing_start_progress + installing_range  # 90.0
        current_progress = min(current_progress, final_dependencies_progress)

        await download_tracker.update_task_progress(
            task_id, progress=current_progress, status_text=status_text
        )

    async def get_all_statuses(self) -> List[ManagedUiStatus]:
        """
        Retrieves the current status for all registered UI environments.
        """
        statuses: List[ManagedUiStatus] = []
        registered_paths = self.registry.get_all_paths()

        for ui_name, install_path in registered_paths.items():
            is_installed = install_path.is_dir()
            running_task_id = self.running_ui_tasks.get(ui_name)
            is_running = running_task_id is not None

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

    async def install_ui_environment(
        self, ui_name: UiNameType, install_path: pathlib.Path, task_id: str
    ):
        """
        Orchestrates the complete installation of a new UI environment.
        """
        await asyncio.sleep(0.5)

        ui_info = await self._get_ui_info(ui_name, task_id)
        if not ui_info:
            return

        try:
            streamer = lambda line: self._stream_progress_to_tracker(task_id, line)
            # The callback now expects the item_size argument.
            pip_progress_cb = (
                lambda phase, processed, total, name, size: self._pip_progress_callback(
                    task_id, phase, processed, total, name, size
                )
            )

            await download_tracker.update_task_progress(task_id, 0, f"Cloning {ui_name}...")
            if not await ui_installer.clone_repo(ui_info["git_url"], install_path, streamer):
                logger.warning(f"Could not clone {ui_name}, but proceeding as it may exist.")

            await download_tracker.update_task_progress(
                task_id, 15.0, "Creating virtual environment..."
            )
            if not await ui_installer.create_venv(install_path, streamer):
                raise RuntimeError(f"Failed to create venv for {ui_name}.")

            await download_tracker.update_task_progress(task_id, 25.0, "Analyzing dependencies...")
            if not await ui_installer.install_dependencies(
                install_path,
                ui_info["requirements_file"],
                stream_callback=streamer,
                progress_callback=pip_progress_cb,
                extra_packages=ui_info.get("extra_packages"),
            ):
                raise RuntimeError(f"Failed to install dependencies for {ui_name}.")

            await download_tracker.update_task_progress(task_id, 90.0, "Finalizing installation...")
            self.registry.add_installation(ui_name, install_path)
            await download_tracker.complete_download(task_id, f"Successfully installed {ui_name}.")

        except Exception as e:
            error_message = f"Installation failed for {ui_name}: {e}"
            logger.error(error_message, exc_info=True)
            await download_tracker.fail_download(task_id, error_message)

    def run_ui(self, ui_name: UiNameType, task_id: str):
        """
        Starts a registered UI environment as a background process.
        """
        install_path = self.registry.get_path(ui_name)
        if not install_path or not install_path.exists():
            self._fail_task_fast(
                task_id, ui_name, f"Installation path for {ui_name} not found or is invalid."
            )
            return

        download_tracker.start_tracking(
            download_id=task_id,
            repo_id="UI Process",
            filename=ui_name,
            task=asyncio.create_task(self._run_and_manage_process(ui_name, install_path, task_id)),
        )

    async def stop_ui(self, task_id: str):
        """
        Stops a running UI process by its task ID.
        """
        process = self.running_processes.get(task_id)
        if not process:
            return

        logger.info(f"Terminating process {process.pid} for task {task_id}.")
        try:
            process.terminate()
            await asyncio.wait_for(process.wait(), timeout=10)
        except asyncio.TimeoutError:
            logger.warning(f"Process {process.pid} did not terminate gracefully. Killing.")
            process.kill()

    async def delete_environment(self, ui_name: UiNameType) -> bool:
        """
        Deletes a UI environment's directory and removes it from the registry.
        """
        install_path = self.registry.get_path(ui_name)
        if not install_path:
            logger.warning(f"Cannot delete '{ui_name}', not found in registry.")
            return False

        if await ui_operator.delete_ui_environment(install_path):
            self.registry.remove_installation(ui_name)
            return True
        return False

    def analyze_adoption_candidate(
        self, ui_name: UiNameType, path: pathlib.Path
    ) -> AdoptionAnalysisResult:
        """
        Analyzes a directory to determine if it's a valid, adoptable UI installation.
        """
        adopter = UiAdopter(ui_name, path)
        return adopter.analyze()

    def repair_and_adopt_ui(
        self, ui_name: UiNameType, path: pathlib.Path, issues_to_fix: List[str], task_id: str
    ):
        """
        Creates a background task to repair a UI environment and then adopt it.
        """
        download_tracker.start_tracking(
            download_id=task_id,
            repo_id="UI Adoption Repair",
            filename=ui_name,
            task=asyncio.create_task(
                self._run_repair_process(ui_name, path, issues_to_fix, task_id)
            ),
        )

    def finalize_adoption(self, ui_name: UiNameType, path: pathlib.Path) -> bool:
        """
        Directly adopts a UI by adding it to the registry without repairs.
        """
        logger.info(f"Finalizing adoption for '{ui_name}' at '{path}' without repairs.")
        try:
            self.registry.add_installation(ui_name, path)
            return True
        except Exception as e:
            logger.error(f"Failed to finalize adoption for {ui_name}: {e}", exc_info=True)
            return False

    async def _run_repair_process(
        self, ui_name: UiNameType, path: pathlib.Path, issues_to_fix: List[str], task_id: str
    ):
        """The core async method that performs the repair actions."""
        logger.info(f"Starting repair process for '{ui_name}'. Issues: {issues_to_fix}")
        ui_info = await self._get_ui_info(ui_name, task_id)
        if not ui_info:
            return

        try:
            streamer = lambda line: self._stream_progress_to_tracker(task_id, line)
            pip_progress_cb = (
                lambda phase, processed, total, name, size: self._pip_progress_callback(
                    task_id, phase, processed, total, name, size
                )
            )

            if "VENV_MISSING" in issues_to_fix or "VENV_INCOMPLETE" in issues_to_fix:
                await download_tracker.update_task_progress(
                    task_id, 10, "Creating virtual environment..."
                )
                if not await ui_installer.create_venv(path, streamer):
                    raise RuntimeError("Failed to create virtual environment.")

                await download_tracker.update_task_progress(
                    task_id, 50, "Installing dependencies..."
                )
                if not await ui_installer.install_dependencies(
                    path,
                    ui_info["requirements_file"],
                    stream_callback=streamer,
                    progress_callback=pip_progress_cb,
                    extra_packages=ui_info.get("extra_packages"),
                ):
                    raise RuntimeError("Failed to install dependencies.")

            await download_tracker.update_task_progress(task_id, 95, "Finalizing adoption...")
            self.registry.add_installation(ui_name, path)
            await download_tracker.complete_download(
                task_id, f"Successfully repaired and adopted {ui_name}."
            )

        except Exception as e:
            await download_tracker.fail_download(task_id, f"Repair process failed: {e}")

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

            streamer = lambda line: self._stream_progress_to_tracker(task_id, line)
            await ui_operator._stream_process(process, streamer)

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

    async def _get_ui_info(
        self, ui_name: UiNameType, task_id: Optional[str] = None
    ) -> Optional[dict]:
        """Helper to retrieve UI metadata from constants."""
        ui_info = UI_REPOSITORIES.get(ui_name)
        if not ui_info and task_id:
            await self._fail_task_fast(task_id, ui_name, f"Unknown UI '{ui_name}'.")
        return ui_info

    def _fail_task_fast(self, task_id: str, ui_name: UiNameType, message: str):
        """Helper to quickly fail a task that cannot even start."""
        logger.error(message)

        async def fail_task():
            await download_tracker.fail_download(task_id, message)

        download_tracker.start_tracking(
            download_id=task_id,
            repo_id="UI Process",
            filename=ui_name,
            task=asyncio.create_task(fail_task()),
        )
