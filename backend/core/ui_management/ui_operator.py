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

# --- NEW: Import custom error classes for standardized handling (global import) ---
from core.errors import MalError, OperationFailedError, BadRequestError, EntityNotFoundError

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


async def delete_ui_environment(
    ui_dir: pathlib.Path,
) -> None:  # --- REFACTOR: Changed return type from bool to None, will raise on failure ---
    """
    Completely and safely removes a M.A.L.-managed UI environment directory.
    @refactor: Now raises BadRequestError or OperationFailedError on failure.
    """
    if not ui_dir.is_dir():
        logger.warning(f"Cannot delete '{ui_dir}'. It is not a valid directory.")
        # --- REFACTOR: Raise BadRequestError ---
        raise BadRequestError(f"Cannot delete '{ui_dir}'. It is not a valid directory.")

    # Security check: A managed UI must contain a 'venv' folder.
    # This prevents accidental deletion of arbitrary directories.
    # --- REFACTOR: Check for venv explicitly and raise BadRequestError if not found ---
    venv_found = False
    for item in ui_dir.iterdir():
        if item.is_dir() and item.name == "venv":
            venv_found = True
            break

    if not venv_found:
        error_msg = f"Security check failed: Refusing to delete '{ui_dir}' as it does not appear to be a valid M.A.L. environment (no venv found)."
        logger.error(error_msg)
        raise BadRequestError(message=error_msg)

    logger.info(f"Deleting UI environment at '{ui_dir}'...")
    try:
        # Use shutil.rmtree for recursive deletion.
        shutil.rmtree(ui_dir)
        logger.info(f"Successfully deleted '{ui_dir}'.")
        # --- REFACTOR: No return needed on success ---
    except OSError as e:  # --- REFACTOR: Catch specific OSError for file system ops ---
        error_msg = f"Failed to delete directory '{ui_dir}': {e}"
        logger.error(error_msg, exc_info=True)
        # --- REFACTOR: Raise OperationFailedError ---
        raise OperationFailedError(
            operation_name=f"Delete UI environment '{ui_dir}'",
            original_exception=e,
            message=error_msg,
        ) from e
    except Exception as e:  # Catch any other unexpected errors
        error_msg = f"An unexpected error occurred while deleting directory '{ui_dir}': {e}"
        logger.critical(error_msg, exc_info=True)
        raise OperationFailedError(
            operation_name=f"Delete UI environment '{ui_dir}'",
            original_exception=e,
            message=error_msg,
        ) from e


async def run_ui(
    ui_dir: pathlib.Path,
    start_script: str,
) -> asyncio.subprocess.Process:  # --- REFACTOR: Changed return type, will raise on failure ---
    """
    Launches a UI, intelligently deciding whether to run a Python script
    via the venv or to execute a shell/batch script directly.
    @refactor: Now raises EntityNotFoundError, BadRequestError, or OperationFailedError on failure.
    """
    script_path = ui_dir / start_script
    if not script_path.exists():
        msg = f"Start script '{start_script}' not found at '{script_path}'. Cannot run UI."
        logger.error(msg)
        # --- REFACTOR: Raise EntityNotFoundError ---
        raise EntityNotFoundError(
            entity_name="Start Script", entity_id=str(script_path), message=msg
        )

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
                # --- NEW: Log and raise OperationFailedError for permission issues ---
                logger.warning(f"Could not set executable permissions for '{script_path}': {e}")
                raise OperationFailedError(
                    operation_name=f"Set executable permissions for '{script_path}'",
                    original_exception=e,
                    message=f"Failed to set executable permissions for '{script_path}'. Please check file permissions.",
                ) from e
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
            msg = f"Virtual environment python not found at '{venv_python}'. Cannot run UI."
            logger.error(msg)
            # --- REFACTOR: Raise EntityNotFoundError ---
            raise EntityNotFoundError(
                entity_name="Venv Python Executable", entity_id=str(venv_python), message=msg
            )
        # Use -u for unbuffered output, which is crucial for real-time log streaming.
        command_to_run = [str(venv_python), "-u", str(script_path)]

    if not command_to_run:
        # This case should not be reached if constants.py is well-defined.
        msg = f"Could not determine how to run '{start_script}'."
        logger.error(msg)
        # --- REFACTOR: Raise OperationFailedError ---
        raise OperationFailedError(
            operation_name=f"Determine run command for '{start_script}'",
            original_exception=ValueError(msg),  # Use ValueError as original exception
            message=msg,
        )

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
        return process  # --- REFACTOR: Return process directly on success ---
    except FileNotFoundError as e:  # --- NEW: Catch specific FileNotFoundError for command ---
        msg = f"FATAL: The command '{command_to_run[0]}' was not found. Is it in your system's PATH? Error: {e}"
        logger.error(msg, exc_info=True)
        raise OperationFailedError(
            operation_name=f"Start UI process for '{ui_dir.name}'",
            original_exception=e,
            message=msg,
        ) from e
    except OSError as e:  # --- NEW: Catch OSError for other process-related issues ---
        msg = f"FATAL: An OS error occurred while trying to start the UI process. Error: {e}"
        logger.error(msg, exc_info=True)
        raise OperationFailedError(
            operation_name=f"Start UI process for '{ui_dir.name}'",
            original_exception=e,
            message=msg,
        ) from e
    except Exception as e:
        msg = f"FATAL: Could not start the UI process due to an unexpected error. Error: {e}"
        logger.critical(msg, exc_info=True)
        # --- REFACTOR: Raise OperationFailedError ---
        raise OperationFailedError(
            operation_name=f"Start UI process for '{ui_dir.name}'",
            original_exception=e,
            message=msg,
        ) from e
