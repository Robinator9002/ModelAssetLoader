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
    @refactor All I/O operations have been made non-blocking by offloading them
    to a separate thread pool using asyncio.to_thread(). This prevents the main
    server event loop from being frozen during potentially slow disk scans.
    """

    async def list_host_directories(
        self, path_to_scan_str: Optional[str] = None, max_depth: int = 1
    ) -> Dict[str, Any]:
        """
        Asynchronously lists directories on the host system, starting from a given
        path or system defaults.
        """
        logger.info(
            f"Scanning host directories. Target: '{path_to_scan_str or 'System Default'}', Depth: {max_depth}"
        )
        if max_depth <= 0:
            max_depth = 1

        root_scan_paths_result = await self._determine_root_scan_paths(path_to_scan_str)
        if "error" in root_scan_paths_result:
            return {"success": False, "data": [], **root_scan_paths_result}

        all_scan_results = []
        for root_path in root_scan_paths_result["paths"]:
            visited_ids = set()
            node_name = root_path.name if root_path.name else str(root_path)

            # The recursive scan is now fully non-blocking.
            children = await self._scan_recursive(root_path, 1, max_depth, visited_ids)

            root_node = {
                "name": node_name,
                "path": str(root_path),
                "type": "directory",
                "children": children,
            }
            all_scan_results.append(root_node)

        message = f"Scan completed. {len(all_scan_results)} root item(s) processed."
        return {"success": True, "message": message, "data": all_scan_results}

    def _get_default_scan_paths_sync(self) -> List[pathlib.Path]:
        """
        Synchronous helper to determine default scan paths. This contains
        blocking I/O and is intended to be run in a thread.
        """
        if platform.system() == "Windows":
            drive_letters = string.ascii_uppercase
            return [pathlib.Path(f"{d}:\\") for d in drive_letters if os.path.exists(f"{d}:")]
        else:  # Linux, macOS
            return [pathlib.Path("/")]

    async def _determine_root_scan_paths(self, path_str: Optional[str]) -> Dict[str, Any]:
        """Asynchronously determines the initial path(s) to start scanning from."""
        if path_str:
            try:
                path = pathlib.Path(path_str)
                # @fix {PERFORMANCE} Run blocking resolve() and is_dir() in a thread.
                is_dir = await asyncio.to_thread(path.is_dir)
                if not is_dir:
                    return {"error": f"Path '{path_str}' is not a directory."}
                return {"paths": [path]}
            except Exception as e:
                # Path validation errors (e.g., invalid characters) can happen here.
                return {"error": f"Error resolving path '{path_str}': {e}"}
        else:
            # @fix {PERFORMANCE} Run the blocking default path discovery in a thread.
            default_paths = await asyncio.to_thread(self._get_default_scan_paths_sync)
            return {"paths": default_paths}

    def _scan_path_sync(
        self,
        current_path: pathlib.Path,
        depth: int,
        max_depth: int,
        visited_ids: Set[tuple],
    ) -> List[Dict[str, Any]]:
        """
        This is the synchronous, blocking version of the recursive scan logic.
        It's designed to be safely executed in a separate thread.
        """
        if depth > max_depth:
            return []

        try:
            # These are all blocking calls: is_symlink, resolve, stat.
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
                # is_dir() is also a blocking call.
                if entry.name.startswith(".") or not entry.is_dir():
                    continue

                dir_info = {
                    "name": entry.name,
                    "path": str(entry.absolute()),
                    "type": "directory",
                    "children": None,
                }

                if depth < max_depth:
                    # Recursively call the same synchronous method for children.
                    children_result = self._scan_path_sync(entry, depth + 1, max_depth, visited_ids)
                    if children_result:
                        dir_info["children"] = children_result

                items.append(dir_info)
        except (PermissionError, FileNotFoundError) as e:
            logger.warning(f"Could not read directory {current_path}: {e}")

        return sorted(items, key=lambda x: x["name"].lower())

    async def _scan_recursive(
        self,
        current_path: pathlib.Path,
        depth: int,
        max_depth: int,
        visited_ids: Set[tuple],
    ) -> List[Dict[str, Any]]:
        """
        Asynchronously scans directories by offloading the blocking I/O
        of the synchronous helper to a separate thread.
        """
        # @fix {PERFORMANCE} The entire blocking scan logic is now run in a thread pool.
        # This prevents the main asyncio event loop from being blocked, ensuring
        # the server remains responsive even during intensive filesystem scans.
        return await asyncio.to_thread(
            self._scan_path_sync,
            current_path,
            depth,
            max_depth,
            visited_ids,
        )
