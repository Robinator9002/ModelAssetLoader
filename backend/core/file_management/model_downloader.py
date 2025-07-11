# backend/core/file_management/model_downloader.py
import logging
import os
import shutil
import asyncio
import tempfile
from pathlib import Path
from typing import Optional

import httpx
from huggingface_hub import hf_hub_url
from huggingface_hub.utils import (
    RepositoryNotFoundError,
    EntryNotFoundError,
    GatedRepoError,
)

from .download_tracker import download_tracker

logger = logging.getLogger(__name__)


class ModelDownloader:
    """Handles the logic of downloading model files, with cancellation support."""

    async def download_model_file(
        self,
        download_id: str,
        repo_id: str,
        hf_filename: str,
        target_directory: Path,
        target_filename_override: Optional[str] = None,
        revision: Optional[str] = None,
    ):
        final_filename = target_filename_override or hf_filename
        logger.info(
            f"Starting download task {download_id} for '{hf_filename}' -> '{final_filename}'."
        )

        tmp_file_path: Optional[Path] = None
        try:
            download_url = hf_hub_url(
                repo_id=repo_id, filename=hf_filename, revision=revision, repo_type="model"
            )

            async with httpx.AsyncClient(follow_redirects=True, timeout=None) as client:
                async with client.stream("GET", download_url) as response:
                    response.raise_for_status()
                    total_size = int(response.headers.get("content-length", 0))

                    with tempfile.NamedTemporaryFile(
                        delete=False, mode="wb", dir=target_directory.parent
                    ) as tmp_file:
                        tmp_file_path = Path(tmp_file.name)
                        downloaded_bytes = 0

                        # Define a blocking write function to be run in a thread
                        def write_chunk(chunk):
                            tmp_file.write(chunk)

                        async for chunk in response.aiter_bytes():
                            # --- FIXED: Run the blocking write operation in a separate thread ---
                            # This unblocks the event loop, allowing it to send WebSocket updates.
                            await asyncio.to_thread(write_chunk, chunk)

                            downloaded_bytes += len(chunk)
                            # --- FIXED: Call the correct, purpose-built tracker method ---
                            await download_tracker.update_progress_from_bytes(
                                download_id, downloaded_bytes, total_size
                            )

            final_local_path = target_directory / final_filename
            final_local_path.parent.mkdir(parents=True, exist_ok=True)

            # The move operation can also be blocking for large files
            await asyncio.to_thread(shutil.move, tmp_file_path, final_local_path)
            tmp_file_path = None  # Prevent deletion in finally block

            await download_tracker.complete_download(download_id, str(final_local_path))

        except asyncio.CancelledError:
            logger.warning(f"Download {download_id} was cancelled by the user.")
            await download_tracker.fail_download(
                download_id, "Download cancelled by user.", cancelled=True
            )
            raise
        except (RepositoryNotFoundError, EntryNotFoundError, GatedRepoError) as e:
            await download_tracker.fail_download(download_id, f"Hugging Face API Error: {e}")
        except httpx.HTTPStatusError as e:
            await download_tracker.fail_download(
                download_id, f"HTTP Error {e.response.status_code}"
            )
        except Exception as e:
            logger.error(f"Unexpected download error for '{hf_filename}': {e}", exc_info=True)
            await download_tracker.fail_download(download_id, f"An unexpected error occurred: {e}")
        finally:
            if tmp_file_path and tmp_file_path.exists():
                logger.info(
                    f"Cleaning up temporary file {tmp_file_path} for cancelled/failed download."
                )
                # This is also blocking, so run it in a thread
                await asyncio.to_thread(os.remove, tmp_file_path)
