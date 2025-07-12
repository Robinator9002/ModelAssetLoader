# backend/core/ui_management/ui_adopter.py
import logging
import pathlib
import sys
from typing import Dict, Any, List, TypedDict

from ..constants.constants import UI_REPOSITORIES, UiNameType

logger = logging.getLogger(__name__)


# We'll use TypedDicts for now to define the structure of our analysis.
# Later, these will be replaced by more robust Pydantic models for the API.
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

    def analyze(self) -> AdoptionAnalysisResult:
        """
        Performs a comprehensive analysis of the target directory.
        It checks for critical files, the virtual environment, and other markers
        to determine the health and adoptability of the installation.

        Returns:
            A dictionary containing the analysis results.
        """
        logger.info(f"Starting adoption analysis for '{self.ui_name}' at '{self.path}'...")

        if not self.ui_info:
            # This should ideally be caught before calling, but as a safeguard:
            self._add_issue(
                code="INVALID_UI_TYPE",
                message=f"'{self.ui_name}' is not a recognized UI type.",
                is_fixable=False,
            )
            return self._get_final_result()

        # --- Run all diagnostic checks ---
        self._check_path_validity()
        self._check_start_script()
        self._check_requirements_file()
        self._check_venv_integrity()
        # Add more checks here in the future (e.g., git repo status)

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
        # An installation is considered "unadoptable" only if a critical,
        # unfixable issue is present (like the path not existing).
        is_adoptable = not any(not issue["is_fixable"] for issue in self.issues)

        return {
            "is_adoptable": is_adoptable,
            "is_healthy": is_healthy,
            "issues": self.issues,
        }

    # --- Individual Diagnostic Checks ---

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
        """Checks for the presence of the UI's main start script."""
        start_script = self.ui_info.get("start_script")
        if not start_script or not (self.path / start_script).is_file():
            self._add_issue(
                code="MISSING_START_SCRIPT",
                message=f"The main start script ('{start_script}') could not be found. This is a strong indicator that this is not a valid {self.ui_name} installation.",
                is_fixable=False,  # For now, we consider this unfixable. Could be changed to git pull later.
                fix_description="Re-clone the repository to restore missing files.",
            )

    def _check_requirements_file(self):
        """Checks for the presence of the requirements.txt file."""
        req_file = self.ui_info.get("requirements_file")
        if not req_file or not (self.path / req_file).is_file():
            self._add_issue(
                code="MISSING_REQUIREMENTS_FILE",
                message=f"The dependency file ('{req_file}') is missing. A virtual environment cannot be reliably created or validated without it.",
                is_fixable=False,  # Also considered unfixable for now.
                fix_description="Re-clone the repository to restore missing files.",
            )

    def _check_venv_integrity(self):
        """Checks for the existence and basic integrity of the venv."""
        venv_path = self.path / "venv"
        if not venv_path.is_dir():
            self._add_issue(
                code="VENV_MISSING",
                message="No 'venv' directory was found. A new virtual environment is required to run the UI.",
                is_fixable=True,
                fix_description="Create a new virtual environment and install all dependencies.",
                default_fix_enabled=True,
            )
            return  # Stop here if venv is missing, no point checking for python.exe

        # Determine the expected path to the python executable based on OS
        python_exe_path = (
            venv_path / "Scripts" / "python.exe"
            if sys.platform == "win32"
            else venv_path / "bin" / "python"
        )

        if not python_exe_path.is_file():
            self._add_issue(
                code="VENV_INCOMPLETE",
                message="A 'venv' directory exists, but the Python executable is missing. The environment seems to be corrupt or incomplete.",
                is_fixable=True,
                fix_description="Re-create the virtual environment to fix it.",
                default_fix_enabled=True,
            )
