# backend/core/ui_management/ui_installer.py
import asyncio
import logging
import pathlib
import sys
import re
import json
import tempfile
import shutil
from typing import Callable, Coroutine, Any, Optional, Literal, List, Dict, Tuple

# --- Type Definitions ---
StreamCallback = Callable[[str], Coroutine[Any, Any, None]]
PipPhase = Literal["collecting", "installing"]
PipProgressCallback = Callable[[PipPhase, int, int, str, Optional[int]], Coroutine[Any, Any, None]]
ProcessCreatedCallback = Callable[[asyncio.subprocess.Process], None]

# --- NEW: Import custom error classes for standardized handling (global import) ---
from core.errors import MalError, OperationFailedError, BadRequestError, EntityNotFoundError

logger = logging.getLogger(__name__)


async def _stream_process(
    process: asyncio.subprocess.Process,
    stream_callback: Optional[StreamCallback] = None,
) -> tuple[int, str]:
    """
    Reads stdout and stderr from a process, streams it back via callback,
    and returns the full combined output.
    """
    output_lines = []

    async def read_stream(stream, stream_name):
        while not stream.at_eof():
            try:
                line_bytes = await stream.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace").strip()
                if line:
                    output_lines.append(line)
                    if stream_callback:
                        await stream_callback(f"[{process.pid}:{stream_name}] {line}")
            except Exception as e:
                logger.warning(f"Error reading stream line: {e}")
                break

    await asyncio.gather(
        read_stream(process.stdout, "stdout"), read_stream(process.stderr, "stderr")
    )
    await process.wait()
    return_code = process.returncode
    logger.info(f"Process {process.pid} finished with exit code {return_code}.")
    return return_code, "\n".join(output_lines)


async def clone_repo(
    git_url: str,
    target_dir: pathlib.Path,
    stream_callback: Optional[StreamCallback] = None,
) -> None:  # --- REFACTOR: Changed return type from bool to None, will raise on failure ---
    """
    Clones a git repository into a specified target directory.
    If the directory already exists, it will be completely removed to ensure
    a clean, fresh installation.
    @refactor: Now raises OperationFailedError on failure.
    """
    if target_dir.exists():
        logger.warning(
            f"Target directory {target_dir} already exists. Deleting for a fresh install."
        )
        if stream_callback:
            await stream_callback(f"Cleaning up existing directory: {target_dir.name}...")
        try:
            shutil.rmtree(target_dir)
        except OSError as e:  # --- REFACTOR: Catch specific OSError for file system ops ---
            error_msg = f"Error: Could not delete existing directory {target_dir}. Please remove it manually. Details: {e}"
            logger.error(error_msg)
            if stream_callback:
                await stream_callback(error_msg)
            # --- REFACTOR: Raise OperationFailedError ---
            raise OperationFailedError(
                operation_name=f"Delete existing directory '{target_dir}'",
                original_exception=e,
                message=error_msg,
            ) from e

    logger.info(f"Cloning '{git_url}' into '{target_dir}'...")
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        process = await asyncio.create_subprocess_exec(
            "git",
            "clone",
            "--depth",
            "1",
            "--progress",
            git_url,
            str(target_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        return_code, output = await _stream_process(
            process, stream_callback
        )  # --- REFACTOR: Capture output for error message ---
        if return_code != 0:  # --- REFACTOR: Check return code and raise ---
            error_msg = f"Git clone failed with exit code {return_code}. Output: {output}"
            logger.error(error_msg)
            if stream_callback:
                await stream_callback(error_msg)
            raise OperationFailedError(
                operation_name=f"Git Clone from '{git_url}'",
                original_exception=Exception(
                    error_msg
                ),  # Wrap output in a generic Exception for original_exception
            )
    except OperationFailedError:  # Re-raise our custom errors directly
        raise
    except Exception as e:  # Catch any other unexpected errors during subprocess creation
        error_msg = f"Failed to start git clone process: {e}"
        logger.error(error_msg, exc_info=True)
        if stream_callback:
            await stream_callback(error_msg)
        raise OperationFailedError(
            operation_name=f"Start Git Clone Process from '{git_url}'",
            original_exception=e,
            message=error_msg,
        ) from e


async def create_venv(
    ui_dir: pathlib.Path, stream_callback: Optional[StreamCallback] = None
) -> None:  # --- REFACTOR: Changed return type from bool to None, will raise on failure ---
    """
    Creates a Python virtual environment in the specified directory.
    If a venv already exists, it is deleted to ensure a clean state.
    @refactor: Now raises OperationFailedError on failure.
    """
    venv_path = ui_dir / "venv"
    if venv_path.exists():
        logger.warning(
            f"Virtual environment already exists at '{venv_path}'. Deleting for fresh setup."
        )
        if stream_callback:
            await stream_callback("Removing existing virtual environment...")
        try:
            shutil.rmtree(venv_path)
        except OSError as e:  # --- REFACTOR: Catch specific OSError for file system ops ---
            error_msg = (
                f"Error: Could not delete existing venv. Please remove it manually. Details: {e}"
            )
            logger.error(error_msg)
            if stream_callback:
                await stream_callback(error_msg)
            # --- REFACTOR: Raise OperationFailedError ---
            raise OperationFailedError(
                operation_name=f"Delete existing venv at '{venv_path}'",
                original_exception=e,
                message=error_msg,
            ) from e

    logger.info(f"Creating virtual environment in '{venv_path}'...")
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "venv",
            str(venv_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        return_code, output = await _stream_process(
            process, stream_callback
        )  # --- REFACTOR: Capture output ---
        if return_code != 0:  # --- REFACTOR: Check return code and raise ---
            error_msg = f"Virtual environment creation failed with exit code {return_code}. Output: {output}"
            logger.error(error_msg)
            if stream_callback:
                await stream_callback(error_msg)
            raise OperationFailedError(
                operation_name=f"Create virtual environment at '{venv_path}'",
                original_exception=Exception(error_msg),
            )
    except OperationFailedError:  # Re-raise our custom errors directly
        raise
    except Exception as e:  # Catch any other unexpected errors during subprocess creation
        error_msg = f"Failed to start venv creation process: {e}"
        logger.error(error_msg, exc_info=True)
        if stream_callback:
            await stream_callback(error_msg)
        raise OperationFailedError(
            operation_name=f"Start Venv Creation Process at '{venv_path}'",
            original_exception=e,
            message=error_msg,
        ) from e


async def get_dependency_report(
    venv_python: pathlib.Path,
    req_path: pathlib.Path,
    extra_packages: Optional[List[str]],
    progress_callback: Optional[PipProgressCallback],
) -> Dict[str, Any]:
    """
    Runs a pip dry-run with a JSON report to analyze dependencies.
    @refactor: Now raises OperationFailedError on failure.
    """
    logger.info("Starting dependency analysis with 'pip --dry-run'...")

    report = {}
    # --- NEW: Ensure report_path is always defined ---
    report_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tmp_report_file:
            report_path = pathlib.Path(tmp_report_file.name)

        command = [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--dry-run",
            "--no-cache-dir",
            "-r",
            str(req_path),
            "--report",
            str(report_path),
        ]
        if extra_packages:
            command.extend(extra_packages)

        process = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        collect_regex = re.compile(r"^\s*Collecting\s+([a-zA-Z0-9-_.]+)", re.IGNORECASE)
        packages_found = []

        async def read_analysis_stream(stream, is_stderr: bool):
            while not stream.at_eof():
                try:
                    line_bytes = await stream.readline()
                    if not line_bytes:
                        break
                    line = line_bytes.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    if is_stderr and progress_callback:
                        match = collect_regex.match(line)
                        if match:
                            package_name = match.group(1)
                            if package_name not in packages_found:
                                packages_found.append(package_name)
                                await progress_callback(
                                    "collecting",
                                    len(packages_found),
                                    -1,
                                    f"Analyzing: {package_name}",
                                    None,
                                )
                except Exception as e:
                    logger.warning(f"Error reading pip analysis stream line: {e}")
                    break

        await asyncio.gather(
            read_analysis_stream(process.stdout, is_stderr=False),
            read_analysis_stream(process.stderr, is_stderr=True),
        )
        await process.wait()

        if process.returncode != 0:
            error_msg = f"Pip dependency report generation failed with code {process.returncode}."
            logger.error(error_msg)
            # --- REFACTOR: Raise OperationFailedError ---
            raise OperationFailedError(
                operation_name="Generate Pip Dependency Report",
                original_exception=Exception(error_msg),
            )

        if report_path.exists() and report_path.stat().st_size > 0:
            with open(report_path, "r") as f:
                report = json.load(f)
        else:
            logger.warning("Dependency report was not generated or is empty.")
            # --- NEW: Consider raising an error here if an empty report is a critical failure ---
            # For now, it logs a warning and returns empty, which might be acceptable.

    except OperationFailedError:  # Re-raise our custom errors directly
        raise
    except Exception as e:  # Catch any other unexpected errors during process creation or file ops
        error_msg = f"Failed to perform dependency analysis: {e}"
        logger.error(error_msg, exc_info=True)
        raise OperationFailedError(
            operation_name="Perform Dependency Analysis", original_exception=e, message=error_msg
        ) from e
    finally:
        if report_path and report_path.exists():  # --- NEW: Check if report_path was defined ---
            report_path.unlink()
    logger.info("Finished dependency analysis.")
    return report


async def install_dependencies(
    ui_dir: pathlib.Path,
    requirements_file: str,
    stream_callback: Optional[StreamCallback] = None,
    progress_callback: Optional[PipProgressCallback] = None,
    extra_packages: Optional[List[str]] = None,
    process_created_callback: Optional[ProcessCreatedCallback] = None,
) -> None:  # --- REFACTOR: Changed return type from bool to None, will raise on failure ---
    """
    Installs dependencies from a requirements file into a venv using a two-stage process.
    @refactor: Now raises OperationFailedError, EntityNotFoundError, or BadRequestError on failure.
    """
    venv_python = (
        ui_dir / "venv" / "Scripts" / "python.exe"
        if sys.platform == "win32"
        else ui_dir / "venv" / "bin" / "python"
    )
    req_path = ui_dir / requirements_file

    if not venv_python.exists():
        # --- REFACTOR: Raise EntityNotFoundError for missing venv python ---
        raise EntityNotFoundError(
            entity_name="Venv Python Executable",
            entity_id=str(venv_python),
            message=f"Virtual environment Python executable not found at '{venv_python}'. Cannot install dependencies.",
        )
    if not req_path.exists():
        # --- REFACTOR: Raise EntityNotFoundError for missing requirements file ---
        raise EntityNotFoundError(
            entity_name="Requirements File",
            entity_id=str(req_path),
            message=f"Requirements file not found at '{req_path}'. Cannot install dependencies.",
        )

    try:
        report = await get_dependency_report(
            venv_python, req_path, extra_packages, progress_callback
        )
    except MalError:  # Re-raise MalErrors from get_dependency_report directly
        raise
    except Exception as e:  # Wrap any other unexpected errors from get_dependency_report
        raise OperationFailedError(
            operation_name="Get Dependency Report for Installation",
            original_exception=e,
            message=f"Failed to get dependency report before installing dependencies: {e}",
        ) from e

    install_targets = report.get("install", [])

    if not install_targets:
        logger.info("Dependencies are already satisfied.")
        if progress_callback:
            await progress_callback("installing", 1, 1, "Dependencies already satisfied.", 0)
        return  # Success, no installation needed

    package_info = {
        item["metadata"]["name"]
        .lower()
        .replace("_", "-"): {
            "size": item.get("download_info", {}).get("archive_info", {}).get("size", 0),
            "version": item["metadata"]["version"],
        }
        for item in install_targets
        if item.get("metadata")
    }
    total_download_size = sum(info["size"] for info in package_info.values())

    logger.info(f"Starting actual installation of {len(install_targets)} packages...")

    pip_command = [
        str(venv_python),
        "-m",
        "pip",
        "install",
        "--no-cache-dir",
        "--timeout",
        "600",
        "-r",
        str(req_path),
    ]
    if extra_packages:
        pip_command.extend(extra_packages)

    try:
        process = await asyncio.create_subprocess_exec(
            *pip_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        if process_created_callback:
            process_created_callback(process)

        collect_regex = re.compile(r"^\s*Collecting\s+([a-zA-Z0-9-_.]+)", re.IGNORECASE)
        bytes_processed = 0

        async def read_and_parse_stream(stream):
            nonlocal bytes_processed
            while not stream.at_eof():
                try:
                    line_bytes = await stream.readline()
                    if not line_bytes:
                        break
                    line = line_bytes.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    if stream_callback:
                        await stream_callback(line)

                    if progress_callback and total_download_size > 0:
                        match = collect_regex.match(line)
                        if match:
                            package_name = match.group(1).lower().replace("_", "-")
                            info = package_info.get(package_name)
                            if info:
                                bytes_processed += info["size"]
                                await progress_callback(
                                    "collecting",
                                    bytes_processed,
                                    total_download_size,
                                    f"{package_name.capitalize()} {info['version']}",
                                    info["size"],
                                )
                except Exception as e:
                    logger.warning(f"Error reading pip stream line: {e}")
                    break

        if total_download_size == 0 and progress_callback:
            total_packages = len(package_info)
            for i, (name, info) in enumerate(package_info.items()):
                await progress_callback(
                    "collecting", i + 1, total_packages, f"{name.capitalize()} {info['version']}", 0
                )
                await asyncio.sleep(0.01)

        await asyncio.gather(
            read_and_parse_stream(process.stdout), read_and_parse_stream(process.stderr)
        )
        await process.wait()

        if process.returncode != 0:
            error_msg = f"Pip installation failed with exit code {process.returncode}."
            logger.error(error_msg)
            # --- REFACTOR: Raise OperationFailedError ---
            raise OperationFailedError(
                operation_name="Pip Install Dependencies", original_exception=Exception(error_msg)
            )

        if progress_callback:
            await progress_callback("installing", 1, 1, "Installation complete.", 0)
    except OperationFailedError:  # Re-raise our custom errors directly
        raise
    except Exception as e:  # Catch any other unexpected errors during subprocess creation
        error_msg = f"Failed to start pip installation process: {e}"
        logger.error(error_msg, exc_info=True)
        raise OperationFailedError(
            operation_name="Start Pip Installation Process", original_exception=e, message=error_msg
        ) from e
