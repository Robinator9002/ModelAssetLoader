# backend/core/ui_management/process_manager.py
import asyncio
import logging
import pathlib
import json
import os
import signal
from typing import Optional, Dict, List, Tuple, Callable

from ..constants.constants import UI_REPOSITORIES, UiNameType, CONFIG_FILE_DIR
from ..file_management.download_tracker import download_tracker
from .ui_registry import UiRegistry
from . import ui_operator

logger = logging.getLogger(__name__)

# --- Constants ---
PROCESS_REGISTRY_FILE_PATH = CONFIG_FILE_DIR / "process_registry.json"

# --- Helper Functions ---


def _is_pid_running(pid: int) -> bool:
    """
    Checks if a process with the given PID is currently running.
    This is a cross-platform way to check for process existence.
    """
    if os.name == "nt":  # Windows
        # Using the 'tasklist' command is a reliable way to check for a PID on Windows.
        try:
            # We run this synchronously as it's a fast operation.
            output = asyncio.subprocess.check_output(f'tasklist /FI "PID eq {pid}"').decode()
            return str(pid) in output
        except (asyncio.subprocess.CalledProcessError, FileNotFoundError):
            return False
    else:  # POSIX (Linux, macOS)
        try:
            # os.kill with signal 0 is the standard POSIX way to check for process existence
            # without sending an actual signal. It raises an error if the process is not found.
            os.kill(pid, 0)
        except (ProcessLookupError, PermissionError):
            return False
        else:
            return True


class ProcessManager:
    """
    Manages the lifecycle and persistent state of running UI processes.

    This class is a specialized component refactored out of the original UiManager.
    Its sole responsibility is to handle the execution (start, stop), tracking
    (live process objects), and state persistence (saving/loading PIDs to a file)
    of UI environments. It acts as the single source of truth for which processes
    are considered "running" by the application.
    """

    def __init__(self, ui_registry: UiRegistry):
        """
        Initializes the ProcessManager.

        Args:
            ui_registry: An instance of UiRegistry to resolve UI installation paths.
        """
        self.ui_registry = ui_registry
        # Stores the live asyncio.subprocess.Process objects for active management.
        self.live_processes: Dict[str, asyncio.subprocess.Process] = {}
        # Stores the persisted state mapping task_id to (ui_name, pid).
        self.running_ui_tasks: Dict[str, Tuple[UiNameType, int]] = {}

        logger.info("ProcessManager initialized. Loading and reconciling process registry...")
        self._load_and_reconcile_registry()

    # --- Registry Persistence ---

    def _load_and_reconcile_registry(self):
        """
        Loads the process registry from its file and reconciles it with the
        currently running processes on the system to recover state after a restart.
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
                # We don't have the process object, but we can reflect its running state.
                # A background task is created to mark it as 'running' in the tracker.
                asyncio.create_task(self._reconcile_tracker_status(task_id, ui_name))
            else:
                logger.warning(
                    f"Found stale process in registry for {ui_name} (PID: {pid}). Removing."
                )

        self.running_ui_tasks = reconciled_tasks
        self._save_process_registry()
        logger.info(f"Process registry loaded. {len(self.running_ui_tasks)} processes reconciled.")

    def _save_process_registry(self):
        """Saves the current state of running UI tasks to the registry file."""
        try:
            CONFIG_FILE_DIR.mkdir(exist_ok=True)
            with open(PROCESS_REGISTRY_FILE_PATH, "w") as f:
                json.dump(self.running_ui_tasks, f, indent=4)
        except IOError as e:
            logger.error(f"Failed to save process registry: {e}", exc_info=True)

    async def _reconcile_tracker_status(self, task_id: str, ui_name: UiNameType):
        """Creates a placeholder task in the tracker for a reconciled process."""
        # This task does nothing but hold the place in the UI. It will run "forever"
        # until it is manually stopped or the app closes.
        dummy_task = asyncio.create_task(asyncio.sleep(float("inf")))
        download_tracker.start_tracking(task_id, "UI Process", ui_name, dummy_task)
        await download_tracker.update_task_progress(
            task_id, 5, "Process is running (Reconciled)", "running"
        )

    # --- Process Lifecycle Management ---

    def start_process(self, ui_name: UiNameType, task_id: str):
        """
        Starts a registered UI environment as a managed background process.
        This creates an asyncio task that will run and monitor the subprocess.
        """
        install_path = self.ui_registry.get_path(ui_name)
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
            ui_info = UI_REPOSITORIES.get(ui_name)
            if not ui_info:
                raise RuntimeError(f"Unknown UI '{ui_name}'.")

            start_script = ui_info.get("start_script")
            if not start_script:
                raise RuntimeError(f"No 'start_script' defined for {ui_name}.")

            process, error_msg = await ui_operator.run_ui(install_path, start_script)
            if not process:
                raise RuntimeError(error_msg or "UI process failed to start.")

            # Register the new process in our live and persisted states.
            self.live_processes[task_id] = process
            self.running_ui_tasks[task_id] = (ui_name, process.pid)
            self._save_process_registry()
            logger.info(f"Registered and saved process for {ui_name} with PID {process.pid}.")

            await download_tracker.update_task_progress(
                task_id, 5, "Process is running...", "running"
            )

            # Wait for the process to finish and stream its output.
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
            logger.error(f"Error running process for {ui_name}: {e}", exc_info=True)
            await download_tracker.fail_download(task_id, str(e))
        finally:
            # Clean up the finished process from state and registry.
            self.live_processes.pop(task_id, None)
            if task_id in self.running_ui_tasks:
                removed_ui, removed_pid = self.running_ui_tasks.pop(task_id)
                self._save_process_registry()
                logger.info(f"Unregistered process for {removed_ui} with PID {removed_pid}.")

    async def stop_process(self, task_id: str):
        """Stops a running UI process by its task ID, whether live or reconciled."""
        # First, check for a live, managed process object.
        process = self.live_processes.get(task_id)
        if process:
            logger.info(f"Stopping live process for task {task_id} (PID: {process.pid}).")
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=10)
            except asyncio.TimeoutError:
                process.kill()
            # The finally block in _run_and_manage_process will handle registry cleanup.
            return

        # If it's not a live process (i.e., it was reconciled), stop it by its PID.
        if task_id in self.running_ui_tasks:
            ui_name, pid = self.running_ui_tasks[task_id]
            logger.info(f"Stopping reconciled process for {ui_name} (PID: {pid}).")
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                logger.warning(f"Process with PID {pid} not found, already stopped.")
            except Exception as e:
                logger.error(f"Failed to stop process with PID {pid}: {e}", exc_info=True)

            # Manually clean up the tracker and registry since the managing task isn't running.
            self.running_ui_tasks.pop(task_id, None)
            self._save_process_registry()
            await download_tracker.complete_download(task_id, f"Stop request sent for {ui_name}.")

    # --- Helper Methods ---

    def _fail_task_fast(self, task_id: str, ui_name: UiNameType, message: str):
        """Helper to quickly fail a task that cannot even start."""
        logger.error(message)
        task = asyncio.create_task(download_tracker.fail_download(task_id, message))
        download_tracker.start_tracking(task_id, "UI Process", ui_name, task)

    async def _stream_process_output(self, process: asyncio.subprocess.Process, task_id: str):
        """Reads and logs process output for debugging purposes."""

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
