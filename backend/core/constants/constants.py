# backend/core/constants/constants.py
import pathlib
from typing import Literal, Dict, Any

# --- Type Definitions ---
# These are used for strict type checking across the application.

ModelType = Literal[
    "checkpoints",
    "loras",
    "vae",
    "clip",
    "unet",
    "controlnet",
    "embeddings",
    "hypernetworks",
    "diffusers",
    "custom",
]
UiProfileType = Literal["ComfyUI", "A1111", "ForgeUI", "Custom"]
ColorThemeType = Literal["dark", "light"]

# --- New Type for UI Management ---
# This type is derived from the keys of UI_REPOSITORIES to ensure we only
# try to install UIs that are actually defined.
UiNameType = Literal["ComfyUI", "A1111", "ForgeUI"]


# --- Configuration File Constants ---
CONFIG_FILE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "config"
CONFIG_FILE_NAME = "mal_settings.json"
CONFIG_FILE_PATH = CONFIG_FILE_DIR / CONFIG_FILE_NAME


# --- Model Management Constants ---
MODEL_FILE_EXTENSIONS = (".safetensors", ".ckpt", ".pt", ".bin", ".pth", ".onnx")


# --- UI Profile Path Definitions ---
# Defines the subfolder structure for different UI profiles.
KNOWN_UI_PROFILES: Dict[UiProfileType, Dict[str, str]] = {
    "ComfyUI": {
        "checkpoints": "models/checkpoints",
        "loras": "models/loras",
        "vae": "models/vae",
        "clip": "models/clip",
        "controlnet": "models/controlnet",
        "embeddings": "models/embeddings",
        "diffusers": "models/diffusers",
        "unet": "models/unet",
        "hypernetworks": "models/hypernetworks",
    },
    "A1111": {
        "checkpoints": "models/Stable-diffusion",
        "loras": "models/Lora",
        "vae": "models/VAE",
        "embeddings": "embeddings",
        "hypernetworks": "models/hypernetworks",
        "controlnet": "models/ControlNet",
    },
    "ForgeUI": {
        "checkpoints": "models/Stable-diffusion",
        "loras": "models/Lora",
        "vae": "models/VAE",
        "embeddings": "embeddings",
        "hypernetworks": "models/hypernetworks",
        "controlnet": "models/ControlNet",
    },
}


# --- UI Installation & Management Constants ---
# This is the central knowledge base for installing different UIs.
# To add a new UI, simply add an entry here.
UI_REPOSITORIES: Dict[UiNameType, Dict[str, Any]] = {
    "ComfyUI": {
        "git_url": "https://github.com/comfyanonymous/ComfyUI.git",
        "requirements_file": "requirements.txt",
        "python_version": "3.10",  # Example of future metadata
    },
    "A1111": {
        "git_url": "https://github.com/AUTOMATIC1111/stable-diffusion-webui.git",
        "requirements_file": "requirements.txt",
        "python_version": "3.10",
    },
    "ForgeUI": {
        "git_url": "https://github.com/lllyasviel/stable-diffusion-webui-forge.git",
        "requirements_file": "requirements.txt",
        "python_version": "3.10",
    },
}


# --- Host Directory Scanning Constants ---
EXCLUDED_SCAN_PREFIXES_LINUX = ("/proc", "/sys", "/dev", "/snap")
SHALLOW_SCAN_PATHS_LINUX = {"/run", "/mnt", "/media"}
