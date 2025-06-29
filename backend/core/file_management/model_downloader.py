# backend/core/file_management/model_downloader.py
import logging
import os
import pathlib
import shutil
from typing import Dict, Any, Optional

from huggingface_hub import hf_hub_download
from huggingface_hub.utils import RepositoryNotFoundError, EntryNotFoundError, GatedRepoError

logger = logging.getLogger(__name__)

class ModelDownloader:
    """Handles downloading model files from Hugging Face Hub."""

    def download_model_file(
        self,
        repo_id: str,
        hf_filename: str,          # Filename on the Hub, can include subdirs
        target_directory: pathlib.Path,
        revision: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Downloads a model file and places it in the specified target directory.

        Args:
            repo_id: The Hugging Face repository ID (e.g., "author/model_name").
            hf_filename: The file path within the repository to download.
            target_directory: The pre-determined local directory to save the file in.
            revision: The specific git revision (branch, tag, commit hash) to use.

        Returns:
            A dictionary indicating the outcome of the download operation.
        """
        try:
            logger.info(f"Downloading '{hf_filename}' from repo '{repo_id}' (revision: {revision or 'main'}).")

            # hf_hub_download fetches the file to a central cache directory.
            cached_file_path = hf_hub_download(
                repo_id=repo_id,
                filename=hf_filename,
                revision=revision,
                repo_type="model",
                local_dir_use_symlinks=False # Use copies for better cross-drive compatibility
            )
            logger.info(f"File cached at: {cached_file_path}")

            # The final local path should preserve any subdirectory structure from the Hub filename.
            # e.g., if hf_filename is "unet/model.bin", it creates a "unet" subdir.
            final_local_path = target_directory / hf_filename

            # Ensure the parent directory for the final file exists.
            final_local_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy the file from the HF cache to our organized library.
            shutil.copy2(cached_file_path, final_local_path)
            logger.info(f"Successfully copied file to '{final_local_path}'.")

            return {
                "success": True,
                "message": f"File '{os.path.basename(hf_filename)}' downloaded to '{final_local_path.parent}'.",
                "path": str(final_local_path)
            }
        except RepositoryNotFoundError:
            return {"success": False, "error": f"Repository '{repo_id}' not found."}
        except EntryNotFoundError:
            return {"success": False, "error": f"File '{hf_filename}' not found in repo '{repo_id}'."}
        except GatedRepoError:
            return {"success": False, "error": f"Repo '{repo_id}' is gated. Please agree to terms on Hugging Face Hub."}
        except Exception as e:
            logger.error(f"Download error for '{hf_filename}' from '{repo_id}': {e}", exc_info=True)
            return {"success": False, "error": f"An unexpected download error occurred: {str(e)}"}
