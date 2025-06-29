# backend/main.py
from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional

# The Project structure is:
# project_root/
#  ├─ backend/
#  │  ├─ main.py
#  │  ├─ core/
#  │  │  ├─ model_loader.py
#  │  │  └─ file_manager.py
#  │  └─ api/
#  │     └─ models.py
#  └─ frontend/
#  └─ config/
#     └─ mal_settings.json
#
# For this structure, direct relative imports like `from .core...` are common if backend is a package.
# If running main.py directly and backend is not installed as a package,
# Python's path might need adjustment, or use absolute imports assuming 'backend' is in PYTHONPATH.
# For simplicity with uvicorn main:app, we'll assume 'backend' is discoverable.

from backend.core.model_loader import ModelLoader
from backend.core.file_manager import FileManager
from backend.api.models import (
    PaginatedModelListResponse, HFModelListItem, HFModelDetails,
    PathConfigurationRequest, PathConfigurationResponse,
    FileDownloadRequest, FileDownloadResponse,
    DirectoryStructureResponse, # Currently not fully used by an endpoint
    RescanPathRequest, RescanPathResponse, # Currently not fully used
    MalFullConfiguration,
    ScanHostDirectoriesResponse # HostDirectoryItem is implicitly used via this
)

import logging

# --- Logging Configuration ---
# Basic logging setup. For production, we should consider more advanced configurations
# (e.g., structured logging, sending logs to a file or service).
logging.basicConfig(
    level=logging.INFO, # Set to DEBUG for more verbose output during development
    format='%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)

# --- FastAPI Application Instance ---
app = FastAPI(
    title="M.A.L. - Model Asset Loader API",
    description="API for searching Hugging Face models, managing local model files, "
                "and configuring storage paths for AI asset management.",
    version="0.8.0", # Increment version as features are added/refined
    #openapi_tags=[ # Optional: Define tags for better Swagger UI organization
    #    {"name": "Models", "description": "Endpoints for searching and retrieving Hugging Face model information."},
    #    {"name": "FileManager", "description": "Endpoints for managing local file storage and configurations."},
    #]
)

# --- CORS (Cross-Origin Resource Sharing) Middleware ---
# Configure allowed origins for frontend requests.
# For development, "http://localhost:5173" (default Vite dev server) is common.
# For production, this should be replaced by the frontend's actual domain.
origins = [
    "http://localhost:5173", # Vite dev server
    # Add other origins if needed, e.g., the production frontend URL
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Only allow certain Origins, for Safety and Best Practice
    allow_credentials=True, # Allows cookies to be included in requests
    allow_methods=["*"],    # Allows all standard HTTP methods
    allow_headers=["*"],    # Allows all headers
)

# --- Service Instances ---
# Initialize the core service classes.
try:
    model_loader = ModelLoader()
    file_manager = FileManager()
except Exception as e:
    logger.critical(f"Failed to initialize core services: {e}", exc_info=True)
    # Depending on severity, we might want the app to not start or enter a degraded mode.
    # For now, it will likely raise an error if services are None.
    # Consider adding health check endpoints.
    raise RuntimeError(f"Core service initialization failed: {e}") from e


# --- API Endpoints ---

# === Model Search and Details Endpoints ===
@app.get(
    "/api/models/",
    response_model=PaginatedModelListResponse,
    tags=["Models"],
    summary="Search Hugging Face Models",
    description="Searches for models on the Hugging Face Hub with filters, sorting, and pagination."
)
async def search_hf_models(
    search: Optional[str] = Query(None, description="Search term to query model names, descriptions, etc."),
    author: Optional[str] = Query(None, description="Filter models by a specific author or organization."),
    tags: Optional[List[str]] = Query(
        default_factory=list,
        description="List of tags to filter by (e.g., 'text-generation,en'). "
                    "Multiple tags can be provided as separate query params or comma-separated in one."
    ),
    sort: Optional[str] = Query(
        "lastModified",
        enum=["lastModified", "downloads", "likes", "author", "id"], # Add more valid sort fields if supported by HfApi
        description="Field to sort results by."
    ),
    direction: Optional[int] = Query(-1, enum=[-1, 1], description="Sort direction: -1 for descending, 1 for ascending."),
    limit: int = Query(30, ge=1, le=100, description="Number of results per page."),
    page: int = Query(1, ge=1, description="Page number for pagination (1-indexed).")
):
    """
    Searches models on the Hugging Face Hub.
    Processes comma-separated tags from query parameters.
    """
    try:
        processed_tags: List[str] = []
        if tags:
            for tag_group in tags: # Each 'tag_group' could be "tag1" or "tag1,tag2"
                processed_tags.extend(t.strip() for t in tag_group.split(',') if t.strip())
        
        unique_tags = list(set(processed_tags)) if processed_tags else None
        logger.info(
            f"Searching models: query='{search}', author='{author}', tags='{unique_tags}', "
            f"sort='{sort}', dir='{direction}', limit={limit}, page={page}"
        )

        models_data, has_more_results = model_loader.search_models(
            search_query=search, author=author, tags=unique_tags,
            sort_by=sort, sort_direction=direction, limit=limit, page=page
        )
        return PaginatedModelListResponse(
            items=[HFModelListItem(**model_data) for model_data in models_data],
            page=page, limit=limit, has_more=has_more_results
        )
    except Exception as e:
        logger.error(f"Error in search_hf_models endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred while searching for models.")

@app.get(
    "/api/models/{author}/{model_name:path}",
    response_model=HFModelDetails,
    tags=["Models"],
    summary="Get Hugging Face Model Details",
    description="Retrieves detailed information for a specific model from the Hugging Face Hub, including its README."
)
async def get_hf_model_details(author: str, model_name: str):
    """
    Fetches details for a model identified by `author` and `model_name`.
    The `:path` converter for `model_name` allows it to contain slashes if the model name itself has them
    (though typically model names on HF don't, the repo ID `author/model_name` is the full ID).
    """
    full_model_id = f"{author}/{model_name}" # Construct the repo_id
    logger.info(f"Fetching details for model: {full_model_id}")
    try:
        details_data = model_loader.get_model_details(author=author, model_name=model_name)
        if not details_data:
            logger.warning(f"Model '{full_model_id}' not found by model_loader.")
            raise HTTPException(status_code=404, detail=f"Model '{full_model_id}' not found.")
        return HFModelDetails(**details_data)
    except HTTPException: # Re-raise HTTPExceptions (like 404) directly
        raise
    except Exception as e:
        logger.error(f"Error in get_hf_model_details for '{full_model_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred while fetching model details.")


# === FileManager Endpoints ===
@app.get(
    "/api/filemanager/configuration",
    response_model=MalFullConfiguration,
    tags=["FileManager"],
    summary="Get Current FileManager Configuration",
    description="Retrieves the current configuration of the FileManager, including base path, profile, and theme."
)
async def get_file_manager_configuration():
    """Returns the current live configuration settings."""
    logger.debug("Request received for current FileManager configuration.")
    config = file_manager.get_current_configuration()
    return MalFullConfiguration(**config)

@app.post(
    "/api/filemanager/configure",
    response_model=PathConfigurationResponse,
    tags=["FileManager"],
    summary="Configure FileManager Paths and Settings",
    description="Sets the base path, UI profile, custom model paths, and color theme. Configuration is saved to a file."
)
async def configure_file_manager_paths_endpoint(config_request: PathConfigurationRequest):
    """
    Applies new configuration settings to the FileManager.
    Returns the result of the operation and the updated full configuration.
    """
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
    # Prepare response data, ensuring all fields of PathConfigurationResponse are met
    response_data = PathConfigurationResponse(
        success=result.get("success", False),
        message=result.get("message"),
        error=result.get("error"), # Should be None if success is True
        configured_base_path=result.get("configured_base_path"),
        current_config=MalFullConfiguration(**updated_config_dict)
    )
    logger.info(f"Configuration successful. Current base path: {response_data.configured_base_path}")
    return response_data

@app.post(
    "/api/filemanager/download",
    response_model=FileDownloadResponse,
    tags=["FileManager"],
    summary="Download a Model File",
    description="Downloads a specific file from a Hugging Face repository to the configured local path."
)
async def download_model_file_endpoint(download_request: FileDownloadRequest):
    """
    Handles requests to download a model file.
    The FileManager determines the correct local subdirectory based on configuration.
    """
    logger.info(f"Received download request: {download_request.model_dump()}")
    if not file_manager.config.base_path:
        logger.warning("Download request failed: Base path not configured.")
        raise HTTPException(status_code=400, detail="Base path not configured. Please configure paths first.")

    # Pass all relevant fields from the request to the download method
    result = file_manager.download_model_file(
        repo_id=download_request.repo_id,
        filename=download_request.filename,
        model_type=download_request.model_type,
        custom_sub_path=download_request.custom_sub_path,
        revision=download_request.revision
    )

    if not result.get("success"):
        error_detail = result.get("error", "Download failed due to an unknown error.")
        logger.error(f"Download failed for {download_request.repo_id}/{download_request.filename}: {error_detail}")
        # Determine appropriate status code based on error message content
        status_code = 404 if "not found" in error_detail.lower() else 400 # Or 500 for server-side issues
        if "gated" in error_detail.lower(): status_code = 403 # Forbidden due to gated repo
        raise HTTPException(status_code=status_code, detail=error_detail)

    logger.info(f"Download successful: {result.get('message')}")
    return FileDownloadResponse(**result)


@app.get(
    "/api/filemanager/scan-host-directories",
    response_model=ScanHostDirectoriesResponse,
    tags=["FileManager"],
    summary="Scan Host System Directories",
    description="Scans directories on the host system, starting from a specified path or system defaults "
                "(e.g., drives on Windows, '/' on Linux/macOS). Used for selecting a base path."
)
async def scan_host_directories_endpoint(
    path_to_scan: Optional[str] = Query(
        None,
        alias="path", # Allows frontend to use 'path' as query param name
        description="Absolute path to scan. If not provided, scans system default locations."
    ),
    max_depth: int = Query(
        2, # Default depth
        ge=1, le=7, # Min depth 1, Max depth 7 (to prevent excessive scanning)
        description="Maximum depth of subdirectories to scan (1-7). Default is 2."
    )
):
    """
    Scans host directories to help users find and select a base storage path.
    This endpoint is crucial for the initial setup UX.
    """
    logger.info(f"Host directory scan request: path='{path_to_scan}', depth={max_depth}")
    try:
        scan_result = file_manager.list_host_directories(
            path_to_scan_str=path_to_scan,
            max_depth=max_depth
        )
        # The list_host_directories method should return data in the format
        # expected by HostDirectoryItem (List[Dict[str, Any]] where each dict matches HostDirectoryItem).
        # Pydantic will validate this upon creating ScanHostDirectoriesResponse.
        data_for_response = scan_result.get("data", [])

        logger.debug(f"Scan result data for response: {len(data_for_response)} root items.")
        # print(f"Data for response in endpoint: {data_for_response}") # For verbose debugging if needed

        return ScanHostDirectoriesResponse(
            success=scan_result.get("success", False),
            message=scan_result.get("message"),
            error=scan_result.get("error"),
            data=data_for_response
        )
    except Exception as e:
        logger.error(f"Critical error in scan_host_directories_endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"An internal error occurred while scanning host directories: {str(e)}"
        )

# --- Placeholder Endpoints (Not fully implemented or used by current frontend flow) ---
# These are kept for potential future use or if the frontend requires them.

@app.get(
    "/api/filemanager/list-directory",
    response_model=DirectoryStructureResponse,
    tags=["FileManager"],
    summary="List Contents of a Managed Directory (Placeholder)",
    description="Lists contents of a directory within the configured MAL base path. (Currently a placeholder)"
)
async def list_directory_contents_endpoint(
    relative_path: Optional[str] = Query(None, description="Path relative to the configured base_path. If None, lists base_path root."),
    depth: int = Query(1, ge=1, le=5, description="Depth of subdirectories to list.")
):
    logger.info(f"Request to list managed directory: relative_path='{relative_path}', depth={depth}")
    if not file_manager.base_path:
        logger.warning("Cannot list managed directory: Base path not configured.")
        return DirectoryStructureResponse(
            success=False,
            error="Base path not configured. Please set it up first.",
            base_path_configured=False,
            structure=None
        )
    # This method in FileManager is currently a placeholder.
    structure = file_manager.list_managed_directory_contents(
        relative_path_str=relative_path,
        depth=depth
    )
    if structure is None: # Assuming method returns None on error or invalid path
        logger.error(f"Failed to list managed directory contents for '{relative_path}'.")
        raise HTTPException(status_code=400, detail="Invalid path or error listing directory contents.")
    return DirectoryStructureResponse(success=True, structure=structure, base_path_configured=True)

@app.post(
    "/api/filemanager/rescan-path",
    response_model=RescanPathResponse,
    tags=["FileManager"],
    summary="Rescan a Managed Path (Placeholder)",
    description="Triggers a rescan of the specified path within the MAL base path. (Currently a placeholder)"
)
async def rescan_directory_structure_endpoint(request_data: Optional[RescanPathRequest] = Body(None)):
    """
    Placeholder for an endpoint that might trigger a refresh of cached directory structures.
    """
    path_to_scan = request_data.path if request_data and request_data.path else None
    logger.info(f"Request to rescan managed path: '{path_to_scan if path_to_scan else 'base_path_root'}'")

    # This method in FileManager is currently a placeholder.
    result = file_manager.rescan_base_path_structure(path_to_scan_str=path_to_scan)

    if not result.get("success"):
        logger.error(f"Rescan failed: {result.get('error', 'Unknown rescan error.')}")
        raise HTTPException(status_code=500, detail=result.get("error", "Error during rescan operation."))
    return RescanPathResponse(**result)


# --- Main Execution Block (for development) ---
if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting M.A.L. API server (v{app.version}) for development...")
    # reload=True is great for development, Uvicorn will restart on code changes.
    # For production, use a proper ASGI server like Gunicorn with Uvicorn workers.
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
