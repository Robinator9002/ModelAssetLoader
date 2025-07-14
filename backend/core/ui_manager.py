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
    if size_bytes == 0:
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
        self.installation_processes: Dict[str, asyncio.subprocess.Process] = {}
        self.running_ui_tasks: Dict[UiNameType, str] = {}
        self.registry = UiRegistry()
        logger.info("UiManager initialized and connected to UI Registry.")

    async def _stream_process_output(
        self,
        process: asyncio.subprocess.Process,
        task_id: str,
    ):
        """
        Reads stdout and stderr from a process, streams it for logging, and waits for completion.
        This method is internal to the UiManager, giving it full control over managed processes.
        """

        async def read_stream(stream, stream_name):
            while not stream.at_eof():
                try:
                    line_bytes = await stream.readline()
                    if not line_bytes:
                        break
                    line = line_bytes.decode("utf-8", errors="replace").strip()
                    if line:
                        logger.debug(f"[{task_id}:{stream_name}] {line}")
                except Exception as e:
                    logger.warning(f"Error reading stream line from process {process.pid}: {e}")
                    break

        # Asynchronously read from both stdout and stderr.
        await asyncio.gather(
            read_stream(process.stdout, "stdout"), read_stream(process.stderr, "stderr")
        )
        await process.wait()

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
        and human-readable status for the frontend.
        """
        collecting_start_progress = 25.0
        collecting_range = 50.0
        installing_start_progress = collecting_start_progress + collecting_range
        installing_range = 15.0
        current_progress = 0.0
        status_text = ""

        if phase == "collecting":
            if total == -1:
                phase_progress = collecting_range * (1 - 1 / (processed + 1))
                current_progress = collecting_start_progress + phase_progress
                status_text = item_name
            else:
                phase_percent = (processed / total) * collecting_range if total > 0 else 0
                current_progress = collecting_start_progress + phase_percent
                size_str = f"({_format_bytes(item_size)})"
                status_text = f"Collecting: {item_name} {size_str}".strip()

        elif phase == "installing":
            phase_percent = (processed / total) * installing_range if total > 0 else 0
            current_progress = installing_start_progress + phase_percent
            status_text = item_name

        final_dependencies_progress = installing_start_progress + installing_range
        current_progress = min(current_progress, final_dependencies_progress)

        await download_tracker.update_task_progress(
            task_id, progress=current_progress, status_text=status_text
        )

    async def get_all_statuses(self) -> List[ManagedUiStatus]:
        """Retrieves the current status for all registered UI environments."""
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
        """Orchestrates the complete installation of a new UI environment."""
        await asyncio.sleep(0.5)
        ui_info = await self._get_ui_info(ui_name, task_id)
        if not ui_info:
            return

        def process_created_cb(process: asyncio.subprocess.Process):
            self.installation_processes[task_id] = process

        try:
            streamer = lambda line: logger.debug(f"[{task_id}] STREAM: {line}")
            pip_progress_cb = self._pip_progress_callback

            await download_tracker.update_task_progress(task_id, 0, f"Cloning {ui_name}...")
            await ui_installer.clone_repo(ui_info["git_url"], install_path, streamer)

            await download_tracker.update_task_progress(
                task_id, 15.0, "Creating virtual environment..."
            )
            if not await ui_installer.create_venv(install_path, streamer):
                raise RuntimeError(f"Failed to create venv for {ui_name}.")

            await download_tracker.update_task_progress(task_id, 25.0, "Analyzing dependencies...")
            dependencies_installed = await ui_installer.install_dependencies(
                install_path,
                ui_info["requirements_file"],
                stream_callback=streamer,
                progress_callback=lambda *args: pip_progress_cb(task_id, *args),
                extra_packages=ui_info.get("extra_packages"),
                process_created_callback=process_created_cb,
            )
            if not dependencies_installed:
                raise RuntimeError(f"Failed to install dependencies for {ui_name}.")

            await download_tracker.update_task_progress(task_id, 90.0, "Finalizing installation...")
            self.registry.add_installation(ui_name, install_path)
            await download_tracker.complete_download(task_id, f"Successfully installed {ui_name}.")
        except asyncio.CancelledError:
            await download_tracker.fail_download(task_id, "Installation was cancelled by user.")
        except Exception as e:
            await download_tracker.fail_download(task_id, f"Installation failed: {e}")
        finally:
            if task_id in self.installation_processes:
                del self.installation_processes[task_id]

    def run_ui(self, ui_name: UiNameType, task_id: str):
        """Starts a registered UI environment as a background process."""
        install_path = self.registry.get_path(ui_name)
        if not install_path or not install_path.exists():
            self._fail_task_fast(task_id, ui_name, f"Installation path for {ui_name} not found.")
            return

        task = asyncio.create_task(self._run_and_manage_process(ui_name, install_path, task_id))
        download_tracker.start_tracking(task_id, "UI Process", ui_name, task)

    async def stop_ui(self, task_id: str):
        """Stops a running UI process by its task ID."""
        process = self.running_processes.get(task_id)
        if not process:
            return
        try:
            process.terminate()
            await asyncio.wait_for(process.wait(), timeout=10)
        except asyncio.TimeoutError:
            process.kill()

    async def cancel_ui_task(self, task_id: str):
        """Cancels a running UI installation or repair task."""
        process = self.installation_processes.get(task_id)
        if process:
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()
        else:
            await download_tracker.cancel_and_remove(task_id)

    async def delete_environment(self, ui_name: UiNameType) -> bool:
        """Deletes a UI environment's directory and removes it from the registry."""
        install_path = self.registry.get_path(ui_name)
        if not install_path:
            return False
        if await ui_operator.delete_ui_environment(install_path):
            self.registry.remove_installation(ui_name)
            return True
        return False

    async def analyze_adoption_candidate(
        self, ui_name: UiNameType, path: pathlib.Path
    ) -> AdoptionAnalysisResult:
        """Analyzes a directory to determine if it's a valid, adoptable UI installation."""
        adopter = UiAdopter(ui_name, path)
        return await adopter.analyze()

    def repair_and_adopt_ui(
        self, ui_name: UiNameType, path: pathlib.Path, issues_to_fix: List[str], task_id: str
    ):
        """Creates a background task to repair a UI environment and then adopt it."""
        task = asyncio.create_task(self._run_repair_process(ui_name, path, issues_to_fix, task_id))
        download_tracker.start_tracking(task_id, "UI Adoption Repair", ui_name, task)

    def finalize_adoption(self, ui_name: UiNameType, path: pathlib.Path) -> bool:
        """Directly adopts a UI by adding it to the registry without repairs."""
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
        ui_info = await self._get_ui_info(ui_name, task_id)
        if not ui_info:
            return

        def process_created_cb(process: asyncio.subprocess.Process):
            self.installation_processes[task_id] = process

        try:
            streamer = lambda line: logger.debug(f"[{task_id}] STREAM: {line}")
            pip_progress_cb = self._pip_progress_callback

            if "VENV_MISSING" in issues_to_fix:
                await download_tracker.update_task_progress(
                    task_id, 10, "Creating virtual environment..."
                )
                if not await ui_installer.create_venv(path, streamer):
                    raise RuntimeError("Failed to create virtual environment.")

            if any(
                code in issues_to_fix
                for code in ["VENV_DEPS_INCOMPLETE", "VENV_INCOMPLETE", "VENV_MISSING"]
            ):
                await download_tracker.update_task_progress(
                    task_id, 50, "Installing dependencies..."
                )
                dependencies_installed = await ui_installer.install_dependencies(
                    path,
                    ui_info["requirements_file"],
                    stream_callback=streamer,
                    progress_callback=lambda *args: pip_progress_cb(task_id, *args),
                    extra_packages=ui_info.get("extra_packages"),
                    process_created_callback=process_created_cb,
                )
                if not dependencies_installed:
                    raise RuntimeError("Failed to install dependencies.")

            await download_tracker.update_task_progress(task_id, 95, "Finalizing adoption...")
            self.registry.add_installation(ui_name, path)
            await download_tracker.complete_download(
                task_id, f"Successfully repaired and adopted {ui_name}."
            )
        except asyncio.CancelledError:
            await download_tracker.fail_download(task_id, "Repair was cancelled by user.")
        except Exception as e:
            await download_tracker.fail_download(task_id, f"Repair process failed: {e}")
        finally:
            if task_id in self.installation_processes:
                del self.installation_processes[task_id]

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
                task_id, 5, "Process is running...", "running"
            )

            await self._stream_process_output(process, task_id)

            if process.returncode == 0:
                await download_tracker.complete_download(task_id, f"{ui_name} finished.")
            else:
                await download_tracker.fail_download(
                    task_id, f"{ui_name} exited with code {process.returncode}."
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
        task = asyncio.create_task(download_tracker.fail_download(task_id, message))
        download_tracker.start_tracking(task_id, "UI Process", ui_name, task)
