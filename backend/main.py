# backend/main.py
from fastapi import FastAPI, HTTPException, Query, Body, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any

from backend.core.model_loader import ModelLoader
from backend.core.file_manager import FileManager
from backend.api.models import (
    PaginatedModelListResponse, HFModelListItem, HFModelDetails,
    PathConfigurationRequest, PathConfigurationResponse,
    FileDownloadRequest, FileDownloadResponse,
    DirectoryStructureResponse,
    RescanPathRequest, RescanPathResponse,
    MalFullConfiguration,
    ScanHostDirectoriesResponse, HostDirectoryItem 
)

import logging
import pathlib

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(
    title="M.A.L. - Model Asset Loader API",
    description="API for searching, retrieving, and managing AI models, with refined lazy loading for directories.",
    version="0.7.0", 
)

origins = [ "http://localhost:5173" ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

model_loader = ModelLoader()
file_manager = FileManager()

# --- Model Search and Details Endpoints ( остаются без изменений ) ---
@app.get("/api/models/", response_model=PaginatedModelListResponse, tags=["Models"])
async def search_hf_models(
    search: Optional[str] = Query(None), author: Optional[str] = Query(None),
    tags: Optional[List[str]] = Query(default_factory=list),
    sort: Optional[str] = Query("lastModified", enum=["lastModified", "downloads", "likes", "author", "id"]),
    direction: Optional[int] = Query(-1, enum=[-1, 1]),
    limit: int = Query(30, ge=1, le=100), page: int = Query(1, ge=1)
):
    try:
        processed_tags: List[str] = []
        if tags:
            for tag_group in tags: 
                processed_tags.extend(t.strip() for t in tag_group.split(',') if t.strip())
        unique_tags = list(set(processed_tags)) if processed_tags else None
        models_data, has_more_results = model_loader.search_models(
            search_query=search, author=author, tags=unique_tags,
            sort_by=sort, sort_direction=direction, limit=limit, page=page
        )
        return PaginatedModelListResponse(
            items=[HFModelListItem(**model_data) for model_data in models_data],
            page=page, limit=limit, has_more=has_more_results
        )
    except Exception as e:
        logger.error(f"Error in search_hf_models: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error searching models.")

@app.get("/api/models/{author}/{model_name:path}", response_model=HFModelDetails, tags=["Models"])
async def get_hf_model_details(author: str, model_name: str):
    full_model_id = f"{author}/{model_name}"
    try:
        details_data = model_loader.get_model_details(author=author, model_name=model_name)
        if not details_data: raise HTTPException(status_code=404, detail=f"Model '{full_model_id}' not found.")
        return HFModelDetails(**details_data)
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error in get_hf_model_details for '{full_model_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching model details.")

# --- FileManager Endpoints ( остаются без изменений, außer scan-host-directories ) ---
@app.get("/api/filemanager/configuration", response_model=MalFullConfiguration, tags=["FileManager"])
async def get_file_manager_configuration():
    config = file_manager.get_current_configuration()
    return MalFullConfiguration(**config)

@app.post("/api/filemanager/configure", response_model=PathConfigurationResponse, tags=["FileManager"])
async def configure_file_manager_paths_endpoint(config_request: PathConfigurationRequest):
    result = file_manager.configure_paths(
        base_path_str=config_request.base_path,
        profile=config_request.profile,
        custom_model_type_paths=config_request.custom_model_type_paths,
        color_theme=config_request.color_theme
    )
    if not result.get("success"): raise HTTPException(status_code=400, detail=result.get("error", "Konfiguration fehlgeschlagen."))
    updated_config = file_manager.get_current_configuration()
    response_data = PathConfigurationResponse(**result)
    response_data.current_config = MalFullConfiguration(**updated_config)
    return response_data

@app.post("/api/filemanager/download", response_model=FileDownloadResponse, tags=["FileManager"])
async def download_model_file_endpoint(download_request: FileDownloadRequest):
    if not file_manager.base_path: raise HTTPException(status_code=400, detail="Basispfad nicht konfiguriert.")
    result = file_manager.download_model_file(**download_request.model_dump())
    if not result.get("success"):
        status = 404 if "nicht gefunden" in result.get("error", "").lower() else 500
        raise HTTPException(status_code=status, detail=result.get("error", "Download fehlgeschlagen."))
    return FileDownloadResponse(**result)

@app.get("/api/filemanager/list-directory", response_model=DirectoryStructureResponse, tags=["FileManager"])
async def list_directory_contents_endpoint(relative_path: Optional[str] = Query(None), depth: int = Query(1, ge=1, le=5)):
    if not file_manager.base_path:
        return DirectoryStructureResponse(success=False, error="Basispfad nicht konfiguriert.", base_path_configured=False, structure=None)
    structure = file_manager.list_folder_contents(relative_path_str=relative_path, depth=depth)
    if structure is None: raise HTTPException(status_code=400, detail="Ungültiger Pfad oder Fehler beim Auflisten.")
    return DirectoryStructureResponse(success=True, structure=structure, base_path_configured=True)

@app.post("/api/filemanager/rescan-path", response_model=RescanPathResponse, tags=["FileManager"])
async def rescan_directory_structure_endpoint(request_data: Optional[RescanPathRequest] = Body(None)):
    path_to_scan = request_data.path if request_data and request_data.path else None
    result = file_manager.rescan_base_path_structure(path_to_scan_str=path_to_scan)
    if not result.get("success"): raise HTTPException(status_code=500, detail=result.get("error", "Fehler beim Rescan."))
    return RescanPathResponse(**result)

@app.get("/api/filemanager/scan-host-directories", response_model=ScanHostDirectoriesResponse, tags=["FileManager"])
async def scan_host_directories_endpoint(
    path_to_scan: Optional[str] = Query(None, alias="path", description="Absoluter Pfad zum Scannen. Standard: System-Default."),
    max_depth: int = Query(2, ge=1, le=7, description="Maximale Tiefe des Scans (1-7). Standard ist 2 für initialen Load.") 
    # le=7 erlaubt initial_depth(2) + expand_depth(2) + expand_depth(2) + Puffer
):
    logger.info(f"Host directory scan request: path='{path_to_scan}', depth={max_depth}")
    try:
        scan_result = file_manager.list_host_directories(path_to_scan_str=path_to_scan, max_depth=max_depth)
        # Konvertiere die Datenstruktur für die Pydantic-Validierung, falls nötig.
        # HostDirectoryItem erwartet 'children' als Optional[List['HostDirectoryItem']] = None
        # Die `list_host_directories` sollte dies bereits so zurückgeben.
        data_for_response = scan_result.get("data", []) # Default zu leerer Liste

        print("finished scan_host_directories_endpoint, data_for_response:", data_for_response)
        
        return ScanHostDirectoriesResponse(
            success=scan_result.get("success", False),
            message=scan_result.get("message"),
            error=scan_result.get("error"),
            data=data_for_response # Direkt übergeben, Pydantic validiert
        )
    except Exception as e:
        logger.error(f"Schwerwiegender Fehler im Endpunkt scan_host_directories_endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Interner Fehler beim Scannen der Host-Verzeichnisse: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting M.A.L. API server for development (v{app.version})...")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
