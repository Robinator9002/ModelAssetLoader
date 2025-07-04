# backend/main.py
from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    status,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional

import logging
import json
import uuid
import asyncio

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger(__name__)

# --- Core Service Imports ---
from backend.core.source_manager import SourceManager
from backend.core.file_manager import FileManager
from backend.core.ui_manager import UiManager
from backend.core.file_management.download_tracker import download_tracker
from backend.core.constants.constants import UI_REPOSITORIES

# --- API Model Imports ---
from backend.api.models import (
    PaginatedModelListResponse,
    HFModelDetails,
    PathConfigurationRequest,
    PathConfigurationResponse,
    FileDownloadRequest,
    FileDownloadResponse,
    MalFullConfiguration,
    FileManagerListResponse,
    ScanHostDirectoriesResponse,
    HFModelListItem,
    LocalFileActionRequest,
    LocalFileContentResponse,
    # --- New UI Management Models ---
    AvailableUiItem,
    AllUiStatusResponse,
    UiActionResponse,
    UiStopRequest,
    UiNameTypePydantic,
)

# --- FastAPI Application Instance ---
app = FastAPI(
    title="M.A.L. - Model Asset Loader API",
    description="API for searching external model sources, managing local model files, "
    "and configuring/managing AI UI environments.",
    version="1.1.0",
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
ui_manager = UiManager()


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


# --- WebSocket Endpoint for Real-time Updates ---
@app.websocket("/ws/downloads")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    # Define a single broadcast function
    async def broadcast_status_update(data: dict):
        await manager.broadcast(json.dumps(data, default=str))

    # Connect the broadcast function to both trackers
    download_tracker.set_broadcast_callback(broadcast_status_update)
    ui_manager.broadcast_callback = broadcast_status_update

    try:
        # Send initial state for file downloads
        initial_statuses = download_tracker.get_all_statuses()
        await websocket.send_text(
            json.dumps({"type": "initial_state", "downloads": initial_statuses})
        )
        # Keep the connection alive
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        # If all clients are disconnected, clear the callbacks
        if not manager.active_connections:
            download_tracker.set_broadcast_callback(None)
            ui_manager.broadcast_callback = None
            logger.info("Last WebSocket client disconnected, clearing broadcast callbacks.")


# --- API Endpoints ---


# === Model Search and Details Endpoints ===
@app.get(
    "/api/models",
    response_model=PaginatedModelListResponse,
    tags=["Models"],
    summary="Search Models from a Source",
)
async def search_models(
    source: str = Query(
        "huggingface", description="The API source to search (e.g., 'huggingface')."
    ),
    search: Optional[str] = Query(None),
    author: Optional[str] = Query(None),
    tags: Optional[List[str]] = Query(default_factory=list),
    sort: Optional[str] = Query("lastModified"),
    direction: Optional[int] = Query(-1, enum=[-1, 1]),
    limit: int = Query(30, ge=1, le=100),
    page: int = Query(1, ge=1),
):
    try:
        processed_tags = [
            t.strip() for tag_group in tags for t in tag_group.split(",") if t.strip()
        ]
        unique_tags = list(set(processed_tags)) if processed_tags else None
        models_data, has_more_results = source_manager.search_models(
            source=source,
            search_query=search,
            author=author,
            tags=unique_tags,
            sort_by=sort,
            sort_direction=direction,
            limit=limit,
            page=page,
        )
        return PaginatedModelListResponse(
            items=[HFModelListItem(**model_data) for model_data in models_data],
            page=page,
            limit=limit,
            has_more=has_more_results,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in search_models endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred.")


@app.get(
    "/api/models/{source}/{model_id:path}",
    response_model=HFModelDetails,
    tags=["Models"],
    summary="Get Model Details from a Source",
)
async def get_model_details(source: str, model_id: str):
    try:
        details_data = source_manager.get_model_details(model_id=model_id, source=source)
        if not details_data:
            raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found.")
        return HFModelDetails(**details_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_model_details for '{model_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred.")


# === FileManager Endpoints ===
@app.get(
    "/api/filemanager/configuration",
    response_model=MalFullConfiguration,
    tags=["FileManager"],
    summary="Get Current FileManager Configuration",
)
async def get_file_manager_configuration():
    config = file_manager.get_current_configuration()
    return MalFullConfiguration(**config)


@app.post(
    "/api/filemanager/configure",
    response_model=PathConfigurationResponse,
    tags=["FileManager"],
    summary="Configure FileManager Paths and Settings",
)
async def configure_file_manager_paths_endpoint(config_request: PathConfigurationRequest):
    result = file_manager.configure_paths(
        base_path_str=config_request.base_path,
        profile=config_request.profile,
        custom_model_type_paths=config_request.custom_model_type_paths,
        color_theme=config_request.color_theme,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Configuration failed."))
    updated_config_dict = file_manager.get_current_configuration()
    return PathConfigurationResponse(
        success=result.get("success", False),
        message=result.get("message"),
        configured_base_path=result.get("configured_base_path"),
        current_config=MalFullConfiguration(**updated_config_dict),
    )


@app.post(
    "/api/filemanager/download",
    response_model=FileDownloadResponse,
    tags=["FileManager"],
    summary="Download a Model File",
)
async def download_model_file_endpoint(download_request: FileDownloadRequest):
    if not file_manager.config.base_path:
        raise HTTPException(status_code=400, detail="Base path not configured.")
    result = file_manager.start_download_model_file(
        source=download_request.source,
        repo_id=download_request.repo_id,
        filename=download_request.filename,
        model_type=download_request.model_type,
        custom_sub_path=download_request.custom_sub_path,
        revision=download_request.revision,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Download failed."))
    return FileDownloadResponse(**result)


@app.post(
    "/api/filemanager/downloads/{download_id}/cancel",
    status_code=status.HTTP_202_ACCEPTED,
    tags=["FileManager"],
    summary="Request to cancel a running download",
)
async def cancel_download_endpoint(download_id: str):
    await file_manager.cancel_download(download_id)
    return {"message": "Cancellation request accepted."}


@app.delete(
    "/api/filemanager/downloads/{download_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["FileManager"],
    summary="Dismiss a finished download from the UI",
)
async def dismiss_download_endpoint(download_id: str):
    await file_manager.dismiss_download(download_id)
    return


@app.get(
    "/api/filemanager/scan-host-directories",
    response_model=ScanHostDirectoriesResponse,
    tags=["FileManager"],
    summary="Scan Host System Directories",
)
async def scan_host_directories_endpoint(
    path_to_scan: Optional[str] = Query(None, alias="path"),
    max_depth: int = Query(2, ge=1, le=7),
):
    scan_result = file_manager.list_host_directories(path_to_scan_str=path_to_scan, max_depth=max_depth)
    return ScanHostDirectoriesResponse(**scan_result)


@app.get(
    "/api/filemanager/files",
    response_model=FileManagerListResponse,
    tags=["FileManager"],
    summary="List Files with Smart Navigation",
)
async def list_managed_files_endpoint(
    path: Optional[str] = Query(None),
    mode: str = Query("models", enum=["explorer", "models"]),
):
    if not file_manager.base_path:
        raise HTTPException(status_code=400, detail="Base path is not configured.")
    result = file_manager.list_managed_files(relative_path_str=path, mode=mode)
    return result


@app.delete(
    "/api/filemanager/files",
    status_code=status.HTTP_200_OK,
    tags=["FileManager"],
    summary="Delete a Managed File or Directory",
)
async def delete_managed_item_endpoint(request: LocalFileActionRequest):
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
    summary="Get Content of a Text File",
)
async def get_managed_file_preview_endpoint(path: str = Query(...)):
    if not file_manager.base_path:
        raise HTTPException(status_code=400, detail="Base path is not configured.")
    result = file_manager.get_file_preview(relative_path_str=path)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to get file preview."))
    return result


# === NEW: UI Environment Management Endpoints ===
@app.get(
    "/api/uis",
    response_model=List[AvailableUiItem],
    tags=["UIs"],
    summary="List Available UIs for Installation",
)
async def list_available_uis():
    """Returns a list of all UIs that the application knows how to install."""
    available_uis = [
        AvailableUiItem(ui_name=name, git_url=details["git_url"])
        for name, details in UI_REPOSITORIES.items()
    ]
    return available_uis


@app.get(
    "/api/uis/status",
    response_model=AllUiStatusResponse,
    tags=["UIs"],
    summary="Get Status of All Managed UIs",
)
async def get_all_ui_statuses():
    """
    Checks the local environment and returns the status (installed, running)
    for all manageable UIs.
    """
    # This assumes a base path is set for managing UIs.
    # For now, we'll use the file_manager's base_path as the parent for a 'managed_uis' folder.
    if not file_manager.base_path:
        return AllUiStatusResponse(items=[]) # Return empty list if not configured

    install_dir = file_manager.base_path / "managed_uis"
    status_items = await ui_manager.get_all_statuses(install_dir)
    return AllUiStatusResponse(items=status_items)


@app.post(
    "/api/uis/{ui_name}/install",
    response_model=UiActionResponse,
    tags=["UIs"],
    summary="Install a UI Environment",
)
async def install_ui_environment(ui_name: UiNameTypePydantic):
    """Triggers a background task to clone and set up a UI environment."""
    if not file_manager.base_path:
        raise HTTPException(status_code=400, detail="Base path for installations is not configured.")

    install_dir = file_manager.base_path / "managed_uis"
    task_id = str(uuid.uuid4())

    download_tracker.start_tracking(
        download_id=task_id,
        repo_id=f"UI Installation",
        filename=ui_name,
        task=asyncio.create_task(
            ui_manager.install_ui_environment(
                ui_name=ui_name, base_install_path=install_dir, task_id=task_id
            )
        ),
    )
    return UiActionResponse(
        success=True,
        message=f"Installation for {ui_name} started.",
        task_id=task_id,
    )


@app.delete(
    "/api/uis/{ui_name}",
    status_code=status.HTTP_200_OK,
    tags=["UIs"],
    summary="Delete a UI Environment",
)
async def delete_ui_environment(ui_name: UiNameTypePydantic):
    """Deletes the entire directory for an installed UI environment."""
    if not file_manager.base_path:
        raise HTTPException(status_code=400, detail="Base path for installations is not configured.")

    install_dir = file_manager.base_path / "managed_uis"
    success = await ui_manager.delete_environment(
        ui_name=ui_name, base_install_path=install_dir
    )
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to delete {ui_name} environment.")
    return {"success": True, "message": f"{ui_name} environment deleted successfully."}


@app.post(
    "/api/uis/{ui_name}/run",
    response_model=UiActionResponse,
    tags=["UIs"],
    summary="Run an Installed UI",
)
async def run_ui(ui_name: UiNameTypePydantic):
    """Triggers a background task to start a managed UI."""
    if not file_manager.base_path:
        raise HTTPException(status_code=400, detail="Base path for installations is not configured.")

    install_dir = file_manager.base_path / "managed_uis"
    task_id = str(uuid.uuid4())

    # We use the same tracker, but could create a separate one for processes.
    download_tracker.start_tracking(
        download_id=task_id,
        repo_id=f"UI Process",
        filename=ui_name,
        task=asyncio.create_task(
            ui_manager.run_ui(
                ui_name=ui_name, base_install_path=install_dir, task_id=task_id
            )
        ),
    )
    return UiActionResponse(
        success=True,
        message=f"Request to run {ui_name} accepted.",
        task_id=task_id,
    )


@app.post(
    "/api/uis/stop",
    status_code=status.HTTP_200_OK,
    tags=["UIs"],
    summary="Stop a Running UI Process",
)
async def stop_ui(request: UiStopRequest):
    """Stops a running UI process using its unique task ID."""
    await ui_manager.stop_ui(task_id=request.task_id)
    return {"success": True, "message": f"Stop request for task {request.task_id} sent."}


# --- Main Execution Block ---
if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting M.A.L. API server (v{app.version}) for development...")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
