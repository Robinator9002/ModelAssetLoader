# backend/dependencies.py
import logging

# --- Core Service Imports ---
# Import the main manager classes that represent our application's core services.
from core.services.source_manager import SourceManager
from core.services.file_manager import FileManager
from core.services.ui_manager import UiManager
from core.ui_management.ui_registry import UiRegistry

logger = logging.getLogger(__name__)

# --- Singleton Service Instantiation ---
# Here, we create single, application-wide instances of our core services.
# This is crucial for maintaining a consistent state across the entire app.

logger.info("Instantiating core application services for dependency injection...")

try:
    # 1. Instantiate the UiRegistry first, as it's a shared dependency.
    # This ensures that both FileManager and UiManager are working with the exact
    # same list of installed UI environments.
    ui_registry = UiRegistry()

    # 2. Instantiate the main managers, injecting any shared dependencies.
    source_manager = SourceManager()
    # We pass the singleton ui_registry to both managers that need it.
    file_manager = FileManager(ui_registry)
    ui_manager = UiManager(ui_registry)

    logger.info("Core application services instantiated successfully.")

except Exception as e:
    logger.critical(f"Failed to instantiate core services: {e}", exc_info=True)
    # The application cannot function without these services, so we re-raise.
    raise


# --- Dependency Provider Functions ---
# These functions are the core of the new dependency injection pattern.
# Instead of importing the instances directly, routers will use FastAPI's
# `Depends()` with these functions. This makes dependencies explicit and
# decouples the routers from the instantiation logic.


def get_source_manager() -> SourceManager:
    """Provides the singleton SourceManager instance."""
    return source_manager


def get_file_manager() -> FileManager:
    """Provides the singleton FileManager instance."""
    return file_manager


def get_ui_manager() -> UiManager:
    """Provides the singleton UiManager instance."""
    return ui_manager
