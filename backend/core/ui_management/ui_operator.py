# backend/core/ui_management/ui_operator.py
import asyncio
import logging
import pathlib
import shutil
import sys
from typing import Optional, Tuple

from .ui_installer import StreamCallback
from ..constants.constants import UiNameType

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

    # Security check to avoid deleting arbitrary directories.
    # A managed UI must contain a 'venv' folder.
    if "venv" not in [d.name for d in ui_dir.iterdir() if d.is_dir()]:
        logger.error(
            f"Security check failed: Refusing to delete '{ui_dir}' as it does not appear to be a valid M.A.L. environment (no venv found)."
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
