# backend/core/ui_management/ui_adopter.py
import logging
import pathlib
import sys
from typing import Dict, Any, List, TypedDict, Optional

from ..constants.constants import UI_REPOSITORIES, UiNameType
from .ui_installer import get_dependency_report

# --- NEW: Import custom error classes for standardized handling (global import) ---
from core.errors import MalError, OperationFailedError, BadRequestError, EntityNotFoundError

logger = logging.getLogger(__name__)


class AdoptionIssue(TypedDict):
    code: str
    message: str
    is_fixable: bool
    fix_description: str
    default_fix_enabled: bool


class AdoptionAnalysisResult(TypedDict):
    is_adoptable: bool
    is_healthy: bool
    issues: List[AdoptionIssue]


class UiAdopter:
    """
    Handles the analysis and adoption process for existing UI installations.
    This class acts as the "diagnostician" for a potential adoption candidate.
    """

    def __init__(self, ui_name: UiNameType, path: pathlib.Path):
        """
        Initializes the adopter with the target UI and path.

        Args:
            ui_name: The type of UI being adopted (e.g., 'ComfyUI').
            path: The path to the user-provided installation directory.
        """
        self.ui_name = ui_name
        self.path = path
        self.ui_info = UI_REPOSITORIES.get(ui_name)
        self.issues: List[AdoptionIssue] = []

    async def analyze(self) -> AdoptionAnalysisResult:
        """
        Performs a comprehensive analysis of the target directory.
        It checks for critical files, the virtual environment, and other markers
        to determine the health and adoptability of the installation.

        @refactor: This method now raises BadRequestError if the UI type is invalid,
                   or OperationFailedError if a critical analysis step fails.
        """
        logger.info(f"Starting adoption analysis for '{self.ui_name}' at '{self.path}'...")

        if not self.ui_info:
            # --- REFACTOR: Raise BadRequestError if UI type is not recognized ---
            raise BadRequestError(f"'{self.ui_name}' is not a recognized UI type for adoption.")

        try:
            self._check_path_validity()
            self._check_start_script()
            self._check_requirements_file()
            await self._check_venv_and_dependencies()

            logger.info(f"Analysis complete. Found {len(self.issues)} issue(s).")
            return self._get_final_result()
        except MalError:
            # Re-raise any MalError that might be raised by helper methods directly.
            raise
        except Exception as e:
            # Catch any other unexpected errors during analysis and wrap them.
            logger.critical(
                f"An unhandled exception occurred during adoption analysis: {e}", exc_info=True
            )
            raise OperationFailedError(
                operation_name=f"Analyze adoption candidate '{self.ui_name}'", original_exception=e
            )

    def _add_issue(
        self,
        code: str,
        message: str,
        is_fixable: bool,
        fix_description: str = "",
        default_fix_enabled: bool = True,
    ):
        """A helper to standardize adding issues to the list."""
        self.issues.append(
            {
                "code": code,
                "message": message,
                "is_fixable": is_fixable,
                "fix_description": fix_description,
                "default_fix_enabled": default_fix_enabled,
            }
        )

    def _get_final_result(self) -> AdoptionAnalysisResult:
        """Compiles the final analysis result from the list of issues."""
        is_healthy = not self.issues
        is_adoptable = not any(not issue["is_fixable"] for issue in self.issues)

        return {
            "is_adoptable": is_adoptable,
            "is_healthy": is_healthy,
            "issues": self.issues,
        }

    def _check_path_validity(self):
        """
        Checks if the provided path exists and is a directory.
        @refactor: This method now raises BadRequestError for invalid paths.
        """
        if not self.path.exists():
            # --- REFACTOR: Raise BadRequestError ---
            raise BadRequestError(f"The specified directory does not exist: {self.path}")
        elif not self.path.is_dir():
            # --- REFACTOR: Raise BadRequestError ---
            raise BadRequestError(f"The specified path is a file, not a directory: {self.path}")

    def _check_start_script(self):
        """
        Checks for the presence of the UI's main start script.
        @refactor: This method now raises EntityNotFoundError if the script is missing.
        """
        start_script = self.ui_info.get("start_script")
        if not start_script or not (self.path / start_script).is_file():
            # --- REFACTOR: Raise EntityNotFoundError ---
            raise EntityNotFoundError(
                entity_name="Start Script",
                entity_id=f"'{start_script}' for UI '{self.ui_name}' at '{self.path}'",
                message=f"The main start script ('{start_script}') could not be found. This is a strong indicator that this is not a valid {self.ui_name} installation.",
            )

    def _check_requirements_file(self):
        """
        Checks for the presence of the requirements.txt file.
        @refactor: This method now raises EntityNotFoundError if the file is missing.
        """
        req_file = self.ui_info.get("requirements_file")
        if not req_file or not (self.path / req_file).is_file():
            # --- REFACTOR: Raise EntityNotFoundError ---
            raise EntityNotFoundError(
                entity_name="Requirements File",
                entity_id=f"'{req_file}' for UI '{self.ui_name}' at '{self.path}'",
                message=f"The dependency file ('{req_file}') is missing. A virtual environment cannot be reliably created or validated without it.",
            )

    async def _check_venv_and_dependencies(self):
        """
        Checks for the venv's existence, its basic integrity, and whether all
        required dependencies from requirements.txt are installed.
        @refactor: This method now raises OperationFailedError for critical venv issues.
        """
        venv_path = self.path / "venv"
        if not venv_path.is_dir():
            self._add_issue(
                code="VENV_MISSING",
                message="No 'venv' directory was found. A new virtual environment is required to run the UI.",
                is_fixable=True,
                fix_description="Create a new virtual environment and install all dependencies.",
                default_fix_enabled=True,
            )
            return

        python_exe_path = (
            venv_path / "Scripts" / "python.exe"
            if sys.platform == "win32"
            else venv_path / "bin" / "python"
        )

        if not python_exe_path.is_file():
            # --- REFACTOR: Raise OperationFailedError for incomplete venv ---
            raise OperationFailedError(
                operation_name="Venv Integrity Check",
                original_exception=FileNotFoundError(
                    f"Python executable missing in venv: {python_exe_path}"
                ),
                message="A 'venv' directory exists, but the Python executable is missing. The environment seems to be corrupt or incomplete.",
            )

        req_file = self.ui_info.get("requirements_file")
        req_path = self.path / req_file
        if not req_path.is_file():
            # This case should ideally be caught by _check_requirements_file,
            # but as a safeguard, if it's still missing here, we return.
            return

        logger.info(f"Checking dependency integrity for '{self.ui_name}'...")
        extra_packages = self.ui_info.get("extra_packages")
        try:
            report = await get_dependency_report(
                venv_python=python_exe_path,
                req_path=req_path,
                extra_packages=extra_packages,
                progress_callback=None,
            )
        except MalError:
            # Re-raise MalErrors from get_dependency_report directly.
            raise
        except Exception as e:
            # Wrap any other unexpected errors from get_dependency_report.
            raise OperationFailedError(
                operation_name="Get Dependency Report",
                original_exception=e,
                message=f"Failed to get dependency report for '{self.ui_name}'.",
            )

        packages_to_install = report.get("install", [])
        if packages_to_install:
            package_count = len(packages_to_install)
            self._add_issue(
                code="VENV_DEPS_INCOMPLETE",
                message=f"The virtual environment is missing {package_count} required package(s).",
                is_fixable=True,
                fix_description="Run the dependency installer to download and set up the required packages.",
                default_fix_enabled=True,
            )
