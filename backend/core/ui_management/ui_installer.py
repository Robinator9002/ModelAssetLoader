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
    output_lines = []

    async def read_stream(stream, stream_name):
        while not stream.at_eof():
            try:
                line_bytes = await stream.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace").strip()
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
        "--no-cache-dir",
    ]

    if extra_packages:
        logger.info(f"Installing extra packages: {extra_packages}")
        pip_command.extend(extra_packages)

    phase: PipPhase = "collecting"
    try:
        with open(req_path, "r", encoding="utf-8") as f:
            top_level_packages = [
                line.strip() for line in f if line.strip() and not line.startswith("#")
            ]
            top_level_total = len(top_level_packages)
            if extra_packages:
                top_level_total += len(extra_packages)
    except Exception:
        top_level_total = 1

    processed_count = 0

    collect_regex = re.compile(r"Collecting\s+([a-zA-Z0-9-_.]+)")
    installing_regex = re.compile(r"Installing collected packages:\s+(.*)")

    async def pip_streamer(line: str):
        nonlocal phase, processed_count

        if stream_callback:
            await stream_callback(line)

        if phase == "collecting":
            collect_match = collect_regex.match(line)
            if collect_match:
                processed_count += 1
                package_name = collect_match.group(1).strip()
                if progress_callback:
                    await progress_callback(
                        "collecting", processed_count, top_level_total, package_name
                    )

            installing_match = installing_regex.match(line)
            if installing_match:
                phase = "installing"
                packages_to_install = [p.strip() for p in installing_match.group(1).split(",")]
                install_packages_total = len(packages_to_install)

                logger.info(
                    f"Switched to 'installing' phase. {install_packages_total} packages to install."
                )

                async def progress_ticker():
                    """This ticker simulates the installation progress smoothly."""
                    for i in range(1, install_packages_total + 1):
                        if process.returncode is not None:
                            break  # Stop if the main process has already finished

                        # Update the frontend
                        if progress_callback:
                            status_text = f"Installing {i}/{install_packages_total}"
                            await progress_callback(
                                "installing", i, install_packages_total, status_text
                            )

                        # Calculate a short delay to make the progress bar move smoothly
                        await asyncio.sleep(0.1)

                if install_packages_total > 0:
                    asyncio.create_task(progress_ticker())

    process = await asyncio.create_subprocess_exec(
        *pip_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    return_code, _ = await _stream_process(process, pip_streamer)
    return return_code == 0
