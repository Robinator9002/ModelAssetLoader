# backend/routers/models.py
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

# --- API Model Imports ---
# Import the specific Pydantic models needed for these endpoints.
from api.models import (
    ModelDetails,
    PaginatedModelListResponse,
    ModelListItem,
)

# --- Service Imports ---
# This router needs access to the source_manager to perform its duties.
# We will create this instance in a central place and import it.
# For now, we assume it's available from a central dependencies file.
from dependencies import source_manager

logger = logging.getLogger(__name__)

# Create an APIRouter instance. This is like a mini-FastAPI app.
# All routes defined here will be prefixed with '/api', and grouped under the 'Models' tag in the docs.
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

    This function was moved from main.py to this router to improve code
    organization and separation of concerns. It delegates the actual search
    logic to the `source_manager`.
    """
    try:
        unique_tags = list(set(tags)) if tags else None
        models_data, has_more = source_manager.search_models(
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
    except Exception as e:
        logger.error(f"Error in search_models: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error during model search.")


@router.get(
    "/models/{source}/{model_id:path}",
    response_model=ModelDetails,
    summary="Get Model Details from a Source",
)
async def get_model_details_endpoint(source: str, model_id: str):
    """
    Endpoint for retrieving detailed information about a specific model.

    This function was also moved from main.py. It delegates the detail
    retrieval logic to the `source_manager`.
    """
    try:
        details_data = source_manager.get_model_details(model_id=model_id, source=source)
        if not details_data:
            raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found.")
        return ModelDetails(**details_data)
    except HTTPException:
        # Re-raise HTTPExceptions directly to let FastAPI handle them.
        raise
    except Exception as e:
        logger.error(f"Error in get_model_details for '{model_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred.")
