# backend/core/file_manager.py
import os
import shutil
import json
import pathlib
import platform # For OS-specific logic like drive letters
import string   # For getting drive letters on Windows
from typing import List, Dict, Optional, Any, Literal, Set

from huggingface_hub import hf_hub_download, HfApi
from huggingface_hub.utils import RepositoryNotFoundError, EntryNotFoundError, GatedRepoError
import logging

logger = logging.getLogger(__name__)

# --- Configuration File Setup ---
# Determine the config directory relative to this file's location (backend/core)
# Assuming this file is in backend/core, then parent is backend, parent.parent is project root.
# Config will be stored in project_root/config/mal_settings.json
CONFIG_FILE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "config"
CONFIG_FILE_NAME = "mal_settings.json"
CONFIG_FILE_PATH = CONFIG_FILE_DIR / CONFIG_FILE_NAME

# --- Type Definitions (consistent with Pydantic models) ---
ModelType = Literal[
    "checkpoints", "loras", "vae", "clip", "unet", "controlnet",
    "embeddings", "hypernetworks", "diffusers", "custom"
]
UiProfileType = Literal["ComfyUI", "A1111", "ForgeUI", "Custom"]
ColorThemeType = Literal["dark", "light"]


# --- Default Paths for Known UI Profiles ---
# These are relative to the configured base_path.
KNOWN_UI_PROFILES: Dict[UiProfileType, Dict[str, str]] = {
    "ComfyUI": {
        "checkpoints": "models/checkpoints",
        "loras": "models/loras",
        "vae": "models/vae",
        "clip": "models/clip", # For CLIP Vision models, etc.
        "controlnet": "models/controlnet",
        "embeddings": "models/embeddings", # Textual Inversion embeddings
        "diffusers": "models/diffusers",   # For full Diffusers model pipelines
        "unet": "models/unet",             # For UNet models if stored separately
        "hypernetworks": "models/hypernetworks",
    },
    "A1111": { # Automatic1111 Stable Diffusion WebUI
        "checkpoints": "models/Stable-diffusion",
        "loras": "models/Lora",
        "vae": "models/VAE",
        "embeddings": "embeddings", # Textual Inversion embeddings
        "hypernetworks": "models/hypernetworks",
        "controlnet": "models/ControlNet", # Or sometimes extensions/sd-webui-controlnet/models
    },
    "ForgeUI": { # SD.Next / ForgeUI (often similar to A1111)
        "checkpoints": "models/Stable-diffusion",
        "loras": "models/Lora",
        "vae": "models/VAE",
        "embeddings": "embeddings",
        "hypernetworks": "models/hypernetworks",
        "controlnet": "models/ControlNet",
    }
    # "Custom" profile paths are defined by the user.
}

# --- Host Directory Scanning Constants ---
# Paths to exclude from deep scanning to avoid issues with pseudo-filesystems or excessive depth.
# These are checked if they are *not* the initial scan root.
EXCLUDED_SCAN_PREFIXES_LINUX = ("/proc", "/sys", "/dev", "/snap")
# Paths that, if encountered as children of another path, should only be scanned shallowly.
# Example: If scanning '/', and we encounter '/run', list children of '/run' but don't go deeper into them.
SHALLOW_SCAN_PATHS_LINUX = {"/run", "/mnt", "/media"} # /mnt and /media often have mount points

class FileManager:
    """
    Manages file operations, configuration storage, model downloads,
    and directory scanning for the Model Asset Loader.
    """
    def __init__(self):
        self.hf_api = HfApi()
        self.base_path: Optional[pathlib.Path] = None
        self.ui_profile: Optional[UiProfileType] = None
        self.custom_paths: Dict[str, str] = {} # For "Custom" profile
        self.color_theme: ColorThemeType = 'dark' # Default theme

        self._ensure_config_dir_exists()
        self._load_config_from_file()
        logger.info(
            f"FileManager initialized. Profile: '{self.ui_profile}', "
            f"Base Path: '{self.base_path}', Theme: '{self.color_theme}'"
        )

    def _ensure_config_dir_exists(self):
        """Ensures the configuration directory exists."""
        try:
            CONFIG_FILE_DIR.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Configuration directory ensured: {CONFIG_FILE_DIR}")
        except Exception as e:
            logger.error(f"Could not create or access config directory {CONFIG_FILE_DIR}: {e}")

    def _save_config_to_file(self) -> bool:
        """Saves the current configuration to the JSON file."""
        if not CONFIG_FILE_DIR.exists() or not CONFIG_FILE_DIR.is_dir():
            logger.error(f"Config directory {CONFIG_FILE_DIR} does not exist. Cannot save settings.")
            return False

        config_data = {
            "base_path": str(self.base_path) if self.base_path else None,
            "ui_profile": self.ui_profile,
            "custom_paths": self.custom_paths,
            "color_theme": self.color_theme
        }
        try:
            with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4)
            logger.info(f"Configuration saved to {CONFIG_FILE_PATH}")
            return True
        except Exception as e:
            logger.error(f"Error saving configuration to {CONFIG_FILE_PATH}: {e}", exc_info=True)
            return False

    def _load_config_from_file(self):
        """Loads configuration from the JSON file if it exists."""
        if CONFIG_FILE_PATH.exists() and CONFIG_FILE_PATH.is_file():
            try:
                with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                    config_data = json.load(f)

                base_path_str = config_data.get("base_path")
                loaded_base_path = None
                if base_path_str:
                    try:
                        # Resolve to an absolute path and check if it's a directory
                        resolved_path = pathlib.Path(base_path_str).resolve()
                        if resolved_path.is_dir():
                            loaded_base_path = resolved_path
                        else:
                            logger.warning(
                                f"Loaded base_path '{base_path_str}' from config "
                                f"is not a valid directory. Ignoring."
                            )
                    except Exception as path_e:
                        logger.warning(
                            f"Error resolving loaded base_path '{base_path_str}' from config: {path_e}. Ignoring."
                        )
                self.base_path = loaded_base_path
                self.ui_profile = config_data.get("ui_profile")
                self.custom_paths = config_data.get("custom_paths", {})
                self.color_theme = config_data.get("color_theme", 'dark') # Default to 'dark' if missing
                logger.info(f"Configuration loaded from {CONFIG_FILE_PATH}")
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON from config file {CONFIG_FILE_PATH}: {e}. Using defaults.")
                self._initialize_default_config_state()
            except Exception as e:
                logger.error(f"Unexpected error loading config from {CONFIG_FILE_PATH}: {e}", exc_info=True)
                self._initialize_default_config_state()
        else:
            logger.info(f"Config file {CONFIG_FILE_PATH} not found. Initializing with default state.")
            self._initialize_default_config_state()

    def _initialize_default_config_state(self):
        """Resets configuration to a default (empty) state."""
        self.base_path = None
        self.ui_profile = None
        self.custom_paths = {}
        self.color_theme = 'dark'

    def get_current_configuration(self) -> Dict[str, Any]:
        """Returns the current live configuration of the FileManager."""
        return {
            "base_path": str(self.base_path) if self.base_path else None,
            "ui_profile": self.ui_profile,
            "custom_model_type_paths": self.custom_paths,
            "color_theme": self.color_theme
        }

    def configure_paths(
        self,
        base_path_str: Optional[str],
        profile: Optional[UiProfileType],
        custom_model_type_paths: Optional[Dict[str, str]] = None,
        color_theme: Optional[ColorThemeType] = None
    ) -> Dict[str, Any]:
        """
        Configures the base path, UI profile, custom paths, and color theme.
        Saves the configuration if changes are made.
        """
        config_changed = False
        error_message: Optional[str] = None

        if base_path_str is not None: # Allow empty string to clear base_path
            if base_path_str == "": # Explicitly clear base_path
                if self.base_path is not None:
                    self.base_path = None
                    config_changed = True
                    logger.info("Base path cleared by user.")
            else:
                try:
                    p = pathlib.Path(base_path_str).resolve()
                    if not p.is_dir():
                        # Try to create it if it doesn't exist
                        p.mkdir(parents=True, exist_ok=True)
                        logger.info(f"Created base path directory: {p}")
                    if self.base_path != p:
                        self.base_path = p
                        config_changed = True
                        logger.info(f"Base path configured to: {p}")
                except Exception as e:
                    error_message = f"Invalid base path '{base_path_str}' or could not create it: {e}"
                    logger.error(error_message)
                    return {"success": False, "error": error_message}

        if profile is not None and self.ui_profile != profile:
            self.ui_profile = profile
            config_changed = True
            logger.info(f"UI profile changed to: {profile}")

        if custom_model_type_paths is not None and self.custom_paths != custom_model_type_paths:
            self.custom_paths = custom_model_type_paths
            config_changed = True
            logger.info(f"Custom model type paths updated: {custom_model_type_paths}")

        if color_theme is not None and self.color_theme != color_theme:
            self.color_theme = color_theme
            config_changed = True
            logger.info(f"Color theme changed to: {color_theme}")

        if config_changed:
            if not self._save_config_to_file():
                # Error saving, but some changes might have been applied in memory
                # This case should be handled carefully.
                return {"success": False, "error": "Configuration updated in memory, but failed to save to file."}

        return {
            "success": True,
            "message": "Configuration updated successfully." if config_changed else "No changes to configuration.",
            "configured_base_path": str(self.base_path) if self.base_path else None
        }

    def get_target_directory(self, model_type: ModelType, custom_sub_path: Optional[str] = None) -> Optional[pathlib.Path]:
        """
        Determines the target directory for a given model type based on the current configuration.

        Args:
            model_type: The type of the model (e.g., "checkpoints", "loras").
            custom_sub_path: An optional user-defined sub-path, overriding profile settings.

        Returns:
            A pathlib.Path object to the target directory, or None if base_path is not set
            or the path cannot be safely determined.
        """
        if not self.base_path:
            logger.warning("Cannot get target directory: base_path is not configured.")
            return None

        relative_path_str = ""

        if custom_sub_path:
            # User explicitly provided a sub-path
            relative_path_str = custom_sub_path
            logger.debug(f"Using custom sub-path for {model_type}: {custom_sub_path}")
        elif self.ui_profile == "Custom":
            relative_path_str = self.custom_paths.get(str(model_type), str(model_type))
            logger.debug(f"Using 'Custom' profile path for {model_type}: {relative_path_str}")
        elif self.ui_profile in KNOWN_UI_PROFILES:
            profile_paths = KNOWN_UI_PROFILES.get(self.ui_profile, {})
            relative_path_str = profile_paths.get(str(model_type), str(model_type)) # Fallback to model_type itself
            logger.debug(f"Using '{self.ui_profile}' profile path for {model_type}: {relative_path_str}")
        else:
            # No profile or unknown profile, use model_type as the directory name directly under base_path
            relative_path_str = str(model_type)
            logger.debug(f"No specific profile match for {model_type}, using as directory name: {relative_path_str}")

        # Ensure relative_path_str is not empty; if so, default to model_type name
        if not relative_path_str.strip():
            relative_path_str = str(model_type)
            logger.debug(f"Relative path was empty, defaulting to model type name: {relative_path_str}")

        try:
            # Sanitize the relative path to prevent path traversal issues (e.g., '../', '/')
            # 1. Normalize path separators for the current OS
            normalized_path = os.path.normpath(relative_path_str)

            # 2. Split into components
            path_components = normalized_path.split(os.sep)

            # 3. Filter out problematic components like '..' or empty strings (from multiple slashes)
            # Also disallow absolute paths in the relative_path_str.
            # An absolute path starts with os.sep or, on Windows, a drive letter like C:\
            if os.path.isabs(normalized_path):
                logger.error(f"Security: Absolute path '{relative_path_str}' provided as relative path. Denying.")
                return None

            # Filter '..' and empty components
            # Allow '.' as it means current directory and normpath handles it.
            safe_components = [comp for comp in path_components if comp and comp != '..']
            if not safe_components: # If all components were filtered out (e.g. "../..")
                 logger.warning(f"Relative path '{relative_path_str}' resolved to empty after sanitization. Defaulting to model type.")
                 safe_components = [str(model_type)]


            clean_relative_path = pathlib.Path(*safe_components)
            target_dir = (self.base_path / clean_relative_path).resolve()

            # Final security check: ensure the resolved target_dir is still within the base_path
            if not str(target_dir).startswith(str(self.base_path.resolve())):
                logger.error(
                    f"Security: Resolved target directory '{target_dir}' is outside "
                    f"the configured base path '{self.base_path.resolve()}'. Denying."
                )
                return None
            return target_dir
        except Exception as e:
            logger.error(f"Error determining target directory for '{relative_path_str}': {e}", exc_info=True)
            return None

    def download_model_file(
            self,
            repo_id: str,
            filename: str, # This is the filename on Hugging Face Hub
            model_type: ModelType,
            custom_sub_path: Optional[str] = None,
            revision: Optional[str] = None # Git revision (branch, tag, commit hash)
        ) -> Dict[str, Any]:
        """
        Downloads a model file from Hugging Face Hub to the appropriate local directory.

        Args:
            repo_id: The repository ID on Hugging Face (e.g., "author/model_name").
            filename: The specific file to download from the repository.
            model_type: The type of model, used to determine the subdirectory.
            custom_sub_path: Optional user-defined sub-path relative to base_path.
            revision: Optional git revision (branch, tag, commit hash).

        Returns:
            A dictionary indicating success or failure, with messages and paths.
        """
        if not self.base_path:
            return {"success": False, "error": "Base path is not configured. Please configure it first."}

        target_model_type_dir = self.get_target_directory(model_type, custom_sub_path)
        if not target_model_type_dir:
            error_msg = (f"Could not determine a valid target directory for model type '{model_type}' "
                         f"with custom path '{custom_sub_path if custom_sub_path else 'N/A'}'. "
                         f"Ensure paths are valid and within the base directory.")
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        try:
            # The filename from HF Hub might include subdirectories within the repo.
            # We want to preserve this structure *within* the target_model_type_dir.
            # Example: filename on Hub is "unet/diffusion_pytorch_model.bin"
            # target_model_type_dir is ".../base_path/models/diffusers"
            # final_local_path should be ".../base_path/models/diffusers/unet/diffusion_pytorch_model.bin"

            # hf_hub_download handles the download to a cache.
            # We then copy it to our organized structure.
            logger.info(f"Attempting to download '{filename}' from repo '{repo_id}' (revision: {revision or 'main'}).")
            cached_file_path_str = hf_hub_download(
                repo_id=repo_id,
                filename=filename, # This is the rfilename on the Hub
                revision=revision,
                repo_type="model", # Explicitly state repo type
                local_dir_use_symlinks=False # Avoid symlinks for broader compatibility
            )
            logger.info(f"File '{filename}' cached at: {cached_file_path_str}")

            # Determine the final local path, preserving subdirectories from the Hub filename
            # os.path.basename(filename) would strip repository subdirectories.
            # We need to construct the path correctly.
            # final_local_path = target_model_type_dir / filename # This correctly appends parts
            # Example: target_model_type_dir = /path/to/checkpoints
            # filename = subfolder/model.safetensors
            # final_local_path = /path/to/checkpoints/subfolder/model.safetensors

            # Ensure the full path for the file exists within target_model_type_dir
            # If 'filename' contains slashes (e.g., "unet/model.bin"),
            # target_model_type_dir / filename will correctly form the path.
            # We need to create the parent directory of the *final file*.
            final_local_path = target_model_type_dir.joinpath(filename).resolve()

            # Security check: ensure the final path is still within the target_model_type_dir,
            # which itself is already verified to be within base_path.
            # This handles cases where 'filename' might have '..' after normalization,
            # though pathlib's joinpath and resolve should typically handle this.
            if not str(final_local_path).startswith(str(target_model_type_dir.resolve())):
                logger.error(
                    f"Security: Calculated final download path '{final_local_path}' for file '{filename}' "
                    f"is outside its determined model type directory '{target_model_type_dir.resolve()}'. Aborting."
                )
                return {"success": False, "error": f"Invalid file path construction for '{filename}'."}

            final_local_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Ensured directory exists: {final_local_path.parent}")

            shutil.copy2(cached_file_path_str, final_local_path)
            logger.info(f"Successfully copied '{cached_file_path_str}' to '{final_local_path}'.")

            return {
                "success": True,
                "message": f"File '{os.path.basename(filename)}' downloaded successfully to '{final_local_path.parent}'.",
                "path": str(final_local_path)
            }
        except RepositoryNotFoundError:
            logger.warning(f"Repository '{repo_id}' not found on Hugging Face Hub.")
            return {"success": False, "error": f"Repository '{repo_id}' not found."}
        except EntryNotFoundError:
            logger.warning(f"File '{filename}' not found in repository '{repo_id}' (revision: {revision or 'default'}).")
            return {"success": False, "error": f"File '{filename}' not found in repository '{repo_id}'."}
        except GatedRepoError:
            logger.warning(f"Access to repository '{repo_id}' is gated. Please agree to terms on Hugging Face Hub.")
            return {"success": False, "error": f"Repository '{repo_id}' is gated. Manual access required on Hugging Face."}
        except Exception as e:
            logger.error(f"Download error for '{filename}' from '{repo_id}': {e}", exc_info=True)
            return {"success": False, "error": f"Download error for '{filename}': {str(e)}"}

    def _scan_host_dirs_recursive(
        self,
        current_path: pathlib.Path,
        current_depth: int,
        max_depth: int,
        visited_ids: Set[tuple], # To detect symlink loops or already visited inodes
        initial_scan_root: pathlib.Path, # The absolute, resolved path of the initial scan request
        is_shallow_scan_area: bool = False # True if current_path is a SHALLOW_SCAN_PATHS child
    ) -> List[Dict[str, Any]]:
        """
        Recursively scans directories on the host system.

        Internal helper method.
        """
        items: List[Dict[str, Any]] = []
        current_path_str = str(current_path)

        # 1. Max depth check
        if current_depth > max_depth:
            return items

        # 2. Exclude problematic system paths (Linux/macOS specific for now)
        #    This check applies if current_path is a child/grandchild etc. of the initial scan root.
        if platform.system() != "Windows" and current_path != initial_scan_root:
            if any(current_path_str.startswith(prefix) for prefix in EXCLUDED_SCAN_PREFIXES_LINUX):
                logger.debug(f"Excluding deep scan for system path prefix: {current_path_str}")
                return items

        # 3. Symlink and visited check (ID-based: device + inode)
        try:
            # Resolve symlinks to get the canonical path for stat and ID, but be careful.
            # We list the symlink's name, but its children come from the target.
            target_for_stat = current_path
            # is_symlink = current_path.is_symlink() # Check original path

            if current_path.is_symlink():
                try:
                    # Try to resolve strictly first to get the canonical target for ID
                    target_for_stat = current_path.resolve(strict=True)
                except FileNotFoundError:
                    logger.debug(f"Symlink {current_path_str} is broken. Skipping.")
                    return items
                except Exception: # Fallback to non-strict if strict fails for other reasons (e.g. perms)
                    try:
                        target_for_stat = current_path.resolve(strict=False)
                    except Exception as e_resolve:
                        logger.warning(f"Could not resolve symlink {current_path_str} for stat: {e_resolve}. Skipping.")
                        return items
            
            if not target_for_stat.exists() or not target_for_stat.is_dir():
                 logger.debug(f"Path {current_path_str} (target for stat: {target_for_stat}) does not exist or is not a directory. Skipping.")
                 return items

            path_stat = target_for_stat.stat() # Stat the target of the symlink, or the path itself
            path_id = (path_stat.st_dev, path_stat.st_ino)

            if path_id in visited_ids:
                logger.warning(
                    f"Path {current_path_str} (target: {target_for_stat}, ID: {path_id}) "
                    f"detected as symlink loop or already visited. Skipping."
                )
                return items
            visited_ids.add(path_id) # Add canonical path ID to visited set
            
        except (OSError, PermissionError) as e_stat:
            # Log permission errors but continue, as some dirs might be inaccessible
            logger.warning(f"Could not stat {current_path_str} (target: {target_for_stat if 'target_for_stat' in locals() else 'N/A'}): {e_stat}. Skipping.")
            return items
        except Exception as e_stat_general:
            # Catch any other unexpected errors during stat/resolve
            logger.error(f"Unexpected error stating/resolving {current_path_str}: {e_stat_general}", exc_info=True)
            return items

        # 4. Iterate through directory contents
        try:
            # Use a temporary list for entries to handle potential errors during iteration
            entries_to_process = []
            for entry in current_path.iterdir():
                entries_to_process.append(entry)

            for entry in entries_to_process:
                # Skip hidden files/directories (like .DS_Store, .git)
                if entry.name.startswith('.'):
                    continue
                
                try:
                    # We are only interested in directories for further scanning
                    if not entry.is_dir(): # This checks the entry itself, symlink or not
                        continue
                except (OSError, FileNotFoundError): # Entry might have been removed or became inaccessible
                    logger.debug(f"Could not access or determine type of entry {entry}. Skipping.")
                    continue
                
                # Important: The 'path' for the API item should be the symlink's path if 'entry' is a symlink,
                # or the direct path if it's a regular directory.
                # However, recursion happens on the resolved path.
                # For the API, we return the path as the user would see it.
                api_path_for_item = str(entry.absolute())

                # Check if this entry's resolved path is the same as the initial scan root.
                # This is to prevent symlinks inside a scanned directory pointing back to the root
                # from causing the root to appear as a child of itself.
                try:
                    resolved_entry_target = entry.resolve(strict=False) # Non-strict for this check
                    if resolved_entry_target == initial_scan_root and entry.name != initial_scan_root.name:
                        logger.warning(
                            f"Skipping child entry '{entry.name}' at '{current_path_str}' because its resolved path "
                            f"'{resolved_entry_target}' is the same as the initial_scan_root '{initial_scan_root}' "
                            f"but has a different name. This avoids redundant listing or potential confusion."
                        )
                        continue
                except Exception as e_resolve_check:
                     logger.debug(f"Could not resolve entry {entry} for initial_scan_root check: {e_resolve_check}")
                     # Continue, as this is a preventative check


                dir_info = {
                    "name": entry.name,
                    "path": api_path_for_item, # The path as it appears in the filesystem
                    "type": "directory",
                    "children": None # Initialize, will be populated by recursion if applicable
                }
                
                # Recursion logic:
                # If the current_path we are iterating is a "shallow scan area" (e.g., /run when /run was a child of /),
                # then we do not recurse into the children of *this* current_path.
                # The children of current_path (i.e., 'entry' items) will be listed, but their children won't.
                
                # Determine if the *next* level of recursion (for 'entry') should be shallow.
                # This is true if 'entry' itself resolves to a path defined in SHALLOW_SCAN_PATHS_LINUX
                # AND this 'entry' is not the initial root of the entire scan operation.
                next_level_is_shallow = False
                if platform.system() != "Windows":
                    try:
                        resolved_entry_for_shallow_check = entry.resolve(strict=False)
                        if str(resolved_entry_for_shallow_check) in SHALLOW_SCAN_PATHS_LINUX and \
                           resolved_entry_for_shallow_check != initial_scan_root:
                            next_level_is_shallow = True
                            logger.debug(f"Entry {entry} (resolved: {resolved_entry_for_shallow_check}) is a shallow scan target. Its children won't be deeply scanned.")
                    except Exception:
                        pass # Ignore errors in this specific check

                # Only recurse if:
                # 1. We are not already in a shallow scan area that prevents further depth for its children.
                # 2. The current depth is less than the maximum allowed depth.
                if not is_shallow_scan_area and (current_depth < max_depth):
                    children = self._scan_host_dirs_recursive(
                        entry, # Recurse on the entry itself (symlink or dir)
                        current_depth + 1,
                        max_depth,
                        visited_ids,
                        initial_scan_root,
                        is_shallow_scan_area=next_level_is_shallow # Pass shallow flag for next level
                    )
                    if children: # Only add children list if it's not empty
                        dir_info["children"] = children
                elif is_shallow_scan_area:
                     logger.debug(f"Shallow scan: Not recursing into children of {entry} because parent {current_path_str} was a shallow scan area's child.")

                items.append(dir_info)
            
            # Sort items alphabetically by name for consistent output
            items.sort(key=lambda x: x['name'].lower())

        except PermissionError:
            logger.warning(f"Permission denied while iterating directory: {current_path_str}. Some items may be missing.")
        except FileNotFoundError:
            logger.warning(f"Directory not found during iterdir(): {current_path_str}. It might have been removed.")
        except Exception as e:
            logger.error(f"Unexpected error scanning directory contents of {current_path_str}: {e}", exc_info=True)
        
        return items

    def list_host_directories(self, path_to_scan_str: Optional[str] = None, max_depth: int = 1) -> Dict[str, Any]:
        """
        Lists directories on the host system, starting from a given path or system defaults.

        Args:
            path_to_scan_str: The absolute path to start scanning from.
                              If None, uses system defaults (drives on Windows, '/' on Linux/macOS).
            max_depth: Maximum depth of subdirectories to scan. 1 means only direct children.

        Returns:
            A dictionary with scan results, including success status, messages, and data.
        """
        logger.info(f"Scanning host directories. Target: '{path_to_scan_str or 'System Default'}', Max Depth: {max_depth}")
        if max_depth <= 0:
            logger.warning(f"max_depth was {max_depth}, adjusting to 1.")
            max_depth = 1 # Ensure at least one level is scanned

        root_scan_paths_to_process: List[pathlib.Path] = []
        scan_operation_description = ""
        
        if path_to_scan_str:
            scan_operation_description = f"path '{path_to_scan_str}'"
            try:
                start_path = pathlib.Path(path_to_scan_str)
                # Resolve to an absolute path. strict=True ensures it exists.
                resolved_start_path = start_path.resolve(strict=True)
                if not resolved_start_path.is_dir():
                     return {"success": False, "error": f"Path '{path_to_scan_str}' (resolved: {resolved_start_path}) is not a directory.", "data": []}
                root_scan_paths_to_process.append(resolved_start_path)
            except FileNotFoundError:
                return {"success": False, "error": f"Path '{path_to_scan_str}' not found.", "data": []}
            except Exception as e: # Catch other resolution errors (e.g., permissions early on)
                return {"success": False, "error": f"Error resolving path '{path_to_scan_str}': {e}", "data": []}
        else: # No specific path given, use system defaults
            if platform.system() == 'Windows':
                scan_operation_description = "Windows drives"
                # Get available drive letters
                drive_letters = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:")]
                for drive_path_str in drive_letters:
                    try:
                        drive_path = pathlib.Path(drive_path_str).resolve(strict=True) # Ensure drive exists
                        if drive_path.is_dir(): # Check if it's accessible as a directory
                            root_scan_paths_to_process.append(drive_path)
                    except Exception as e:
                        logger.warning(f"Could not access drive {drive_path_str}: {e}")
            else: # Linux, macOS, etc.
                scan_operation_description = "root directory '/'"
                root_path = pathlib.Path('/')
                try:
                    if root_path.is_dir() and root_path.resolve(strict=True): # Check existence and accessibility
                        root_scan_paths_to_process.append(root_path)
                    else:
                        logger.error("Root directory '/' is not accessible or not a directory.")
                except Exception as e:
                     logger.error(f"Error accessing root directory '/': {e}")
        
        if not root_scan_paths_to_process:
            message = f"No scannable start paths found for {scan_operation_description}."
            logger.info(message)
            return {"success": True, "message": message, "data": []}

        all_scan_results: List[Dict[str, Any]] = []
        for initial_root_path_item in root_scan_paths_to_process:
            visited_ids_for_this_root_scan = set() # Fresh set for each root scan (e.g., each drive)
            
            # The name of the root node in the response
            node_name = initial_root_path_item.name if initial_root_path_item.name else str(initial_root_path_item)
            # For '/' on Linux/macOS, .name is empty, so str() gives '/'
            if str(initial_root_path_item) == "/" and not node_name : node_name = "/"
            
            # This is the absolute, resolved path that _scan_host_dirs_recursive uses as its initial reference
            # to avoid symlink loops pointing back to the very start of this specific scan operation.
            initial_scan_root_absolute_resolved = initial_root_path_item # Already resolved

            root_node_api_data = {
                "name": node_name,
                "path": str(initial_root_path_item), # The path as requested or determined
                "type": "directory",
                "children": None # Initialize
            }
            
            # The children of initial_root_path_item are at depth 1.
            # initial_root_path_item itself is effectively depth 0 relative to this scan.
            # Determine if this initial_root_path_item itself is a shallow scan area.
            is_initial_root_shallow = False
            if platform.system() != "Windows":
                 if str(initial_root_path_item) in SHALLOW_SCAN_PATHS_LINUX:
                     is_initial_root_shallow = True
                     logger.debug(f"Initial scan root {initial_root_path_item} is a shallow scan target. Its children won't be deeply scanned.")


            children_items = self._scan_host_dirs_recursive(
                initial_root_path_item, # Start recursion from this root
                current_depth=1,        # Children are at depth 1
                max_depth=max_depth,
                visited_ids=visited_ids_for_this_root_scan,
                initial_scan_root=initial_scan_root_absolute_resolved,
                is_shallow_scan_area=is_initial_root_shallow # Pass the shallow flag for the root's children
            )
            if children_items:
                root_node_api_data["children"] = children_items
            all_scan_results.append(root_node_api_data)

        final_message = f"Scan for {scan_operation_description} completed. {len(all_scan_results)} root item(s) processed."
        logger.info(final_message)
        return {"success": True, "message": final_message, "data": all_scan_results}

    # --- Methods for managing local directory structure (within base_path) ---
    # These methods are not yet implemented but could be added for features like
    # listing contents of the MAL-managed directories, rescanning them, etc.

    def list_managed_directory_contents(
        self, relative_path_str: Optional[str] = None, depth: int = 1
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Lists the contents of a directory within the configured base_path.
        (Placeholder - to be implemented if needed for UI browsing of managed files)
        """
        if not self.base_path:
            logger.warning("Cannot list managed directory: base_path is not configured.")
            return None
        # Implementation would involve scanning self.base_path / relative_path_str
        # similar to _scan_host_dirs_recursive but constrained to base_path
        # and potentially filtering for known model files or specific structures.
        logger.info(f"Placeholder: list_managed_directory_contents called for '{relative_path_str}', depth {depth}")
        return [] # Placeholder

    def rescan_base_path_structure(self, path_to_scan_str: Optional[str] = None) -> Dict[str, Any]:
        """
        Rescans the structure of the configured base_path or a specific sub-path within it.
        (Placeholder - to be implemented for refreshing UI views of local files)
        """
        if not self.base_path:
            return {"success": False, "error": "Base path is not configured."}
        
        scan_target_path = self.base_path
        if path_to_scan_str:
            try:
                # Ensure path_to_scan_str is relative to base_path and safe
                # This logic needs to be robust like in get_target_directory
                # For now, assuming it's a simple relative path for placeholder.
                prospective_path = (self.base_path / path_to_scan_str).resolve()
                if not str(prospective_path).startswith(str(self.base_path.resolve())):
                    return {"success": False, "error": "Specified path for rescan is outside the base path."}
                if not prospective_path.is_dir():
                    return {"success": False, "error": "Specified path for rescan is not a directory."}
                scan_target_path = prospective_path
            except Exception as e:
                 return {"success": False, "error": f"Invalid path for rescan: {e}"}

        logger.info(f"Placeholder: Rescanning structure for path: {scan_target_path}")
        # Actual rescanning logic would go here.
        # This might involve clearing a cache and re-populating it,
        # or simply returning a success message for now.
        return {"success": True, "message": f"Rescan initiated for {scan_target_path} (placeholder)."}

