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
    and returns the full combined output. This is used for general command
    output like git clone or venv creation.
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
    """
    Clones a git repository into a specified target directory.
    Skips cloning if the directory already exists and is not empty.
    """
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
    """
    Creates a Python virtual environment in the specified directory.
    Skips creation if a 'venv' directory already exists.
    """
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
    """
    Installs dependencies from a requirements file into the virtual environment.
    This function parses the output of the 'pip install' command in real-time
    to provide accurate progress updates for both the 'collecting' and 'installing'
    phases of the operation.
    """
    venv_python = (
        ui_dir / "venv" / "Scripts" / "python.exe"
        if sys.platform == "win32"
        else ui_dir / "venv" / "bin" / "python"
    )
    req_path = ui_dir / requirements_file

    if not venv_python.exists():
        logger.error(f"Virtual environment Python executable not found for {ui_dir.name}.")
        return False
    if not req_path.exists():
        logger.error(f"Requirements file '{requirements_file}' not found in {ui_dir.name}.")
        return False

    # The single command for installation. Its output will be parsed directly.
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

    process = await asyncio.create_subprocess_exec(
        *pip_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    logger.info(f"Starting pip install ({process.pid}) and parsing output in real-time.")

    # Regex patterns to parse pip's output.
    collect_regex = re.compile(r"^\s*Collecting\s+([a-zA-Z0-9-_.]+)", re.IGNORECASE)
    install_regex = re.compile(r"^\s*Installing collected packages:.*", re.IGNORECASE)

    collected_packages = []
    in_install_phase = False

    async def read_and_parse_stream(stream):
        """Reads and parses a stream (stdout/stderr) line-by-line for progress."""
        nonlocal in_install_phase

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

                if progress_callback:
                    # Phase 1: Collecting packages.
                    collect_match = collect_regex.match(line)
                    if collect_match and not in_install_phase:
                        package_name = collect_match.group(1)
                        if package_name not in collected_packages:
                            collected_packages.append(package_name)
                            # Send the number of packages found so far, and -1 for the total
                            # to signal that the total is not yet known.
                            await progress_callback(
                                "collecting", len(collected_packages), -1, package_name
                            )
                        continue

                    # Phase 2: Transition to Installing packages.
                    install_match = install_regex.match(line)
                    if install_match and not in_install_phase:
                        in_install_phase = True
                        # Now we have the complete list of packages.
                        # Signal the start of the installation phase with the correct total.
                        await progress_callback(
                            "installing", 0, len(collected_packages), "Starting installation..."
                        )
                        continue

            except Exception as e:
                logger.warning(f"Error reading pip stream line: {e}")
                break

    # Process stdout and stderr concurrently.
    await asyncio.gather(
        read_and_parse_stream(process.stdout), read_and_parse_stream(process.stderr)
    )

    await process.wait()

    if process.returncode == 0 and progress_callback:
        # On success, send a final update to ensure the progress bar completes.
        total = len(collected_packages) if collected_packages else 1
        await progress_callback("installing", total, total, "Installation complete.")
        logger.info(f"Pip install process {process.pid} completed successfully.")
    elif process.returncode != 0:
        logger.error(f"Pip installation failed with exit code {process.returncode}.")

    return process.returncode == 0
