# backend/routers/ui_router.py
import logging
import pathlib
import uuid
from typing import List

from fastapi import APIRouter, HTTPException, Body, status, Depends

# --- API Model Imports ---
from api.models import (
    AvailableUiItem,
    AllUiStatusResponse,
    UiActionResponse,
    UiInstallRequest,
    UiNameTypePydantic,
    AdoptionAnalysisResponse,
    UiAdoptionAnalysisRequest,
    UiAdoptionRepairRequest,
    UiAdoptionFinalizeRequest,
)

from dependencies import get_ui_manager
from core.services.ui_manager import UiManager
from core.constants.constants import UI_REPOSITORIES
from core.errors import MalError
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class UiTaskRequest(BaseModel):
    """Request model for actions targeting a UI task by its ID."""

    task_id: str


router = APIRouter(
    prefix="/api/uis",
    tags=["UIs"],
)


# --- Endpoint Definitions ---


@router.get(
    "",
    response_model=List[AvailableUiItem],
    summary="List Available UIs for Installation",
)
async def list_available_uis_endpoint():
    """Returns a list of all UIs that are defined in the backend constants."""
    return [
        AvailableUiItem(
            ui_name=name,
            git_url=details["git_url"],
            default_profile_name=details["default_profile_name"],
        )
        for name, details in UI_REPOSITORIES.items()
    ]


@router.get(
    "/status",
    response_model=AllUiStatusResponse,
    summary="Get Status of All Registered UI Instances",
)
async def get_all_ui_statuses_endpoint(um: UiManager = Depends(get_ui_manager)):
    """Gets the live installation and running status of all managed UI instances."""
    try:
        return AllUiStatusResponse(items=await um.get_all_statuses())
    except MalError as e:
        logger.error(f"[{e.error_code}] Error getting all UI statuses: {e.message}", exc_info=False)
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.critical(
            f"An unhandled exception occurred getting all UI statuses: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected internal error occurred while fetching UI statuses.",
        )


@router.post(
    "/install",
    response_model=UiActionResponse,
    summary="Install a New UI Instance",
)
async def install_ui_endpoint(
    request: UiInstallRequest = Body(...), um: UiManager = Depends(get_ui_manager)
):
    """Triggers the installation of a new UI instance as a background task."""
    task_id = str(uuid.uuid4())
    try:
        # --- REFACTOR: Pass the new display_name to the manager ---
        um.install_ui_environment(
            ui_name=request.ui_name,
            display_name=request.display_name,
            # Path logic remains simple here; manager/installer handles complexity
            install_path=(
                pathlib.Path(request.custom_install_path) if request.custom_install_path else None
            ),
            task_id=task_id,
        )
        return UiActionResponse(
            success=True,
            message=f"Installation for '{request.display_name}' started.",
            task_id=task_id,
            set_as_active_on_completion=request.set_as_active,
        )
    except MalError as e:
        logger.error(f"[{e.error_code}] Error during UI installation: {e.message}", exc_info=False)
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.critical(
            f"An unhandled exception occurred during UI installation: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail="An unexpected internal error occurred during UI installation."
        )


# --- REFACTOR: Route now uses installation_id ---
@router.post(
    "/run/{installation_id}",
    response_model=UiActionResponse,
    summary="Run an Installed UI Instance",
)
async def run_ui_endpoint(installation_id: str, um: UiManager = Depends(get_ui_manager)):
    """Triggers a UI process to start in the background using its unique ID."""
    try:
        task_id = str(uuid.uuid4())
        um.run_ui(installation_id=installation_id, task_id=task_id)
        return UiActionResponse(
            success=True,
            message=f"Request to run UI instance {installation_id} accepted.",
            task_id=task_id,
            set_as_active_on_completion=False,
        )
    except MalError as e:
        logger.error(f"[{e.error_code}] Error running UI: {e.message}", exc_info=False)
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.critical(f"An unhandled exception occurred during UI run: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An unexpected internal error occurred during UI run."
        )


@router.post(
    "/stop",
    status_code=status.HTTP_200_OK,
    summary="Stop a Running UI Process",
)
async def stop_ui_endpoint(request: UiTaskRequest, um: UiManager = Depends(get_ui_manager)):
    """Sends a request to stop a running UI process by its task ID."""
    try:
        await um.stop_ui(task_id=request.task_id)
        return {"success": True, "message": f"Stop request for task {request.task_id} sent."}
    except MalError as e:
        logger.error(f"[{e.error_code}] Error stopping UI: {e.message}", exc_info=False)
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.critical(f"An unhandled exception occurred during UI stop: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An unexpected internal error occurred during UI stop."
        )


@router.post(
    "/cancel",
    status_code=status.HTTP_200_OK,
    summary="Cancel a running UI installation or repair task",
)
async def cancel_ui_task_endpoint(request: UiTaskRequest, um: UiManager = Depends(get_ui_manager)):
    """Sends a cancellation request for an in-progress installation or repair."""
    try:
        await um.cancel_ui_task(request.task_id)
        return {
            "success": True,
            "message": f"Cancellation request for UI task {request.task_id} sent.",
        }
    except MalError as e:
        logger.error(f"[{e.error_code}] Error cancelling UI task: {e.message}", exc_info=False)
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.critical(
            f"An unhandled exception occurred during UI task cancellation: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected internal error occurred during UI task cancellation.",
        )


# --- REFACTOR: Route now uses installation_id ---
@router.delete(
    "/{installation_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a Registered UI Instance",
)
async def delete_ui_endpoint(installation_id: str, um: UiManager = Depends(get_ui_manager)):
    """Deletes a UI instance's files from disk and unregisters it."""
    try:
        await um.delete_environment(installation_id=installation_id)
        return {"success": True, "message": f"UI instance {installation_id} deleted successfully."}
    except MalError as e:
        logger.error(
            f"[{e.error_code}] Error deleting UI instance '{installation_id}': {e.message}",
            exc_info=False,
        )
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.critical(
            f"An unhandled exception occurred deleting UI instance '{installation_id}': {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="An unexpected internal error occurred during UI deletion."
        )


# --- UI Adoption Endpoints ---


@router.post(
    "/adopt/analyze",
    response_model=AdoptionAnalysisResponse,
    tags=["UIs", "Adoption"],
    summary="Analyze a Directory for UI Adoption",
)
async def analyze_adoption_endpoint(
    request: UiAdoptionAnalysisRequest, um: UiManager = Depends(get_ui_manager)
):
    """Analyzes a directory to check if it's a valid, adoptable UI installation."""
    try:
        analysis_result = await um.analyze_adoption_candidate(
            request.ui_name, pathlib.Path(request.path)
        )
        return AdoptionAnalysisResponse(**analysis_result)
    except MalError as e:
        logger.error(
            f"[{e.error_code}] Error during adoption analysis: {e.message}", exc_info=False
        )
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.critical(
            f"An unhandled exception occurred during adoption analysis: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected internal error occurred during adoption analysis.",
        )


@router.post(
    "/adopt/repair",
    response_model=UiActionResponse,
    tags=["UIs", "Adoption"],
    summary="Repair and Adopt a UI Environment",
)
async def repair_and_adopt_endpoint(
    request: UiAdoptionRepairRequest, um: UiManager = Depends(get_ui_manager)
):
    """Triggers a repair-and-adopt process as a background task."""
    try:
        task_id = str(uuid.uuid4())
        # --- REFACTOR: Pass the new display_name to the manager ---
        um.repair_and_adopt_ui(
            ui_name=request.ui_name,
            display_name=request.display_name,
            path=pathlib.Path(request.path),
            issues_to_fix=request.issues_to_fix,
            task_id=task_id,
        )
        return UiActionResponse(
            success=True,
            message=f"Repair process for '{request.display_name}' started.",
            task_id=task_id,
            set_as_active_on_completion=True,
        )
    except MalError as e:
        logger.error(
            f"[{e.error_code}] Error during UI repair and adoption: {e.message}", exc_info=False
        )
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.critical(
            f"An unhandled exception occurred during UI repair and adoption: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected internal error occurred during UI repair and adoption.",
        )


@router.post(
    "/adopt/finalize",
    status_code=status.HTTP_200_OK,
    tags=["UIs", "Adoption"],
    summary="Finalize Adoption of a UI without Repairs",
)
async def finalize_adoption_endpoint(
    request: UiAdoptionFinalizeRequest, um: UiManager = Depends(get_ui_manager)
):
    """Finalizes the adoption of a healthy UI by simply registering it."""
    try:
        # --- REFACTOR: Pass the new display_name to the manager ---
        um.finalize_adoption(request.ui_name, request.display_name, pathlib.Path(request.path))
        return {"success": True, "message": f"'{request.display_name}' adopted successfully."}
    except MalError as e:
        logger.error(
            f"[{e.error_code}] Error finalizing adoption for '{request.display_name}': {e.message}",
            exc_info=False,
        )
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.critical(
            f"An unhandled exception occurred finalizing adoption for '{request.display_name}': {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected internal error occurred during adoption finalization.",
        )
