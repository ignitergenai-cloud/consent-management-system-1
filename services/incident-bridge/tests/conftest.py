"""Shared test fixtures for the incident-bridge service."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from incident_bridge.config import IncidentBridgeSettings
from incident_bridge.services.bridge_event_log import BridgeEventLog
from incident_bridge.services.event_transformer import EventTransformer


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@pytest.fixture()
def settings() -> IncidentBridgeSettings:
    """Return a default :class:`IncidentBridgeSettings` instance for tests."""
    return IncidentBridgeSettings()


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------


@pytest.fixture()
def event_transformer() -> EventTransformer:
    """Return a fresh :class:`EventTransformer`."""
    return EventTransformer()


@pytest.fixture()
def bridge_event_log() -> BridgeEventLog:
    """Return a fresh :class:`BridgeEventLog` with default capacity."""
    return BridgeEventLog(maxlen=100)


@pytest.fixture()
def mock_sns_publisher() -> AsyncMock:
    """Return a mock :class:`SNSPublisher` with an async ``publish_event``."""
    publisher = AsyncMock()
    publisher.publish_event.return_value = "mock-message-id"
    return publisher


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_cms_incident_event() -> dict[str, Any]:
    """Return a minimal CMS ``IncidentDetected`` event envelope."""
    return {
        "event_id": "evt-001",
        "event_type": "IncidentDetected",
        "source": "consent-api",
        "timestamp": "2026-01-15T12:00:00Z",
        "correlation_id": "corr-001",
        "payload": {
            "incident_id": "INC-1001",
            "severity": "HIGH",
            "category": "consent",
            "subcategory": "data-breach",
            "title": "Potential data breach detected",
            "description": "Unusual access patterns found",
            "affected_users": 150,
            "metrics": {"error_rate": 0.05},
            "recommended_action": "Investigate access logs",
        },
    }


@pytest.fixture()
def sample_mims_pause_command() -> dict[str, Any]:
    """Return a sample MIMS PAUSE command dictionary."""
    return {
        "command_type": "PAUSE",
        "incident_id": "INC-1001",
        "scope": "all",
        "reason": "Active incident investigation",
    }


@pytest.fixture()
def sample_mims_resume_command() -> dict[str, Any]:
    """Return a sample MIMS RESUME command dictionary."""
    return {
        "command_type": "RESUME",
        "incident_id": "INC-1001",
        "scope": "all",
        "reason": "Incident resolved",
        "resume_condition": "All clear from security team",
    }
