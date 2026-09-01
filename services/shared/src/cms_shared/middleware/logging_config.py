"""Structured JSON logging configuration using structlog."""

import logging
import sys

import structlog

from cms_shared.middleware.correlation import get_correlation_id


def add_correlation_id(logger, method_name, event_dict):
    """Add correlation ID to all log entries."""
    correlation_id = get_correlation_id()
    if correlation_id:
        event_dict["correlation_id"] = correlation_id
    return event_dict


def setup_logging(service_name: str, log_level: str = "INFO") -> None:
    """Configure structured JSON logging.

    Args:
        service_name: Name of the service for log identification.
        log_level: Logging level (default: INFO).
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
            add_correlation_id,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    # Set service name in context
    structlog.contextvars.bind_contextvars(service=service_name)
