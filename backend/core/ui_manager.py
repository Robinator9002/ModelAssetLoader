# backend/core/ui_manager.py
import asyncio
import logging
import pathlib
from typing import Optional

# --- Import the building blocks ---

# The "knowledge base" containing Git URLs and other metadata
from .constants.constants import UI_REPOSITORIES, UiNameType

# The "workhorse" that executes the actual commands
from .ui_management import ui_installer

# A shared tracker for reporting progress to the frontend (can be the existing download_tracker)
from .file_management.download_tracker import download_tracker, BroadcastCallable

logger = logging.getLogger(__name__)


class UiManager:
    """
    Orchestrates the installation and management of different AI UIs.

    This class acts as the high-level facade, connecting the API endpoints
    to the low-level installation logic.
    """

    def __init__(self, broadcast_callback: Optional[BroadcastCallable] = None):
        """
        Initializes the UiManager.

        Args:
            broadcast_callback: An async function to broadcast status updates,
                                typically provided by the WebSocket manager.
        """
        self.broadcast_callback = broadcast_callback
        logger.info("UiManager initialized.")

    async def install_ui_environment(
        self, ui_name: UiNameType, base_install_path: pathlib.Path, task_id: str
    ):
        """
        Manages the full installation process for a given UI.

        This method orchestrates cloning, venv creation, and dependency installation.
        It reports progress and final status through the tracker.

        Args:
            ui_name: The name of the UI to install (e.g., "ComfyUI").
            base_install_path: The root directory where all UIs will be stored.
            task_id: A unique ID to track this specific installation task.
        """
        ui_info = UI_REPOSITORIES.get(ui_name)
        if not ui_info:
            logger.error(f"Unknown UI '{ui_name}'. Cannot install.")
            await download_tracker.fail_download(
                task_id, f"Unknown UI '{ui_name}'. Installation aborted."
            )
            return

        target_dir = base_install_path / ui_name
        git_url = ui_info["git_url"]
        req_file = ui_info["requirements_file"]

        # --- Define a callback to stream progress back to the tracker ---
        async def stream_progress_to_tracker(line: str):
            # This is a placeholder for more detailed progress updates.
            # For now, we'll just log it, but we could update the tracker here.
            logger.info(f"[{task_id}:{ui_name}] {line}")
            # In the future, we could parse pip's output for percentage, etc.
            # For now, the frontend will just see a live log.
            if self.broadcast_callback:
                await self.broadcast_callback(
                    {"type": "log", "task_id": task_id, "message": line}
                )

        try:
            # --- Step 1: Clone Repository ---
            logger.info(f"Step 1/3: Cloning {ui_name}...")
            await download_tracker.update_progress(task_id, 0, 100) # Placeholder progress
            success = await ui_installer.clone_repo(
                git_url, target_dir, stream_progress_to_tracker
            )
            if not success:
                raise RuntimeError(f"Failed to clone repository for {ui_name}.")

            # --- Step 2: Create Virtual Environment ---
            logger.info(f"Step 2/3: Creating venv for {ui_name}...")
            await download_tracker.update_progress(task_id, 33, 100)
            success = await ui_installer.create_venv(
                target_dir, stream_progress_to_tracker
            )
            if not success:
                raise RuntimeError(f"Failed to create virtual environment for {ui_name}.")

            # --- Step 3: Install Dependencies ---
            logger.info(f"Step 3/3: Installing dependencies for {ui_name}...")
            await download_tracker.update_progress(task_id, 66, 100)
            success = await ui_installer.install_dependencies(
                target_dir, req_file, stream_progress_to_tracker
            )
            if not success:
                raise RuntimeError(f"Failed to install dependencies for {ui_name}.")

            # --- Final Step: Mark as Complete ---
            logger.info(f"Successfully installed {ui_name} at {target_dir}")
            await download_tracker.complete_download(task_id, str(target_dir))

        except Exception as e:
            error_message = f"Installation failed for {ui_name}: {e}"
            logger.error(error_message, exc_info=True)
            await download_tracker.fail_download(task_id, error_message)

    def start_install_task(self, ui_name: UiNameType, task_id: str):
        """
        A placeholder method to show how this would be called from an API endpoint.
        In a real scenario, the base_path would come from the ConfigManager.
        """
        # This base path should come from the main app's configuration
        base_install_path = pathlib.Path("./installed_uis")
        base_install_path.mkdir(exist_ok=True)

        # Register the task with the tracker
        download_tracker.start_tracking(
            download_id=task_id,
            repo_id=f"install:{ui_name}",
            filename=f"{ui_name} Environment",
            task=None, # The task is created below
        )

        # Create and run the installation task in the background
        install_task = asyncio.create_task(
            self.install_ui_environment(ui_name, base_install_path, task_id)
        )
        
        # We can optionally store the task in the tracker if we need to cancel it
        if task_id in download_tracker.active_downloads:
            download_tracker.active_downloads[task_id].task = install_task

        logger.info(f"Scheduled installation task {task_id} for {ui_name}.")

