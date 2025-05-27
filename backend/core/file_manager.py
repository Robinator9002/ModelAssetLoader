import os
import shutil
import json
import pathlib
from typing import List, Dict, Optional, Any, Literal, Set
from huggingface_hub import hf_hub_download, HfApi
from huggingface_hub.utils import RepositoryNotFoundError, EntryNotFoundError, GatedRepoError
import logging
import string # Für Laufwerksbuchstaben unter Windows

logger = logging.getLogger(__name__)

CONFIG_FILE_DIR = pathlib.Path(__file__).resolve().parent.parent / "config"
CONFIG_FILE_NAME = "mal_settings.json"
CONFIG_FILE_PATH = CONFIG_FILE_DIR / CONFIG_FILE_NAME


ModelType = Literal[
    "checkpoints", "loras", "vae", "clip", "unet", "controlnet",
    "embeddings", "hypernetworks", "diffusers", "custom"
]
UiProfileType = Literal["ComfyUI", "A1111", "ForgeUI", "Custom"]
ColorThemeType = Literal["dark", "light"]


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

EXCLUDED_SCAN_PREFIXES = ("/proc", "/sys", "/dev")
SHALLOW_SCAN_PATHS = {"/run"} 

class FileManager:
    def __init__(self):
        self.hf_api = HfApi()
        self.base_path: Optional[pathlib.Path] = None
        self.ui_profile: Optional[UiProfileType] = None
        self.custom_paths: Dict[str, str] = {}
        self.color_theme: ColorThemeType = 'dark' 
        self._ensure_config_dir_exists()
        self._load_config_from_file()
        logger.info(f"FileManager initialized. Config loaded: profile='{self.ui_profile}', base_path='{self.base_path}', theme='{self.color_theme}'")

    def _ensure_config_dir_exists(self):
        try:
            CONFIG_FILE_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Could not create or access config directory {CONFIG_FILE_DIR}: {e}")

    def _save_config_to_file(self) -> bool:
        if not CONFIG_FILE_DIR.exists() or not CONFIG_FILE_DIR.is_dir():
            logger.error(f"Config directory {CONFIG_FILE_DIR} does not exist. Cannot save.")
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
            return True
        except Exception as e:
            logger.error(f"Error saving configuration to {CONFIG_FILE_PATH}: {e}", exc_info=True)
            return False

    def _load_config_from_file(self):
        if CONFIG_FILE_PATH.exists() and CONFIG_FILE_PATH.is_file():
            try:
                with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                base_path_str = config_data.get("base_path")
                loaded_base_path = None
                if base_path_str:
                    try:
                        resolved_path = pathlib.Path(base_path_str).resolve()
                        if resolved_path.is_dir(): loaded_base_path = resolved_path
                        else: logger.warning(f"Loaded base_path '{base_path_str}' is not a valid directory.")
                    except Exception as path_e: logger.warning(f"Error resolving loaded base_path '{base_path_str}': {path_e}.")
                self.base_path = loaded_base_path
                self.ui_profile = config_data.get("ui_profile")
                self.custom_paths = config_data.get("custom_paths", {})
                self.color_theme = config_data.get("color_theme", 'dark')
            except Exception as e:
                logger.error(f"Error loading config from {CONFIG_FILE_PATH}: {e}", exc_info=True)
                self._initialize_default_config_state()
        else:
            self._initialize_default_config_state()
    
    def _initialize_default_config_state(self):
        self.base_path = None
        self.ui_profile = None
        self.custom_paths = {}
        self.color_theme = 'dark'

    def get_current_configuration(self) -> Dict[str, Any]:
        return {"base_path": str(self.base_path) if self.base_path else None, "ui_profile": self.ui_profile, "custom_model_type_paths": self.custom_paths, "color_theme": self.color_theme}

    def configure_paths(
        self, base_path_str: Optional[str], profile: Optional[UiProfileType], 
        custom_model_type_paths: Optional[Dict[str, str]] = None, color_theme: Optional[ColorThemeType] = None
    ) -> Dict[str, Any]:
        config_changed = False
        if base_path_str is not None:
            try:
                p = pathlib.Path(base_path_str).resolve();
                if not p.is_dir(): p.mkdir(parents=True, exist_ok=True)
                if self.base_path != p: self.base_path = p; config_changed = True
            except Exception as e: return {"success": False, "error": "Basispfad ist ungültig oder konnte nicht erstellt werden."}
        if profile is not None and self.ui_profile != profile: self.ui_profile = profile; config_changed = True
        if custom_model_type_paths is not None and self.custom_paths != custom_model_type_paths : self.custom_paths = custom_model_type_paths; config_changed = True
        if color_theme is not None and self.color_theme != color_theme: self.color_theme = color_theme; config_changed = True
        if config_changed: self._save_config_to_file()
        return {"success": True, "message": "Konfiguration aktualisiert.", "configured_base_path": str(self.base_path) if self.base_path else None}

    def get_target_directory(self, model_type: ModelType, custom_sub_path: Optional[str] = None) -> Optional[pathlib.Path]:
        if not self.base_path: return None
        relative_path_str = ""
        if custom_sub_path: relative_path_str = custom_sub_path
        elif self.ui_profile == "Custom": relative_path_str = self.custom_paths.get(str(model_type), str(model_type))
        elif self.ui_profile in KNOWN_UI_PROFILES: relative_path_str = KNOWN_UI_PROFILES.get(self.ui_profile, {}).get(str(model_type), str(model_type))
        else: relative_path_str = str(model_type) 
        if not relative_path_str.strip(): relative_path_str = str(model_type)
        try:
            chars_to_strip = "".join(list(set([os.sep, '.'] + ([os.altsep] if os.altsep else []))))
            path_after_lstrip = relative_path_str.lstrip(chars_to_strip)
            clean_relative_path = os.path.normpath(path_after_lstrip)
            if '..' in clean_relative_path.split(os.sep) or clean_relative_path.startswith(os.sep) or \
               (os.altsep and os.altsep != os.sep and clean_relative_path.startswith(os.altsep)): return None
            target_dir = (self.base_path / clean_relative_path).resolve()
            if not str(target_dir).startswith(str(self.base_path.resolve())): return None
            return target_dir
        except Exception: return None

    def download_model_file(
            self, repo_id: str, filename: str, model_type: ModelType,
            custom_sub_path: Optional[str] = None, revision: Optional[str] = None
        ) -> Dict[str, Any]:
        if not self.base_path: return {"success": False, "error": "Basispfad nicht konfiguriert."}
        target_model_type_dir = self.get_target_directory(model_type, custom_sub_path)
        if not target_model_type_dir: return {"success": False, "error": f"Zielverzeichnis für '{model_type}' konnte nicht bestimmt werden."}
        try:
            hf_full_filename = filename 
            actual_filename = os.path.basename(hf_full_filename)
            if '..' in actual_filename.replace('\\', '/').split('/'): return {"success": False, "error": f"Ungültiger Dateiname '{actual_filename}'."}
            final_local_path = target_model_type_dir / actual_filename
            target_model_type_dir.mkdir(parents=True, exist_ok=True) 
            cached_file_path_str = hf_hub_download(repo_id=repo_id, filename=hf_full_filename, revision=revision, repo_type="model", local_dir_use_symlinks=False)
            shutil.copy2(cached_file_path_str, final_local_path) 
            return {"success": True, "message": f"'{actual_filename}' erfolgreich heruntergeladen.", "path": str(final_local_path)}
        except Exception as e: return {"success": False, "error": f"Downloadfehler für '{filename}': {str(e)}"}

    def _scan_host_dirs_recursive(
        self, 
        current_path: pathlib.Path, 
        current_depth: int, 
        max_depth: int, 
        visited_ids: Set[tuple], 
        initial_scan_root: pathlib.Path,
        # Flag to indicate if we are processing children of a path that should only be shallowly scanned
        # when it's encountered as a child of another path (e.g. /run when scanning /)
        parent_was_shallow_scan_target: bool = False 
    ) -> List[Dict[str, Any]]:
        items = []
        current_path_str = str(current_path)

        # 1. Tiefenbegrenzung (generell)
        if current_depth > max_depth:
            return items

        # 2. Ausschluss problematischer Systempfade 
        #    (außer wenn sie der explizit angeforderte Startpfad des Scans sind)
        if current_path != initial_scan_root: # This check applies if current_path is a child/grandchild etc.
            if any(current_path_str.startswith(prefix) for prefix in EXCLUDED_SCAN_PREFIXES):
                logger.debug(f"Excluding deep scan for system path prefix: {current_path_str}")
                return items 
        
        # 3. Symlink- und Besucht-Check (ID-basiert)
        try:
            target_for_stat = current_path
            is_symlink = current_path.is_symlink()
            if is_symlink:
                try:
                    target_for_stat = current_path.resolve(strict=True) # Try strict first for ID
                except FileNotFoundError: 
                    logger.debug(f"Symlink {current_path} is broken. Skipping.")
                    return items
                except Exception: # Fallback to non-strict if strict fails for other reasons
                    try:
                        target_for_stat = current_path.resolve(strict=False)
                    except Exception as e_resolve:
                        logger.warning(f"Could not resolve symlink {current_path} for stat: {e_resolve}. Skipping.")
                        return items
            
            if not target_for_stat.exists() or not target_for_stat.is_dir():
                 logger.debug(f"Path {current_path} (target for stat: {target_for_stat}) does not exist or is not a directory. Skipping.")
                 return items

            path_stat = target_for_stat.stat()
            path_id = (path_stat.st_dev, path_stat.st_ino)

            if path_id in visited_ids:
                logger.warning(f"Symlink loop or already visited (ID: {path_id}) for {current_path} (target: {target_for_stat}). Skipping.")
                return items
            visited_ids.add(path_id)
            
        except (OSError, PermissionError) as e_stat: 
            logger.warning(f"Could not stat {current_path} (target: {target_for_stat if 'target_for_stat' in locals() else 'N/A'}): {e_stat}. Skipping.")
            return items
        except Exception as e_stat_general: 
            logger.error(f"Unexpected error stating {current_path}: {e_stat_general}", exc_info=True)
            return items

        # 4. Iteriere durch Verzeichnisinhalte
        try:
            for entry in current_path.iterdir(): 
                if entry.name.startswith('.'): continue
                
                try:
                    if not entry.is_dir(): continue # Nur Verzeichnisse berücksichtigen
                except (OSError, FileNotFoundError): continue
                
                resolved_entry_path_str = ""
                try:
                    resolved_entry_path = entry.resolve(strict=True) # Try strict for canonical path
                    resolved_entry_path_str = str(resolved_entry_path)
                except Exception: 
                    resolved_entry_path_str = str(entry.absolute()) # Fallback

                # **VERBESSERTER SCHUTZ GEGEN ÜBERSCHREIBEN DES AKTUELLEN SCAN ROOTS DURCH KIND-SYMLINK**
                if str(resolved_entry_path) == str(initial_scan_root) and entry.name != initial_scan_root.name :
                    logger.warning(f"Skipping child entry '{entry.name}' at '{current_path}' because its resolved path '{resolved_entry_path_str}' is the same as the initial_scan_root '{initial_scan_root}' but has a different name (e.g. 'host' for '/'). This prevents data corruption.")
                    continue
                
                path_for_api_item = str(entry.absolute()) 

                dir_info = {"name": entry.name, "path": path_for_api_item, "type": "directory", "children": None }
                
                # Rekursionslogik
                # Wenn der aktuelle Pfad ein "SHALLOW_SCAN_PATH" ist UND er nicht der initial_scan_root ist
                # (d.h. wir sind als Kind von / in /run gelandet), dann für seine Kinder nicht weiter rekursieren.
                # Die Kinder von /run werden also gelistet, aber deren Kinder nicht.
                # Die parent_was_shallow_scan_target flag wird hier nicht mehr benötigt, da wir es pro Ebene entscheiden.
                
                perform_deep_recursion_for_child = True
                if current_path_str in SHALLOW_SCAN_PATHS and current_path != initial_scan_root:
                    # We are inside /run (and /run was not the initial scan target)
                    # Do not recurse into children of /run's children.
                    # So, if current_depth is already 1 (meaning 'entry' is a child of /run),
                    # the next depth would be 2. We stop if max_depth for /run's children should be 1.
                    # This means for /run's children, current_depth + 1 (which is 2) must not exceed an effective max_depth of 1.
                    # Effectively, we don't recurse for children of /run's children if /run was a child itself.
                    if current_depth >= 1 : # current_depth is 1 for children of /run, so next level is 2.
                        perform_deep_recursion_for_child = False
                        logger.debug(f"Shallow scan: Not recursing into children of {entry} because parent {current_path_str} is a shallow_scan_path encountered as a child.")


                if perform_deep_recursion_for_child and (current_depth < max_depth):
                    children = self._scan_host_dirs_recursive(entry, current_depth + 1, max_depth, visited_ids, initial_scan_root)
                    if children: dir_info["children"] = children
                
                items.append(dir_info)
            
            items.sort(key=lambda x: x['name'].lower())

        except PermissionError: pass 
        except FileNotFoundError: logger.warning(f"Directory not found during iterdir(): {current_path}") 
        except Exception as e: logger.error(f"Unexpected error scanning directory contents of {current_path}: {e}", exc_info=True)
        
        return items

    def list_host_directories(self, path_to_scan_str: Optional[str] = None, max_depth: int = 1) -> Dict[str, Any]:
        logger.info(f"Scanning host dirs. Target: '{path_to_scan_str or 'System Default'}', Depth: {max_depth}")
        if max_depth <=0: max_depth = 1 

        root_scan_paths_to_process: List[pathlib.Path] = []
        scan_description = ""
        
        if path_to_scan_str: 
            scan_description = f"Pfad '{path_to_scan_str}'"
            try:
                start_path = pathlib.Path(path_to_scan_str)
                resolved_start_path = start_path.resolve(strict=True) 
                if not resolved_start_path.is_dir():
                     return {"success": False, "error": f"Pfad '{path_to_scan_str}' ist kein Verzeichnis.", "data": []}
                root_scan_paths_to_process.append(resolved_start_path)
            except FileNotFoundError:
                return {"success": False, "error": f"Pfad '{path_to_scan_str}' nicht gefunden.", "data": []}
            except Exception as e:
                return {"success": False, "error": f"Fehler beim Auflösen: '{path_to_scan_str}'. {e}", "data": []}
        else: 
            if os.name == 'nt':
                scan_description = "Windows-Laufwerke"
                # ... (Windows drive logic remains)
            else: 
                scan_description = "Wurzelverzeichnis '/'"
                root_path = pathlib.Path('/')
                if root_path.is_dir(): root_scan_paths_to_process.append(root_path)
                else: logger.error("Wurzelverzeichnis '/' nicht zugreifbar.")
        
        if not root_scan_paths_to_process:
            return {"success": True, "message": f"Keine Startpfade für {scan_description} gefunden.", "data": []} 

        all_results: List[Dict[str, Any]] = []
        for root_path_item in root_scan_paths_to_process:
            visited_ids_for_this_scan = set() 
            
            node_name = root_path_item.name if root_path_item.name else str(root_path_item)
            if str(root_path_item) == "/" : node_name = "/" 
            
            initial_scan_root_abs = root_path_item.resolve(strict=False)

            root_node_data = {
                "name": node_name,
                "path": str(root_path_item), 
                "type": "directory",
                "children": None
            }
            
            # current_depth for root_path_item's children is 1.
            # The root_path_item itself is at an effective depth of 0 relative to the scan.
            children_items = self._scan_host_dirs_recursive(
                root_path_item, 
                1, # Start scanning children at depth 1
                max_depth, 
                visited_ids_for_this_scan,
                initial_scan_root_abs # Pass the actual root of this scan operation
            )
            if children_items:
                root_node_data["children"] = children_items
            all_results.append(root_node_data)

        logger.info(f"Scan für '{scan_description}' abgeschlossen. {len(all_results)} Wurzelelement(e) gefunden.")
        return {"success": True, "message": f"Scan für {scan_description} erfolgreich.", "data": all_results}
