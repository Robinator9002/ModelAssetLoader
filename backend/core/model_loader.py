# backend/core/model_loader.py
from typing import List, Dict, Optional, Tuple, Any
from huggingface_hub import HfApi, ModelInfo # RepoSibling is also part of ModelInfo.siblings
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
        Converts a ModelInfo object to a dictionary suitable for HFModelListItem.
        Internal helper method.
        """
        model_name_derived = model_info.id.split('/')[-1] if '/' in model_info.id else model_info.id
        return {
            "id": model_info.id,
            "author": model_info.author,
            "model_name": model_name_derived,
            "lastModified": model_info.lastModified,
            "tags": model_info.tags or [],
            "pipeline_tag": model_info.pipeline_tag,
            "downloads": model_info.downloads,
            "likes": model_info.likes
        }

    def _model_info_to_dict_details(self, model_info: ModelInfo, readme_content: Optional[str]) -> Dict[str, Any]:
        """
        Converts a ModelInfo object to a dictionary suitable for HFModelDetails.
        Internal helper method.
        """
        model_name_derived = model_info.id.split('/')[-1] if '/' in model_info.id else model_info.id
        files = []
        if model_info.siblings: # siblings are the files in the repo
            files = [{"rfilename": f.rfilename, "size": f.size} for f in model_info.siblings]

        # --- WICHTIGER FIX HIER ---
        # Ensure 'gated' is a string or None for Pydantic model compatibility
        gated_value = model_info.gated
        if isinstance(gated_value, bool):
            gated_value = str(gated_value) # Convert True to "True", False to "False"
        elif gated_value is None: # Ensure None remains None, not "None" string
             gated_value = None
        # If it's already a string (e.g., "auto", "manual"), it's fine.
        # --- ENDE WICHTIGER FIX ---

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
            "gated": gated_value, # Use the processed value
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
        """
        models_iterator = self.client.list_models(
            search=search_query,
            author=author,
            filter=tags,
            sort=sort_by,
            direction=sort_direction,
            limit=None, 
            full=False, 
            cardData=False
        )

        results = []
        start_index = (page - 1) * limit
        items_considered_count = 0 
        
        try:
            for i, model_info in enumerate(models_iterator):
                items_considered_count = i + 1 
                
                if i >= start_index and len(results) < limit:
                    results.append(self._model_info_to_dict_list_item(model_info))
                
                if len(results) == limit and items_considered_count > (start_index + limit):
                    break 
            
            has_more = (len(results) == limit) and (items_considered_count > start_index + limit)

        except (GatedRepoError, RepositoryNotFoundError, HFValidationError) as e:
            logger.error(f"API error during model search: {e}")
            return [], False
        except Exception as e:
            logger.error(f"Unexpected error during model search: {e}")
            raise

        return results, has_more

    def get_model_details(self, author: str, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves detailed information for a specific model, including README content.
        """
        repo_id = f"{author}/{model_name}"
        try:
            model_info = self.client.model_info(repo_id, files_metadata=True)
            if not model_info:
                return None

            readme_content = None
            readme_filename_on_hub = None
            if model_info.siblings:
                for sibling in model_info.siblings:
                    if sibling.rfilename.upper() == "README.MD":
                        readme_filename_on_hub = sibling.rfilename 
                        break
            
            if readme_filename_on_hub:
                try:
                    readme_path = self.client.hf_hub_download(
                        repo_id=repo_id,
                        filename=readme_filename_on_hub, 
                        repo_type="model"
                    )
                    with open(readme_path, 'r', encoding='utf-8') as f:
                        readme_content = f.read()
                except RepositoryNotFoundError:
                    logger.warning(f"README file '{readme_filename_on_hub}' for {repo_id} listed but not found for download.")
                except Exception as e:
                    logger.warning(f"Could not download or read README for {repo_id} (file: {readme_filename_on_hub}): {e}")
            
            return self._model_info_to_dict_details(model_info, readme_content)

        except RepositoryNotFoundError:
            logger.info(f"Model {repo_id} not found.")
            return None
        except (GatedRepoError, HFValidationError) as e:
            logger.error(f"API error getting model details for {repo_id}: {e}")
            return None 
        except Exception as e:
            logger.error(f"Unexpected error getting model details for {repo_id}: {e}")
            raise
