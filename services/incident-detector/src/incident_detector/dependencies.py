"""FastAPI dependency injection helpers for the Incident Detector service."""

from __future__ import annotations

from fastapi import Request

from cms_shared.aws.dynamodb import DynamoDBManager
from cms_shared.aws.sns import SNSPublisher

from incident_detector.config import IncidentDetectorSettings
from incident_detector.services.incident_manager import IncidentManager
from incident_detector.services.metric_collector import MetricCollector


def get_settings(request: Request) -> IncidentDetectorSettings:
    """Return the application settings stored on ``app.state``."""
    return request.app.state.settings


def get_dynamo_manager(request: Request) -> DynamoDBManager:
    """Return the DynamoDB manager stored on ``app.state``."""
    return request.app.state.dynamo_manager


def get_sns_publisher(request: Request) -> SNSPublisher:
    """Return the SNS publisher stored on ``app.state``."""
    return request.app.state.sns_publisher


def get_metric_collector(request: Request) -> MetricCollector:
    """Return the shared metric collector stored on ``app.state``."""
    return request.app.state.metric_collector


def get_incident_manager(request: Request) -> IncidentManager:
    """Return the incident manager stored on ``app.state``."""
    return request.app.state.incident_manager
