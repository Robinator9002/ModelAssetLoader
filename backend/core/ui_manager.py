# backend/core/ui_manager.py
import asyncio
import logging
import pathlib
import json
import os
import signal
from typing import Optional, Dict, List, Tuple

from api.models import ManagedUiStatus
from core.constants.constants import UI_REPOSITORIES, UiNameType, CONFIG_FILE_DIR
from core.file_management.download_tracker import download_tracker, BroadcastCallable
from core.ui_management import ui_installer, ui_operator
from core.ui_management.ui_adopter import UiAdopter, AdoptionAnalysisResult
from core.ui_management.ui_registry import UiRegistry

logger = logging.getLogger(__name__)

# --- NEW: Path for the process registry file ---
# This file will store the PIDs of running UI processes to allow for state
# recovery after the application restarts.
PROCESS_REGISTRY_FILE_PATH = CONFIG_FILE_DIR / "process_registry.json"


def _format_bytes(size_bytes: int) -> str:
    """A helper utility to format a size in bytes to a human-readable string."""
    if size_bytes is None or size_bytes == 0:
        return ""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024**2:
        return f"{size_bytes/1024:.1f} KB"
    if size_bytes < 1024**3:
        return f"{size_bytes/1024**2:.1f} MB"
    return f"{size_bytes/1024**3:.2f} GB"


def _is_pid_running(pid: int) -> bool:
    """
    Checks if a process with the given PID is currently running.
    This is a cross-platform way to check for process existence.
    """
    if os.name == "nt":  # Windows
        # Use tasklist command to check for the PID
        try:
            output = asyncio.subprocess.check_output(f'tasklist /FI "PID eq {pid}"').decode()
            return str(pid) in output
        except (asyncio.subprocess.CalledProcessError, FileNotFoundError):
            return False
    else:  # POSIX (Linux, macOS)
        try:
            # os.kill with signal 0 is a standard way to check for process existence
            # without actually sending a signal. It raises PermissionError if the
            # process exists but we can't signal it, and ProcessLookupError if it doesn't.
            os.kill(pid, 0)
        except (ProcessLookupError, PermissionError):
            return False
        else:
            return True


class UiManager:
    """
    Manages the lifecycle of UI environments, acting as the central orchestrator.
    --- REFACTOR: Now includes a persistent process registry. ---
    """

    def __init__(self, broadcast_callback: Optional[BroadcastCallable] = None):
        self.broadcast_callback = broadcast_callback
        # --- REFACTOR: These dictionaries now represent the *live* process state. ---
        self.running_processes: Dict[str, asyncio.subprocess.Process] = {}
        self.installation_processes: Dict[str, asyncio.subprocess.Process] = {}
        # --- REFACTOR: This dictionary is now loaded from and saved to a file. ---
        self.running_ui_tasks: Dict[str, Tuple[UiNameType, int]] = (
            {}
        )  # Maps task_id to (ui_name, pid)
        self.registry = UiRegistry()
        logger.info("UiManager initialized. Loading process registry...")
        self._load_and_reconcile_registry()

    # --- NEW: Methods for process registry persistence ---

    def _load_and_reconcile_registry(self):
        """
        Loads the process registry from the file and reconciles it with the
        currently running processes on the system.
        """
        if not PROCESS_REGISTRY_FILE_PATH.exists():
            logger.info("Process registry not found. Starting with a clean state.")
            return

        try:
            with open(PROCESS_REGISTRY_FILE_PATH, "r") as f:
                persisted_tasks = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error reading process registry: {e}. Starting fresh.", exc_info=True)
            return

        reconciled_tasks = {}
        for task_id, (ui_name, pid) in persisted_tasks.items():
            if _is_pid_running(pid):
                logger.info(
                    f"Reconciling running process: {ui_name} (PID: {pid}, TaskID: {task_id})"
                )
                reconciled_tasks[task_id] = (ui_name, pid)
                # We don't have the process object, so we can't monitor it,
                # but we can at least reflect its running state.
                # A background task is created to mark it as 'running' in the tracker.
                asyncio.create_task(self._reconcile_tracker_status(task_id, ui_name))
            else:
                logger.warning(
                    f"Found stale process in registry for {ui_name} (PID: {pid}). Removing."
                )

        self.running_ui_tasks = reconciled_tasks
        self._save_process_registry()
        logger.info(
            f"Process registry loaded and reconciled. {len(self.running_ui_tasks)} processes are active."
        )

    def _save_process_registry(self):
        """Saves the current state of running UI tasks to the registry file."""
        try:
            CONFIG_FILE_DIR.mkdir(exist_ok=True)
            with open(PROCESS_REGISTRY_FILE_PATH, "w") as f:
                json.dump(self.running_ui_tasks, f, indent=4)
        except IOError as e:
            logger.error(f"Failed to save process registry: {e}", exc_info=True)

    async def _reconcile_tracker_status(self, task_id: str, ui_name: UiNameType):
        """Creates a dummy task in the tracker for a reconciled process."""
        # This task does nothing but hold the place in the UI.
        dummy_task = asyncio.create_task(asyncio.sleep(float("inf")))
        download_tracker.start_tracking(task_id, "UI Process", ui_name, dummy_task)
        await download_tracker.update_task_progress(
            task_id, 5, "Process is running (Reconciled)", "running"
        )

    async def get_all_statuses(self) -> List[ManagedUiStatus]:
        """Retrieves the current status for all registered UI environments."""
        statuses: List[ManagedUiStatus] = []
        # Create a reverse map for quick lookup of running status by ui_name
        running_ui_map = {
            ui_name: task_id for task_id, (ui_name, pid) in self.running_ui_tasks.items()
        }

        for ui_name, install_path in self.registry.get_all_paths().items():
            if not install_path.is_dir():
                logger.warning(
                    f"Installation for '{ui_name}' at '{install_path}' not found. Unregistering."
                )
                self.registry.remove_installation(ui_name)
                continue

            running_task_id = running_ui_map.get(ui_name)
            statuses.append(
                ManagedUiStatus(
                    ui_name=ui_name,
                    is_installed=True,
                    is_running=running_task_id is not None,
                    install_path=str(install_path),
                    running_task_id=running_task_id,
                )
            )
        return statuses

    async def install_ui_environment(
        self, ui_name: UiNameType, install_path: pathlib.Path, task_id: str
    ):
        """Orchestrates the complete, resilient installation of a new UI environment."""
        # ... (rest of the method is unchanged)
        await asyncio.sleep(0.5)
        ui_info = await self._get_ui_info(ui_name, task_id)
        if not ui_info:
            return

        def process_created_cb(process: asyncio.subprocess.Process):
            self.installation_processes[task_id] = process

        async def streamer(line: str):
            logger.debug(f"[{task_id}] {line}")

        try:
            requirements_file_name = ui_info.get("requirements_file")
            if not requirements_file_name:
                raise RuntimeError(f"No 'requirements_file' defined for {ui_name}.")

            await download_tracker.update_task_progress(
                task_id, 0, f"Cloning {ui_name} repository..."
            )
            if not await ui_installer.clone_repo(ui_info["git_url"], install_path, streamer):
                raise RuntimeError("Failed to clone repository.")

            await download_tracker.update_task_progress(
                task_id, 15.0, "Creating virtual environment..."
            )
            if not await ui_installer.create_venv(install_path, streamer):
                raise RuntimeError(f"Failed to create venv for {ui_name}.")

            await download_tracker.update_task_progress(task_id, 25.0, "Installing dependencies...")
            dependencies_installed = await ui_installer.install_dependencies(
                install_path,
                requirements_file_name,
                stream_callback=streamer,
                progress_callback=lambda *args: self._pip_progress_callback(task_id, *args),
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
            logger.error(f"Installation process for {ui_name} failed.", exc_info=True)
            await download_tracker.fail_download(task_id, f"Installation failed: {e}")
        finally:
            self.installation_processes.pop(task_id, None)

    def run_ui(self, ui_name: UiNameType, task_id: str):
        """Starts a registered UI environment as a background task."""
        install_path = self.registry.get_path(ui_name)
        if not install_path or not install_path.exists():
            self._fail_task_fast(task_id, ui_name, f"Installation path for {ui_name} not found.")
            return
        task = asyncio.create_task(self._run_and_manage_process(ui_name, install_path, task_id))
        download_tracker.start_tracking(task_id, "UI Process", ui_name, task)

    async def _run_and_manage_process(
        self, ui_name: UiNameType, install_path: pathlib.Path, task_id: str
    ):
        """The core async method that runs a UI process and tracks its lifecycle."""
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

            # --- REFACTOR: Persist the new running process ---
            self.running_processes[task_id] = process
            self.running_ui_tasks[task_id] = (ui_name, process.pid)
            self._save_process_registry()
            logger.info(f"Registered and saved process for {ui_name} with PID {process.pid}.")

            await download_tracker.update_task_progress(
                task_id, 5, "Process is running...", "running"
            )

            await self._stream_process_output(process, task_id)

            if process.returncode == 0:
                await download_tracker.complete_download(
                    task_id, f"{ui_name} finished successfully."
                )
            else:
                await download_tracker.fail_download(
                    task_id, f"{ui_name} exited with code {process.returncode}."
                )
        except Exception as e:
            await download_tracker.fail_download(task_id, str(e))
        finally:
            # --- REFACTOR: Remove the finished process from state and registry ---
            self.running_processes.pop(task_id, None)
            if task_id in self.running_ui_tasks:
                removed_ui, removed_pid = self.running_ui_tasks.pop(task_id)
                self._save_process_registry()
                logger.info(
                    f"Unregistered and saved process for {removed_ui} with PID {removed_pid}."
                )

    async def stop_ui(self, task_id: str):
        """Stops a running UI process by its task ID."""
        # Check live processes first
        process = self.running_processes.get(task_id)
        if process:
            logger.info(f"Stopping live process for task {task_id} (PID: {process.pid}).")
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=10)
            except asyncio.TimeoutError:
                process.kill()
            # The finally block in _run_and_manage_process will handle registry cleanup
            return

        # If not a live process (i.e., it was reconciled), stop by PID
        if task_id in self.running_ui_tasks:
            ui_name, pid = self.running_ui_tasks[task_id]
            logger.info(f"Stopping reconciled process for {ui_name} (PID: {pid}).")
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                logger.warning(f"Process with PID {pid} not found, already stopped.")
            except Exception as e:
                logger.error(f"Failed to stop process with PID {pid}: {e}", exc_info=True)

            # Manually clean up the tracker and registry
            self.running_ui_tasks.pop(task_id, None)
            self._save_process_registry()
            await download_tracker.complete_download(task_id, f"Stop request sent for {ui_name}.")

    async def cancel_ui_task(self, task_id: str):
        """Cancels a running UI installation or repair task."""
        # ... (method is unchanged)
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
        # ... (method is unchanged)
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
        # ... (method is unchanged)
        adopter = UiAdopter(ui_name, path)
        return await adopter.analyze()

    def repair_and_adopt_ui(
        self, ui_name: UiNameType, path: pathlib.Path, issues_to_fix: List[str], task_id: str
    ):
        """Creates a background task to repair a UI environment and then adopt it."""
        # ... (method is unchanged)
        task = asyncio.create_task(self._run_repair_process(ui_name, path, issues_to_fix, task_id))
        download_tracker.start_tracking(task_id, "UI Adoption Repair", ui_name, task)

    def finalize_adoption(self, ui_name: UiNameType, path: pathlib.Path) -> bool:
        """Directly adopts a UI by adding it to the registry without repairs."""
        # ... (method is unchanged)
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
        # ... (method is unchanged)
        ui_info = await self._get_ui_info(ui_name, task_id)
        if not ui_info:
            return

        def process_created_cb(process: asyncio.subprocess.Process):
            self.installation_processes[task_id] = process

        async def streamer(line: str):
            logger.debug(f"[{task_id}] {line}")

        try:
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
                    streamer,
                    lambda *args: self._pip_progress_callback(task_id, *args),
                    ui_info.get("extra_packages"),
                    process_created_cb,
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
            self.installation_processes.pop(task_id, None)

    async def _pip_progress_callback(
        self,
        task_id: str,
        phase: ui_installer.PipPhase,
        processed: int,
        total: int,
        item_name: str,
        item_size: Optional[int],
    ):
        """Translates structured pip progress into frontend status updates."""
        # ... (method is unchanged)
        collecting_start_progress, collecting_range = 25.0, 50.0
        installing_start_progress, installing_range = 75.0, 15.0
        current_progress, status_text = 0.0, ""

        if phase == "collecting":
            if total == -1:
                phase_progress = collecting_range * (1 - 1 / (processed + 1))
                current_progress = collecting_start_progress + phase_progress
                status_text = item_name
            else:
                phase_percent = (processed / total) * collecting_range if total > 0 else 0
                current_progress = collecting_start_progress + phase_percent
                size_str = f"({_format_bytes(item_size)})" if item_size else ""
                status_text = f"Collecting: {item_name} {size_str}".strip()
        elif phase == "installing":
            phase_percent = (processed / total) * installing_range if total > 0 else 0
            current_progress = installing_start_progress + phase_percent
            status_text = item_name

        await download_tracker.update_task_progress(
            task_id, progress=min(current_progress, 90.0), status_text=status_text
        )

    async def _get_ui_info(
        self, ui_name: UiNameType, task_id: Optional[str] = None
    ) -> Optional[dict]:
        """Helper to retrieve UI metadata from constants."""
        # ... (method is unchanged)
        ui_info = UI_REPOSITORIES.get(ui_name)
        if not ui_info and task_id:
            await self._fail_task_fast(task_id, ui_name, f"Unknown UI '{ui_name}'.")
        return ui_info

    def _fail_task_fast(self, task_id: str, ui_name: UiNameType, message: str):
        """Helper to quickly fail a task that cannot even start."""
        # ... (method is unchanged)
        logger.error(message)
        task = asyncio.create_task(download_tracker.fail_download(task_id, message))
        download_tracker.start_tracking(task_id, "UI Process", ui_name, task)

    async def _stream_process_output(self, process: asyncio.subprocess.Process, task_id: str):
        """Reads and logs process output for debugging purposes."""

        # ... (method is unchanged)
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

        await asyncio.gather(
            read_stream(process.stdout, "stdout"), read_stream(process.stderr, "stderr")
        )
        await process.wait()
