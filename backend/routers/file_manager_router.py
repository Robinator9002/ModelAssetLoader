# backend/routers/file_manager_router.py
import logging
from typing import Optional

# --- REFACTOR: Import Depends for dependency injection ---
from fastapi import APIRouter, HTTPException, Query, status, Depends
from pydantic import BaseModel

# --- API Model Imports ---
from api.models import (
    MalFullConfiguration,
    PathConfigurationRequest,
    PathConfigurationResponse,
    FileDownloadRequest,
    FileDownloadResponse,
    ScanHostDirectoriesResponse,
    FileManagerListResponse,
    LocalFileActionRequest,
    LocalFileContentResponse,
)

# --- REFACTOR: Import the provider function and the service class for type hinting ---
from dependencies import get_file_manager
from core.services.file_manager import FileManager

# --- NEW: Import custom error classes for standardized handling ---
from core.errors import MalError, OperationFailedError, BadRequestError

logger = logging.getLogger(__name__)


# --- Pydantic models for request bodies specific to this router ---
class DownloadTaskRequest(BaseModel):
    """Request model for actions targeting a download task by its ID."""

    download_id: str


# --- Router Definition ---
router = APIRouter(
    prefix="/api/filemanager",
    tags=["FileManager"],
)


# --- Endpoint Definitions ---


@router.get(
    "/configuration",
    response_model=MalFullConfiguration,
    summary="Get Current FileManager Configuration",
)
async def get_config_endpoint(fm: FileManager = Depends(get_file_manager)):
    """
    Returns the full, current application configuration.
    The FileManager instance is now injected by FastAPI.
    """
    # This endpoint currently doesn't have a try...except block to refactor,
    # as fm.get_current_configuration() is expected to always return a config.
    return MalFullConfiguration(**fm.get_current_configuration())


@router.post(
    "/configure",
    response_model=PathConfigurationResponse,
    summary="Configure FileManager Paths and Settings",
)
async def configure_paths_endpoint(
    config_request: PathConfigurationRequest, fm: FileManager = Depends(get_file_manager)
):
    """
    Configures the application's base paths and model folder structure.
    Delegates the logic to the injected file_manager service.
    """
    # This currently relies on a success boolean from the service.
    # Once fm.configure_paths is refactored to raise MalError, this
    # block will be updated to catch MalError.
    success, message = fm.configure_paths(
        base_path_str=config_request.base_path,
        profile=config_request.profile,
        custom_model_type_paths=config_request.custom_model_type_paths,
        color_theme=config_request.color_theme,
        config_mode=config_request.config_mode,
        automatic_mode_ui=config_request.automatic_mode_ui,
    )
    if not success:
        # For now, keep as HTTPException. This will be refactored once
        # the underlying service raises BadRequestError or similar.
        raise HTTPException(status_code=400, detail=message)
    return PathConfigurationResponse(
        success=True,
        message=message,
        current_config=MalFullConfiguration(**fm.get_current_configuration()),
    )


@router.post(
    "/download",
    response_model=FileDownloadResponse,
    summary="Download a Model File",
)
async def download_file_endpoint(
    download_request: FileDownloadRequest, fm: FileManager = Depends(get_file_manager)
):
    """Initiates a model file download as a background task."""
    if not fm.base_path:
        # This is a specific validation, can remain as HTTPException
        raise HTTPException(status_code=400, detail="Base path not configured.")
    # This currently relies on a success dictionary from the service.
    # Once fm.start_download_model_file is refactored to raise MalError,
    # this block will be updated to catch MalError.
    result = fm.start_download_model_file(
        source=download_request.source,
        repo_id=download_request.repo_id,
        filename=download_request.filename,
        model_type=download_request.model_type,
        custom_sub_path=download_request.custom_sub_path,
        revision=download_request.revision,
    )
    if not result.get("success"):
        # For now, keep as HTTPException. This will be refactored once
        # the underlying service raises OperationFailedError or similar.
        raise HTTPException(status_code=400, detail=result.get("error", "Download failed."))
    return FileDownloadResponse(**result)


@router.post(
    "/download/cancel",
    status_code=status.HTTP_200_OK,
    summary="Cancel a running model file download task",
)
async def cancel_download_endpoint(
    request: DownloadTaskRequest, fm: FileManager = Depends(get_file_manager)
):
    """Sends a cancellation request for an in-progress download."""
    # This endpoint doesn't have a try...except block to refactor.
    await fm.cancel_download(request.download_id)
    return {"success": True, "message": f"Cancellation request for {request.download_id} sent."}


@router.post(
    "/download/dismiss",
    status_code=status.HTTP_200_OK,
    summary="Dismiss a finished task from the tracker",
)
async def dismiss_download_endpoint(
    request: DownloadTaskRequest, fm: FileManager = Depends(get_file_manager)
):
    """Removes a completed, failed, or cancelled task from the UI."""
    # This endpoint doesn't have a try...except block to refactor.
    await fm.dismiss_download(request.download_id)
    return {"success": True, "message": f"Task {request.download_id} dismissed."}


@router.get(
    "/scan-host-directories",
    response_model=ScanHostDirectoriesResponse,
    summary="Scan Host System Directories",
)
async def scan_host_directories_endpoint(
    fm: FileManager = Depends(get_file_manager),
    path: Optional[str] = Query(None),
    max_depth: int = Query(1, ge=1, le=5),
):
    """Endpoint to scan the host filesystem for directories, used by the folder selector."""
    try:
        # This currently relies on a success dictionary from the service.
        # Once fm.list_host_directories is refactored to raise MalError,
        # this check will be removed and errors will be caught below.
        result = await fm.list_host_directories(path_to_scan_str=path, max_depth=max_depth)
        if not result.get("success"):
            # For now, keep as HTTPException. This will be refactored once
            # the underlying service raises BadRequestError or OperationFailedError.
            raise HTTPException(
                status_code=400, detail=result.get("error", "Failed to scan directories.")
            )
        return ScanHostDirectoriesResponse(**result)
    # --- REFACTOR: Catch custom MalError first ---
    except MalError as e:
        # If the underlying service raises a MalError, translate it to an HTTPException
        # using the error's status code and message.
        logger.error(
            f"[{e.error_code}] Error scanning host directories: {e.message}", exc_info=False
        )
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        # Catch any other truly unexpected errors and log them as critical.
        logger.critical(
            f"An unhandled exception occurred during host directory scan: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected internal error occurred while scanning directories.",
        )


@router.get(
    "/files",
    response_model=FileManagerListResponse,
    summary="List Files and Directories in Managed Path",
)
async def list_managed_files_endpoint(
    fm: FileManager = Depends(get_file_manager),
    path: Optional[str] = Query(None),
    mode: str = Query("models", enum=["models", "explorer"]),
):
    """Lists the contents of the configured base model directory."""
    if not fm.base_path:
        # This is a specific validation, can remain as HTTPException
        raise HTTPException(status_code=400, detail="Base path not configured.")
    # This endpoint currently doesn't have a try...except block to refactor,
    # as fm.list_managed_files() is expected to return a list or raise an error
    # that would be handled by a higher-level middleware if not caught here.
    return fm.list_managed_files(relative_path_str=path, mode=mode)


@router.delete(
    "/files",
    status_code=status.HTTP_200_OK,
    summary="Delete a File or Directory",
)
async def delete_managed_item_endpoint(
    request: LocalFileActionRequest, fm: FileManager = Depends(get_file_manager)
):
    """Deletes a file or directory from the managed path."""
    # This currently relies on a success dictionary from the service.
    # Once fm.delete_managed_item is refactored to raise MalError,
    # this block will be updated to catch MalError.
    result = await fm.delete_managed_item(relative_path_str=request.path)
    if not result.get("success"):
        # For now, keep as HTTPException. This will be refactored once
        # the underlying service raises OperationFailedError or BadRequestError.
        raise HTTPException(status_code=400, detail=result.get("error", "Deletion failed."))
    return result


@router.get(
    "/files/preview",
    response_model=LocalFileContentResponse,
    summary="Get Content of a Text File for Preview",
)
async def get_file_preview_endpoint(
    path: str = Query(...), fm: FileManager = Depends(get_file_manager)
):
    """Gets the content of a text file for previewing in the UI."""
    # This currently relies on a success dictionary from the service.
    # Once fm.get_file_preview is refactored to raise MalError,
    # this block will be updated to catch MalError.
    result = await fm.get_file_preview(relative_path_str=path)
    if not result.get("success"):
        # For now, keep as HTTPException. This will be refactored once
        # the underlying service raises EntityNotFoundError or BadRequestError.
        raise HTTPException(status_code=400, detail=result.get("error", "Preview failed."))
    return result
