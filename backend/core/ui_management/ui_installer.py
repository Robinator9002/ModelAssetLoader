# backend/core/ui_management/ui_installer.py
import asyncio
import logging
import pathlib
import sys
from typing import Callable, Coroutine, Any, Optional

# --- Type definition for a callback that can stream process output ---
# This allows the caller (the UiManager) to receive real-time updates.
StreamCallback = Callable[[str], Coroutine[Any, Any, None]]

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
    """
    Clones a Git repository into a specified directory.

    Args:
        git_url: The URL of the repository to clone.
        target_dir: The destination path for the repository.
        stream_callback: Callback for streaming command output.

    Returns:
        True if cloning was successful, False otherwise.
    """
    if target_dir.exists() and any(target_dir.iterdir()):
        logger.warning(
            f"Target directory {target_dir} already exists and is not empty. Skipping clone."
        )
        if stream_callback:
            await stream_callback(f"Directory {target_dir.name} already exists. Skipping clone.")
        return True  # Treat as success if it's already there

    logger.info(f"Cloning '{git_url}' into '{target_dir}'...")
    target_dir.mkdir(parents=True, exist_ok=True)

    # Use --depth 1 to get only the latest version, saving time and space.
    # Use --progress to get real-time feedback from git.
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
    Creates a Python virtual environment inside the UI's directory.

    Args:
        ui_dir: The root directory of the cloned UI.
        stream_callback: Callback for streaming command output.

    Returns:
        True if venv creation was successful, False otherwise.
    """
    venv_path = ui_dir / "venv"
    if venv_path.exists():
        logger.info(f"Virtual environment already exists at '{venv_path}'. Skipping.")
        if stream_callback:
            await stream_callback("Virtual environment already exists. Skipping.")
        return True

    logger.info(f"Creating virtual environment in '{venv_path}'...")
    # sys.executable gives us the path to the current Python interpreter
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
) -> bool:
    """
    Installs dependencies from a requirements.txt file into the UI's venv.

    Args:
        ui_dir: The root directory of the cloned UI.
        requirements_file: The name of the requirements file.
        stream_callback: Callback for streaming command output.

    Returns:
        True if installation was successful, False otherwise.
    """
    venv_python = (
        ui_dir / "venv" / "Scripts" / "python.exe"
        if sys.platform == "win32"
        else ui_dir / "venv" / "bin" / "python"
    )
    req_path = ui_dir / requirements_file

    if not venv_python.exists():
        logger.error(f"Venv Python not found at '{venv_python}'. Cannot install.")
        return False
    if not req_path.exists():
        logger.error(f"Requirements file not found at '{req_path}'. Cannot install.")
        return False

    logger.info(f"Installing dependencies from '{req_path}'...")
    process = await asyncio.create_subprocess_exec(
        str(venv_python),
        "-m",
        "pip",
        "install",
        "-r",
        str(req_path),
        "--no-cache-dir",  # Avoids caching issues
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    return_code, _ = await _stream_process(process, stream_callback)
    return return_code == 0


# --- Standalone Test Runner ---
# This allows us to test the installer logic directly from the command line
# without needing the full FastAPI application.
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

    # Example usage: python -m backend.core.ui_management.ui_installer
    async def main():
        print("--- M.A.L. UI Installer Standalone Test ---")
        test_dir = pathlib.Path("./temp_install_test")
        if test_dir.exists():
            import shutil

            print(f"Removing old test directory: {test_dir}")
            shutil.rmtree(test_dir)
        test_dir.mkdir()

        print(f"\n[1] Cloning ComfyUI into {test_dir}...")

        async def simple_streamer(line: str):
            print(f"  > {line}")

        success = await clone_repo(
            "https://github.com/comfyanonymous/ComfyUI.git",
            test_dir / "ComfyUI",
            simple_streamer,
        )
        if not success:
            print("\n--- TEST FAILED: CLONE ---")
            return

        print("\n--- CLONE SUCCEEDED ---")

        print(f"\n[2] Creating venv in {test_dir / 'ComfyUI'}...")
        success = await create_venv(test_dir / "ComfyUI", simple_streamer)
        if not success:
            print("\n--- TEST FAILED: VENV ---")
            return

        print("\n--- VENV SUCCEEDED ---")

        print(f"\n[3] Installing dependencies...")
        success = await install_dependencies(
            test_dir / "ComfyUI", "requirements.txt", simple_streamer
        )
        if not success:
            print("\n--- TEST FAILED: PIP INSTALL ---")
            return

        print("\n--- PIP INSTALL SUCCEEDED ---")
        print("\n--- ALL TESTS PASSED ---")

    asyncio.run(main())
