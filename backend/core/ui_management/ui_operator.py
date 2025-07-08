# backend/core/ui_management/ui_operator.py
import asyncio
import logging
import pathlib
import shutil
import sys
from typing import Optional, Tuple

from .ui_installer import StreamCallback
from ..constants.constants import UI_REPOSITORIES, UiNameType

logger = logging.getLogger(__name__)


async def _stream_process(
    process: asyncio.subprocess.Process,
    stream_callback: Optional[StreamCallback] = None,
) -> tuple[int, str]:
    """
    Reads stdout and stderr from a process line by line, optionally streaming it.
    This is essential for providing real-time feedback to the user.
    """
    output_lines = []

    async def read_stream(stream, stream_name):
        while not stream.at_eof():
            line_bytes = await stream.readline()
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="replace").strip()
            output_lines.append(line)
            log_line = f"[{process.pid}:{stream_name}] {line}"
            logger.debug(log_line)
            if stream_callback:
                await stream_callback(line)

    await asyncio.gather(
        read_stream(process.stdout, "stdout"), read_stream(process.stderr, "stderr")
    )

    await process.wait()
    return_code = process.returncode
    combined_output = "\n".join(output_lines)
    logger.info(f"Process {process.pid} finished with exit code {return_code}.")
    return return_code, combined_output


async def delete_ui_environment(ui_dir: pathlib.Path) -> bool:
    """Completely removes a M.A.L.-managed UI environment directory."""
    if not ui_dir.is_dir():
        logger.warning(f"Cannot delete '{ui_dir}'. It is not a valid directory.")
        return False

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
) -> Tuple[Optional[asyncio.subprocess.Process], Optional[str]]:
    """Launches a UI using its specific virtual environment and start script."""
    venv_python = (
        ui_dir / "venv" / "Scripts" / "python.exe"
        if sys.platform == "win32"
        else ui_dir / "venv" / "bin" / "python"
    )
    script_path = ui_dir / start_script

    if not venv_python.exists():
        msg = f"ERROR: Virtual environment python not found at '{venv_python}'. Cannot run UI."
        logger.error(msg)
        return None, msg

    if not script_path.exists():
        msg = f"ERROR: Start script '{start_script}' not found at '{script_path}'. Cannot run UI."
        logger.error(msg)
        return None, msg

    logger.info(f"Attempting to run '{script_path}' with '{venv_python}'...")
    try:
        process = await asyncio.create_subprocess_exec(
            str(venv_python),
            str(script_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=ui_dir,
        )
        logger.info(f"Successfully started process {process.pid} for {ui_dir.name}.")
        return process, None
    except Exception as e:
        msg = f"FATAL: Could not start the UI process. See logs. Error: {e}"
        logger.error(f"Failed to start process for {ui_dir.name}: {e}", exc_info=True)
        return None, msg


# --- PHASE 2: NEW FUNCTIONS ---


async def validate_git_repo(path: pathlib.Path) -> Tuple[Optional[UiNameType], Optional[str]]:
    """
    Validates if a directory is a known UI by checking its Git remote URL.

    Returns:
        A tuple of (ui_name, error_message). On success, ui_name is populated.
        On failure, error_message is populated.
    """
    if not path.is_dir():
        return None, "The provided path is not a valid directory."
    git_dir = path / ".git"
    if not git_dir.is_dir():
        return None, "This directory does not appear to be a Git repository."

    try:
        process = await asyncio.create_subprocess_exec(
            "git",
            "config",
            "--get",
            "remote.origin.url",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=path,
        )
        return_code, output = await _stream_process(process)
        if return_code != 0:
            return None, f"Could not get remote URL. Git error: {output}"

        remote_url = output.strip()
        for ui_name, details in UI_REPOSITORIES.items():
            if details["git_url"] == remote_url:
                logger.info(f"Validated '{path}' as a '{ui_name}' installation.")
                return ui_name, None

        return None, "The Git remote URL does not match any known UI."
    except Exception as e:
        logger.error(f"Error during Git validation for '{path}': {e}", exc_info=True)
        return None, "An unexpected error occurred during validation."


async def backup_ui_environment(
    source_dir: pathlib.Path, stream_callback: Optional[StreamCallback] = None
) -> Optional[str]:
    """
    Creates a .zip backup of a directory. Runs in a thread to avoid blocking.

    Returns:
        The absolute path to the created backup file, or None on error.
    """
    backup_dir = source_dir.parent
    backup_name = f"{source_dir.name}_backup_{asyncio.get_event_loop().time():.0f}"
    backup_path_base = backup_dir / backup_name

    if stream_callback:
        await stream_callback(f"Starting backup of '{source_dir.name}'...")

    try:
        # shutil.make_archive is blocking, so we run it in a separate thread.
        backup_file_path = await asyncio.to_thread(
            shutil.make_archive,
            base_name=str(backup_path_base),
            format="zip",
            root_dir=source_dir,
        )
        msg = f"Backup complete. Saved to: {backup_file_path}"
        logger.info(msg)
        if stream_callback:
            await stream_callback(msg)
        return backup_file_path
    except Exception as e:
        error_msg = f"Failed to create backup for '{source_dir.name}': {e}"
        logger.error(error_msg, exc_info=True)
        if stream_callback:
            await stream_callback(f"ERROR: {error_msg}")
        return None
