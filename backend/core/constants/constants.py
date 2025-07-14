# backend/core/constants/constants.py
import pathlib
import os
from typing import Literal, Dict, Any, Set

# --- Type Definitions ---
# These Literal types provide strict type checking for key identifiers across the application,
# preventing typos and ensuring consistency.

# Defines the types of models the application can manage.
# These values are used as keys in the KNOWN_UI_PROFILES dictionary.
ModelType = Literal[
    "Checkpoint",
    "VAE",
    "LoRA",
    "LyCORIS",
    "ControlNet",
    "Upscaler",
    "Hypernetwork",
    "TextualInversion",
    "MotionModule",
    "Other",
]

# Defines the UI folder structures the application understands.
UiProfileType = Literal["ComfyUI", "A1111"]

# Defines the available color themes for the frontend.
ColorThemeType = Literal["dark", "light"]

# This type is dynamically derived from the keys of UI_REPOSITORIES to ensure
# we only ever try to install or manage UIs that are explicitly defined below.
UiNameType = Literal["ComfyUI", "A1111", "Forge", "Fooocus"]


# --- File System Paths and Directories ---
# Using pathlib for robust, cross-platform path handling.
BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent
CONFIG_FILE_DIR = BACKEND_DIR / "config"
CONFIG_FILE_NAME = "mal_settings.json"
CONFIG_FILE_PATH = CONFIG_FILE_DIR / CONFIG_FILE_NAME
MANAGED_UIS_ROOT_PATH = BACKEND_DIR.parent.parent / "managed_uis"


# --- Model File Extensions ---
# A set is used for efficient 'in' checks when scanning for model files.
MODEL_FILE_EXTENSIONS: Set[str] = {
    ".safetensors",
    ".ckpt",
    ".pt",
    ".bin",
    ".pth",
    ".onnx",
}


# --- UI Profile Path Definitions ---
# This dictionary maps a standardized ModelType to its specific subdirectory
# for each known UI profile. This is the core of the automatic path resolution.
KNOWN_UI_PROFILES: Dict[UiProfileType, Dict[ModelType, str]] = {
    "ComfyUI": {
        "Checkpoint": "models/checkpoints",
        "VAE": "models/vae",
        "LoRA": "models/loras",
        "LyCORIS": "models/loras",  # ComfyUI often uses the same folder for LoRA and LyCORIS
        "ControlNet": "models/controlnet",
        "TextualInversion": "models/embeddings",
        "Hypernetwork": "models/hypernetworks",
        "Upscaler": "models/upscale_models",
        "MotionModule": "models/motion_modules",
    },
    "A1111": {
        "Checkpoint": "models/Stable-diffusion",
        "VAE": "models/VAE",
        "LoRA": "models/Lora",
        "LyCORIS": "models/LyCORIS",
        "ControlNet": "models/ControlNet",
        "TextualInversion": "embeddings",
        "Hypernetwork": "models/hypernetworks",
        "Upscaler": "models/ESRGAN",  # A1111 has several upscaler folders, this is a common one
    },
}


# --- UI Repositories and Configuration ---
# This dictionary is the single source of truth for UI-specific details.
# It defines the git repository, required files, and the correct launch script.
UI_REPOSITORIES: Dict[UiNameType, Dict[str, Any]] = {
    "ComfyUI": {
        "git_url": "https://github.com/comfyanonymous/ComfyUI.git",
        "requirements_file": "requirements.txt",
        "start_script": "main.py",
        "default_profile_name": "ComfyUI",
    },
    "A1111": {
        "git_url": "https://github.com/AUTOMATIC1111/stable-diffusion-webui.git",
        "requirements_file": "requirements.txt",
        # We point to the shell/batch script, not the python file, to ensure
        # all environment checks and setup steps are properly executed by the UI itself.
        "start_script": "webui.sh" if os.name != "nt" else "webui.bat",
        "default_profile_name": "A1111",
    },
    "Forge": {
        "git_url": "https://github.com/lllyasviel/stable-diffusion-webui-forge.git",
        "requirements_file": "requirements.txt",
        # Forge also uses a shell script launcher.
        "start_script": "webui.sh" if os.name != "nt" else "webui.bat",
        # Forge uses an A1111-compatible folder structure for models.
        "default_profile_name": "A1111",
    },
    "Fooocus": {
        "git_url": "https://github.com/lllyasviel/Fooocus.git",
        "requirements_file": "requirements.txt",
        # Fooocus is special; it often uses an entrypoint file that handles updates.
        "start_script": "entry_with_update.py",
        # Its internal structure is closer to ComfyUI for key models.
        "default_profile_name": "ComfyUI",
        # Fooocus has specific package needs not always in its requirements.
        "extra_packages": ["pygit2"],
    },
}

# --- Host Directory Scanning Constants ---
# Defines system paths to exclude during directory scans to improve performance
# and avoid issues with virtual or protected file systems on Linux.
EXCLUDED_SCAN_PREFIXES_LINUX = ("/proc", "/sys", "/dev", "/snap")
SHALLOW_SCAN_PATHS_LINUX = {"/run", "/mnt", "/media"}
