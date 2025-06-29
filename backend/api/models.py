# backend/api/models.py
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime

# --- Hugging Face Model Information ---

class HFModelFile(BaseModel):
    """Represents a file within a Hugging Face model repository."""
    rfilename: str = Field(..., description="The relative name of the file in the repository.")
    size: Optional[int] = Field(None, description="Size of the file in bytes, if available.")

    class Config:
        populate_by_name = True # For Pydantic V1 compatibility

class HFModelListItem(BaseModel):
    """Represents a model item as typically returned in a list (e.g., search results)."""
    id: str = Field(..., description="The unique identifier of the model (e.g., 'author/model_name').")
    author: Optional[str] = Field(None, description="The author or organization of the model.")
    model_name: str = Field(..., description="The name of the model, typically derived from the ID.")
    lastModified: Optional[datetime] = Field(None, alias="lastModified", description="Timestamp of the last modification.")
    tags: List[str] = Field(default_factory=list, description="List of tags associated with the model.")
    pipeline_tag: Optional[str] = Field(None, description="The primary pipeline tag (e.g., 'text-generation').")
    downloads: Optional[int] = Field(None, description="Number of downloads in the last month.")
    likes: Optional[int] = Field(None, description="Number of likes.")

    class Config:
        populate_by_name = True

class PaginatedModelListResponse(BaseModel):
    """Response model for a paginated list of Hugging Face models."""
    items: List[HFModelListItem]
    page: int = Field(..., description="The current page number (1-indexed).")
    limit: int = Field(..., description="The number of items per page.")
    has_more: bool = Field(..., description="Indicates if more pages are available.")

class HFModelDetails(HFModelListItem):
    """Represents detailed information for a specific Hugging Face model."""
    sha: Optional[str] = Field(None, description="The commit hash of the model's repository.")
    private: Optional[bool] = Field(None, description="Indicates if the model repository is private.")
    gated: Optional[str] = Field(None, description="Gated status (e.g., 'auto', 'manual', 'True', or None).")
    library_name: Optional[str] = Field(None, description="The primary library associated with the model (e.g., 'transformers').")
    siblings: List[HFModelFile] = Field(..., description="List of all files in the model repository.")
    readme_content: Optional[str] = Field(None, description="The content of the model's README.md file.")

    class Config:
        populate_by_name = True

# --- Types for FileManager Configuration and Operations ---

# These Literal types define the allowed string values for certain fields, ensuring type safety.
UiProfileTypePydantic = Literal["ComfyUI", "A1111", "ForgeUI", "Custom"]
ModelTypePydantic = Literal[
    "checkpoints", "loras", "vae", "clip", "unet", "controlnet",
    "embeddings", "hypernetworks", "diffusers", "custom"
]
ColorThemeTypePydantic = Literal["dark", "light"]

# --- Models for Path and File Configuration ---

class MalFullConfiguration(BaseModel):
    """Represents the full, current configuration of the FileManager."""
    base_path: Optional[str] = Field(None, description="The absolute base path for storing all models.")
    profile: Optional[UiProfileTypePydantic] = Field(None, description="The selected UI profile for default paths.")
    custom_model_type_paths: Dict[str, str] = Field(default_factory=dict, description="Custom paths for model types if profile is 'Custom'.")
    color_theme: Optional[ColorThemeTypePydantic] = Field("dark", description="The active UI color theme ('dark' or 'light').")

class PathConfigurationRequest(BaseModel):
    """Request model for configuring FileManager paths and settings."""
    base_path: Optional[str] = Field(None, description="The absolute base path for storing models. Use null or an empty string to clear.")
    profile: Optional[UiProfileTypePydantic] = Field(None, description="The UI profile to use (e.g., 'ComfyUI').")
    custom_model_type_paths: Optional[Dict[str, str]] = Field(None, description="Dictionary of custom paths if profile is 'Custom'. Key: ModelType, Value: relative path.")
    color_theme: Optional[ColorThemeTypePydantic] = Field(None, description="The UI color theme ('dark' or 'light').")

class PathConfigurationResponse(BaseModel):
    """Response model for a path configuration attempt."""
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
    configured_base_path: Optional[str] = Field(None, description="The newly configured absolute base path, if successful.")
    current_config: Optional[MalFullConfiguration] = Field(None, description="The complete current configuration after the operation.")

# --- Models for File Download ---

class FileDownloadRequest(BaseModel):
    """Request model for downloading a model file."""
    repo_id: str = Field(..., description="The Hugging Face repository ID (e.g., 'author/model_name').")
    filename: str = Field(..., description="The name of the file to download from the repository (can include subpaths).")
    model_type: ModelTypePydantic
    custom_sub_path: Optional[str] = Field(None, description="Optional custom sub-path relative to the base path, overriding profile settings.")
    revision: Optional[str] = Field(None, description="Optional Git revision (branch, tag, or commit hash).")

class FileDownloadResponse(BaseModel):
    """Response model for a file download attempt."""
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
    path: Optional[str] = Field(None, description="The absolute local path to the downloaded file, if successful.")

# --- Models for Directory Structure and Scanning ---

class DirectoryItem(BaseModel):
    """Represents an item (file or directory) within the MAL-managed base_path."""
    name: str
    path: str = Field(..., description="Path relative to the FileManager's base_path.")
    type: Literal["file", "directory"]
    children: Optional[List['DirectoryItem']] = None

DirectoryItem.model_rebuild() # Handles the self-referencing 'children' for Pydantic V1

class DirectoryStructureResponse(BaseModel):
    """Response model for listing contents of a managed directory."""
    success: bool
    structure: Optional[List[DirectoryItem]] = None
    error: Optional[str] = None
    base_path_configured: bool

class RescanPathRequest(BaseModel):
    """Request model for rescanning a path within the managed base_path."""
    path: Optional[str] = Field(None, description="Optional path relative to base_path to rescan. If None, rescans entire base_path.")

class RescanPathResponse(BaseModel):
    """Response model for a path rescan attempt."""
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None

# --- Models for Host Directory Scanning (for setup) ---

class HostDirectoryItem(BaseModel):
    """Represents a directory when scanning the host system for initial base_path selection."""
    name: str
    path: str = Field(..., description="Absolute path on the host system.")
    type: Literal["directory"] = "directory" # Always 'directory' for host scanning
    children: Optional[List['HostDirectoryItem']] = None

HostDirectoryItem.model_rebuild() # Handles self-referencing 'children' for Pydantic V1

class ScanHostDirectoriesResponse(BaseModel):
    """Response model for the host directory scan operation."""
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
    data: Optional[List[HostDirectoryItem]] = Field(None, description="List of scanned root directories and their children.")

# Final rebuild for any models with forward references.
PathConfigurationResponse.model_rebuild()
