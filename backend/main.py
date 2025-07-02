# backend/main.py
from fastapi import FastAPI, HTTPException, Query, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional

import logging
import json

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Core Service Imports ---
from backend.core.source_manager import SourceManager
from backend.core.file_manager import FileManager
from backend.core.file_management.download_tracker import download_tracker

# --- API Model Imports ---
from backend.api.models import (
    PaginatedModelListResponse, HFModelDetails,
    PathConfigurationRequest, PathConfigurationResponse,
    FileDownloadRequest, FileDownloadResponse,
    MalFullConfiguration, FileManagerListResponse,
    ScanHostDirectoriesResponse, HFModelListItem,
    LocalFileItem, LocalFileActionRequest, LocalFileContentResponse
)

# --- FastAPI Application Instance ---
app = FastAPI(
    title="M.A.L. - Model Asset Loader API",
    description="API for searching external model sources, managing local model files, "
                "and configuring storage paths for AI asset management.",
    version="1.0.0",
)

# --- CORS Middleware ---
origins = [
    "http://localhost:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Service Instances ---
source_manager = SourceManager()
file_manager = FileManager()


# --- Robust WebSocket Connection Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected: {websocket.client}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected: {websocket.client}")

    async def broadcast(self, message: str):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

# --- Der WebSocket-Endpunkt (jetzt ohne störenden GET-Handler) ---
@app.websocket("/ws/downloads")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    async def broadcast_status_update(data: dict):
        await manager.broadcast(json.dumps(data, default=str))

    download_tracker.set_broadcast_callback(broadcast_status_update)
    
    try:
        initial_statuses = download_tracker.get_all_statuses()
        await websocket.send_text(json.dumps({"type": "initial_state", "downloads": initial_statuses}))
        while True:
            # Warte auf Nachrichten oder einen Disconnect
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        if not manager.active_connections:
            download_tracker.set_broadcast_callback(None)
            logger.info("Last WebSocket client disconnected, clearing broadcast callback.")

# --- API Endpoints ---

# === Model Search and Details Endpoints ===
@app.get(
    "/api/models",
    response_model=PaginatedModelListResponse,
    tags=["Models"],
    summary="Search Models from a Source",
    description="Searches for models from a specified source (e.g., 'huggingface') with filters and pagination."
)
async def search_models(
    # Add 'source' parameter to select the API source.
    source: str = Query('huggingface', description="The API source to search (e.g., 'huggingface')."),
    search: Optional[str] = Query(None, description="Search term to query model names, descriptions, etc."),
    author: Optional[str] = Query(None, description="Filter models by a specific author or organization."),
    tags: Optional[List[str]] = Query(default_factory=list, description="List of tags to filter by."),
    sort: Optional[str] = Query("lastModified", description="Field to sort results by."),
    direction: Optional[int] = Query(-1, enum=[-1, 1], description="Sort direction: -1 for descending, 1 for ascending."),
    limit: int = Query(30, ge=1, le=100, description="Number of results per page."),
    page: int = Query(1, ge=1, description="Page number for pagination (1-indexed).")
):
    try:
        processed_tags = [t.strip() for tag_group in tags for t in tag_group.split(',') if t.strip()]
        unique_tags = list(set(processed_tags)) if processed_tags else None
        
        logger.info(f"Searching models via SourceManager: source='{source}', query='{search}', tags='{unique_tags}'")

        # Use source_manager instead of model_loader
        models_data, has_more_results = source_manager.search_models(
            source=source,
            search_query=search, author=author, tags=unique_tags,
            sort_by=sort, sort_direction=direction, limit=limit, page=page
        )
        return PaginatedModelListResponse(
            items=[HFModelListItem(**model_data) for model_data in models_data],
            page=page, limit=limit, has_more=has_more_results
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in search_models endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred while searching for models.")

# Changed path to be more RESTful and generic for multiple sources.
@app.get(
    "/api/models/{source}/{model_id:path}",
    response_model=HFModelDetails,
    tags=["Models"],
    summary="Get Model Details from a Source",
    description="Retrieves detailed information for a specific model from the specified source."
)
async def get_model_details(source: str, model_id: str):
    logger.info(f"Fetching details for model '{model_id}' from source '{source}'")
    try:
        # Use source_manager to get details.
        details_data = source_manager.get_model_details(model_id=model_id, source=source)
        if not details_data:
            logger.warning(f"Model '{model_id}' not found by source_manager for source '{source}'.")
            raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found in source '{source}'.")
        return HFModelDetails(**details_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_model_details for '{model_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred while fetching model details.")


# === FileManager Endpoints ===
@app.get(
    "/api/filemanager/configuration",
    response_model=MalFullConfiguration,
    tags=["FileManager"],
    summary="Get Current FileManager Configuration"
)
async def get_file_manager_configuration():
    logger.debug("Request received for current FileManager configuration.")
    config = file_manager.get_current_configuration()
    return MalFullConfiguration(**config)

@app.post(
    "/api/filemanager/configure",
    response_model=PathConfigurationResponse,
    tags=["FileManager"],
    summary="Configure FileManager Paths and Settings"
)
async def configure_file_manager_paths_endpoint(config_request: PathConfigurationRequest):
    logger.info(f"Received configuration request: {config_request.model_dump(exclude_none=True)}")
    result = file_manager.configure_paths(
        base_path_str=config_request.base_path,
        profile=config_request.profile,
        custom_model_type_paths=config_request.custom_model_type_paths,
        color_theme=config_request.color_theme
    )
    if not result.get("success"):
        logger.error(f"Configuration failed: {result.get('error', 'Unknown configuration error.')}")
        raise HTTPException(status_code=400, detail=result.get("error", "Configuration failed."))

    updated_config_dict = file_manager.get_current_configuration()
    response_data = PathConfigurationResponse(
        success=result.get("success", False),
        message=result.get("message"),
        configured_base_path=result.get("configured_base_path"),
        current_config=MalFullConfiguration(**updated_config_dict)
    )
    logger.info(f"Configuration successful. Current base path: {response_data.configured_base_path}")
    return response_data

@app.post(
    "/api/filemanager/download",
    response_model=FileDownloadResponse,
    tags=["FileManager"],
    summary="Download a Model File"
)
async def download_model_file_endpoint(download_request: FileDownloadRequest):
    """
    Schedules a file from a source repository to be downloaded.
    The download now runs as a native asyncio task, not a FastAPI BackgroundTask.
    """
    logger.info(f"Received download request: {download_request.model_dump()}")
    if not file_manager.config.base_path:
        raise HTTPException(status_code=400, detail="Base path not configured.")

    # Call start_download_model_file without the background_tasks argument
    result = file_manager.start_download_model_file(
        source=download_request.source,
        repo_id=download_request.repo_id,
        filename=download_request.filename,
        model_type=download_request.model_type,
        custom_sub_path=download_request.custom_sub_path,
        revision=download_request.revision
    )

    if not result.get("success"):
        error_detail = result.get("error", "Download failed.")
        status_code = 400
        if "not found" in error_detail.lower(): status_code = 404
        if "gated" in error_detail.lower(): status_code = 403
        raise HTTPException(status_code=status_code, detail=error_detail)

    logger.info(f"Download successfully queued: {result.get('message')}")
    return FileDownloadResponse(**result)

# --- Cancel Endpoint ---
@app.post(
    "/api/filemanager/downloads/{download_id}/cancel",
    status_code=status.HTTP_202_ACCEPTED,
    tags=["FileManager"],
    summary="Request to cancel a running download"
)
async def cancel_download_endpoint(download_id: str):
    """Requests to cancel a download task that is currently in 'pending' or 'downloading' state."""
    await file_manager.cancel_download(download_id)
    return {"message": "Cancellation request accepted."}

# --- Dismiss Endpoint ---
@app.delete(
    "/api/filemanager/downloads/{download_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["FileManager"],
    summary="Dismiss a finished download from the UI"
)
async def dismiss_download_endpoint(download_id: str):
    """Removes a download from the tracker once it is in a final state (completed, error, cancelled)."""
    await file_manager.dismiss_download(download_id)
    return

@app.get(
    "/api/filemanager/scan-host-directories",
    response_model=ScanHostDirectoriesResponse,
    tags=["FileManager"],
    summary="Scan Host System Directories"
)
async def scan_host_directories_endpoint(
    path_to_scan: Optional[str] = Query(None, alias="path"),
    max_depth: int = Query(2, ge=1, le=7)
):
    logger.info(f"Host directory scan request: path='{path_to_scan}', depth={max_depth}")
    try:
        scan_result = file_manager.list_host_directories(
            path_to_scan_str=path_to_scan,
            max_depth=max_depth
        )
        return ScanHostDirectoriesResponse(
            success=scan_result.get("success", False),
            message=scan_result.get("message"),
            error=scan_result.get("error"),
            data=scan_result.get("data", [])
        )
    except Exception as e:
        logger.error(f"Critical error in scan_host_directories_endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred while scanning host directories.")


# --- Local File Management Endpoint ---
@app.get(
    "/api/filemanager/files",
    response_model=FileManagerListResponse, # <-- Use the new response model
    tags=["FileManager"],
    summary="List Files with Smart Navigation"
)
async def list_managed_files_endpoint(
    path: Optional[str] = Query(None, description="Relative path from the base directory."),
    mode: str = Query('models', enum=['explorer', 'models'], description="View mode for filtering.")
):
    if not file_manager.base_path:
        raise HTTPException(status_code=400, detail="Base path is not configured.")
    
    result = file_manager.list_managed_files(relative_path_str=path, mode=mode)
    return result

@app.delete(
    "/api/filemanager/files",
    status_code=status.HTTP_200_OK,
    tags=["FileManager"],
    summary="Delete a Managed File or Directory"
)
async def delete_managed_item_endpoint(request: LocalFileActionRequest):
    """

    Deletes a specified file or directory within the `base_path`.
    The path must be relative to the configured base directory.
    """
    if not file_manager.base_path:
        raise HTTPException(status_code=400, detail="Base path is not configured.")
    
    result = file_manager.delete_managed_item(relative_path_str=request.path)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to delete item."))
    
    return result

@app.get(
    "/api/filemanager/files/preview",
    response_model=LocalFileContentResponse,
    tags=["FileManager"],
    summary="Get Content of a Text File"
)
async def get_managed_file_preview_endpoint(path: str = Query(..., description="Relative path to the file to be previewed.")):
    """
    Retrieves the content of a small, allowed text file (e.g., .txt, .md)
    for previewing in the UI.
    """
    if not file_manager.base_path:
        raise HTTPException(status_code=400, detail="Base path is not configured.")
    
    result = file_manager.get_file_preview(relative_path_str=path)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to get file preview."))
        
    return result

# --- Main Execution Block ---
if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting M.A.L. API server (v{app.version}) for development...")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
