# backend/core/file_management/host_scanner.py
import logging
import os
import pathlib
import platform
import string
import asyncio
from typing import Dict, List, Optional, Any, Set

from ..constants.constants import EXCLUDED_SCAN_PREFIXES_LINUX, SHALLOW_SCAN_PATHS_LINUX

logger = logging.getLogger(__name__)


class HostScanner:
    """
    Handles scanning directories on the host filesystem.
    --- REFACTOR: All I/O operations are now non-blocking. ---
    """

    # --- REFACTOR: Changed to an async method. ---
    async def list_host_directories(
        self, path_to_scan_str: Optional[str] = None, max_depth: int = 1
    ) -> Dict[str, Any]:
        """
        Asynchronously lists directories on the host system, starting from a given
        path or system defaults. This is the public-facing entry point.
        """
        logger.info(
            f"Scanning host directories. Target: '{path_to_scan_str or 'System Default'}', Depth: {max_depth}"
        )
        if max_depth <= 0:
            max_depth = 1

        # --- REFACTOR: Await the now-async method. ---
        root_scan_paths_result = await self._determine_root_scan_paths(path_to_scan_str)
        if "error" in root_scan_paths_result:
            return {"success": False, "data": [], **root_scan_paths_result}

        all_scan_results = []
        for root_path in root_scan_paths_result["paths"]:
            visited_ids = set()
            node_name = root_path.name if root_path.name else str(root_path)

            # --- REFACTOR: Await the now-async recursive scan. ---
            children = await self._scan_recursive(root_path, 1, max_depth, visited_ids, root_path)

            root_node = {
                "name": node_name,
                "path": str(root_path),
                "type": "directory",
                "children": children,
            }
            all_scan_results.append(root_node)

        message = f"Scan completed. {len(all_scan_results)} root item(s) processed."
        return {"success": True, "message": message, "data": all_scan_results}

    # --- REFACTOR: Changed to an async method to handle blocking I/O. ---
    async def _determine_root_scan_paths(self, path_str: Optional[str]) -> Dict[str, Any]:
        """Asynchronously determines the initial path(s) to start scanning from."""
        if path_str:
            try:
                # --- FIX: Run blocking resolve() in a separate thread. ---
                path = await asyncio.to_thread(pathlib.Path(path_str).resolve, strict=True)
                # --- FIX: Run blocking is_dir() in a separate thread. ---
                if not await asyncio.to_thread(path.is_dir):
                    return {"error": f"Path '{path_str}' is not a directory."}
                return {"paths": [path]}
            except FileNotFoundError:
                return {"error": f"Path '{path_str}' not found."}
            except Exception as e:
                return {"error": f"Error resolving path '{path_str}': {e}"}
        else:  # No path given, use system defaults
            if platform.system() == "Windows":
                # --- FIX: Run blocking os.path.exists in a separate thread. ---
                drive_letters = string.ascii_uppercase
                tasks = [asyncio.to_thread(os.path.exists, f"{d}:") for d in drive_letters]
                drive_exists_results = await asyncio.gather(*tasks)
                drives = [
                    pathlib.Path(f"{drive_letters[i]}:\\")
                    for i, exists in enumerate(drive_exists_results)
                    if exists
                ]
                return {"paths": drives}
            else:  # Linux, macOS
                return {"paths": [pathlib.Path("/")]}

    # --- NEW: Synchronous helper for the recursive scan logic. ---
    def _perform_scan_at_path(
        self,
        current_path: pathlib.Path,
        depth: int,
        max_depth: int,
        visited_ids: Set[tuple],
        scan_root: pathlib.Path,
    ) -> List[Dict[str, Any]]:
        """
        This method contains the original, blocking I/O logic. It's designed
        to be run in a separate thread via `asyncio.to_thread`.
        """
        if depth > max_depth:
            return []

        try:
            target_for_stat = (
                current_path.resolve(strict=True) if current_path.is_symlink() else current_path
            )
            path_id = (target_for_stat.stat().st_dev, target_for_stat.stat().st_ino)
            if path_id in visited_ids:
                logger.warning(f"Symlink loop detected at {current_path}. Skipping.")
                return []
            visited_ids.add(path_id)
        except (OSError, FileNotFoundError) as e:
            logger.warning(f"Cannot access path {current_path}: {e}. Skipping.")
            return []

        items = []
        try:
            # This iterdir() call is the main blocking operation.
            for entry in current_path.iterdir():
                if entry.name.startswith(".") or not entry.is_dir():
                    continue

                dir_info = {
                    "name": entry.name,
                    "path": str(entry.absolute()),
                    "type": "directory",
                    "children": None,
                }

                if depth < max_depth:
                    # Recursively call the synchronous method
                    children_result = self._perform_scan_at_path(
                        entry, depth + 1, max_depth, visited_ids, scan_root
                    )
                    if children_result:
                        dir_info["children"] = children_result

                items.append(dir_info)
        except (PermissionError, FileNotFoundError) as e:
            logger.warning(f"Could not read directory {current_path}: {e}")

        return sorted(items, key=lambda x: x["name"].lower())

    # --- REFACTOR: Changed to an async method. ---
    async def _scan_recursive(
        self,
        current_path: pathlib.Path,
        depth: int,
        max_depth: int,
        visited_ids: Set[tuple],
        scan_root: pathlib.Path,
    ) -> List[Dict[str, Any]]:
        """
        Asynchronously scans directories by offloading the blocking I/O
        to a separate thread.
        """
        # --- FIX: The entire blocking scan logic is now run in a thread pool. ---
        # This prevents the main asyncio event loop from being blocked, ensuring
        # the server remains responsive even during intensive filesystem scans.
        return await asyncio.to_thread(
            self._perform_scan_at_path,
            current_path,
            depth,
            max_depth,
            visited_ids,
            scan_root,
        )
