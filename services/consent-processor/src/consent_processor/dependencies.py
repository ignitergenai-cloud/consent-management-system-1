"""FastAPI dependency injection providers for the Consent Processor."""

from __future__ import annotations

from functools import lru_cache

from fastapi import Request

from cms_shared.aws.dynamodb import DynamoDBManager
from cms_shared.aws.sns import SNSPublisher

from consent_processor.config import ConsentProcessorSettings
from consent_processor.services.consent_workflow import ConsentWorkflow


@lru_cache
def get_settings() -> ConsentProcessorSettings:
    """Return cached application settings.

    Uses :func:`functools.lru_cache` so the settings object is created
    once and reused for every subsequent injection.
    """
    return ConsentProcessorSettings()


def get_db(request: Request) -> DynamoDBManager:
    """Retrieve the DynamoDBManager from application state.

    Args:
        request: The incoming HTTP request.

    Returns:
        The initialised DynamoDB manager stored during application startup.
    """
    return request.app.state.db


def get_sns(request: Request) -> SNSPublisher:
    """Retrieve the SNSPublisher from application state.

    Args:
        request: The incoming HTTP request.

    Returns:
        The initialised SNS publisher stored during application startup.
    """
    return request.app.state.sns


def get_workflow(request: Request) -> ConsentWorkflow:
    """Retrieve the ConsentWorkflow from application state.

    Args:
        request: The incoming HTTP request.

    Returns:
        The ConsentWorkflow instance configured during application startup.
    """
    return request.app.state.workflow
