# backend/core/model_loader.py
from typing import List, Dict, Optional, Tuple, Any
from huggingface_hub import HfApi, ModelInfo
from huggingface_hub.utils import GatedRepoError, RepositoryNotFoundError, HFValidationError
import logging

logger = logging.getLogger(__name__)

class ModelLoader:
    """
    Handles interactions with the Hugging Face Hub API.

    This class provides methods to search, list, and retrieve detailed
    information about models hosted on the Hugging Face Hub. It serves as a
    dedicated layer for all Hub-related communications.
    """

    def __init__(self):
        """Initializes the ModelLoader with an HfApi client."""
        self.client = HfApi()
        logger.info("ModelLoader initialized with HfApi client.")

    def _model_info_to_dict_list_item(self, model_info: ModelInfo) -> Dict[str, Any]:
        """
        Converts a ModelInfo object into a dictionary for a model list item.

        This helper method maps fields from the Hugging Face `ModelInfo` object
        to the structure defined by the `HFModelListItem` Pydantic model, ensuring
        consistency for API responses.

        Args:
            model_info: The ModelInfo object from the huggingface_hub library.

        Returns:
            A dictionary representing the model for a list view.
        """
        # The model name is often the last part of the repo ID (e.g., 'model_name' in 'author/model_name').
        model_name_derived = model_info.id.split('/')[-1] if '/' in model_info.id else model_info.id
        return {
            "id": model_info.id,
            "author": model_info.author,
            "model_name": model_name_derived,
            "lastModified": model_info.lastModified,
            "tags": model_info.tags or [], # Ensure tags is always a list, not None.
            "pipeline_tag": model_info.pipeline_tag,
            "downloads": model_info.downloads,
            "likes": model_info.likes
        }

    def _model_info_to_dict_details(self, model_info: ModelInfo, readme_content: Optional[str]) -> Dict[str, Any]:
        """
        Converts a ModelInfo object and README content into a detailed model dictionary.

        This helper maps fields to the structure defined by the `HFModelDetails`
        Pydantic model, including file lists and README content.

        Args:
            model_info: The full ModelInfo object from the huggingface_hub library.
            readme_content: The string content of the model's README file.

        Returns:
            A dictionary with detailed model information.
        """
        model_name_derived = model_info.id.split('/')[-1] if '/' in model_info.id else model_info.id
        files = [{"rfilename": f.rfilename, "size": f.size} for f in model_info.siblings] if model_info.siblings else []

        # Pydantic Compatibility Fix for the 'gated' attribute:
        # The 'gated' attribute from ModelInfo can be a bool, a string ("auto", "manual"), or None.
        # Our Pydantic model `HFModelDetails` expects Optional[str] for consistency.
        # This logic converts boolean values to their string representation.
        gated_value = model_info.gated
        if isinstance(gated_value, bool):
            gated_value = str(gated_value)  # Convert True -> "True", False -> "False"

        return {
            "id": model_info.id,
            "author": model_info.author,
            "model_name": model_name_derived,
            "lastModified": model_info.lastModified,
            "tags": model_info.tags or [],
            "pipeline_tag": model_info.pipeline_tag,
            "downloads": model_info.downloads,
            "likes": model_info.likes,
            "sha": model_info.sha,
            "private": model_info.private,
            "gated": gated_value,  # Use the processed, string-compatible value
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

        This method fetches a list of models based on search criteria and paginates
        the results.

        Args:
            search_query: The main search term.
            author: Filter models by a specific author or organization.
            tags: A list of tags to filter by.
            sort_by: The field to sort results by (e.g., "downloads", "likes").
            sort_direction: Sort direction: -1 for descending, 1 for ascending.
            limit: The number of results to return per page.
            page: The desired page number (1-indexed).

        Returns:
            A tuple containing:
                - A list of model dictionaries for the requested page.
                - A boolean indicating if more pages are available (`has_more`).
        """
        # --- Pagination Strategy ---
        # The `huggingface_hub.list_models` returns an iterator over all matching models.
        # It does not provide a total count, making traditional database-style pagination
        # (e.g., with OFFSET) impossible.
        # To implement pagination and determine if a next page exists (`has_more`),
        # we manually process the iterator. We iterate up to the end of the *next* page
        # to see if there are enough items to confirm a "next page" exists.
        
        logger.info(f"Searching HF models: page={page}, limit={limit}, query='{search_query}', sort='{sort_by}'")

        models_iterator = self.client.list_models(
            search=search_query,
            author=author,
            filter=tags,
            sort=sort_by,
            direction=sort_direction,
            limit=None,       # Fetch all matching metadata from the Hub API.
            full=False,       # Performance: Don't fetch full card data for list items.
            cardData=False
        )

        results_for_page = []
        start_index = (page - 1) * limit
        # We need to check one item beyond the current page to determine `has_more`.
        end_index_for_check = start_index + limit + 1
        
        items_processed_count = 0

        try:
            for i, model_info in enumerate(models_iterator):
                items_processed_count = i + 1

                # If the item is within the bounds of the current page, add it to results.
                if start_index <= i < (start_index + limit):
                    results_for_page.append(self._model_info_to_dict_list_item(model_info))
                
                # Optimization: If we have processed enough items to determine `has_more`
                # and have filled the current page, we can stop iterating early.
                if items_processed_count >= end_index_for_check:
                    break
            
            # `has_more` is true if the total number of items we could process from the iterator
            # is greater than the number of items that would fill up to the end of the current page.
            has_more = items_processed_count > (start_index + limit)

        except (GatedRepoError, RepositoryNotFoundError, HFValidationError) as e:
            logger.error(f"Hugging Face API error during model search (query: '{search_query}'): {e}")
            return [], False # Return empty list and no more pages on a known API error.
        except Exception as e:
            logger.error(f"An unexpected error occurred during model search: {e}", exc_info=True)
            raise # Re-raise for FastAPI's main error handler to catch.

        return results_for_page, has_more

    def get_model_details(self, author: str, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves detailed information for a specific model, including its README.

        Args:
            author: The author or organization that owns the model repository.
            model_name: The name of the model.

        Returns:
            A dictionary containing detailed model information, or None if the
            model is not found or another error occurs.
        """
        repo_id = f"{author}/{model_name}"
        logger.info(f"Fetching details for model repository: {repo_id}")
        try:
            # Fetch model info, including metadata about its files (siblings).
            model_info = self.client.model_info(repo_id, files_metadata=True)
            if not model_info:
                # This case is usually caught by RepositoryNotFoundError, but is a safe fallback.
                logger.warning(f"API call for {repo_id} returned no data.")
                return None

            readme_content = None
            readme_filename = next((s.rfilename for s in model_info.siblings if s.rfilename.upper() == "README.MD"), None)

            if readme_filename:
                try:
                    # Download the README file's content.
                    readme_path = self.client.hf_hub_download(
                        repo_id=repo_id,
                        filename=readme_filename,
                        repo_type="model"
                    )
                    with open(readme_path, 'r', encoding='utf-8') as f:
                        readme_content = f.read()
                except Exception as e:
                    logger.warning(
                        f"Could not download or read README ('{readme_filename}') for repo {repo_id}: {e}"
                    )
            
            return self._model_info_to_dict_details(model_info, readme_content)

        except RepositoryNotFoundError:
            logger.info(f"Model repository '{repo_id}' not found on Hugging Face Hub.")
            return None # Expected error, return None for a 404 response upstream.
        except (GatedRepoError, HFValidationError) as e:
            logger.error(f"API error for {repo_id}: {e}")
            return None # Specific, known client errors.
        except Exception as e:
            logger.error(f"An unexpected error occurred retrieving details for {repo_id}: {e}", exc_info=True)
            raise # Re-raise unexpected errors for the server to handle.
