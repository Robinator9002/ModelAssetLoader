# backend/dependencies.py
import logging

# --- Core Service Imports ---
# Import the main manager classes that represent our application's core services.
from core.source_manager import SourceManager
from core.file_manager import FileManager
from core.ui_manager import UiManager

logger = logging.getLogger(__name__)

# --- Service Instantiation ---
# Here, we create single, application-wide instances of our core services.
#
# Rationale:
# By creating these "singleton" instances in a dedicated, central file, we establish
# a clear and simple pattern for dependency management. Any part of our application
# that needs access to a core service (like an API router) can now import it
# directly from this file.
#
# This approach has several advantages:
# 1.  **Prevents Circular Imports:** It breaks the dependency cycle that would occur
#     if routers needed to import services from `main.py`, while `main.py` needs
#     to import the routers.
# 2.  **Single Source of Truth:** There is only one instance of each manager,
#     ensuring that all parts of the application share the same state.
# 3.  **Simplicity:** It's a straightforward and easy-to-understand alternative
#     to more complex dependency injection frameworks for this application's scale.

logger.info("Instantiating core application services...")

try:
    source_manager = SourceManager()
    file_manager = FileManager()
    ui_manager = UiManager()
    logger.info("Core application services instantiated successfully.")
except Exception as e:
    logger.critical(f"Failed to instantiate core services: {e}", exc_info=True)
    # In a real production scenario, we might want to exit the application here
    # as it cannot function without these core components.
    raise
