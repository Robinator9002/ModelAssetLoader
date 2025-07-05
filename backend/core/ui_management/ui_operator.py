# backend/core/ui_management/ui_operator.py
import asyncio
import logging
import pathlib
import shutil
import sys
from typing import Optional

# Import the helper from the installer to stream process output
from .ui_installer import _stream_process, StreamCallback

logger = logging.getLogger(__name__)


async def delete_ui_environment(ui_dir: pathlib.Path) -> bool:
    """
    Completely removes a UI environment directory.

    This is a destructive operation. It uses shutil.rmtree to recursively
    delete the entire folder, including the git repo and the venv.

    Args:
        ui_dir: The root directory of the UI to delete.

    Returns:
        True if deletion was successful, False otherwise.
    """
    if not ui_dir.is_dir():
        logger.warning(f"Cannot delete '{ui_dir}'. It is not a valid directory.")
        return False

    # Basic security check: ensure we're not deleting something obviously wrong
    # A more robust check might ensure it's within a known 'installed_uis' path.
    if "venv" not in [d.name for d in ui_dir.iterdir() if d.is_dir()]:
        logger.error(
            f"Security check failed: Refusing to delete '{ui_dir}' as it does not appear to be a valid UI environment (no venv found)."
        )
        return False

    logger.info(f"Deleting UI environment at '{ui_dir}'...")
    try:
        shutil.rmtree(ui_dir)
        logger.info(f"Successfully deleted '{ui_dir}'.")
        return True
    except Exception as e:
        logger.error(f"Failed to delete directory '{ui_dir}': {e}", exc_info=True)
        return False


async def run_ui(
    ui_dir: pathlib.Path,
    start_script: str,
    stream_callback: Optional[StreamCallback] = None,
) -> Optional[asyncio.subprocess.Process]:
    """
    Launches a UI using its specific virtual environment and start script.

    Args:
        ui_dir: The root directory of the installed UI.
        start_script: The name of the script to execute (e.g., "main.py").
        stream_callback: An async function to stream stdout/stderr in real-time.

    Returns:
        The process object if successfully started, otherwise None.
    """
    venv_python = (
        ui_dir / "venv" / "Scripts" / "python.exe"
        if sys.platform == "win32"
        else ui_dir / "venv" / "bin" / "python"
    )
    script_path = ui_dir / start_script

    if not venv_python.exists():
        logger.error(f"Venv Python not found at '{venv_python}'. Cannot run UI.")
        if stream_callback:
            await stream_callback(f"ERROR: Virtual environment not found for this UI.")
        return None

    if not script_path.exists():
        logger.error(f"Start script not found at '{script_path}'. Cannot run UI.")
        if stream_callback:
            await stream_callback(f"ERROR: Start script '{start_script}' not found.")
        return None

    logger.info(f"Attempting to run '{script_path}' with '{venv_python}'...")
    if stream_callback:
        await stream_callback(f"Starting {ui_dir.name}...")

    try:
        # We pass the command and its arguments to start the UI's main script.
        # We also need to set the working directory to the UI's root.
        process = await asyncio.create_subprocess_exec(
            str(venv_python),
            str(script_path),
            # Add any required arguments for the script here if necessary
            # e.g., "--listen", "--port", "8188"
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=ui_dir,  # Set the working directory
        )
        logger.info(f"Successfully started process {process.pid} for {ui_dir.name}.")

        # The caller (UiManager) will be responsible for managing this process object
        # and streaming its output.
        return process
    except Exception as e:
        logger.error(f"Failed to start process for {ui_dir.name}: {e}", exc_info=True)
        if stream_callback:
            await stream_callback(f"FATAL: Could not start the UI process. See logs.")
        return None
