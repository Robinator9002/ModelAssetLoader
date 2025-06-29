# backend/core/sources/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any, Tuple

class APISource(ABC):
    """
    Abstract Base Class for an external API source.

    This class defines a contract that all data source handlers (like Hugging Face,
    Civitai, etc.) must follow. This ensures that the main application can
    interact with any source in a consistent way.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Returns the unique, identifying name of the source (e.g., 'huggingface')."""
        pass

    @abstractmethod
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
        Searches for models from this specific source.

        Args:
            search_query: The main search term.
            author: Filter by a specific author or organization.
            tags: A list of tags to filter by.
            sort_by: The field to sort results by.
            sort_direction: Sort direction (-1 for desc, 1 for asc).
            limit: The number of results per page.
            page: The page number (1-indexed).

        Returns:
            A tuple containing:
                - A list of model data dictionaries.
                - A boolean indicating if more pages are available (`has_more`).
        """
        pass

    @abstractmethod
    def get_model_details(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves detailed information for a specific model.

        Args:
            model_id: The unique identifier for the model within this source
                      (e.g., 'author/model_name').

        Returns:
            A dictionary containing detailed model information, or None if not found.
        """
        pass
