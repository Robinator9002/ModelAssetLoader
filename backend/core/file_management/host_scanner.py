# backend/core/file_management/host_scanner.py
import logging
import os
import pathlib
import platform
import string
from typing import Dict, List, Optional, Any, Set

from .constants import EXCLUDED_SCAN_PREFIXES_LINUX, SHALLOW_SCAN_PATHS_LINUX

logger = logging.getLogger(__name__)

class HostScanner:
    """Handles scanning directories on the host filesystem."""

    def list_host_directories(self, path_to_scan_str: Optional[str] = None, max_depth: int = 1) -> Dict[str, Any]:
        """
        Lists directories on the host system, starting from a given path or system defaults.
        This is the public-facing entry point for scanning operations.
        """
        logger.info(f"Scanning host directories. Target: '{path_to_scan_str or 'System Default'}', Depth: {max_depth}")
        if max_depth <= 0: max_depth = 1

        root_scan_paths = self._determine_root_scan_paths(path_to_scan_str)
        if "error" in root_scan_paths:
            return {"success": False, "data": [], **root_scan_paths}

        all_scan_results = []
        for root_path in root_scan_paths["paths"]:
            visited_ids = set() # Reset visited IDs for each distinct root scan (e.g., each drive)
            node_name = root_path.name if root_path.name else str(root_path)

            root_node = {
                "name": node_name,
                "path": str(root_path),
                "type": "directory",
                "children": self._scan_recursive(root_path, 1, max_depth, visited_ids, root_path)
            }
            all_scan_results.append(root_node)

        message = f"Scan completed. {len(all_scan_results)} root item(s) processed."
        return {"success": True, "message": message, "data": all_scan_results}

    def _determine_root_scan_paths(self, path_str: Optional[str]) -> Dict[str, Any]:
        """Determines the initial path(s) to start scanning from."""
        if path_str:
            try:
                path = pathlib.Path(path_str).resolve(strict=True)
                if not path.is_dir():
                    return {"error": f"Path '{path_str}' is not a directory."}
                return {"paths": [path]}
            except FileNotFoundError:
                return {"error": f"Path '{path_str}' not found."}
            except Exception as e:
                return {"error": f"Error resolving path '{path_str}': {e}"}
        else: # No path given, use system defaults
            if platform.system() == 'Windows':
                drives = [pathlib.Path(f"{d}:\\") for d in string.ascii_uppercase if os.path.exists(f"{d}:")]
                return {"paths": drives}
            else: # Linux, macOS
                return {"paths": [pathlib.Path('/')]}

    def _scan_recursive(
        self, current_path: pathlib.Path, depth: int, max_depth: int, visited_ids: Set[tuple], scan_root: pathlib.Path
    ) -> List[Dict[str, Any]]:
        """Recursively scans directories, handling symlinks and permissions."""
        if depth > max_depth:
            return []

        # Prevent recursion into special system directories on Linux/macOS
        if platform.system() != "Windows" and any(str(current_path).startswith(p) for p in EXCLUDED_SCAN_PREFIXES_LINUX):
            return []

        # Use stat on the canonical path to detect symlink loops
        try:
            # We must stat the target of a symlink to get its real device/inode ID
            target_for_stat = current_path.resolve(strict=True) if current_path.is_symlink() else current_path
            path_id = (target_for_stat.stat().st_dev, target_for_stat.stat().st_ino)
            if path_id in visited_ids:
                logger.warning(f"Symlink loop or duplicate path detected: {current_path}. Skipping.")
                return []
            visited_ids.add(path_id)
        except (OSError, FileNotFoundError) as e:
            logger.warning(f"Cannot access path {current_path}: {e}. Skipping.")
            return []

        items = []
        try:
            for entry in current_path.iterdir():
                # Skip hidden entries and non-directories
                if entry.name.startswith('.') or not entry.is_dir():
                    continue

                # Check if this area should be scanned shallowly (e.g., /mnt, /media)
                is_shallow_area = False
                if platform.system() != "Windows":
                     try:
                         resolved_entry = entry.resolve(strict=False)
                         if str(resolved_entry) in SHALLOW_SCAN_PATHS_LINUX and resolved_entry != scan_root:
                            is_shallow_area = True
                     except Exception:
                        pass # Ignore resolution errors for this check

                children = None
                if not is_shallow_area:
                     children = self._scan_recursive(entry, depth + 1, max_depth, visited_ids, scan_root)

                items.append({
                    "name": entry.name,
                    "path": str(entry.absolute()),
                    "type": "directory",
                    "children": children or [] # Ensure children is always a list
                })
        except (PermissionError, FileNotFoundError) as e:
            logger.warning(f"Could not read directory {current_path}: {e}")

        return sorted(items, key=lambda x: x['name'].lower())
