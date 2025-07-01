# backend/core/file_management/model_downloader.py
import logging
import os
import shutil
import asyncio
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

import httpx  # Using httpx for async streaming downloads
from huggingface_hub import hf_hub_url
from huggingface_hub.utils import RepositoryNotFoundError, EntryNotFoundError, GatedRepoError

from .download_tracker import download_tracker

logger = logging.getLogger(__name__)

class ModelDownloader:
    """Handles the logic of downloading model files, now with proper progress tracking."""

    async def download_model_file(
        self,
        download_id: str,
        repo_id: str,
        hf_filename: str,
        target_directory: Path,
        target_filename_override: Optional[str] = None, # FIXED: Added the missing argument
        revision: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Downloads a model file asynchronously using streaming to report progress.
        """
        # --- FIXED: Determine the final filename to be used for saving ---
        # If an override is provided (e.g., the sanitized name), use it.
        # Otherwise, fall back to the original filename from the repository.
        final_filename = target_filename_override or hf_filename
        
        logger.info(f"Starting download task {download_id} for '{hf_filename}' from '{repo_id}' -> saving as '{final_filename}'.")

        try:
            # 1. Get the direct download URL from Hugging Face using the original hf_filename
            download_url = hf_hub_url(repo_id=repo_id, filename=hf_filename, revision=revision, repo_type="model")

            async with httpx.AsyncClient(follow_redirects=True, timeout=None) as client:
                async with client.stream("GET", download_url) as response:
                    response.raise_for_status()

                    # 2. Get total file size from headers
                    total_size = int(response.headers.get("content-length", 0))

                    # 3. Download in chunks to a temporary file
                    downloaded_bytes = 0
                    with tempfile.NamedTemporaryFile(delete=False, mode='wb', dir=target_directory.parent) as tmp_file:
                        tmp_file_path = Path(tmp_file.name)
                        async for chunk in response.aiter_bytes():
                            tmp_file.write(chunk)
                            downloaded_bytes += len(chunk)
                            await download_tracker.update_progress(download_id, downloaded_bytes, total_size)

            # 4. Once download is complete, move the temporary file to its final destination
            #    using the determined final_filename.
            final_local_path = target_directory / final_filename
            final_local_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(tmp_file_path, final_local_path)

            await download_tracker.complete_download(download_id, str(final_local_path))
            logger.info(f"[{download_id}] File '{hf_filename}' downloaded and moved to '{final_local_path}'.")

            return {
                "success": True,
                "message": f"File '{os.path.basename(final_filename)}' downloaded successfully.",
                "path": str(final_local_path)
            }
        
        except (RepositoryNotFoundError, EntryNotFoundError, GatedRepoError) as e:
            error_message = f"Hugging Face API Error: {e}"
            logger.error(f"[{download_id}] {error_message}", exc_info=True)
            await download_tracker.fail_download(download_id, error_message)
            return {"success": False, "error": error_message}
        
        except httpx.HTTPStatusError as e:
            error_message = f"HTTP Error {e.response.status_code} while downloading file: {e.response.text}"
            logger.error(f"[{download_id}] {error_message}", exc_info=True)
            await download_tracker.fail_download(download_id, error_message)
            return {"success": False, "error": error_message}

        except Exception as e:
            error_message = f"An unexpected error occurred: {str(e)}"
            logger.error(f"[{download_id}] An unexpected download error occurred for '{hf_filename}': {e}", exc_info=True)
            await download_tracker.fail_download(download_id, error_message)
            return {"success": False, "error": error_message}
        finally:
            # Ensure temporary file is cleaned up in case of an error during the move
            if 'tmp_file_path' in locals() and tmp_file_path.exists():
                try:
                    os.remove(tmp_file_path)
                except OSError as e:
                    logger.error(f"Error removing temporary file {tmp_file_path}: {e}")
