# backend/core/errors.py
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class MalError(Exception):
    """
    Base exception class for all custom errors in the M.A.L. application.

    This allows for a single `try...except MalError` block to catch all
    application-specific errors, while letting other unexpected exceptions
    be handled separately.

    Attributes:
        message (str): A user-friendly message describing the error.
        status_code (int): The HTTP status code to be returned to the client.
        error_code (str): A machine-readable code for the specific error type.
    """

    def __init__(
        self,
        message: str = "An unexpected error occurred.",
        status_code: int = 500,
        error_code: str = "INTERNAL_SERVER_ERROR",
        original_exception: Optional[Exception] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(self.message)

        if original_exception:
            logger.error(
                f"[{self.error_code}] {self.message}: {original_exception}", exc_info=False
            )


class EntityNotFoundError(MalError):
    """Raised when a specific entity (e.g., a model, a UI) cannot be found."""

    def __init__(self, entity_name: str, entity_id: str):
        message = f"{entity_name} '{entity_id}' could not be found."
        super().__init__(message=message, status_code=404, error_code="ENTITY_NOT_FOUND")


class BadRequestError(MalError):
    """Raised for invalid user input, such as a bad path or invalid configuration."""

    def __init__(self, message: str):
        super().__init__(message=message, status_code=400, error_code="BAD_REQUEST")


class ExternalApiError(MalError):
    """Raised when an external API (e.g., Hugging Face) fails or returns an error."""

    def __init__(self, service_name: str, original_exception: Exception):
        message = f"An error occurred while communicating with {service_name}."
        super().__init__(
            message=message,
            status_code=502,  # Bad Gateway
            error_code="EXTERNAL_API_ERROR",
            original_exception=original_exception,
        )


class OperationFailedError(MalError):
    """A generic error for when a backend operation fails unexpectedly."""

    def __init__(self, operation_name: str, original_exception: Exception):
        message = f"The operation '{operation_name}' failed unexpectedly."
        super().__init__(
            message=message,
            status_code=500,
            error_code="OPERATION_FAILED",
            original_exception=original_exception,
        )
