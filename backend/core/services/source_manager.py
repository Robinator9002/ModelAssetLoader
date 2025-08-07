# backend/core/source_manager.py
import logging
from typing import List, Dict, Optional, Any, Tuple

from core.sources.base import APISource
from core.sources.hf_source import HuggingFaceSource
from core.ui_management.ui_registry import UiRegistry
# --- NEW: Import custom error classes for standardized handling ---
from core.errors import BadRequestError

# To add a new source (e.g., Civitai):
# 1. Create a `civitai_source.py` that implements `APISource`.
# 2. Import it here: `from .sources.civitai_source import CivitaiSource`.
# 3. Add an instance of it to the `self.sources` dictionary in __init__.

logger = logging.getLogger(__name__)


class SourceManager:
    """
    Manages and orchestrates multiple API sources for models.

    This class acts as a single point of entry for searching and retrieving
    model information, abstracting away the specifics of each source API.
    """

    def __init__(self):
        """Initializes the SourceManager and registers all available sources."""
        self.sources: Dict[str, APISource] = {}
        self._register_sources()
        logger.info(
            f"SourceManager initialized with sources: {list(self.sources.keys())}"
        )

    def _register_sources(self):
        """
        Creates instances of all available APISource implementations
        and registers them.
        """
        # Register Hugging Face source
        hf_source = HuggingFaceSource()
        self.sources[hf_source.name] = hf_source

        # Register other sources here in the future
        # civitai_source = CivitaiSource()
        # self.sources[civitai_source.name] = civitai_source

    def search_models(
        self, source: Optional[str] = None, **kwargs: Any
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Searches for models, either from a specific source or all sources.

        Args:
            source: The name of the source to search (e.g., 'huggingface').
                    If None, it will (in the future) search all sources.
            **kwargs: Search parameters to be passed to the source's search method.

        Returns:
            A tuple of (results_list, has_more_flag).
        @refactor: This method now raises BadRequestError for unregistered sources.
        """
        # For now, default to 'huggingface' if no source is specified.
        # A multi-source search would require more complex logic for merging and pagination.
        target_source_name = source or "huggingface"

        if target_source_name not in self.sources:
            # --- REFACTOR: Raise BadRequestError for an invalid source ---
            raise BadRequestError(f"Source '{target_source_name}' is not registered or supported.")

        logger.info(f"Delegating search to '{target_source_name}' source.")
        target_source = self.sources[target_source_name]
        # The search_models method of the target_source (e.g., HuggingFaceSource)
        # will be refactored to raise ExternalApiError or other MalErrors.
        # This method will then simply propagate those errors.
        return target_source.search_models(**kwargs)

    def get_model_details(self, model_id: str, source: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves model details from a specific source.

        Args:
            model_id: The unique ID of the model.
            source: The name of the source where the model resides.

        Returns:
            A dictionary with detailed model information, or None if not found.
        @refactor: This method now raises BadRequestError for unregistered sources,
        and delegates to the source which will raise EntityNotFoundError or ExternalApiError.
        """
        if source not in self.sources:
            # --- REFACTOR: Raise BadRequestError for an invalid source ---
            logger.error(
                f"Attempted to get details from unregistered source: '{source}'"
            )
            raise BadRequestError(f"Source '{source}' is not registered or supported.")

        logger.info(f"Delegating detail request for '{model_id}' to '{source}' source.")
        target_source = self.sources[source]
        # The get_model_details method of the target_source (e.g., HuggingFaceSource)
        # will be refactored to raise EntityNotFoundError or ExternalApiError.
        # This method will then simply propagate those errors.
        return target_source.get_model_details(model_id=model_id)
