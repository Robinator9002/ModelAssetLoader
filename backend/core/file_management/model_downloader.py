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
        revision: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Downloads a model file asynchronously using streaming to report progress.
        """
        logger.info(f"Starting download task {download_id} for '{hf_filename}' from '{repo_id}'.")

        # --- REFACTOR: Using httpx for streaming and manual progress tracking ---
        try:
            # 1. Get the direct download URL from Hugging Face
            download_url = hf_hub_url(repo_id=repo_id, filename=hf_filename, revision=revision, repo_type="model")

            async with httpx.AsyncClient(follow_redirects=True, timeout=None) as client:
                async with client.stream("GET", download_url) as response:
                    # Raise an exception for bad status codes (4xx or 5xx)
                    response.raise_for_status()

                    # 2. Get total file size from headers
                    total_size_str = response.headers.get("content-length")
                    if total_size_str is None:
                        logger.warning(f"[{download_id}] Content-Length header not found. Progress will be unavailable.")
                        total_size = 0
                    else:
                        total_size = int(total_size_str)

                    # 3. Download in chunks to a temporary file
                    downloaded_bytes = 0
                    # Create a temporary file to avoid incomplete files in the target directory
                    with tempfile.NamedTemporaryFile(delete=False, mode='wb', dir=target_directory.parent) as tmp_file:
                        tmp_file_path = Path(tmp_file.name)
                        async for chunk in response.aiter_bytes():
                            tmp_file.write(chunk)
                            downloaded_bytes += len(chunk)
                            # Report progress to the tracker
                            await download_tracker.update_progress(download_id, downloaded_bytes, total_size)

            # 4. Once download is complete, move the temporary file to its final destination
            final_local_path = target_directory / hf_filename
            final_local_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(tmp_file_path, final_local_path)

            await download_tracker.complete_download(download_id, str(final_local_path))
            logger.info(f"[{download_id}] File '{hf_filename}' downloaded and moved to '{final_local_path}'.")

            return {
                "success": True,
                "message": f"File '{os.path.basename(hf_filename)}' downloaded successfully.",
                "path": str(final_local_path)
            }
        
        # Specific Hugging Face errors that can occur when resolving the URL
        except (RepositoryNotFoundError, EntryNotFoundError, GatedRepoError) as e:
            error_message = f"Hugging Face API Error: {e}"
            logger.error(f"[{download_id}] {error_message}", exc_info=True)
            await download_tracker.fail_download(download_id, error_message)
            return {"success": False, "error": error_message}
        
        # HTTP errors during download
        except httpx.HTTPStatusError as e:
            error_message = f"HTTP Error {e.response.status_code} while downloading file: {e.response.text}"
            logger.error(f"[{download_id}] {error_message}", exc_info=True)
            await download_tracker.fail_download(download_id, error_message)
            return {"success": False, "error": error_message}

        # Any other exceptions
        except Exception as e:
            logger.error(f"[{download_id}] An unexpected download error occurred for '{hf_filename}': {e}", exc_info=True)
            error_message = f"An unexpected error occurred: {str(e)}"
            await download_tracker.fail_download(download_id, error_message)
            return {"success": False, "error": error_message}
        finally:
            # Ensure temporary file is cleaned up in case of an error during the move
            if 'tmp_file_path' in locals() and tmp_file_path.exists():
                os.remove(tmp_file_path)
