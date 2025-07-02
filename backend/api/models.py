# backend/api/models.py
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime

# --- Generic Model Information ---
# These models are now designed to be source-agnostic where possible,
# with source-specific details included.

class ModelFile(BaseModel):
    """Represents a file within a model repository."""
    rfilename: str = Field(..., description="The relative name of the file in the repository.")
    size: Optional[int] = Field(None, description="Size of the file in bytes.")

class ModelListItem(BaseModel):
    """Represents a model item in a list (e.g., search results)."""
    id: str = Field(..., description="The unique identifier of the model (e.g., 'author/model_name').")
    source: str = Field(..., description="The source of the model (e.g., 'huggingface').") # Added source
    author: Optional[str] = Field(None, description="The author or organization of the model.")
    model_name: str = Field(..., description="The name of the model, typically derived from the ID.")
    lastModified: Optional[datetime] = Field(None, description="Timestamp of the last modification.")
    tags: List[str] = Field(default_factory=list, description="List of tags associated with the model.")
    downloads: Optional[int] = Field(None, description="Number of downloads.")
    likes: Optional[int] = Field(None, description="Number of likes.")

class PaginatedModelListResponse(BaseModel):
    """Response model for a paginated list of models."""
    items: List[ModelListItem]
    page: int
    limit: int
    has_more: bool

class ModelDetails(ModelListItem):
    """Represents detailed information for a specific model."""
    sha: Optional[str] = Field(None, description="The commit hash of the model's repository.")
    private: Optional[bool] = Field(None, description="Indicates if the model repository is private.")
    gated: Optional[str] = Field(None, description="Gated status (e.g., 'auto', 'manual', 'True').")
    library_name: Optional[str] = Field(None, description="The primary library associated with the model.")
    pipeline_tag: Optional[str] = Field(None, description="The primary pipeline tag (e.g., 'text-generation').")
    siblings: List[ModelFile] = Field(..., description="List of all files in the model repository.")
    readme_content: Optional[str] = Field(None, description="The content of the model's README.md file.")

# For clarity in the OpenAPI docs, we can alias them, but functionally they are the same now.
HFModelListItem = ModelListItem
HFModelDetails = ModelDetails
HFModelFile = ModelFile

# --- Types for FileManager Configuration and Operations ---
UiProfileTypePydantic = Literal["ComfyUI", "A1111", "ForgeUI", "Custom"]
ModelTypePydantic = Literal[
    "checkpoints", "loras", "vae", "clip", "unet", "controlnet",
    "embeddings", "hypernetworks", "diffusers", "custom"
]
ColorThemeTypePydantic = Literal["dark", "light"]

# --- Models for Path and File Configuration ---
class MalFullConfiguration(BaseModel):
    """Represents the full, current configuration of the FileManager."""
    base_path: Optional[str]
    ui_profile: Optional[UiProfileTypePydantic] = Field(None, alias="profile")
    custom_model_type_paths: Dict[str, str]
    color_theme: Optional[ColorThemeTypePydantic]

    class Config:
        populate_by_name = True

class PathConfigurationRequest(BaseModel):
    base_path: Optional[str] = Field(None)
    profile: Optional[UiProfileTypePydantic] = Field(None)
    custom_model_type_paths: Optional[Dict[str, str]] = Field(None)
    color_theme: Optional[ColorThemeTypePydantic] = Field(None)

class PathConfigurationResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    configured_base_path: Optional[str] = None
    current_config: Optional[MalFullConfiguration] = None

# --- Models for File Download ---
class FileDownloadRequest(BaseModel):
    """Request model for downloading a model file."""
    source: str = Field(..., description="The source of the model (e.g., 'huggingface').") # Added source
    repo_id: str = Field(..., description="The repository ID (e.g., 'author/model_name').")
    filename: str = Field(..., description="The name of the file to download.")
    model_type: ModelTypePydantic
    custom_sub_path: Optional[str] = Field(None)
    revision: Optional[str] = Field(None)

class FileDownloadResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
    download_id: Optional[str] = Field(None, description="The unique ID for tracking the download.")

# --- Models for Local File Management (NEW) ---

class LocalFileItem(BaseModel):
    """Represents a file or directory within the managed base_path."""
    name: str = Field(..., description="The name of the file or directory.")
    path: str = Field(..., description="The relative path from the base_path.")
    item_type: Literal["file", "directory"] = Field(..., alias="type")
    size: Optional[int] = Field(None, description="Size of the file in bytes (null for directories).")
    last_modified: Optional[datetime] = Field(None, description="Timestamp of the last modification.")

    class Config:
        populate_by_name = True

class LocalFileActionRequest(BaseModel):
    """Request model for actions on a local file or directory."""
    path: str = Field(..., description="The relative path of the item to act upon.")

class LocalFileContentResponse(BaseModel):
    """Response model for fetching the content of a text file."""
    success: bool
    path: str
    content: Optional[str] = None
    error: Optional[str] = None

# --- Models for Directory Structure and Scanning (Existing) ---
class DirectoryItem(BaseModel):
    name: str
    path: str
    type: Literal["file", "directory"]
    children: Optional[List['DirectoryItem']] = None

DirectoryItem.model_rebuild()

class DirectoryStructureResponse(BaseModel):
    success: bool
    structure: Optional[List[DirectoryItem]] = None
    error: Optional[str] = None
    base_path_configured: bool

class RescanPathRequest(BaseModel):
    path: Optional[str] = Field(None)

class RescanPathResponse(BaseModel):
    success: bool
    message: Optional[str] = None

class HostDirectoryItem(BaseModel):
    name: str
    path: str
    type: Literal["directory"] = "directory"
    children: Optional[List['HostDirectoryItem']] = None

HostDirectoryItem.model_rebuild()

class ScanHostDirectoriesResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
    data: Optional[List[HostDirectoryItem]] = None

PathConfigurationResponse.model_rebuild()
