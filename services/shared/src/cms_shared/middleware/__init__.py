"""Middleware for FastAPI services."""

from cms_shared.middleware.correlation import CorrelationIdMiddleware, get_correlation_id
from cms_shared.middleware.error_handler import (
    ItemNotFoundError,
    register_exception_handlers,
)
from cms_shared.middleware.logging_config import setup_logging

__all__ = [
    "CorrelationIdMiddleware",
    "get_correlation_id",
    "ItemNotFoundError",
    "register_exception_handlers",
    "setup_logging",
]
