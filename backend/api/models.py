# backend/api/models.py
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field # field_validator is not used in current version
from datetime import datetime

# --- Hugging Face Model Information ---
class HFModelFile(BaseModel):
    """Represents a file within a Hugging Face model repository."""
    rfilename: str = Field(..., description="The relative name of the file in the repository.")
    size: Optional[int] = Field(None, description="Size of the file in bytes, if available.")

    # Pydantic V1 style for allowing population by alias (though not strictly needed here)
    # For Pydantic V2, this would be model_config = {"populate_by_name": True}
    class Config:
        populate_by_name = True

class HFModelListItem(BaseModel):
    """Represents a model item as typically returned in a list (e.g., search results)."""
    id: str = Field(..., description="The unique identifier of the model (e.g., 'author/model_name').")
    author: Optional[str] = Field(None, description="The author or organization of the model.")
    model_name: str = Field(..., description="The name of the model (derived from ID if not directly available).")
    lastModified: Optional[datetime] = Field(None, alias="lastModified", description="Timestamp of the last modification.")
    tags: List[str] = Field(default_factory=list, description="List of tags associated with the model.")
    pipeline_tag: Optional[str] = Field(None, description="The primary pipeline tag (e.g., 'text-generation').")
    downloads: Optional[int] = Field(None, description="Number of downloads in the last month.")
    likes: Optional[int] = Field(None, description="Number of likes.")

    class Config:
        populate_by_name = True


class PaginatedModelListResponse(BaseModel):
    """Response model for a paginated list of Hugging Face models."""
    items: List[HFModelListItem] = Field(..., description="List of model items on the current page.")
    page: int = Field(..., description="The current page number (1-indexed).")
    limit: int = Field(..., description="The number of items per page.")
    has_more: bool = Field(..., description="Indicates if more pages are available.")

class HFModelDetails(HFModelListItem):
    """Represents detailed information for a specific Hugging Face model."""
    sha: Optional[str] = Field(None, description="The commit hash of the model's repository.")
    private: Optional[bool] = Field(None, description="Indicates if the model repository is private.")
    gated: Optional[str] = Field(None, description="Gated status (e.g., 'auto', 'manual', 'True', 'False', or None).")
    library_name: Optional[str] = Field(None, description="The primary library associated with the model (e.g., 'transformers', 'diffusers').")
    siblings: List[HFModelFile] = Field(..., description="List of files in the model repository.")
    readme_content: Optional[str] = Field(None, description="The content of the model's README.md file.")

    class Config:
        populate_by_name = True


# --- Types for FileManager Configuration and Operations ---
# These Literal types define the allowed string values for certain fields.
UiProfileTypePydantic = Literal["ComfyUI", "A1111", "ForgeUI", "Custom"]
ModelTypePydantic = Literal[
    "checkpoints", "loras", "vae", "clip", "unet", "controlnet",
    "embeddings", "hypernetworks", "diffusers", "custom"
]
ColorThemeTypePydantic = Literal["dark", "light"]

# --- Models for Path Configuration ---
class PathConfigurationRequest(BaseModel):
    """Request model for configuring FileManager paths and settings."""
    base_path: Optional[str] = Field(None, description="The absolute base path for storing models. Empty string or null to clear.")
    profile: Optional[UiProfileTypePydantic] = Field(None, description="The UI profile to use (e.g., 'ComfyUI').")
    custom_model_type_paths: Optional[Dict[str, str]] = Field(
        None, description="Dictionary of custom paths if profile is 'Custom'. Key: ModelType, Value: relative path."
    )
    color_theme: Optional[ColorThemeTypePydantic] = Field(None, description="The color theme for the UI ('dark' or 'light').")

class MalFullConfiguration(BaseModel):
    """Represents the full current configuration of the FileManager."""
    base_path: Optional[str] = Field(None, description="The absolute base path for storing models.")
    profile: Optional[UiProfileTypePydantic] = Field(None, description="The selected UI profile.")
    custom_model_type_paths: Dict[str, str] = Field(
        default_factory=dict, description="Custom paths for model types if profile is 'Custom'."
    )
    color_theme: Optional[ColorThemeTypePydantic] = Field(
        "dark", description="The active color theme ('dark' or 'light')."
    )

class PathConfigurationResponse(BaseModel):
    """Response model for path configuration attempts."""
    success: bool = Field(..., description="Indicates if the configuration was successful.")
    message: Optional[str] = Field(None, description="A message providing details about the operation.")
    error: Optional[str] = Field(None, description="An error message if the operation failed.")
    configured_base_path: Optional[str] = Field(None, description="The newly configured absolute base path, if successful.")
    current_config: Optional[MalFullConfiguration] = Field(
        None, description="The complete current configuration after the operation."
    )
    # Pydantic V2: PathConfigurationResponse.model_rebuild() might be needed if MalFullConfiguration is defined later
    # For Pydantic V1, forward references are often handled by string type hints or later model_rebuild calls.

# --- Models for File Download ---
class FileDownloadRequest(BaseModel):
    """Request model for downloading a model file."""
    repo_id: str = Field(..., description="The Hugging Face repository ID (e.g., 'author/model_name').")
    filename: str = Field(..., description="The name of the file to download from the repository (can include subpaths).")
    model_type: ModelTypePydantic = Field(..., description="The type of model, used to determine the target subdirectory.")
    custom_sub_path: Optional[str] = Field(
        None, description="Optional custom sub-path relative to the base path, overrides profile settings."
    )
    revision: Optional[str] = Field(None, description="Optional Git revision (branch, tag, or commit hash).")

class FileDownloadResponse(BaseModel):
    """Response model for file download attempts."""
    success: bool = Field(..., description="Indicates if the download was successful.")
    message: Optional[str] = Field(None, description="A message providing details about the download.")
    error: Optional[str] = Field(None, description="An error message if the download failed.")
    path: Optional[str] = Field(None, description="The absolute local path to the downloaded file, if successful.")

# --- Models for Managed Directory Structure (within base_path, not yet fully used) ---
class DirectoryItem(BaseModel):
    """Represents an item (file or directory) within the MAL-managed base_path."""
    name: str = Field(..., description="Name of the file or directory.")
    path: str = Field(..., description="Path relative to the FileManager's base_path.")
    type: Literal["file", "directory"] = Field(..., description="Type of the item.")
    children: Optional[List['DirectoryItem']] = Field(None, description="List of child items if type is 'directory'.")

DirectoryItem.model_rebuild() # For Pydantic V1 to handle the self-referencing 'children'

class DirectoryStructureResponse(BaseModel):
    """Response model for listing contents of a managed directory."""
    success: bool = Field(..., description="Indicates if the listing was successful.")
    structure: Optional[List[DirectoryItem]] = Field(None, description="The directory structure, if successful.")
    error: Optional[str] = Field(None, description="An error message if listing failed.")
    base_path_configured: bool = Field(..., description="Indicates if the FileManager's base_path is currently configured.")

class RescanPathRequest(BaseModel):
    """Request model for rescanning a path within the managed base_path."""
    path: Optional[str] = Field(None, description="Optional path relative to base_path to rescan. If None, rescans entire base_path.")

class RescanPathResponse(BaseModel):
    """Response model for path rescan attempts."""
    success: bool = Field(..., description="Indicates if the rescan was successful (or initiated).")
    message: Optional[str] = Field(None, description="A message about the rescan operation.")
    error: Optional[str] = Field(None, description="An error message if rescan failed.")


# --- Models for Host Directory Scanning (browsing the user's filesystem) ---
class HostDirectoryItem(BaseModel):
    """
    Represents a directory item when scanning the host system for initial base_path selection.
    Paths are absolute on the host system.
    """
    name: str = Field(..., description="Name of the directory.")
    path: str = Field(..., description="Absolute path on the host system.")
    type: Literal["directory"] = Field("directory", description="Type is always 'directory' for host scanning.") # Only directories are listed
    children: Optional[List['HostDirectoryItem']] = Field(None, description="List of child directories.")

HostDirectoryItem.model_rebuild() # For Pydantic V1 self-referencing

class ScanHostDirectoriesRequest(BaseModel):
    """
    Represents query parameters for scanning host directories.
    Not directly used as a request body, but defines expected parameters.
    """
    path_to_scan: Optional[str] = Field(
        None, alias="path", description="Specific absolute path to scan. If None, scans system default (drives on Win, / on Linux/macOS)."
    )
    max_depth: int = Field(
        2, ge=1, le=7, # ge=greater or equal, le=less or equal
        description="Maximum depth of subdirectories to scan (1-7). Default is 2 for initial load."
    )

class ScanHostDirectoriesResponse(BaseModel):
    """Response model for the host directory scan operation."""
    success: bool = Field(..., description="Indicates if the scan operation was successful.")
    message: Optional[str] = Field(None, description="A message providing details about the scan.")
    error: Optional[str] = Field(None, description="An error message if the scan failed.")
    data: Optional[List[HostDirectoryItem]] = Field(
        None, description="List of scanned root directories and their children."
    )

# Call model_rebuild for models with forward references if using Pydantic V1
# This is important if MalFullConfiguration is used as a type hint before its full definition
# is seen by the interpreter in PathConfigurationResponse.
PathConfigurationResponse.model_rebuild()
