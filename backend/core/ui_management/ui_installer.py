# backend/core/ui_management/ui_installer.py
import asyncio
import logging
import pathlib
import sys
from typing import Callable, Coroutine, Any, Optional

# --- Type definition for a callback that can stream process output ---
StreamCallback = Callable[[str], Coroutine[Any, Any, None]]
# --- NEW: Type definition for a callback that can report progress ---
ProgressCallback = Callable[[int, int], Coroutine[Any, Any, None]]


logger = logging.getLogger(__name__)


async def _stream_process(
    process: asyncio.subprocess.Process,
    stream_callback: Optional[StreamCallback] = None,
) -> tuple[int, str]:
    """
    Reads stdout and stderr from a process line by line, optionally streaming it.
    This is essential for providing real-time feedback to the user.

    Args:
        process: The asyncio subprocess to monitor.
        stream_callback: An async function to call with each line of output.

    Returns:
        A tuple of (return_code, combined_output).
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

    # Concurrently read stdout and stderr
    await asyncio.gather(
        read_stream(process.stdout, "stdout"), read_stream(process.stderr, "stderr")
    )

    await process.wait()
    return_code = process.returncode
    combined_output = "\n".join(output_lines)
    logger.info(f"Process {process.pid} finished with exit code {return_code}.")
    return return_code, combined_output


async def clone_repo(
    git_url: str,
    target_dir: pathlib.Path,
    stream_callback: Optional[StreamCallback] = None,
) -> bool:
    """Clones a Git repository into a specified directory."""
    if target_dir.exists() and any(target_dir.iterdir()):
        logger.warning(
            f"Target directory {target_dir} already exists and is not empty. Skipping clone."
        )
        if stream_callback:
            await stream_callback(f"Directory {target_dir.name} already exists. Skipping clone.")
        return True

    logger.info(f"Cloning '{git_url}' into '{target_dir}'...")
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

    return_code, _ = await _stream_process(process, stream_callback)
    return return_code == 0


async def create_venv(
    ui_dir: pathlib.Path, stream_callback: Optional[StreamCallback] = None
) -> bool:
    """Creates a Python virtual environment inside the UI's directory."""
    venv_path = ui_dir / "venv"
    if venv_path.exists():
        logger.info(f"Virtual environment already exists at '{venv_path}'. Skipping.")
        if stream_callback:
            await stream_callback("Virtual environment already exists. Skipping.")
        return True

    logger.info(f"Creating virtual environment in '{venv_path}'...")
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "venv",
        str(venv_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    return_code, _ = await _stream_process(process, stream_callback)
    return return_code == 0


async def install_dependencies(
    ui_dir: pathlib.Path,
    requirements_file: str,
    stream_callback: Optional[StreamCallback] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> bool:
    """
    Installs dependencies from a requirements.txt file into the UI's venv,
    with enhanced progress tracking.
    """
    venv_python = (
        ui_dir / "venv" / "Scripts" / "python.exe"
        if sys.platform == "win32"
        else ui_dir / "venv" / "bin" / "python"
    )
    req_path = ui_dir / requirements_file

    if not venv_python.exists() or not req_path.exists():
        logger.error(f"Venv or requirements file not found for {ui_dir.name}.")
        return False

    # --- Enhanced Progress Logic ---
    try:
        # 1. Count total packages to install
        with open(req_path, "r") as f:
            packages = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        total_packages = len(packages)
        packages_processed = 0
        if progress_callback:
            await progress_callback(0, total_packages)
    except Exception as e:
        logger.error(f"Could not read requirements file {req_path}: {e}")
        total_packages = 1 # Avoid division by zero
        packages_processed = 0


    logger.info(f"Installing {total_packages} dependencies from '{req_path}'...")
    process = await asyncio.create_subprocess_exec(
        str(venv_python), "-m", "pip", "install", "-r", str(req_path), "--no-cache-dir",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # --- Custom stream handling to track progress ---
    async def read_and_track_stream(stream):
        nonlocal packages_processed
        while not stream.at_eof():
            line_bytes = await stream.readline()
            if not line_bytes: break
            
            line = line_bytes.decode("utf-8", errors="replace").strip()
            if stream_callback:
                await stream_callback(line)
            
            # Check for keywords that indicate a new package is being handled
            if progress_callback and (line.startswith("Collecting ") or line.startswith("Downloading ")):
                packages_processed += 1
                await progress_callback(min(packages_processed, total_packages), total_packages)

    # We only care about stdout for pip progress, but must drain stderr to avoid deadlocks
    await asyncio.gather(
        read_and_track_stream(process.stdout),
        _stream_process(type("Process", (), {"stdout": process.stderr, "stderr": type("Stream", (), {"at_eof": lambda: True})()})(), stream_callback) # Drain stderr
    )

    await process.wait()
    return process.returncode == 0
