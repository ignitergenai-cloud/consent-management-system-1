"""Dependency injection functions for the Incident Bridge service.

Provides FastAPI dependency functions that retrieve initialized components
from the application state for use in route handlers.
"""

from fastapi import Request

from cms_shared.aws.sns import SNSPublisher

from incident_bridge.config import IncidentBridgeSettings
from incident_bridge.services.bridge_event_log import BridgeEventLog
from incident_bridge.services.mims_publisher import MIMSPublisher


def get_settings(request: Request) -> IncidentBridgeSettings:
    """Retrieve the service settings from application state.

    Args:
        request: The incoming HTTP request.

    Returns:
        The incident bridge settings instance.
    """
    return request.app.state.settings


def get_sns_publisher(request: Request) -> SNSPublisher:
    """Retrieve the SNS publisher from application state.

    Args:
        request: The incoming HTTP request.

    Returns:
        The initialized SNSPublisher.
    """
    return request.app.state.sns


def get_event_log(request: Request) -> BridgeEventLog:
    """Retrieve the bridge event log from application state.

    Args:
        request: The incoming HTTP request.

    Returns:
        The in-memory BridgeEventLog instance.
    """
    return request.app.state.bridge_event_log


def get_bridge_status(request: Request) -> dict:
    """Retrieve the current bridge status from application state.

    Args:
        request: The incoming HTTP request.

    Returns:
        A dictionary describing the current bridge status including
        whether consumers are running, the MIMS topic, and event count.
    """
    settings: IncidentBridgeSettings = request.app.state.settings
    bridge_event_log: BridgeEventLog = request.app.state.bridge_event_log
    incident_task = getattr(request.app.state, "incident_consumer_task", None)
    commands_task = getattr(request.app.state, "commands_consumer_task", None)

    consumers_running = (
        (incident_task is not None and not incident_task.done())
        and (commands_task is not None and not commands_task.done())
    )

    return {
        "consumers_running": consumers_running,
        "mims_topic": settings.sns_mims_inbound_topic,
        "total_events_processed": bridge_event_log.total_count,
    }
