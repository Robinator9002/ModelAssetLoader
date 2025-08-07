# backend/routers/ui_router.py
import logging
import pathlib
import uuid
from typing import List

# --- REFACTOR: Import Depends for dependency injection ---
from fastapi import APIRouter, HTTPException, Body, status, Depends
from pydantic import BaseModel

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

# --- REFACTOR: Import the provider function and the service class for type hinting ---
from dependencies import get_ui_manager
from core.services.ui_manager import UiManager
from core.constants.constants import UI_REPOSITORIES

# --- NEW: Import custom error classes for standardized handling ---
from core.errors import MalError, OperationFailedError, BadRequestError, EntityNotFoundError

logger = logging.getLogger(__name__)


# --- Pydantic models for request bodies specific to this router ---
class UiTaskRequest(BaseModel):
    """Request model for actions targeting a UI task by its ID."""

    task_id: str


# --- Router Definition ---
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
    # This endpoint is simple and doesn't require the manager or complex error handling.
    # If UI_REPOSITORIES were to be dynamically loaded and fail, a try-except would be needed.
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
    summary="Get Status of All Registered UIs",
)
async def get_all_ui_statuses_endpoint(um: UiManager = Depends(get_ui_manager)):
    """Gets the live installation and running status of all managed UIs."""
    try:
        # Any errors from um.get_all_statuses would be MalErrors from deeper layers.
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
    summary="Install a UI Environment",
)
async def install_ui_endpoint(
    request: UiInstallRequest = Body(...), um: UiManager = Depends(get_ui_manager)
):
    """Triggers the installation of a UI environment as a background task."""
    task_id = str(uuid.uuid4())
    # Path logic remains in the router as it's directly related to the request payload.
    install_path = um.get_default_install_path(request.ui_name)
    if request.custom_install_path:
        install_path = pathlib.Path(request.custom_install_path)

    try:
        # The responsibility for path creation/validation and raising appropriate
        # errors (like BadRequestError for invalid paths or OperationFailedError for
        # permission issues) should ideally be handled within the FileManager or
        # a dedicated utility, and then propagated as MalError.
        # Here, we ensure the parent directory exists, and let the service handle deeper issues.
        install_path.parent.mkdir(parents=True, exist_ok=True)

        # Delegate the actual installation logic to the injected ui_manager.
        # um.install_ui_environment is expected to raise MalError on failure.
        um.install_ui_environment(
            ui_name=request.ui_name,
            install_path=install_path,
            task_id=task_id,
        )

        return UiActionResponse(
            success=True,
            message=f"Installation for {request.ui_name} started.",
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


@router.post(
    "/{ui_name}/run",
    response_model=UiActionResponse,
    summary="Run an Installed UI",
)
async def run_ui_endpoint(ui_name: UiNameTypePydantic, um: UiManager = Depends(get_ui_manager)):
    """Triggers a UI process to start in the background."""
    try:
        task_id = str(uuid.uuid4())
        # um.run_ui is expected to raise MalError on failure.
        um.run_ui(ui_name=ui_name, task_id=task_id)
        return UiActionResponse(
            success=True,
            message=f"Request to run {ui_name} accepted.",
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
    """Sends a request to stop a running UI process."""
    try:
        # um.stop_ui is expected to raise MalError on failure.
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
        # um.cancel_ui_task is expected to raise MalError on failure.
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


@router.delete(
    "/{ui_name}",
    status_code=status.HTTP_200_OK,
    summary="Delete a Registered UI Environment",
)
async def delete_ui_endpoint(ui_name: UiNameTypePydantic, um: UiManager = Depends(get_ui_manager)):
    """Deletes a UI environment's files from disk and unregisters it."""
    try:
        # The um.delete_environment method is expected to raise MalError on failure,
        # so the explicit success check is removed.
        await um.delete_environment(ui_name=ui_name)
        return {"success": True, "message": f"{ui_name} environment deleted successfully."}
    # --- REFACTOR: Catch custom MalError first ---
    except MalError as e:
        logger.error(
            f"[{e.error_code}] Error deleting UI environment '{ui_name}': {e.message}",
            exc_info=False,
        )
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.critical(
            f"An unhandled exception occurred deleting UI environment '{ui_name}': {e}",
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
    # --- REFACTOR: Catch custom MalError first ---
    except MalError as e:
        logger.error(
            f"[{e.error_code}] Error during adoption analysis: {e.message}", exc_info=False
        )
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        # Catch any other truly unexpected errors and log them as critical.
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
        # um.repair_and_adopt_ui is expected to raise MalError on failure.
        um.repair_and_adopt_ui(
            ui_name=request.ui_name,
            path=pathlib.Path(request.path),
            issues_to_fix=request.issues_to_fix,
            task_id=task_id,
        )
        return UiActionResponse(
            success=True,
            message=f"Repair process for {request.ui_name} started.",
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
        # The um.finalize_adoption method is expected to raise MalError on failure,
        # so the explicit success check is removed.
        um.finalize_adoption(request.ui_name, pathlib.Path(request.path))
        return {"success": True, "message": f"{request.ui_name} adopted successfully."}
    # --- REFACTOR: Catch custom MalError first ---
    except MalError as e:
        logger.error(
            f"[{e.error_code}] Error finalizing adoption for '{request.ui_name}': {e.message}",
            exc_info=False,
        )
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.critical(
            f"An unhandled exception occurred finalizing adoption for '{request.ui_name}': {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected internal error occurred during adoption finalization.",
        )
