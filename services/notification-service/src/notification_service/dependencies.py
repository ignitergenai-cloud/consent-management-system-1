"""Dependency injection functions for the Notification Service.

Provides FastAPI dependency functions that retrieve initialized components
from the application state for use in route handlers.
"""

from fastapi import Request

from cms_shared.aws.dynamodb import DynamoDBManager
from cms_shared.aws.ses import SESClient
from cms_shared.aws.sns import SNSPublisher

from notification_service.config import NotificationServiceSettings
from notification_service.services.template_engine import TemplateEngine


def get_settings(request: Request) -> NotificationServiceSettings:
    """Retrieve the service settings from application state.

    Args:
        request: The incoming HTTP request.

    Returns:
        The notification service settings instance.
    """
    return request.app.state.settings


def get_db(request: Request) -> DynamoDBManager:
    """Retrieve the DynamoDB manager from application state.

    Args:
        request: The incoming HTTP request.

    Returns:
        The initialized DynamoDB manager.
    """
    return request.app.state.db


def get_sns(request: Request) -> SNSPublisher:
    """Retrieve the SNS publisher from application state.

    Args:
        request: The incoming HTTP request.

    Returns:
        The initialized SNS publisher.
    """
    return request.app.state.sns


def get_ses(request: Request) -> SESClient:
    """Retrieve the SES client from application state.

    Args:
        request: The incoming HTTP request.

    Returns:
        The initialized SES client.
    """
    return request.app.state.ses


def get_template_engine(request: Request) -> TemplateEngine:
    """Retrieve the template engine from application state.

    Args:
        request: The incoming HTTP request.

    Returns:
        The initialized Jinja2 template engine.
    """
    return request.app.state.template_engine
