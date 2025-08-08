# backend/core/ui_management/process_manager.py
import asyncio
import logging
import pathlib
import json
import os
import signal
from typing import Optional, Dict, Tuple

from ..constants.constants import UI_REPOSITORIES, CONFIG_FILE_DIR
from ..file_management.download_tracker import download_tracker
from .ui_registry import UiRegistry
from . import ui_operator

from core.errors import MalError, OperationFailedError, BadRequestError, EntityNotFoundError

logger = logging.getLogger(__name__)

PROCESS_REGISTRY_FILE_PATH = CONFIG_FILE_DIR / "process_registry.json"


def _is_pid_running(pid: int) -> bool:
    if os.name == "nt":
        try:
            output = asyncio.subprocess.check_output(f'tasklist /FI "PID eq {pid}"').decode()
            return str(pid) in output
        except (asyncio.subprocess.CalledProcessError, FileNotFoundError):
            return False
    else:
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, PermissionError):
            return False
        else:
            return True


class ProcessManager:
    """
    Manages the lifecycle and persistent state of running UI processes.
    Its sole responsibility is to handle the execution, tracking, and state
    persistence of UI environments based on their unique installation_id.
    """

    def __init__(self, ui_registry: UiRegistry):
        self.ui_registry = ui_registry
        self.live_processes: Dict[str, asyncio.subprocess.Process] = {}
        # --- FIX: Persisted state now maps task_id to (installation_id, pid) ---
        self.running_ui_tasks: Dict[str, Tuple[str, int]] = {}

        logger.info("ProcessManager initialized. Loading and reconciling process registry...")
        self._load_and_reconcile_registry()

    def _load_and_reconcile_registry(self):
        if not PROCESS_REGISTRY_FILE_PATH.exists():
            return

        try:
            with open(PROCESS_REGISTRY_FILE_PATH, "r") as f:
                persisted_tasks = json.load(f)
        except (json.JSONDecodeError, IOError):
            return

        reconciled_tasks = {}
        for task_id, (installation_id, pid) in persisted_tasks.items():
            if _is_pid_running(pid):
                logger.info(
                    f"Reconciling running process: installation_id={installation_id}, PID={pid}"
                )
                reconciled_tasks[task_id] = (installation_id, pid)
                asyncio.create_task(self._reconcile_tracker_status(task_id, installation_id))
            else:
                logger.warning(f"Found stale process in registry for PID {pid}. Removing.")

        self.running_ui_tasks = reconciled_tasks
        self._save_process_registry()

    def _save_process_registry(self):
        try:
            CONFIG_FILE_DIR.mkdir(exist_ok=True)
            with open(PROCESS_REGISTRY_FILE_PATH, "w") as f:
                json.dump(self.running_ui_tasks, f, indent=4)
        except IOError as e:
            logger.error(f"Failed to save process registry: {e}", exc_info=True)

    async def _reconcile_tracker_status(self, task_id: str, installation_id: str):
        details = self.ui_registry.get_installation(installation_id)
        display_name = details.get("display_name") if details else "Unknown UI"
        dummy_task = asyncio.create_task(asyncio.sleep(float("inf")))
        download_tracker.start_tracking(task_id, "UI Process", display_name, dummy_task)
        await download_tracker.update_task_progress(
            task_id, 5, "Process is running (Reconciled)", "running"
        )

    # --- FIX: Method now accepts installation_id instead of ui_name ---
    def start_process(self, installation_id: str, task_id: str):
        details = self.ui_registry.get_installation(installation_id)
        if not details:
            raise EntityNotFoundError(entity_name="UI Installation", entity_id=installation_id)

        install_path = pathlib.Path(details["path"])
        if not install_path.exists():
            raise BadRequestError(
                f"Installation path for '{details['display_name']}' not found at '{install_path}'."
            )

        task = asyncio.create_task(
            self._run_and_manage_process(installation_id, install_path, task_id)
        )
        download_tracker.start_tracking(task_id, "UI Process", details["display_name"], task)

    async def _run_and_manage_process(
        self, installation_id: str, install_path: pathlib.Path, task_id: str
    ):
        details = self.ui_registry.get_installation(installation_id)
        ui_name = details["ui_name"] if details else None
        display_name = details.get("display_name") if details else "Unknown UI"

        try:
            if not ui_name:
                raise BadRequestError(f"Could not resolve UI type for {installation_id}")

            ui_info = UI_REPOSITORIES.get(ui_name)
            if not ui_info:
                raise BadRequestError(f"UI type '{ui_name}' is not recognized.")

            start_script = ui_info.get("start_script")
            if not start_script:
                raise OperationFailedError(
                    operation_name="UI Process Start Configuration",
                    original_exception=ValueError(f"No 'start_script' defined for {ui_name}."),
                )

            process = await ui_operator.run_ui(install_path, start_script)
            self.live_processes[task_id] = process
            self.running_ui_tasks[task_id] = (installation_id, process.pid)
            self._save_process_registry()
            logger.info(f"Registered process for {display_name} with PID {process.pid}.")

            await download_tracker.update_task_progress(
                task_id, 5, "Process is running...", "running"
            )
            await self._stream_process_output(process, task_id)

            if process.returncode == 0:
                await download_tracker.complete_download(
                    task_id, f"{display_name} finished successfully."
                )
            else:
                await download_tracker.fail_download(
                    task_id, f"{display_name} exited with code {process.returncode}."
                )
        except asyncio.CancelledError:
            await download_tracker.fail_download(
                task_id, "UI process was cancelled by user.", cancelled=True
            )
        except MalError as e:
            await download_tracker.fail_download(task_id, e.message)
        except Exception as e:
            await download_tracker.fail_download(
                task_id, f"A critical internal error occurred: {e}"
            )
        finally:
            self.live_processes.pop(task_id, None)
            if task_id in self.running_ui_tasks:
                self.running_ui_tasks.pop(task_id)
                self._save_process_registry()

    async def stop_process(self, task_id: str):
        process = self.live_processes.get(task_id)
        if process:
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=10)
            except asyncio.TimeoutError:
                process.kill()
                raise OperationFailedError(
                    operation_name=f"Stop UI task {task_id}",
                    original_exception=TimeoutError("Process did not terminate gracefully."),
                )
            return

        if task_id in self.running_ui_tasks:
            installation_id, pid = self.running_ui_tasks[task_id]
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception as e:
                raise OperationFailedError(
                    operation_name=f"Stop reconciled UI process {installation_id}",
                    original_exception=e,
                )
            self.running_ui_tasks.pop(task_id, None)
            self._save_process_registry()
            await download_tracker.complete_download(task_id, "Stop request sent.")
        else:
            raise EntityNotFoundError(entity_name="UI Process Task", entity_id=task_id)

    # --- FIX: Add the public method UiManager needs ---
    def get_running_tasks_by_installation_id(self) -> Dict[str, str]:
        """
        Returns a dictionary mapping installation_id to its running task_id.
        This is the data structure the UiManager needs for status checks.
        """
        return {
            installation_id: task_id
            for task_id, (installation_id, pid) in self.running_ui_tasks.items()
        }

    async def _stream_process_output(self, process: asyncio.subprocess.Process, task_id: str):
        async def read_stream(stream, stream_name):
            while stream and not stream.at_eof():
                line_bytes = await stream.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace").strip()
                if line:
                    logger.debug(f"[{task_id}:{stream_name}] {line}")

        await asyncio.gather(
            read_stream(process.stdout, "stdout"), read_stream(process.stderr, "stderr")
        )
        await process.wait()
