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

# --- NEW: Import custom error classes for standardized handling (global import) ---
from core.errors import MalError, OperationFailedError, BadRequestError, EntityNotFoundError

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
            # --- NEW: Wrap in OperationFailedError if this were a public method ---
            # For internal loading, logging and returning is sufficient.
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
            # --- NEW: Wrap in OperationFailedError if this were a public method ---
            # For internal saving, logging is sufficient.

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
        @refactor: This method now raises EntityNotFoundError or BadRequestError.
        """
        install_path = self.ui_registry.get_path(ui_name)
        if not install_path:
            # --- REFACTOR: Raise EntityNotFoundError for missing UI ---
            raise EntityNotFoundError(entity_name="UI", entity_id=ui_name)
        if not install_path.exists():
            # --- REFACTOR: Raise BadRequestError if path doesn't exist ---
            raise BadRequestError(
                f"Installation path for UI '{ui_name}' not found at '{install_path}'."
            )

        task = asyncio.create_task(self._run_and_manage_process(ui_name, install_path, task_id))
        download_tracker.start_tracking(task_id, "UI Process", ui_name, task)

    async def _run_and_manage_process(
        self, ui_name: UiNameType, install_path: pathlib.Path, task_id: str
    ):
        """The core async method that runs a UI process and tracks its lifecycle."""
        try:
            ui_info = UI_REPOSITORIES.get(ui_name)
            if not ui_info:
                # --- REFACTOR: Raise BadRequestError for unknown UI type ---
                raise BadRequestError(f"UI type '{ui_name}' is not recognized.")

            start_script = ui_info.get("start_script")
            if not start_script:
                # --- REFACTOR: Raise OperationFailedError for missing start script config ---
                raise OperationFailedError(
                    operation_name="UI Process Start Configuration",
                    original_exception=ValueError(f"No 'start_script' defined for {ui_name}."),
                )

            # ui_operator.run_ui is expected to raise MalError on failure now
            process, error_msg = await ui_operator.run_ui(install_path, start_script)
            if not process:
                # This branch should ideally not be reached if ui_operator raises MalError directly.
                # However, as a safeguard, if it still returns None, we raise an OperationFailedError.
                raise OperationFailedError(
                    operation_name=f"Start UI '{ui_name}' process",
                    original_exception=Exception(
                        error_msg or "UI process failed to start unexpectedly."
                    ),
                )

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
        except asyncio.CancelledError:
            await download_tracker.fail_download(
                task_id, "UI process was cancelled by user.", cancelled=True
            )
        # --- REFACTOR: Catch MalError first, then generic Exception ---
        except MalError as e:
            logger.error(
                f"UI process for {ui_name} failed with MalError: {e.message}", exc_info=False
            )
            await download_tracker.fail_download(task_id, e.message)
        except Exception as e:
            logger.critical(
                f"An unhandled exception occurred during UI process for {ui_name}!", exc_info=True
            )
            await download_tracker.fail_download(
                task_id, f"A critical internal error occurred: {e}"
            )
        finally:
            # Clean up the finished process from state and registry.
            self.live_processes.pop(task_id, None)
            if task_id in self.running_ui_tasks:
                removed_ui, removed_pid = self.running_ui_tasks.pop(task_id)
                self._save_process_registry()
                logger.info(f"Unregistered process for {removed_ui} with PID {removed_pid}.")

    async def stop_process(self, task_id: str):
        """
        Stops a running UI process by its task ID, whether live or reconciled.
        @refactor: This method now raises OperationFailedError.
        """
        process = self.live_processes.get(task_id)
        if process:
            logger.info(f"Stopping live process for task {task_id} (PID: {process.pid}).")
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=10)
            except asyncio.TimeoutError:
                process.kill()
                # --- NEW: Raise OperationFailedError if process needs to be killed ---
                await download_tracker.fail_download(
                    task_id, f"Process {process.pid} did not terminate gracefully and was killed."
                )
                raise OperationFailedError(
                    operation_name=f"Stop UI task {task_id}",
                    original_exception=TimeoutError(
                        f"Process {process.pid} did not terminate gracefully and was killed."
                    ),
                )
            except Exception as e:
                # --- NEW: Raise OperationFailedError for other termination issues ---
                await download_tracker.fail_download(task_id, f"Failed to terminate process: {e}")
                raise OperationFailedError(
                    operation_name=f"Stop UI task {task_id}", original_exception=e
                )
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
                await download_tracker.complete_download(
                    task_id, f"Process {ui_name} (PID: {pid}) already stopped."
                )
            except Exception as e:
                logger.error(f"Failed to stop process with PID {pid}: {e}", exc_info=True)
                await download_tracker.fail_download(
                    task_id, f"Failed to stop process with PID {pid}: {e}"
                )
                raise OperationFailedError(
                    operation_name=f"Stop reconciled UI process {ui_name} (PID: {pid})",
                    original_exception=e,
                )

            # Manually clean up the tracker and registry since the managing task isn't running.
            self.running_ui_tasks.pop(task_id, None)
            self._save_process_registry()
            await download_tracker.complete_download(task_id, f"Stop request sent for {ui_name}.")
        else:
            # If task_id is not found in either live_processes or running_ui_tasks
            logger.warning(f"Attempted to stop task {task_id}, but it was not found as running.")
            # --- NEW: Raise EntityNotFoundError if task not found ---
            raise EntityNotFoundError(entity_name="UI Process Task", entity_id=task_id)

    # --- Helper Methods ---

    def _fail_task_fast(self, task_id: str, ui_name: UiNameType, message: str):
        """
        Helper to quickly fail a task that cannot even start.
        @refactor: This method is now less likely to be called directly for start failures
                   as start_process will raise exceptions.
        """
        logger.error(message)
        # This helper is primarily for immediate UI feedback via download_tracker,
        # not for raising exceptions up the call stack.
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
                    # Log the error but don't re-raise, as streaming should be resilient.
                    logger.warning(f"Error reading stream line from process {process.pid}: {e}")
                    break

        await asyncio.gather(
            read_stream(process.stdout, "stdout"), read_stream(process.stderr, "stderr")
        )
        await process.wait()
