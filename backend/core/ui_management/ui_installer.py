# backend/core/ui_management/ui_installer.py
import asyncio
import logging
import pathlib
import sys
import re
from typing import Callable, Coroutine, Any, Optional, Literal, List

# --- Type Definitions ---
StreamCallback = Callable[[str], Coroutine[Any, Any, None]]
PipPhase = Literal["collecting", "installing"]
PipProgressCallback = Callable[[PipPhase, int, int, str], Coroutine[Any, Any, None]]

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
                    log_line = f"[{process.pid}:{stream_name}] {line}"
                    logger.debug(log_line)
                    if stream_callback:
                        await stream_callback(line)
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
) -> bool:
    if target_dir.exists() and any(target_dir.iterdir()):
        logger.warning(f"Target directory {target_dir} already exists. Skipping clone.")
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
    progress_callback: Optional[PipProgressCallback] = None,
    extra_packages: Optional[List[str]] = None,
) -> bool:
    venv_python = (
        ui_dir / "venv" / "Scripts" / "python.exe"
        if sys.platform == "win32"
        else ui_dir / "venv" / "bin" / "python"
    )
    req_path = ui_dir / requirements_file

    if not venv_python.exists() or not req_path.exists():
        logger.error(f"Venv or requirements file not found for {ui_dir.name}.")
        return False

    # --- Step 1: Dry Run to get the definitive list of packages to process ---
    logger.info("Performing pip dry run to determine dependency list...")
    dry_run_command = [str(venv_python), "-m", "pip", "install", "--dry-run", "-r", str(req_path)]
    if extra_packages:
        dry_run_command.extend(extra_packages)

    dry_run_process = await asyncio.create_subprocess_exec(
        *dry_run_command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, dry_run_output = await _stream_process(dry_run_process)

    collect_regex = re.compile(r"Collecting\s+([a-zA-Z0-9-_.]+)")
    packages_to_process = collect_regex.findall(dry_run_output)
    total_packages = len(packages_to_process)

    if total_packages == 0:
        logger.warning("Pip dry run found 0 packages to process. Assuming dependencies are met.")
        if progress_callback:
            await progress_callback("collecting", 1, 1, "Dependencies already satisfied.")
            await progress_callback("installing", 1, 1, "Done")
        return True

    logger.info(f"Dry run identified {total_packages} packages to process: {packages_to_process}")

    # --- Step 2: Run the REAL pip install in the background ---
    logger.info(f"Starting actual installation for {total_packages} packages...")
    pip_command = [
        str(venv_python),
        "-m",
        "pip",
        "install",
        "--timeout",
        "600",
        "-r",
        str(req_path),
    ]
    if extra_packages:
        pip_command.extend(extra_packages)

    install_process = await asyncio.create_subprocess_exec(
        *pip_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    # Start a background task to consume the output for logging, but not for progress.
    install_log_task = asyncio.create_task(_stream_process(install_process, stream_callback))

    # --- Step 3: SIMULATE progress based on the plan from the dry run ---
    if progress_callback:
        # Simulate Collecting Phase
        logger.info("Simulating 'collecting' phase progress...")
        for i, package_name in enumerate(packages_to_process, 1):
            await progress_callback("collecting", i, total_packages, package_name)
            await asyncio.sleep(0.1)

        # Simulate Installing Phase
        logger.info("Simulating 'installing' phase progress...")
        for i, package_name in enumerate(packages_to_process, 1):
            await progress_callback("installing", i, total_packages, package_name)
            await asyncio.sleep(0.3)

    # --- Step 4: Wait for the actual installation to complete ---
    logger.info("Waiting for actual pip install process to finish...")
    return_code, install_logs = await install_log_task
    logger.info(f"Actual pip install process finished with code {return_code}.")

    if return_code != 0:
        logger.error(f"Pip installation failed. Full logs:\n{install_logs}")

    return return_code == 0
