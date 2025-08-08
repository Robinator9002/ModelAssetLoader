# backend/routers/file_manager_router.py
import logging
from typing import Optional, Dict

from fastapi import APIRouter, HTTPException, Query, status, Depends
from pydantic import BaseModel

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
from dependencies import get_file_manager
from core.services.file_manager import FileManager
from core.errors import MalError

# --- FIX: Import the correct constant name 'KNOWN_UI_PROFILES' ---
from core.constants.constants import KNOWN_UI_PROFILES, UiProfileType, ModelType

logger = logging.getLogger(__name__)


class DownloadTaskRequest(BaseModel):
    download_id: str


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
    try:
        return MalFullConfiguration(**fm.get_current_configuration())
    except MalError as e:
        logger.error(
            f"[{e.error_code}] Error getting file manager configuration: {e.message}",
            exc_info=False,
        )
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.critical(
            f"An unhandled exception occurred getting file manager configuration: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected internal error occurred while fetching configuration.",
        )


@router.post(
    "/configure",
    response_model=PathConfigurationResponse,
    summary="Configure FileManager Paths and Settings",
)
async def configure_paths_endpoint(
    config_request: PathConfigurationRequest, fm: FileManager = Depends(get_file_manager)
):
    try:
        message = fm.configure_paths(
            base_path_str=config_request.base_path,
            profile=config_request.profile,
            custom_model_type_paths=config_request.custom_model_type_paths,
            color_theme=config_request.color_theme,
            config_mode=config_request.config_mode,
            automatic_mode_ui=config_request.automatic_mode_ui,
        )
        return PathConfigurationResponse(
            success=True,
            message=message,
            current_config=MalFullConfiguration(**fm.get_current_configuration()),
        )
    except MalError as e:
        logger.error(
            f"[{e.error_code}] Error configuring file manager paths: {e.message}", exc_info=False
        )
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.critical(
            f"An unhandled exception occurred during file manager configuration: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail="An unexpected internal error occurred during configuration."
        )


@router.get(
    "/known-ui-profiles",
    response_model=Dict[UiProfileType, Dict[ModelType, str]],
    summary="Get Known UI Profile Path Structures",
)
async def get_known_ui_profiles_endpoint():
    """
    Returns the dictionary of known UI profiles and their associated model
    path structures, as defined in the backend's constants.
    """
    # --- FIX: Use the correct variable name ---
    return KNOWN_UI_PROFILES


@router.post(
    "/download",
    response_model=FileDownloadResponse,
    summary="Download a Model File",
)
async def download_file_endpoint(
    download_request: FileDownloadRequest, fm: FileManager = Depends(get_file_manager)
):
    try:
        result = fm.start_download_model_file(
            source=download_request.source,
            repo_id=download_request.repo_id,
            filename=download_request.filename,
            model_type=download_request.model_type,
            custom_sub_path=download_request.custom_sub_path,
            revision=download_request.revision,
        )
        return FileDownloadResponse(**result)
    except MalError as e:
        logger.error(f"[{e.error_code}] Error initiating download: {e.message}", exc_info=False)
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.critical(
            f"An unhandled exception occurred during download initiation: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected internal error occurred during download initiation.",
        )


@router.post(
    "/download/cancel",
    status_code=status.HTTP_200_OK,
    summary="Cancel a running model file download task",
)
async def cancel_download_endpoint(
    request: DownloadTaskRequest, fm: FileManager = Depends(get_file_manager)
):
    try:
        await fm.cancel_download(request.download_id)
        return {"success": True, "message": f"Cancellation request for {request.download_id} sent."}
    except MalError as e:
        logger.error(f"[{e.error_code}] Error cancelling download: {e.message}", exc_info=False)
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.critical(
            f"An unhandled exception occurred during download cancellation: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected internal error occurred during download cancellation.",
        )


@router.post(
    "/download/dismiss",
    status_code=status.HTTP_200_OK,
    summary="Dismiss a finished task from the tracker",
)
async def dismiss_download_endpoint(
    request: DownloadTaskRequest, fm: FileManager = Depends(get_file_manager)
):
    try:
        await fm.dismiss_download(request.download_id)
        return {"success": True, "message": f"Task {request.download_id} dismissed."}
    except MalError as e:
        logger.error(f"[{e.error_code}] Error dismissing download: {e.message}", exc_info=False)
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.critical(
            f"An unhandled exception occurred during download dismissal: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected internal error occurred during download dismissal.",
        )


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
    try:
        result = await fm.list_host_directories(path_to_scan_str=path, max_depth=max_depth)
        return ScanHostDirectoriesResponse(**result)
    except MalError as e:
        logger.error(
            f"[{e.error_code}] Error scanning host directories: {e.message}", exc_info=False
        )
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
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
    try:
        return fm.list_managed_files(relative_path_str=path, mode=mode)
    except MalError as e:
        logger.error(f"[{e.error_code}] Error listing managed files: {e.message}", exc_info=False)
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.critical(
            f"An unhandled exception occurred listing managed files: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail="An unexpected internal error occurred while listing files."
        )


@router.delete(
    "/files",
    status_code=status.HTTP_200_OK,
    summary="Delete a File or Directory",
)
async def delete_managed_item_endpoint(
    request: LocalFileActionRequest, fm: FileManager = Depends(get_file_manager)
):
    try:
        result = await fm.delete_managed_item(relative_path_str=request.path)
        return result
    except MalError as e:
        logger.error(f"[{e.error_code}] Error deleting managed item: {e.message}", exc_info=False)
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.critical(f"An unhandled exception occurred during item deletion: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An unexpected internal error occurred during deletion."
        )


@router.get(
    "/files/preview",
    response_model=LocalFileContentResponse,
    summary="Get Content of a Text File for Preview",
)
async def get_file_preview_endpoint(
    path: str = Query(...), fm: FileManager = Depends(get_file_manager)
):
    try:
        result = await fm.get_file_preview(relative_path_str=path)
        return result
    except MalError as e:
        logger.error(f"[{e.error_code}] Error getting file preview: {e.message}", exc_info=False)
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.critical(f"An unhandled exception occurred getting file preview: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected internal error occurred while getting file preview.",
        )
