# backend/core/sources/hf_source.py
from typing import List, Dict, Optional, Tuple, Any
from huggingface_hub import HfApi, ModelInfo
from huggingface_hub.utils import (
    GatedRepoError,
    RepositoryNotFoundError,
    HFValidationError,
    HfHubHTTPError,
)
import logging

from .base import APISource

# --- NEW: Import custom error classes for standardized handling (global import) ---
from core.errors import (
    MalError,
    OperationFailedError,
    BadRequestError,
    EntityNotFoundError,
    ExternalApiError,
)

logger = logging.getLogger(__name__)

# Define the sort keys that Hugging Face API restricts to descending order only.
DESC_ONLY_SORTS = {"downloads", "likes", "lastModified"}


class HuggingFaceSource(APISource):
    """
    An APISource implementation for interacting with the Hugging Face Hub.
    """

    def __init__(self):
        """Initializes the HuggingFaceSource with an HfApi client."""
        self.client = HfApi()
        logger.info(f"'{self.name}' source initialized with HfApi client.")

    @property
    def name(self) -> str:
        return "huggingface"

    def _model_info_to_dict_list_item(self, model_info: ModelInfo) -> Dict[str, Any]:
        """Converts a ModelInfo object to a dictionary for a model list item."""
        model_name_derived = model_info.id.split("/")[-1] if "/" in model_info.id else model_info.id
        return {
            "id": model_info.id,
            "source": self.name,
            "author": model_info.author,
            "model_name": model_name_derived,
            "lastModified": model_info.lastModified,
            "tags": model_info.tags or [],
            "pipeline_tag": model_info.pipeline_tag,
            "downloads": model_info.downloads,
            "likes": model_info.likes,
        }

    def _model_info_to_dict_details(
        self, model_info: ModelInfo, readme_content: Optional[str]
    ) -> Dict[str, Any]:
        """Converts a ModelInfo object and README to a detailed model dictionary."""
        model_name_derived = model_info.id.split("/")[-1] if "/" in model_info.id else model_info.id
        files = (
            [{"rfilename": f.rfilename, "size": f.size} for f in model_info.siblings]
            if model_info.siblings
            else []
        )

        gated_value = model_info.gated
        if isinstance(gated_value, bool):
            gated_value = str(gated_value)

        return {
            "id": model_info.id,
            "source": self.name,
            "author": model_info.author,
            "model_name": model_name_derived,
            "lastModified": model_info.lastModified,
            "tags": model_info.tags or [],
            "pipeline_tag": model_info.pipeline_tag,
            "downloads": model_info.downloads,
            "likes": model_info.likes,
            "sha": model_info.sha,
            "private": model_info.private,
            "gated": gated_value,
            "library_name": model_info.library_name,
            "siblings": files,
            "readme_content": readme_content,
        }

    def search_models(
        self,
        search_query: Optional[str] = None,
        author: Optional[str] = None,
        tags: Optional[List[str]] = None,
        sort_by: Optional[str] = "lastModified",
        sort_direction: Optional[int] = -1,
        limit: int = 30,
        page: int = 1,
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Searches for models on the Hugging Face Hub with server-side pagination.
        @refactor: Now raises ExternalApiError on API failures.
        """

        final_sort_direction = sort_direction
        if sort_by in DESC_ONLY_SORTS and sort_direction == 1:
            logger.warning(
                f"[{self.name}] The API does not support ascending sort for '{sort_by}'. "
                f"Forcing direction to -1 (descending) for API call."
            )
            final_sort_direction = -1

        logger.info(
            f"[{self.name}] Searching models: page={page}, limit={limit}, query='{search_query}', sort='{sort_by}', direction='{final_sort_direction}'"
        )

        try:
            models_iterator = self.client.list_models(
                search=search_query,
                author=author,
                filter=tags,
                sort=sort_by,
                direction=final_sort_direction,
                limit=None,
                full=False,
                cardData=False,
            )

            results_for_page = []
            start_index = (page - 1) * limit
            end_index_for_check = start_index + limit + 1
            items_processed_count = 0

            for i, model_info in enumerate(models_iterator):
                items_processed_count = i + 1
                if start_index <= i < (start_index + limit):
                    results_for_page.append(self._model_info_to_dict_list_item(model_info))

                if items_processed_count >= end_index_for_check:
                    break

            has_more = items_processed_count > (start_index + limit)

            # --- If the original request was for ascending sort on a descending-only field,
            # we reverse the results of the page to simulate the expected ascending order.
            if sort_by in DESC_ONLY_SORTS and sort_direction == 1:
                logger.info(
                    f"[{self.name}] Reversing page results for '{sort_by}' to simulate ascending order."
                )
                results_for_page.reverse()

            return results_for_page, has_more
        except (HfHubHTTPError, GatedRepoError, RepositoryNotFoundError, HFValidationError) as e:
            # --- REFACTOR: Catch specific Hugging Face errors and raise ExternalApiError ---
            logger.error(f"[{self.name}] API error during search (query: '{search_query}'): {e}")
            raise ExternalApiError(service_name="Hugging Face Hub", original_exception=e) from e
        except Exception as e:
            # --- REFACTOR: Catch any other unexpected errors and raise OperationFailedError ---
            logger.error(f"[{self.name}] Unexpected error during search: {e}", exc_info=True)
            raise OperationFailedError(
                operation_name=f"Search Hugging Face models (query: '{search_query}')",
                original_exception=e,
            ) from e

    def get_model_details(
        self, model_id: str
    ) -> Dict[
        str, Any
    ]:  # --- REFACTOR: Changed return type from Optional[Dict] to Dict, will raise EntityNotFoundError ---
        """
        Retrieves detailed information for a specific model from the Hub.
        @refactor: Now raises EntityNotFoundError or ExternalApiError on failure.
        """
        logger.info(f"[{self.name}] Fetching details for model: {model_id}")
        try:
            model_info = self.client.model_info(model_id, files_metadata=True)
            if (
                not model_info
            ):  # This case should ideally not be reached if RepositoryNotFoundError is caught
                # --- NEW: If model_info is None without a specific Hugging Face error, raise EntityNotFoundError ---
                raise EntityNotFoundError(
                    entity_name="Model",
                    entity_id=model_id,
                    message=f"Model '{model_id}' not found on Hugging Face Hub.",
                )

            readme_content = None
            readme_filename = next(
                (s.rfilename for s in model_info.siblings if s.rfilename.upper() == "README.MD"),
                None,
            )

            if readme_filename:
                try:
                    readme_path = self.client.hf_hub_download(
                        repo_id=model_id, filename=readme_filename, repo_type="model"
                    )
                    with open(readme_path, "r", encoding="utf-8") as f:
                        readme_content = f.read()
                except Exception as e:
                    logger.warning(f"[{self.name}] Could not read README for {model_id}: {e}")
                    # --- NEW: Log but don't re-raise, as missing README isn't critical for model details ---
                    # The model details can still be returned without the README.

            return self._model_info_to_dict_details(model_info, readme_content)
        except RepositoryNotFoundError as e:
            # --- REFACTOR: This is a specific "not found" case, raise EntityNotFoundError ---
            logger.info(f"[{self.name}] Model repository '{model_id}' not found.")
            raise EntityNotFoundError(entity_name="Model", entity_id=model_id) from e
        except (GatedRepoError, HFValidationError, HfHubHTTPError) as e:
            # --- REFACTOR: These are general API failures, raise ExternalApiError ---
            logger.error(f"[{self.name}] API error for {model_id}: {e}")
            raise ExternalApiError(service_name="Hugging Face Hub", original_exception=e) from e
        except Exception as e:
            # --- REFACTOR: Catch any other unexpected errors and raise OperationFailedError ---
            logger.error(
                f"[{self.name}] Unexpected error retrieving details for {model_id}: {e}",
                exc_info=True,
            )
            raise OperationFailedError(
                operation_name=f"Retrieve model details for '{model_id}' from Hugging Face Hub",
                original_exception=e,
            ) from e
