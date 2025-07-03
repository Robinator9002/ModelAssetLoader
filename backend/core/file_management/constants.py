# backend/core/file_management/constants.py
import pathlib
from typing import Literal, Dict, List

# --- Type Definitions ---
ModelType = Literal[
    "checkpoints", "loras", "vae", "clip", "unet", "controlnet",
    "embeddings", "hypernetworks", "diffusers", "custom"
]
UiProfileType = Literal["ComfyUI", "A1111", "ForgeUI", "Custom"]
ColorThemeType = Literal["dark", "light"]

# --- Configuration File Constants ---
CONFIG_FILE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent.parent / "config"
CONFIG_FILE_NAME = "mal_settings.json"
CONFIG_FILE_PATH = CONFIG_FILE_DIR / CONFIG_FILE_NAME

# --- Model File Extensions ---
MODEL_FILE_EXTENSIONS = ('.safetensors', '.ckpt', '.pt', '.bin', '.pth', '.onnx')

# --- UI Profile Definitions ---
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
    }
}

# --- Host Directory Scanning Constants ---
EXCLUDED_SCAN_PREFIXES_LINUX = ("/proc", "/sys", "/dev", "/snap")
SHALLOW_SCAN_PATHS_LINUX = {"/run", "/mnt", "/media"}
