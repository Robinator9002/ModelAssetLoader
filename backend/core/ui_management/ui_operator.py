# backend/core/ui_management/ui_operator.py
import asyncio
import logging
import pathlib
import shutil
import sys
import os
from typing import Optional, Tuple

# Note: Using a relative import to get to the ui_installer for the StreamCallback type.
from .ui_installer import StreamCallback

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
        # Continuously read from the stream until it's at the end of the file.
        while not stream.at_eof():
            try:
                line_bytes = await stream.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace").strip()
                # We only process non-empty lines.
                if line:
                    output_lines.append(line)
                    log_line = f"[{process.pid}:{stream_name}] {line}"
                    logger.debug(log_line)
                    if stream_callback:
                        await stream_callback(line)
            except Exception as e:
                logger.warning(f"Error reading stream line from process {process.pid}: {e}")
                break

    # Asynchronously read from both stdout and stderr.
    await asyncio.gather(
        read_stream(process.stdout, "stdout"), read_stream(process.stderr, "stderr")
    )

    # Wait for the process to terminate and get its return code.
    await process.wait()
    return_code = process.returncode
    combined_output = "\n".join(output_lines)
    logger.info(f"Process {process.pid} finished with exit code {return_code}.")
    return return_code, combined_output


async def delete_ui_environment(ui_dir: pathlib.Path) -> bool:
    """Completely and safely removes a M.A.L.-managed UI environment directory."""
    if not ui_dir.is_dir():
        logger.warning(f"Cannot delete '{ui_dir}'. It is not a valid directory.")
        return False

    # Security check: A managed UI must contain a 'venv' folder.
    # This prevents accidental deletion of arbitrary directories.
    if "venv" not in [d.name for d in ui_dir.iterdir() if d.is_dir()]:
        logger.error(
            f"Security check failed: Refusing to delete '{ui_dir}' as it does not appear to be a valid M.A.L. environment (no venv found)."
        )
        return False

    logger.info(f"Deleting UI environment at '{ui_dir}'...")
    try:
        # Use shutil.rmtree for recursive deletion.
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
    """
    Launches a UI, intelligently deciding whether to run a Python script
    via the venv or to execute a shell/batch script directly.
    """
    script_path = ui_dir / start_script
    if not script_path.exists():
        msg = f"ERROR: Start script '{start_script}' not found at '{script_path}'. Cannot run UI."
        logger.error(msg)
        return None, msg

    command_to_run: list[str] = []

    # Check if the start script is a shell or batch file.
    if start_script.endswith((".sh", ".bat")):
        logger.info(f"Executing shell/batch script directly: '{script_path}'")
        # On non-Windows systems, ensure the script has execute permissions.
        if os.name != "nt":
            try:
                script_path.chmod(0o755)
                logger.info(f"Set executable permissions for '{script_path}'.")
            except Exception as e:
                logger.warning(f"Could not set executable permissions for '{script_path}': {e}")
        command_to_run = [str(script_path)]
    else:
        # For .py files, we use the venv's python interpreter.
        logger.info(f"Executing Python script via virtual environment.")
        venv_python = (
            ui_dir / "venv" / "Scripts" / "python.exe"
            if sys.platform == "win32"
            else ui_dir / "venv" / "bin" / "python"
        )
        if not venv_python.exists():
            msg = f"ERROR: Virtual environment python not found at '{venv_python}'. Cannot run UI."
            logger.error(msg)
            return None, msg
        # Use -u for unbuffered output, which is crucial for real-time log streaming.
        command_to_run = [str(venv_python), "-u", str(script_path)]

    if not command_to_run:
        # This case should not be reached if constants.py is well-defined.
        msg = f"ERROR: Could not determine how to run '{start_script}'."
        logger.error(msg)
        return None, msg

    logger.info(
        f"Attempting to run command: '{' '.join(command_to_run)}' in working directory '{ui_dir}'"
    )
    try:
        # Execute the command, setting the current working directory (cwd) to the UI's root.
        # This is critical for scripts that use relative paths to find their resources.
        process = await asyncio.create_subprocess_exec(
            *command_to_run,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=ui_dir,
        )
        logger.info(f"Successfully started process {process.pid} for {ui_dir.name}.")
        return process, None
    except Exception as e:
        msg = f"FATAL: Could not start the UI process. See logs for details. Error: {e}"
        logger.error(f"Failed to start process for {ui_dir.name}: {e}", exc_info=True)
        return None, msg
