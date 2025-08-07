# backend/routers/models_router.py
import logging
from typing import List, Optional

# --- REFACTOR: Import Depends for dependency injection ---
from fastapi import APIRouter, HTTPException, Query, Depends

# --- API Model Imports ---
from api.models import (
    ModelDetails,
    PaginatedModelListResponse,
    ModelListItem,
)

# --- REFACTOR: Import the provider function and the service class for type hinting ---
from dependencies import get_source_manager
from core.services.source_manager import SourceManager

# --- NEW: Import custom error classes for standardized handling ---
from core.errors import MalError, EntityNotFoundError, ExternalApiError, OperationFailedError

# --- NEW: Import specific Hugging Face Hub exceptions for precise error handling ---
# These imports are necessary for Recipe 2: External API Failures
from huggingface_hub.utils import (
    RepositoryNotFoundError,
    GatedRepoError,
    HFValidationError,
    HfHubHTTPError,
)


logger = logging.getLogger(__name__)

# Create an APIRouter instance. This is like a mini-FastAPI app.
router = APIRouter(
    prefix="/api",
    tags=["Models"],
)


# --- Endpoint Definitions ---


@router.get(
    "/models",
    response_model=PaginatedModelListResponse,
    summary="Search Models from a Source",
)
async def search_models_endpoint(
    # --- REFACTOR: Inject the SourceManager instance ---
    sm: SourceManager = Depends(get_source_manager),
    # Query parameters remain the same
    source: str = Query("huggingface"),
    search: Optional[str] = Query(None),
    author: Optional[str] = Query(None),
    tags: Optional[List[str]] = Query(None, alias="tags[]"),
    sort: Optional[str] = Query("lastModified"),
    direction: Optional[int] = Query(-1, enum=[-1, 1]),
    limit: int = Query(30, ge=1, le=100),
    page: int = Query(1, ge=1),
):
    """
    Endpoint for searching and paginating models from a given source.
    It now delegates the search logic to the injected `source_manager`.
    """
    try:
        unique_tags = list(set(tags)) if tags else None
        # --- REFACTOR: Use the injected instance 'sm' ---
        models_data, has_more = sm.search_models(
            source=source,
            search_query=search,
            author=author,
            tags=unique_tags,
            sort_by=sort,
            sort_direction=direction,
            limit=limit,
            page=page,
        )
        return PaginatedModelListResponse(
            items=[ModelListItem(**m) for m in models_data],
            page=page,
            limit=limit,
            has_more=has_more,
        )
    # --- REFACTOR: Catch custom MalError first ---
    except MalError as e:
        # If the underlying service raises a MalError, translate it to an HTTPException
        # using the error's status code and message.
        logger.error(f"[{e.error_code}] Error in search_models: {e.message}", exc_info=False)
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        # Catch any other truly unexpected errors and log them as critical.
        logger.critical(f"An unhandled exception occurred during model search: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An unexpected internal error occurred during model search."
        )


@router.get(
    "/models/{source}/{model_id:path}",
    response_model=ModelDetails,
    summary="Get Model Details from a Source",
)
async def get_model_details_endpoint(
    source: str, model_id: str, sm: SourceManager = Depends(get_source_manager)
):
    """
    Endpoint for retrieving detailed information about a specific model.
    It now delegates the detail retrieval logic to the injected `source_manager`.
    """
    try:
        # --- REFACTOR: Use the injected instance 'sm' ---
        details_data = sm.get_model_details(model_id=model_id, source=source)
        if not details_data:
            # This check will likely be removed once get_model_details raises EntityNotFoundError
            # directly instead of returning None for not found cases.
            raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found.")
        return ModelDetails(**details_data)
    # --- REFACTOR: Apply Recipe 2 for Hugging Face specific errors ---
    except RepositoryNotFoundError:
        # This is a specific "not found" case from Hugging Face Hub
        logger.info(f"Model repository '{model_id}' not found via Hugging Face Hub.")
        raise EntityNotFoundError(entity_name="Model", entity_id=model_id)
    except (GatedRepoError, HFValidationError, HfHubHTTPError) as e:
        # These are general failures from the external Hugging Face API
        logger.error(f"API error for {model_id} from Hugging Face Hub: {e}")
        raise ExternalApiError(service_name="Hugging Face Hub", original_exception=e)
    # --- Keep re-raising HTTPExceptions directly to let FastAPI handle them ---
    except HTTPException:
        raise
    # --- REFACTOR: Catch custom MalError first for other application-specific errors ---
    except MalError as e:
        logger.error(
            f"[{e.error_code}] Error in get_model_details for '{model_id}': {e.message}",
            exc_info=False,
        )
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        # Catch any other truly unexpected errors and log them as critical.
        logger.critical(
            f"An unhandled exception occurred getting details for '{model_id}': {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="An unexpected internal error occurred.")
