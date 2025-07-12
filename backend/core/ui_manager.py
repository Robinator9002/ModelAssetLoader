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
        Helper method to stream text updates to the download tracker for a given task.
        This keeps the frontend informed of detailed progress without changing the
        overall percentage progress bar.
        """
        if task_id in download_tracker.active_downloads:
            status = download_tracker.active_downloads[task_id]
            # We only update the status text, preserving the last known progress percentage.
            await download_tracker.update_task_progress(
                task_id,
                progress=status.progress,
                status_text=line,
            )

    async def get_all_statuses(self) -> List[ManagedUiStatus]:
        """
        Retrieves the current status for all registered UI environments.

        This method acts as the single source of truth for the state of all UIs
        known to the application. It performs a health check and will automatically
        unregister any installations whose directories have been manually deleted.

        Returns:
            A list of ManagedUiStatus objects representing each registered UI.
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

        This process involves cloning the repository, creating a virtual environment,
        installing dependencies, and finally registering the installation.

        Args:
            ui_name: The name of the UI to install.
            install_path: The target directory for the installation.
            task_id: The unique ID for tracking this task.
        """
        ui_info = await self._get_ui_info(ui_name, task_id)
        if not ui_info:
            return

        try:
            # Correctly define the streamer to use the new helper method
            streamer = lambda line: self._stream_progress_to_tracker(task_id, line)

            await download_tracker.update_task_progress(task_id, 0, f"Cloning {ui_name}...")
            if not await ui_installer.clone_repo(ui_info["git_url"], install_path, streamer):
                raise RuntimeError(f"Failed to clone repository for {ui_name}.")

            await download_tracker.update_task_progress(
                task_id, 15.0, "Creating virtual environment..."
            )
            if not await ui_installer.create_venv(install_path, streamer):
                raise RuntimeError(f"Failed to create venv for {ui_name}.")

            await download_tracker.update_task_progress(task_id, 25.0, "Installing dependencies...")
            if not await ui_installer.install_dependencies(
                install_path,
                ui_info["requirements_file"],
                streamer,
                extra_packages=ui_info.get("extra_packages"),
            ):
                raise RuntimeError(f"Failed to install dependencies for {ui_name}.")

            await download_tracker.update_task_progress(task_id, 95.0, "Finalizing installation...")
            self.registry.add_installation(ui_name, install_path)
            await download_tracker.complete_download(task_id, str(install_path))

        except Exception as e:
            error_message = f"Installation failed for {ui_name}: {e}"
            logger.error(error_message, exc_info=True)
            await download_tracker.fail_download(task_id, error_message)

    def run_ui(self, ui_name: UiNameType, task_id: str):
        """
        Starts a registered UI environment as a background process.

        Args:
            ui_name: The name of the UI to run.
            task_id: The unique ID for tracking this task.
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

        Args:
            task_id: The ID of the running task to terminate.
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

        Args:
            ui_name: The name of the UI to delete.

        Returns:
            True if deletion was successful, False otherwise.
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

        Args:
            ui_name: The type of UI to check for.
            path: The path to the directory to analyze.

        Returns:
            An AdoptionAnalysisResult dictionary with the findings.
        """
        adopter = UiAdopter(ui_name, path)
        return adopter.analyze()

    def repair_and_adopt_ui(
        self, ui_name: UiNameType, path: pathlib.Path, issues_to_fix: List[str], task_id: str
    ):
        """
        Creates a background task to repair a UI environment and then adopt it.

        Args:
            ui_name: The name of the UI being repaired.
            path: The path to the UI installation.
            issues_to_fix: A list of issue codes to be addressed.
            task_id: The unique ID for tracking this repair task.
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

        Args:
            ui_name: The name of the UI to adopt.
            path: The path to the UI installation.

        Returns:
            True if adoption was successful, False otherwise.
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
                    streamer,
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
