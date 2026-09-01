"""Global exception handler for FastAPI services."""

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from cms_shared.middleware.correlation import get_correlation_id

logger = structlog.get_logger()


class ItemNotFoundError(Exception):
    """Raised when a requested item is not found."""

    def __init__(self, message: str = "Item not found") -> None:
        self.message = message
        super().__init__(self.message)


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """Create a consistent error response."""
    correlation_id = get_correlation_id()
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "correlation_id": correlation_id,
            }
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app."""

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        logger.warning("Validation error", error=str(exc))
        return _error_response(400, "BAD_REQUEST", str(exc))

    @app.exception_handler(KeyError)
    async def key_error_handler(request: Request, exc: KeyError) -> JSONResponse:
        logger.warning("Key not found", error=str(exc))
        return _error_response(404, "NOT_FOUND", f"Resource not found: {exc}")

    @app.exception_handler(ItemNotFoundError)
    async def item_not_found_handler(request: Request, exc: ItemNotFoundError) -> JSONResponse:
        logger.warning("Item not found", error=exc.message)
        return _error_response(404, "NOT_FOUND", exc.message)

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception", error=str(exc))
        return _error_response(500, "INTERNAL_ERROR", "An internal error occurred")
