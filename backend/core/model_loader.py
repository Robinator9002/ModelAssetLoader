# backend/core/model_loader.py
from typing import List, Dict, Optional, Tuple, Any
from huggingface_hub import HfApi, ModelInfo
from huggingface_hub.utils import GatedRepoError, RepositoryNotFoundError, HFValidationError
import logging

logger = logging.getLogger(__name__)

class ModelLoader:
    """
    Handles interactions with the Hugging Face Hub API to search,
    list, and retrieve information about models.

    Attributes:
        client (HfApi): An instance of the Hugging Face API client.
    """

    def __init__(self):
        """Initializes the ModelLoader with an HfApi client."""
        self.client = HfApi()

    def _model_info_to_dict_list_item(self, model_info: ModelInfo) -> Dict[str, Any]:
        """
        Converts a ModelInfo object to a dictionary suitable for representing
        a model in a list (e.g., for search results, matching HFModelListItem).

        Internal helper method.
        """
        # Derive model_name from id if it contains a '/', otherwise use id as is.
        # This is a common pattern if the full ID is like "author/model_name".
        model_name_derived = model_info.id.split('/')[-1] if '/' in model_info.id else model_info.id
        return {
            "id": model_info.id,
            "author": model_info.author,
            "model_name": model_name_derived,
            "lastModified": model_info.lastModified,
            "tags": model_info.tags or [], # Ensure tags is always a list
            "pipeline_tag": model_info.pipeline_tag,
            "downloads": model_info.downloads,
            "likes": model_info.likes
        }

    def _model_info_to_dict_details(self, model_info: ModelInfo, readme_content: Optional[str]) -> Dict[str, Any]:
        """
        Converts a ModelInfo object and README content to a dictionary
        suitable for representing detailed model information (matching HFModelDetails).

        Internal helper method.
        """
        model_name_derived = model_info.id.split('/')[-1] if '/' in model_info.id else model_info.id
        files = []
        if model_info.siblings:  # siblings represent the files in the repository
            files = [{"rfilename": f.rfilename, "size": f.size} for f in model_info.siblings]

        # --- Pydantic Compatibility for 'gated' attribute ---
        # The 'gated' attribute from Hugging Face's ModelInfo can be a boolean,
        # a string (e.g., "auto", "manual"), or None.
        # Pydantic models (like HFModelDetails) might expect a consistent type, e.g., Optional[str].
        # This conversion ensures that boolean True/False are converted to "True"/"False" strings,
        # None remains None, and existing strings are passed through.
        gated_value = model_info.gated
        if isinstance(gated_value, bool):
            gated_value = str(gated_value)  # Convert True to "True", False to "False"
        # elif gated_value is None: # This check is redundant if Pydantic model expects Optional[str]
        #     gated_value = None    # as None is a valid value for Optional[str].
        # If it's already a string (e.g., "auto", "manual") or None, it's fine for Optional[str].
        # --- End of Pydantic Compatibility Fix ---

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
            "gated": gated_value,  # Use the processed value
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
        Searches for models on the Hugging Face Hub with pagination.

        Args:
            search_query: The search term.
            author: Filter by author.
            tags: A list of tags to filter by.
            sort_by: Field to sort by (e.g., "lastModified", "downloads", "likes").
            sort_direction: -1 for descending, 1 for ascending.
            limit: Number of results per page.
            page: The page number to retrieve (1-indexed).

        Returns:
            A tuple containing:
                - A list of model dictionaries (matching HFModelListItem structure).
                - A boolean indicating if more results are available (has_more).
        """
        # Note: HfApi().list_models returns an iterator.
        # To implement pagination and determine 'has_more' without a total count from the API,
        # we fetch a bit more than needed for the current page if possible, or iterate
        # and count.
        # Setting 'limit=None' in list_models fetches all matching models if not further constrained.
        # We will fetch all and then paginate manually from the iterator's results.
        models_iterator = self.client.list_models(
            search=search_query,
            author=author,
            filter=tags,
            sort=sort_by,
            direction=sort_direction,
            limit=None, # Fetch all metadata, then paginate manually
            full=False, # Avoid fetching full model card data for list items for performance
            cardData=False # Avoid fetching card data for list items
        )

        results = []
        start_index = (page - 1) * limit
        # items_considered_count is used to determine if there might be more items
        # beyond the current page.
        items_processed_from_iterator = 0

        try:
            for i, model_info in enumerate(models_iterator):
                items_processed_from_iterator = i + 1 # Count how many items we've processed

                if i >= start_index and len(results) < limit:
                    results.append(self._model_info_to_dict_list_item(model_info))

                # Optimization: If we've filled the current page and have already processed
                # enough items to know there's at least one more for the next page,
                # we can break early. This avoids iterating through the entire HfApi result
                # if we only need a few pages.
                if len(results) == limit and items_processed_from_iterator > (start_index + limit):
                    break
            
            # Determine if there are more results.
            # 'has_more' is true if the number of items processed from the iterator
            # is greater than the number of items that would fill up to the *end* of the current page.
            has_more = items_processed_from_iterator > (start_index + limit)

        except (GatedRepoError, RepositoryNotFoundError, HFValidationError) as e:
            logger.error(f"API error during model search (query: '{search_query}'): {e}")
            return [], False # Return empty list and no more pages on API error
        except Exception as e:
            logger.error(f"Unexpected error during model search (query: '{search_query}'): {e}", exc_info=True)
            # Re-raise for unhandled exceptions to allow higher-level error handling
            # or to be caught by FastAPI's exception handlers.
            raise

        return results, has_more

    def get_model_details(self, author: str, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves detailed information for a specific model, including its README content.

        Args:
            author: The author or organization of the model.
            model_name: The name of the model.

        Returns:
            A dictionary containing model details (matching HFModelDetails structure),
            or None if the model is not found or an error occurs.
        """
        repo_id = f"{author}/{model_name}"
        try:
            # Fetch model info, including metadata about its files (siblings)
            model_info = self.client.model_info(repo_id, files_metadata=True)
            if not model_info: # Should be caught by RepositoryNotFoundError, but good practice
                logger.info(f"Model {repo_id} info returned None from API.")
                return None

            readme_content = None
            readme_filename_on_hub = None

            # Find the README file among the model's siblings (files)
            if model_info.siblings:
                for sibling in model_info.siblings:
                    # README.md is case-insensitive on some systems but usually canonical on Hub
                    if sibling.rfilename.upper() == "README.MD":
                        readme_filename_on_hub = sibling.rfilename
                        break # Found the README

            if readme_filename_on_hub:
                try:
                    # Download the README file
                    readme_path_on_disk = self.client.hf_hub_download(
                        repo_id=repo_id,
                        filename=readme_filename_on_hub,
                        repo_type="model" # Ensure we are looking for a model type repo
                    )
                    with open(readme_path_on_disk, 'r', encoding='utf-8') as f:
                        readme_content = f.read()
                except RepositoryNotFoundError:
                    # This can happen if the README is listed as a sibling but is not downloadable
                    # (e.g., due to .gitattributes or other reasons, though rare for READMEs).
                    logger.warning(
                        f"README file '{readme_filename_on_hub}' for {repo_id} "
                        f"was listed in siblings but not found for download."
                    )
                except Exception as e:
                    logger.warning(
                        f"Could not download or read README for {repo_id} "
                        f"(file: {readme_filename_on_hub}): {e}"
                    )
            
            return self._model_info_to_dict_details(model_info, readme_content)

        except RepositoryNotFoundError:
            logger.info(f"Model {repo_id} not found on Hugging Face Hub.")
            return None
        except (GatedRepoError, HFValidationError) as e:
            # These are specific Hugging Face client errors
            logger.error(f"API error retrieving model details for {repo_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error retrieving model details for {repo_id}: {e}", exc_info=True)
            # Re-raise for unhandled exceptions
            raise
