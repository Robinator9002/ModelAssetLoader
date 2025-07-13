# backend/main.py
import asyncio
import json
import logging
import pathlib
import uuid
from typing import List, Optional

from fastapi import (
    Body,
    FastAPI,
    HTTPException,
    Query,
    status,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware

# --- API Model Imports ---
from backend.api.models import (
    AdoptionAnalysisResponse,
    AllUiStatusResponse,
    AvailableUiItem,
    FileDownloadRequest,
    FileDownloadResponse,
    FileManagerListResponse,
    LocalFileActionRequest,
    LocalFileContentResponse,
    MalFullConfiguration,
    ModelDetails,
    PaginatedModelListResponse,
    PathConfigurationRequest,
    PathConfigurationResponse,
    ScanHostDirectoriesResponse,
    UiActionResponse,
    UiAdoptionAnalysisRequest,
    UiAdoptionFinalizeRequest,
    UiAdoptionRepairRequest,
    UiInstallRequest,
    UiNameTypePydantic,
    UiStopRequest,
    ModelListItem,
)

# --- Core Service Imports ---
from backend.core.constants.constants import MANAGED_UIS_ROOT_PATH, UI_REPOSITORIES
from backend.core.file_manager import FileManager
from backend.core.file_management.download_tracker import download_tracker
from backend.core.source_manager import SourceManager
from backend.core.ui_manager import UiManager

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger(__name__)


# --- FastAPI Application Instance ---
app = FastAPI(
    title="M.A.L. - Model Asset Loader API",
    description="API for searching external model sources, managing local model files, "
    "and configuring/managing AI UI environments.",
    version="1.7.6",
)

# --- CORS Middleware ---
origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
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


# --- WebSocket Connection Manager ---
class ConnectionManager:
    """Manages active WebSocket connections for real-time broadcasting."""

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
    """Handles WebSocket connections for real-time task updates."""
    await manager.connect(websocket)

    async def broadcast_status_update(data: dict):
        await manager.broadcast(json.dumps(data, default=str))

    download_tracker.set_broadcast_callback(broadcast_status_update)
    ui_manager.broadcast_callback = broadcast_status_update

    try:
        initial_statuses = download_tracker.get_all_statuses()
        await websocket.send_text(
            json.dumps({"type": "initial_state", "downloads": initial_statuses})
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
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
async def search_models_endpoint(
    source: str = Query("huggingface"),
    search: Optional[str] = Query(None),
    author: Optional[str] = Query(None),
    tags: Optional[List[str]] = Query(None, alias="tags[]"),
    sort: Optional[str] = Query("lastModified"),
    direction: Optional[int] = Query(-1, enum=[-1, 1]),
    limit: int = Query(30, ge=1, le=100),
    page: int = Query(1, ge=1),
):
    try:
        unique_tags = list(set(tags)) if tags else None
        models_data, has_more = source_manager.search_models(
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
            items=[ModelListItem(**m) for m in models_data],
            page=page,
            limit=limit,
            has_more=has_more,
        )
    except Exception as e:
        logger.error(f"Error in search_models: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error during model search.")


@app.get(
    "/api/models/{source}/{model_id:path}",
    response_model=ModelDetails,
    tags=["Models"],
    summary="Get Model Details from a Source",
)
async def get_model_details_endpoint(source: str, model_id: str):
    try:
        details_data = source_manager.get_model_details(model_id=model_id, source=source)
        if not details_data:
            raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found.")
        return ModelDetails(**details_data)
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
async def get_config_endpoint():
    return MalFullConfiguration(**file_manager.get_current_configuration())


@app.post(
    "/api/filemanager/configure",
    response_model=PathConfigurationResponse,
    tags=["FileManager"],
    summary="Configure FileManager Paths and Settings",
)
async def configure_paths_endpoint(config_request: PathConfigurationRequest):
    success, message = file_manager.configure_paths(
        base_path_str=config_request.base_path,
        profile=config_request.profile,
        custom_model_type_paths=config_request.custom_model_type_paths,
        color_theme=config_request.color_theme,
        config_mode=config_request.config_mode,
        automatic_mode_ui=config_request.automatic_mode_ui,
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return PathConfigurationResponse(
        success=True,
        message=message,
        current_config=MalFullConfiguration(**file_manager.get_current_configuration()),
    )


@app.post(
    "/api/filemanager/download",
    response_model=FileDownloadResponse,
    tags=["FileManager"],
    summary="Download a Model File",
)
async def download_file_endpoint(download_request: FileDownloadRequest):
    if not file_manager.base_path:
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
    "/api/filemanager/download/cancel",
    status_code=status.HTTP_200_OK,
    tags=["FileManager"],
    summary="Cancel a running model file download task",
)
async def cancel_download_endpoint(payload: dict = Body(...)):
    download_id = payload.get("download_id")
    if not download_id:
        raise HTTPException(status_code=400, detail="download_id is required.")
    await file_manager.cancel_download(download_id)
    return {"success": True, "message": f"Cancellation request for {download_id} sent."}


@app.get(
    "/api/filemanager/scan-host-directories",
    response_model=ScanHostDirectoriesResponse,
    tags=["FileManager"],
    summary="Scan Host System Directories",
)
async def scan_host_directories_endpoint(
    path: Optional[str] = Query(None), max_depth: int = Query(1, ge=1, le=5)
):
    try:
        result = file_manager.list_host_directories(path_to_scan_str=path, max_depth=max_depth)
        if not result.get("success"):
            raise HTTPException(
                status_code=400, detail=result.get("error", "Failed to scan directories.")
            )
        return ScanHostDirectoriesResponse(**result)
    except Exception as e:
        logger.error(f"Error scanning host directories: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An internal server error occurred while scanning directories."
        )


@app.get(
    "/api/filemanager/files",
    response_model=FileManagerListResponse,
    tags=["FileManager"],
    summary="List Files and Directories in Managed Path",
)
async def list_managed_files_endpoint(
    path: Optional[str] = Query(None), mode: str = Query("models", enum=["models", "explorer"])
):
    if not file_manager.base_path:
        raise HTTPException(status_code=400, detail="Base path not configured.")
    return file_manager.list_managed_files(relative_path_str=path, mode=mode)


@app.delete(
    "/api/filemanager/files",
    status_code=status.HTTP_200_OK,
    tags=["FileManager"],
    summary="Delete a File or Directory",
)
async def delete_managed_item_endpoint(request: LocalFileActionRequest):
    result = file_manager.delete_managed_item(relative_path_str=request.path)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Deletion failed."))
    return result


@app.get(
    "/api/filemanager/files/preview",
    response_model=LocalFileContentResponse,
    tags=["FileManager"],
    summary="Get Content of a Text File for Preview",
)
async def get_file_preview_endpoint(path: str = Query(...)):
    result = file_manager.get_file_preview(relative_path_str=path)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Preview failed."))
    return result


# === UI Environment Management Endpoints ===
@app.get(
    "/api/uis",
    response_model=List[AvailableUiItem],
    tags=["UIs"],
    summary="List Available UIs for Installation",
)
async def list_available_uis_endpoint():
    return [
        AvailableUiItem(
            ui_name=name,
            git_url=details["git_url"],
            default_profile_name=details["default_profile_name"],
        )
        for name, details in UI_REPOSITORIES.items()
    ]


@app.get(
    "/api/uis/status",
    response_model=AllUiStatusResponse,
    tags=["UIs"],
    summary="Get Status of All Registered UIs",
)
async def get_all_ui_statuses_endpoint():
    return AllUiStatusResponse(items=await ui_manager.get_all_statuses())


@app.post(
    "/api/uis/install",
    response_model=UiActionResponse,
    tags=["UIs"],
    summary="Install a UI Environment",
)
async def install_ui_endpoint(request: UiInstallRequest = Body(...)):
    """
    Triggers the background installation of a UI. It handles both default
    and custom installation paths.
    """
    task_id = str(uuid.uuid4())

    install_path: pathlib.Path
    if request.custom_install_path:
        install_path = pathlib.Path(request.custom_install_path)
    else:
        install_path = MANAGED_UIS_ROOT_PATH / request.ui_name

    try:
        install_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to create or access install directory {install_path.parent}: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid installation path: {install_path}")

    install_coro = ui_manager.install_ui_environment(
        ui_name=request.ui_name,
        install_path=install_path,
        task_id=task_id,
    )
    background_task = asyncio.create_task(install_coro)

    download_tracker.start_tracking(
        download_id=task_id,
        repo_id="UI Installation",
        filename=request.ui_name,
        task=background_task,
    )

    return UiActionResponse(
        success=True,
        message=f"Installation for {request.ui_name} started.",
        task_id=task_id,
        set_as_active_on_completion=request.set_as_active,
    )


@app.post(
    "/api/uis/{ui_name}/run",
    response_model=UiActionResponse,
    tags=["UIs"],
    summary="Run an Installed UI",
)
async def run_ui_endpoint(ui_name: UiNameTypePydantic):
    task_id = str(uuid.uuid4())
    ui_manager.run_ui(ui_name=ui_name, task_id=task_id)
    return UiActionResponse(
        success=True,
        message=f"Request to run {ui_name} accepted.",
        task_id=task_id,
        set_as_active_on_completion=False,
    )


@app.post(
    "/api/uis/stop",
    status_code=status.HTTP_200_OK,
    tags=["UIs"],
    summary="Stop a Running UI Process",
)
async def stop_ui_endpoint(request: UiStopRequest):
    await ui_manager.stop_ui(task_id=request.task_id)
    return {"success": True, "message": f"Stop request for task {request.task_id} sent."}


@app.post(
    "/api/uis/cancel",
    status_code=status.HTTP_200_OK,
    tags=["UIs"],
    summary="Cancel a running UI installation or repair task",
)
async def cancel_ui_task_endpoint(payload: dict = Body(...)):
    task_id = payload.get("task_id")
    if not task_id:
        raise HTTPException(status_code=400, detail="task_id is required.")
    await ui_manager.cancel_ui_task(task_id)
    return {"success": True, "message": f"Cancellation request for UI task {task_id} sent."}


@app.delete(
    "/api/uis/{ui_name}",
    status_code=status.HTTP_200_OK,
    tags=["UIs"],
    summary="Delete a Registered UI Environment",
)
async def delete_ui_endpoint(ui_name: UiNameTypePydantic):
    if not await ui_manager.delete_environment(ui_name=ui_name):
        raise HTTPException(status_code=500, detail=f"Failed to delete {ui_name} environment.")
    return {"success": True, "message": f"{ui_name} environment deleted successfully."}


# --- UI Adoption Endpoints ---
@app.post(
    "/api/uis/adopt/analyze",
    response_model=AdoptionAnalysisResponse,
    tags=["UIs", "Adoption"],
    summary="Analyze a Directory for UI Adoption",
)
async def analyze_adoption_endpoint(request: UiAdoptionAnalysisRequest):
    try:
        return AdoptionAnalysisResponse(
            **ui_manager.analyze_adoption_candidate(request.ui_name, pathlib.Path(request.path))
        )
    except Exception as e:
        logger.error(f"Error during adoption analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")


@app.post(
    "/api/uis/adopt/repair",
    response_model=UiActionResponse,
    tags=["UIs", "Adoption"],
    summary="Repair and Adopt a UI Environment",
)
async def repair_and_adopt_endpoint(request: UiAdoptionRepairRequest):
    task_id = str(uuid.uuid4())
    ui_manager.repair_and_adopt_ui(
        ui_name=request.ui_name,
        path=pathlib.Path(request.path),
        issues_to_fix=request.issues_to_fix,
        task_id=task_id,
    )
    return UiActionResponse(
        success=True,
        message=f"Repair process for {request.ui_name} started.",
        task_id=task_id,
        set_as_active_on_completion=True,
    )


@app.post(
    "/api/uis/adopt/finalize",
    status_code=status.HTTP_200_OK,
    tags=["UIs", "Adoption"],
    summary="Finalize Adoption of a UI without Repairs",
)
async def finalize_adoption_endpoint(request: UiAdoptionFinalizeRequest):
    if not ui_manager.finalize_adoption(request.ui_name, pathlib.Path(request.path)):
        raise HTTPException(status_code=500, detail="Failed to finalize adoption.")
    return {"success": True, "message": f"{request.ui_name} adopted successfully."}


# --- Main Execution Block ---
if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting M.A.L. API server (v{app.version}) for development...")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True, workers=1)
