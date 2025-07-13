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

    # --- Step 1: Perform a dry run to get an accurate list and count of packages ---
    logger.info("Performing pip dry run to determine dependency list...")
    dry_run_command = [str(venv_python), "-m", "pip", "install", "--dry-run", "-r", str(req_path)]
    if extra_packages:
        dry_run_command.extend(extra_packages)

    dry_run_process = await asyncio.create_subprocess_exec(
        *dry_run_command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, dry_run_output = await _stream_process(dry_run_process)

    collect_regex = re.compile(r"Collecting\s+([a-zA-Z0-9-_.]+)")
    # This list contains all packages pip will download and install.
    packages_to_process = collect_regex.findall(dry_run_output)
    total_packages = len(packages_to_process)

    if total_packages == 0:
        logger.warning("Pip dry run found 0 packages to process. Assuming dependencies are met.")
        # If a progress callback exists, notify it that we are done with this step.
        if progress_callback:
            # Send a final signal for both phases to complete the progress bar segment.
            await progress_callback("collecting", 1, 1, "Done")
            await progress_callback("installing", 1, 1, "Done")
        return True

    logger.info(f"Dry run identified {total_packages} packages to process.")

    # --- Step 2: Perform the actual installation ---
    logger.info(f"Installing dependencies from '{req_path}'...")
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
        logger.info(f"Installing extra packages: {extra_packages}")
        pip_command.extend(extra_packages)

    phase: PipPhase = "collecting"
    processed_collect_count = 0
    installing_regex = re.compile(r"Installing collected packages:")

    # This task will simulate the 'installing' phase progress.
    # It is started once the 'collecting' phase is detected as complete.
    install_progress_ticker_task: Optional[asyncio.Task] = None

    async def intelligent_install_ticker():
        """
        Simulates installation progress by iterating through the full list of
        packages identified in the dry run. This provides a smoother and more
        representative progress bar for the user during the opaque installation phase.
        """
        # A short initial delay to allow the 'installing...' message to appear.
        await asyncio.sleep(0.5)
        for i, package_name in enumerate(packages_to_process, 1):
            if process.returncode is not None:
                logger.info("Installation process ended; stopping progress ticker.")
                break  # Stop if the main process has already finished

            if progress_callback:
                await progress_callback("installing", i, total_packages, package_name)

            # The delay simulates the time taken to install each package.
            await asyncio.sleep(0.2)

        # Ensure the progress reaches 100% for the installation phase
        if progress_callback and (process.returncode is None):
            await progress_callback("installing", total_packages, total_packages, "Finalizing...")

    async def pip_streamer(line: str):
        nonlocal phase, processed_collect_count, install_progress_ticker_task

        if stream_callback:
            await stream_callback(line)

        # --- Collecting Phase ---
        if phase == "collecting":
            collect_match = collect_regex.search(line)
            if collect_match:
                processed_collect_count += 1
                package_name = collect_match.group(1).strip()
                if progress_callback:
                    await progress_callback(
                        "collecting", processed_collect_count, total_packages, package_name
                    )

            # --- Phase Transition ---
            # When pip signals it's moving to installation, we switch our phase
            # and start the simulated progress for the installation part.
            if installing_regex.search(line):
                phase = "installing"
                logger.info(
                    f"Switched to 'installing' phase. Starting progress ticker for {total_packages} packages."
                )

                # Ensure the collecting phase shows 100% completion
                if progress_callback:
                    await progress_callback("collecting", total_packages, total_packages, "Done")

                # Start the background task for the simulated installation progress
                install_progress_ticker_task = asyncio.create_task(intelligent_install_ticker())

    process = await asyncio.create_subprocess_exec(
        *pip_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    return_code, _ = await _stream_process(process, pip_streamer)

    # Clean up the ticker task if it's still running
    if install_progress_ticker_task and not install_progress_ticker_task.done():
        install_progress_ticker_task.cancel()

    return return_code == 0
