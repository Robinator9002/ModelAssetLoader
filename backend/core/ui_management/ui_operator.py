# backend/core/ui_management/ui_adopter.py
import logging
import pathlib
import sys
from typing import Dict, Any, List, TypedDict

from ..constants.constants import UI_REPOSITORIES, UiNameType
from .ui_installer import get_dependency_report

logger = logging.getLogger(__name__)


class AdoptionIssue(TypedDict):
    """Defines the structure for a single issue found during analysis."""

    code: str
    message: str
    is_fixable: bool
    fix_description: str
    default_fix_enabled: bool


class AdoptionAnalysisResult(TypedDict):
    """Defines the structure for the final result of an adoption analysis."""

    is_adoptable: bool
    is_healthy: bool
    issues: List[AdoptionIssue]


class UiAdopter:
    """
    Handles the analysis and adoption process for existing UI installations.
    This class acts as the "diagnostician" for a potential adoption candidate,
    checking its health and determining if it can be managed by the application.
    """

    def __init__(self, ui_name: UiNameType, path: pathlib.Path):
        """
        Initializes the adopter with the target UI and path.

        Args:
            ui_name: The type of UI being adopted (e.g., 'ComfyUI', 'A1111').
            path: The path to the user-provided installation directory.
        """
        self.ui_name = ui_name
        self.path = path
        self.ui_info = UI_REPOSITORIES.get(ui_name)
        self.issues: List[AdoptionIssue] = []

    async def analyze(self) -> AdoptionAnalysisResult:
        """
        Performs a comprehensive analysis of the target directory.
        It checks for critical files, the virtual environment, and dependency integrity
        to determine the health and adoptability of the installation.

        Returns:
            A dictionary containing the analysis results.
        """
        logger.info(f"Starting adoption analysis for '{self.ui_name}' at '{self.path}'...")

        if not self.ui_info:
            self._add_issue(
                code="INVALID_UI_TYPE",
                message=f"'{self.ui_name}' is not a recognized UI type.",
                is_fixable=False,
            )
            return self._get_final_result()

        # Perform all checks in a logical order.
        self._check_path_validity()
        self._check_start_script()
        self._check_requirements_file()
        await self._check_venv_and_dependencies()

        logger.info(f"Analysis complete. Found {len(self.issues)} issue(s).")
        return self._get_final_result()

    def _add_issue(
        self,
        code: str,
        message: str,
        is_fixable: bool,
        fix_description: str = "",
        default_fix_enabled: bool = True,
    ):
        """A helper method to standardize the creation of adoption issues."""
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
        """Compiles the final analysis result from the list of found issues."""
        is_healthy = not self.issues
        # An installation is adoptable if it has no issues that are marked as unfixable.
        is_adoptable = not any(not issue["is_fixable"] for issue in self.issues)

        return {
            "is_adoptable": is_adoptable,
            "is_healthy": is_healthy,
            "issues": self.issues,
        }

    def _check_path_validity(self):
        """Checks if the provided path exists and is a directory."""
        if not self.path.exists():
            self._add_issue(
                code="PATH_NOT_FOUND",
                message=f"The specified directory does not exist: {self.path}",
                is_fixable=False,
            )
        elif not self.path.is_dir():
            self._add_issue(
                code="PATH_IS_NOT_DIRECTORY",
                message=f"The specified path is a file, not a directory: {self.path}",
                is_fixable=False,
            )

    def _check_start_script(self):
        """Checks for the presence of the UI's main start script (e.g., webui.sh or main.py)."""
        start_script = self.ui_info.get("start_script")
        if not start_script or not (self.path / start_script).is_file():
            self._add_issue(
                code="MISSING_START_SCRIPT",
                message=f"The main start script ('{start_script}') could not be found. This is a strong indicator that this is not a valid {self.ui_name} installation.",
                is_fixable=False,
            )

    def _check_requirements_file(self):
        """Checks for the presence of the requirements.txt file, which is vital for venv validation."""
        req_file = self.ui_info.get("requirements_file")
        if not req_file or not (self.path / req_file).is_file():
            self._add_issue(
                code="MISSING_REQUIREMENTS_FILE",
                message=f"The dependency file ('{req_file}') is missing. A virtual environment cannot be reliably created or validated without it.",
                is_fixable=False,
            )

    async def _check_venv_and_dependencies(self):
        """
        Checks for the venv's existence, its basic integrity, and whether all
        required dependencies from requirements.txt are installed.
        """
        venv_path = self.path / "venv"
        if not venv_path.is_dir():
            self._add_issue(
                code="VENV_MISSING",
                message="No 'venv' directory was found. A new virtual environment is required.",
                is_fixable=True,
                fix_description="Create a new virtual environment and install all dependencies.",
                default_fix_enabled=True,
            )
            # If the venv is missing, we can't check for dependencies, so we stop here.
            return

        python_exe_path = (
            venv_path / "Scripts" / "python.exe"
            if sys.platform == "win32"
            else venv_path / "bin" / "python"
        )

        if not python_exe_path.is_file():
            self._add_issue(
                code="VENV_INCOMPLETE",
                message="A 'venv' directory exists, but the Python executable is missing. The environment appears to be corrupt.",
                is_fixable=True,
                fix_description="Re-create the virtual environment to fix the corruption.",
                default_fix_enabled=True,
            )
            # If the python executable is missing, we can't run pip, so we stop here.
            return

        # If the requirements file is missing, we can't check dependencies.
        # This is already caught by _check_requirements_file, but we check again to be safe.
        req_file = self.ui_info.get("requirements_file")
        req_path = self.path / req_file
        if not req_path.is_file():
            return

        logger.info(f"Checking dependency integrity for '{self.ui_name}'...")
        extra_packages = self.ui_info.get("extra_packages")
        report = await get_dependency_report(
            venv_python=python_exe_path,
            req_path=req_path,
            extra_packages=extra_packages,
            progress_callback=None,  # No progress needed for silent analysis
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
