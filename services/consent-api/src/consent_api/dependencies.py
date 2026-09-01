"""FastAPI dependency injection providers."""

from functools import lru_cache

from fastapi import Depends, Request

from cms_shared.aws.dynamodb import DynamoDBManager
from cms_shared.aws.sns import SNSPublisher

from consent_api.config import ConsentApiSettings
from consent_api.repositories.consent_repository import ConsentRepository
from consent_api.services.consent_service import ConsentService


@lru_cache
def get_settings() -> ConsentApiSettings:
    """Return cached application settings."""
    return ConsentApiSettings()


def get_dynamo_manager(request: Request) -> DynamoDBManager:
    """Retrieve the DynamoDBManager from application state."""
    return request.app.state.dynamo_manager


def get_sns_publisher(request: Request) -> SNSPublisher:
    """Retrieve the SNSPublisher from application state."""
    return request.app.state.sns_publisher


def get_consent_repository(
    dynamo: DynamoDBManager = Depends(get_dynamo_manager),
) -> ConsentRepository:
    """Create a ConsentRepository with the active DynamoDB manager."""
    return ConsentRepository(dynamo)


def get_consent_service(
    repo: ConsentRepository = Depends(get_consent_repository),
    sns: SNSPublisher = Depends(get_sns_publisher),
    settings: ConsentApiSettings = Depends(get_settings),
) -> ConsentService:
    """Create a ConsentService with all required dependencies."""
    return ConsentService(repository=repo, sns_publisher=sns, settings=settings)
