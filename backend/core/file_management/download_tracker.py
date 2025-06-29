# backend/core/file_management/download_tracker.py
import uuid
import logging
import asyncio
from typing import Dict, Any, Optional, Callable, Coroutine, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Define a type for the async callback function that broadcasts updates
BroadcastCallable = Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]

@dataclass
class DownloadStatus:
    """Holds the state and metadata of a single download task."""
    download_id: str
    filename: str
    repo_id: str
    status: str = "pending"  # pending, downloading, completed, error
    progress: float = 0.0  # Percentage (0.0 to 100.0)
    total_size_bytes: int = 0
    downloaded_bytes: int = 0
    error_message: Optional[str] = None
    target_path: Optional[str] = None

class DownloadTracker:
    """
    A singleton-like class to track the status of all active downloads.
    This provides a central in-memory store for download progress, which
    can be used to broadcast updates via WebSockets.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(DownloadTracker, cls).__new__(cls)
            cls._instance.active_downloads: Dict[str, DownloadStatus] = {}
            cls._instance.broadcast_callback: Optional[BroadcastCallable] = None
        return cls._instance

    def set_broadcast_callback(self, callback: BroadcastCallable):
        """
        Sets the asynchronous callback function used to broadcast updates.
        This will typically be a function that sends data over a WebSocket.
        """
        self.broadcast_callback = callback
        logger.info("DownloadTracker: Broadcast callback has been set.")

    async def _broadcast(self, download_status: DownloadStatus):
        """If a callback is set, broadcast the download status."""
        if self.broadcast_callback:
            try:
                await self.broadcast_callback(download_status.__dict__)
            except Exception as e:
                logger.error(f"Error during broadcast for download {download_status.download_id}: {e}", exc_info=True)

    def start_tracking(self, repo_id: str, filename: str) -> DownloadStatus:
        """
        Registers a new download to be tracked and returns its initial status.
        
        Returns:
            The initial DownloadStatus object for the new download.
        """
        download_id = str(uuid.uuid4())
        status = DownloadStatus(
            download_id=download_id,
            filename=filename,
            repo_id=repo_id,
            status="pending"
        )
        self.active_downloads[download_id] = status
        logger.info(f"Started tracking download {download_id} for '{filename}'.")
        # No broadcast here; the initial state is sent when a client connects.
        return status

    async def update_progress(self, download_id: str, downloaded_bytes: int, total_size: int):
        """Updates the progress of a specific download."""
        if download_id in self.active_downloads:
            status = self.active_downloads[download_id]
            status.status = "downloading"
            status.downloaded_bytes = downloaded_bytes
            status.total_size_bytes = total_size
            if total_size > 0:
                status.progress = round((downloaded_bytes / total_size) * 100, 2)
            
            # Broadcast the update
            await self._broadcast(status)
        else:
            logger.warning(f"Attempted to update progress for untracked download_id: {download_id}")

    async def complete_download(self, download_id: str, final_path: str):
        """Marks a download as successfully completed."""
        if download_id in self.active_downloads:
            status = self.active_downloads[download_id]
            status.status = "completed"
            status.progress = 100.0
            status.target_path = final_path
            logger.info(f"Download {download_id} completed successfully. Path: {final_path}")
            
            await self._broadcast(status)
            
            # Optional: Remove completed download after a delay to allow UI to show "completed" state
            await asyncio.sleep(30) # Let it linger for 30s
            if download_id in self.active_downloads and self.active_downloads[download_id].status == "completed":
                del self.active_downloads[download_id]
                logger.info(f"Removed completed download {download_id} from tracking.")

    async def fail_download(self, download_id: str, error_message: str):
        """Marks a download as failed."""
        if download_id in self.active_downloads:
            status = self.active_downloads[download_id]
            status.status = "error"
            status.error_message = error_message
            logger.error(f"Download {download_id} failed: {error_message}")

            await self._broadcast(status)

    def get_all_statuses(self) -> List[Dict[str, Any]]:
        """Returns the status of all currently tracked downloads."""
        return [status.__dict__ for status in self.active_downloads.values()]

# Create a single, shared instance of the tracker
download_tracker = DownloadTracker()
