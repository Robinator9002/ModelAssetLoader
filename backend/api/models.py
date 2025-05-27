# backend/api/models.py
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

# --- Existing Models ---
class HFModelFile(BaseModel):
    rfilename: str = Field(..., description="The name of the file.")
    size: Optional[int] = Field(None, description="Size of the file in bytes.")
    class Config: populate_by_name = True

class HFModelListItem(BaseModel):
    id: str = Field(...)
    author: Optional[str] = None
    model_name: str = Field(...)
    lastModified: Optional[datetime] = Field(None, alias="lastModified")
    tags: List[str] = Field(default_factory=list)
    pipeline_tag: Optional[str] = None
    downloads: Optional[int] = None
    likes: Optional[int] = None
    class Config: populate_by_name = True

class PaginatedModelListResponse(BaseModel):
    items: List[HFModelListItem]
    page: int
    limit: int
    has_more: bool

class HFModelDetails(HFModelListItem):
    sha: Optional[str] = None
    private: Optional[bool] = None
    gated: Optional[str] = None
    library_name: Optional[str] = None
    siblings: List[HFModelFile] = Field(...)
    readme_content: Optional[str] = None
    class Config: populate_by_name = True

# --- Types for FileManager ---
UiProfileTypePydantic = Literal["ComfyUI", "A1111", "ForgeUI", "Custom"]
ModelTypePydantic = Literal[
    "checkpoints", "loras", "vae", "clip", "unet", "controlnet",
    "embeddings", "hypernetworks", "diffusers", "custom"
]
ColorThemeTypePydantic = Literal["dark", "light"] # Neuer Typ für Pydantic

# --- Models for Path Configuration and Download ---
class PathConfigurationRequest(BaseModel):
    base_path: Optional[str] = None # Optional, falls nur Theme geändert wird
    profile: Optional[UiProfileTypePydantic] = None # Optional
    custom_model_type_paths: Optional[Dict[str, str]] = None # Optional
    color_theme: Optional[ColorThemeTypePydantic] = None # Neuer Parameter, optional

class PathConfigurationResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
    configured_base_path: Optional[str] = None
    current_config: Optional['MalFullConfiguration'] = None # Um die volle Konfig zurückzugeben

class FileDownloadRequest(BaseModel):
    repo_id: str
    filename: str
    model_type: ModelTypePydantic
    custom_sub_path: Optional[str] = None
    revision: Optional[str] = None

class FileDownloadResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
    path: Optional[str] = None

class DirectoryItem(BaseModel):
    name: str
    path: str # Relative to the base_path of FileManager
    type: Literal["file", "directory"]
    children: Optional[List['DirectoryItem']] = None

DirectoryItem.model_rebuild() # Pydantic v2 style

class DirectoryStructureResponse(BaseModel):
    success: bool
    structure: Optional[List[DirectoryItem]] = None
    error: Optional[str] = None
    base_path_configured: bool

class RescanPathRequest(BaseModel):
    path: Optional[str] = None

class RescanPathResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None

class MalFullConfiguration(BaseModel):
    base_path: Optional[str] = Field(None, description="The absolute base path for storing models.")
    profile: Optional[UiProfileTypePydantic] = Field(None, description="The selected UI profile.")
    custom_model_type_paths: Dict[str, str] = Field(default_factory=dict, description="Custom paths for model types if profile is 'Custom'.")
    color_theme: Optional[ColorThemeTypePydantic] = Field("dark", description="The active Color Theme ('dark' or 'light').")


# --- Models for Host Directory Scanning ---
class HostDirectoryItem(BaseModel):
    """
    Represents a directory item when scanning the host system.
    Paths are absolute.
    """
    name: str
    path: str # Absolute path on the host system
    type: Literal["directory"] # Only directories are listed
    children: Optional[List['HostDirectoryItem']] = None

HostDirectoryItem.model_rebuild()

class ScanHostDirectoriesRequest(BaseModel):
    """
    Request model for scanning host directories.
    Not directly used as body, but represents query parameters.
    """
    path_to_scan: Optional[str] = Field(None, description="Specific absolute path to scan. If None, scans system default (drives on Win, / on Linux).")
    max_depth: int = Field(2, ge=1, le=5, description="Maximum depth of subdirectories to scan.")

class ScanHostDirectoriesResponse(BaseModel):
    """
    Response model for the host directory scan.
    """
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
    data: Optional[List[HostDirectoryItem]] = Field(None, description="List of scanned root directories and their children.")

PathConfigurationResponse.model_rebuild() # Wegen der Vorwärtsreferenz auf MalFullConfiguration
