# backend/core/file_management/download_tracker.py
import uuid
import logging
import asyncio
from typing import (
    Dict,
    Any,
    Optional,
    Callable,
    Coroutine,
    List,
    Literal,
)
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# --- Define a strict type for download/task states ---
DownloadState = Literal["pending", "downloading", "running", "completed", "error", "cancelled"]

BroadcastCallable = Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]


@dataclass
class DownloadStatus:
    """Holds the state and metadata of a single download or background task."""

    download_id: str
    filename: str
    repo_id: str
    status: DownloadState = "pending"
    progress: float = 0.0
    total_size_bytes: int = 0
    downloaded_bytes: int = 0
    error_message: Optional[str] = None
    target_path: Optional[str] = None
    task: Optional[asyncio.Task] = field(default=None, repr=False, compare=False)

    def to_dict(self) -> Dict[str, Any]:
        """Converts the dataclass to a dictionary, excluding the task object."""
        return {
            "download_id": self.download_id,
            "filename": self.filename,
            "repo_id": self.repo_id,
            "status": self.status,
            "progress": self.progress,
            "total_size_bytes": self.total_size_bytes,
            "downloaded_bytes": self.downloaded_bytes,
            "error_message": self.error_message,
            "target_path": self.target_path,
        }


class DownloadTracker:
    """A singleton-like class to track and manage all active downloads and tasks."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(DownloadTracker, cls).__new__(cls)
            cls._instance.active_downloads = {}
            cls._instance.broadcast_callback = None
        return cls._instance

    def set_broadcast_callback(self, callback: Optional[BroadcastCallable]):
        self.broadcast_callback = callback
        logger.info(
            f"DownloadTracker: Broadcast callback has been {'set' if callback else 'cleared'}."
        )

    async def _broadcast(self, data: Dict[str, Any]):
        if self.broadcast_callback:
            try:
                await self.broadcast_callback(data)
            except Exception as e:
                logger.error(f"Error during broadcast: {e}", exc_info=True)

    def start_tracking(
        self, download_id: str, repo_id: str, filename: str, task: asyncio.Task
    ) -> DownloadStatus:
        """Registers a new download/task. This is a synchronous operation."""
        status = DownloadStatus(
            download_id=download_id, filename=filename, repo_id=repo_id, status="pending", task=task
        )
        self.active_downloads[download_id] = status
        logger.info(f"Started tracking download {download_id} for '{filename}'.")
        asyncio.create_task(self._broadcast({"type": "update", "data": status.to_dict()}))
        return status

    async def update_progress_from_bytes(
        self, download_id: str, downloaded_bytes: int, total_size: int
    ):
        """Updates progress based on byte counts, for file downloads."""
        if download_id in self.active_downloads:
            status = self.active_downloads[download_id]
            if status.status not in ["downloading", "running"]:
                status.status = "downloading"
            status.downloaded_bytes = downloaded_bytes
            status.total_size_bytes = total_size
            status.progress = (
                round((downloaded_bytes / total_size) * 100, 2) if total_size > 0 else 0
            )
            await self._broadcast({"type": "update", "data": status.to_dict()})

    async def update_task_progress(
        self,
        task_id: str,
        progress: float,
        status_text: Optional[str] = None,
        new_status: Optional[DownloadState] = None,
    ):
        """Updates progress for a multi-step task and can optionally update its state."""
        if task_id in self.active_downloads:
            status = self.active_downloads[task_id]

            # --- FIX: Allow updating the status field directly ---
            if new_status:
                status.status = new_status
            elif status.status not in ["downloading", "running"]:
                status.status = "downloading"

            status.progress = round(progress, 2)
            if status_text:
                status.error_message = status_text  # Use error_message to convey status text

            await self._broadcast({"type": "update", "data": status.to_dict()})

    async def complete_download(self, download_id: str, final_path: str):
        if download_id in self.active_downloads:
            status = self.active_downloads[download_id]
            status.status = "completed"
            status.progress = 100.0
            status.target_path = final_path
            logger.info(f"Download {download_id} completed. Path: {final_path}")
            await self._broadcast({"type": "update", "data": status.to_dict()})

    async def fail_download(self, download_id: str, error_message: str, cancelled: bool = False):
        if download_id in self.active_downloads:
            status = self.active_downloads[download_id]
            status.status = "cancelled" if cancelled else "error"
            status.error_message = error_message
            logger.error(f"Download {download_id} failed/cancelled: {error_message}")
            await self._broadcast({"type": "update", "data": status.to_dict()})

    async def cancel_and_remove(self, download_id: str):
        if download_id in self.active_downloads:
            status = self.active_downloads[download_id]
            if status.task and not status.task.done():
                logger.info(f"Requesting cancellation for download task {download_id}.")
                status.task.cancel()
            else:
                logger.warning(
                    f"Cancellation for {download_id} requested, but task is not running."
                )

    async def remove_download(self, download_id: str):
        if download_id in self.active_downloads:
            logger.info(f"Removing download {download_id} from tracking.")
            del self.active_downloads[download_id]
            await self._broadcast({"type": "remove", "download_id": download_id})

    def get_all_statuses(self) -> List[Dict[str, Any]]:
        return [status.to_dict() for status in self.active_downloads.values()]


download_tracker = DownloadTracker()
