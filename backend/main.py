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
# This includes the newly defined models for the adoption workflow.
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
    ModelListItem,
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
)

# --- Core Service Imports ---
from backend.core.constants.constants import UI_REPOSITORIES
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
    version="1.7.0",  # Version bump for adoption feature
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
# These are singletons for the application's lifecycle.
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
        # Broadcasts a message to all connected clients.
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

    # Register the broadcast callback with the managers
    download_tracker.set_broadcast_callback(broadcast_status_update)
    ui_manager.broadcast_callback = broadcast_status_update

    try:
        # Send the current state of all tasks to the newly connected client
        initial_statuses = download_tracker.get_all_statuses()
        await websocket.send_text(
            json.dumps({"type": "initial_state", "downloads": initial_statuses})
        )
        # Keep the connection alive
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        # If no clients are connected, clear the callback to prevent unnecessary work
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
async def get_model_details(source: str, model_id: str):
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
    updated_config_dict = file_manager.get_current_configuration()
    return PathConfigurationResponse(
        success=True,
        message=message,
        current_config=MalFullConfiguration(**updated_config_dict),
    )


@app.post(
    "/api/filemanager/download",
    response_model=FileDownloadResponse,
    tags=["FileManager"],
    summary="Download a Model File",
)
async def download_model_file_endpoint(download_request: FileDownloadRequest):
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


# === UI Environment Management Endpoints ===
@app.get(
    "/api/uis",
    response_model=List[AvailableUiItem],
    tags=["UIs"],
    summary="List Available UIs for Installation",
)
async def list_available_uis():
    """Lists all UIs defined in the constants, regardless of installation status."""
    available_uis = [
        AvailableUiItem(
            ui_name=name,
            git_url=details["git_url"],
            default_profile_name=details["default_profile_name"],
        )
        for name, details in UI_REPOSITORIES.items()
    ]
    return available_uis


@app.get(
    "/api/uis/status",
    response_model=AllUiStatusResponse,
    tags=["UIs"],
    summary="Get Status of All Registered UIs",
)
async def get_all_ui_statuses():
    """Gets the status of all UIs that have been installed and registered."""
    status_items = await ui_manager.get_all_statuses()
    return AllUiStatusResponse(items=status_items)


@app.post(
    "/api/uis/install",
    response_model=UiActionResponse,
    tags=["UIs"],
    summary="Install a UI Environment",
)
async def install_ui_environment(request: UiInstallRequest = Body(...)):
    """Triggers the background installation of a UI."""
    task_id = str(uuid.uuid4())
    ui_manager.install_ui_environment(
        ui_name=request.ui_name,
        install_path=pathlib.Path(request.custom_install_path),
        task_id=task_id,
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
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_ui(ui_name: UiNameTypePydantic):
    """Runs a UI by its name. The manager finds the registered path."""
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
async def stop_ui(request: UiStopRequest):
    """Stops a UI process by its task ID."""
    await ui_manager.stop_ui(task_id=request.task_id)
    return {"success": True, "message": f"Stop request for task {request.task_id} sent."}


@app.delete(
    "/api/uis/{ui_name}",
    status_code=status.HTTP_200_OK,
    tags=["UIs"],
    summary="Delete a Registered UI Environment",
)
async def delete_ui_environment_endpoint(ui_name: UiNameTypePydantic):
    """Deletes a UI environment by its name."""
    success = await ui_manager.delete_environment(ui_name=ui_name)
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to delete {ui_name} environment.")
    return {"success": True, "message": f"{ui_name} environment deleted successfully."}


# --- UI Adoption Endpoints ---


@app.post(
    "/api/uis/adopt/analyze",
    response_model=AdoptionAnalysisResponse,
    tags=["UIs", "Adoption"],
    summary="Analyze a Directory for UI Adoption",
)
async def analyze_adoption_candidate(request: UiAdoptionAnalysisRequest):
    """Analyzes a user-provided directory to check if it's a valid UI installation."""
    try:
        path = pathlib.Path(request.path)
        analysis_result = ui_manager.analyze_adoption_candidate(request.ui_name, path)
        return AdoptionAnalysisResponse(**analysis_result)
    except Exception as e:
        logger.error(f"Error during adoption analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred during analysis.")


@app.post(
    "/api/uis/adopt/repair",
    response_model=UiActionResponse,
    tags=["UIs", "Adoption"],
    summary="Repair and Adopt a UI Environment",
)
async def repair_and_adopt_ui_endpoint(request: UiAdoptionRepairRequest):
    """Starts a background task to repair a UI installation and adopt it upon completion."""
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
        set_as_active_on_completion=True,  # Adopted UIs are often intended to be active
    )


@app.post(
    "/api/uis/adopt/finalize",
    status_code=status.HTTP_200_OK,
    tags=["UIs", "Adoption"],
    summary="Finalize Adoption of a UI without Repairs",
)
async def finalize_adoption_endpoint(request: UiAdoptionFinalizeRequest):
    """Directly registers a UI installation without performing any repairs."""
    success = ui_manager.finalize_adoption(ui_name=request.ui_name, path=pathlib.Path(request.path))
    if not success:
        raise HTTPException(status_code=500, detail="Failed to finalize adoption.")
    return {"success": True, "message": f"{request.ui_name} adopted successfully."}


# --- Main Execution Block ---
if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting M.A.L. API server (v{app.version}) for development...")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True, workers=1)
