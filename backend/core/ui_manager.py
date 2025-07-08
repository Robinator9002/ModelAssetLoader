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
    def __init__(
        self,
        config_manager: ConfigManager,
        broadcast_callback: Optional[BroadcastCallable] = None,
    ):
        self.config = config_manager
        self.broadcast_callback = broadcast_callback
        self.running_processes: Dict[str, asyncio.subprocess.Process] = {}
        self.running_ui_tasks: Dict[UiNameType, str] = {}
        logger.info("UiManager initialized.")

    def _get_install_path_for_ui(self, ui_name: UiNameType) -> Optional[pathlib.Path]:
        if self.config.base_path:
            return self.config.base_path / "managed_uis" / ui_name
        return None

    async def get_all_statuses(self) -> List[ManagedUiStatus]:
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
        ui_info = UI_REPOSITORIES.get(ui_name)
        if not ui_info:
            logger.error(f"Unknown UI '{ui_name}'. Cannot proceed.")
            await download_tracker.fail_download(
                task_id, f"Unknown UI '{ui_name}'. Action aborted."
            )
        return ui_info

    async def _stream_progress_to_tracker(self, task_id: str, line: str):
        if self.broadcast_callback:
            await self.broadcast_callback({"type": "log", "task_id": task_id, "message": line})

    async def install_ui_environment(
        self, ui_name: UiNameType, base_install_path: pathlib.Path, task_id: str
    ):
        ui_info = await self._get_ui_info(ui_name, task_id)
        if not ui_info:
            return

        target_dir = base_install_path / ui_name
        git_url = ui_info["git_url"]
        req_file = ui_info.get("requirements_file")

        if not req_file:
            msg = f"Installation failed: 'requirements_file' not defined for {ui_name}."
            logger.error(msg)
            await download_tracker.fail_download(task_id, msg)
            return

        CLONE_END = 15.0
        VENV_END = 25.0
        COLLECT_START, COLLECT_END = 25.0, 70.0
        INSTALL_START, INSTALL_END = 70.0, 95.0

        COLLECT_RANGE = COLLECT_END - COLLECT_START
        INSTALL_RANGE = INSTALL_END - INSTALL_START

        try:
            streamer = lambda line: self._stream_progress_to_tracker(task_id, line)

            await download_tracker.update_task_progress(task_id, 0, f"Cloning {ui_name}...")
            if not await ui_installer.clone_repo(git_url, target_dir, streamer):
                raise RuntimeError(f"Failed to clone repository for {ui_name}.")

            await download_tracker.update_task_progress(
                task_id, CLONE_END, "Creating virtual environment..."
            )
            if not await ui_installer.create_venv(target_dir, streamer):
                raise RuntimeError(f"Failed to create venv for {ui_name}.")

            async def pip_progress_updater(
                phase: ui_installer.PipPhase, current: int, total: int, package_name: str
            ):
                if phase == "collecting":
                    # Heuristic: Assume the actual number of dependencies to collect is roughly
                    # N times the number of top-level packages. A factor of 3 is a reasonable guess.
                    # This prevents the progress from finishing too early.
                    estimated_total = total * 3 if total > 0 else 1
                    fraction = min(current / estimated_total, 1.0)  # Cap at 100% of this phase

                    progress = COLLECT_START + (fraction * COLLECT_RANGE)
                    status_text = f"Collecting: {package_name}"
                    await download_tracker.update_task_progress(task_id, progress, status_text)

                elif phase == "installing":
                    # This phase is accurate because 'total' is the true count from pip.
                    fraction = current / total if total > 0 else 0
                    progress = INSTALL_START + (fraction * INSTALL_RANGE)
                    status_text = f"Installing ({current}/{total}): {package_name}"
                    await download_tracker.update_task_progress(task_id, progress, status_text)

            await download_tracker.update_task_progress(
                task_id, VENV_END, "Resolving dependencies..."
            )
            if not await ui_installer.install_dependencies(
                target_dir, req_file, streamer, pip_progress_updater
            ):
                raise RuntimeError(f"Failed to install dependencies for {ui_name}.")

            await download_tracker.update_task_progress(
                task_id, INSTALL_END, "Finalizing installation..."
            )
            await download_tracker.complete_download(task_id, str(target_dir))

        except Exception as e:
            error_message = f"Installation failed for {ui_name}: {e}"
            logger.error(error_message, exc_info=True)
            await download_tracker.fail_download(task_id, error_message)

    async def delete_environment(self, ui_name: UiNameType) -> bool:
        target_dir = self._get_install_path_for_ui(ui_name)
        if not target_dir:
            return False
        return await ui_operator.delete_ui_environment(target_dir)

    def run_ui(self, ui_name: UiNameType, task_id: str):
        download_tracker.start_tracking(
            download_id=task_id,
            repo_id=f"UI Process",
            filename=ui_name,
            task=asyncio.create_task(self._run_and_manage_process(ui_name, task_id)),
        )

    async def _run_and_manage_process(self, ui_name: UiNameType, task_id: str):
        process = None
        try:
            ui_info = await self._get_ui_info(ui_name, task_id)
            if not ui_info:
                return

            target_dir = self._get_install_path_for_ui(ui_name)
            if not target_dir or not target_dir.is_dir():
                raise RuntimeError(f"Installation directory for {ui_name} not found.")

            start_script = ui_info.get("start_script")
            if not start_script:
                raise RuntimeError(f"No 'start_script' defined for {ui_name}.")

            process, error_msg = await ui_operator.run_ui(target_dir, start_script)
            if not process:
                raise RuntimeError(error_msg or "UI process failed to start.")

            self.running_processes[task_id] = process
            self.running_ui_tasks[ui_name] = task_id
            await download_tracker.update_task_progress(
                task_id, 5, status_text="Process is running...", new_status="running"
            )

            # This would ideally be a more robust implementation
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
        process = self.running_processes.get(task_id)
        if not process:
            return

        try:
            process.terminate()
            await asyncio.wait_for(process.wait(), timeout=10)
        except asyncio.TimeoutError:
            process.kill()
