# backend/core/ui_management/ui_installer.py
import asyncio
import logging
import pathlib
import sys
import re
import json
import tempfile
from typing import Callable, Coroutine, Any, Optional, Literal, List, Dict, Tuple

# --- Type Definitions ---
StreamCallback = Callable[[str], Coroutine[Any, Any, None]]
PipPhase = Literal["collecting", "installing"]
PipProgressCallback = Callable[[PipPhase, int, int, str, Optional[int]], Coroutine[Any, Any, None]]
# A callback to signal that a process has been created, passing the process object.
ProcessCreatedCallback = Callable[[asyncio.subprocess.Process], None]


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


async def _get_dependency_report(
    venv_python: pathlib.Path,
    req_path: pathlib.Path,
    extra_packages: Optional[List[str]],
    progress_callback: Optional[PipProgressCallback],
) -> Dict[str, Any]:
    """
    Runs a pip dry-run with a JSON report. It parses the command's stderr in
    real-time to provide progress updates during the dependency resolution phase.
    """
    report = {}
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tmp_report_file:
        report_path = pathlib.Path(tmp_report_file.name)

    try:
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

        logger.info(f"Generating dependency report with command: {' '.join(command)}")
        process = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        collect_regex = re.compile(r"^\s*Collecting\s+([a-zA-Z0-9-_.]+)", re.IGNORECASE)
        packages_found = []

        async def read_analysis_stream(stream, is_stderr: bool):
            """Reads a stream, parsing only stderr for progress updates."""
            while not stream.at_eof():
                try:
                    line_bytes = await stream.readline()
                    if not line_bytes:
                        break
                    line = line_bytes.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue

                    if is_stderr and progress_callback:
                        collect_match = collect_regex.match(line)
                        if collect_match:
                            package_name = collect_match.group(1)
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
            logger.error(
                f"Failed to generate dependency report. Pip exited with code {process.returncode}."
            )
            return {}

        if report_path.exists() and report_path.stat().st_size > 0:
            with open(report_path, "r") as f:
                report = json.load(f)
            logger.info(
                f"Successfully generated dependency report with {len(report.get('install', []))} items."
            )
        else:
            logger.warning("Dependency report was not generated or is empty.")

    finally:
        if report_path.exists():
            report_path.unlink()

    return report


async def install_dependencies(
    ui_dir: pathlib.Path,
    requirements_file: str,
    stream_callback: Optional[StreamCallback] = None,
    progress_callback: Optional[PipProgressCallback] = None,
    extra_packages: Optional[List[str]] = None,
    process_created_callback: Optional[ProcessCreatedCallback] = None,
) -> bool:
    """
    Installs dependencies from a requirements file into a venv.

    This function uses a two-stage process to provide accurate, size-weighted
    progress. First, it generates a report to calculate the total download size,
    then it installs the packages while tracking progress against that total.

    Args:
        ui_dir: The root directory of the UI environment.
        requirements_file: The name of the requirements file (e.g., 'requirements.txt').
        stream_callback: An async callback to stream raw process output.
        progress_callback: An async callback for structured progress updates.
        extra_packages: A list of additional packages to install.
        process_created_callback: A callback that receives the process object
                                  immediately after it's created, allowing the
                                  caller to manage or terminate it.
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

    report = await _get_dependency_report(venv_python, req_path, extra_packages, progress_callback)
    install_targets = report.get("install", [])

    if not install_targets:
        logger.info("Dependencies are already satisfied.")
        if progress_callback:
            await progress_callback("installing", 1, 1, "Dependencies already satisfied.", 0)
        return True

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

    # Immediately pass the created process object to the caller if a callback is provided.
    # This is crucial for allowing the caller to terminate the process if needed.
    if process_created_callback:
        process_created_callback(process)

    logger.info(
        f"Starting actual pip install ({process.pid}) with a total download size of {total_download_size} bytes."
    )

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
                    collect_match = collect_regex.match(line)
                    if collect_match:
                        package_name = collect_match.group(1).lower().replace("_", "-")
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
        logger.info("All packages seem to be cached. Simulating collection progress.")
        total_packages = len(package_info)
        for i, (name, info) in enumerate(package_info.items()):
            await progress_callback(
                "collecting",
                i + 1,
                total_packages,
                f"{name.capitalize()} {info['version']}",
                0,
            )
            await asyncio.sleep(0.01)

    await asyncio.gather(
        read_and_parse_stream(process.stdout), read_and_parse_stream(process.stderr)
    )
    await process.wait()

    if process.returncode == 0 and progress_callback:
        await progress_callback("installing", 0, 1, "Finalizing installation...", 0)
        await asyncio.sleep(1)
        await progress_callback("installing", 1, 1, "Installation complete.", 0)
        logger.info(f"Pip install process {process.pid} completed successfully.")
    elif process.returncode != 0:
        logger.error(f"Pip installation failed with exit code {process.returncode}.")

    return process.returncode == 0
