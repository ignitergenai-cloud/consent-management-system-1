"""Shared pytest fixtures for the Incident Detector test suite."""

from __future__ import annotations

import pytest

from incident_detector.config import IncidentDetectorSettings
from incident_detector.services.metric_collector import MetricCollector


@pytest.fixture
def settings() -> IncidentDetectorSettings:
    """Return an :class:`IncidentDetectorSettings` with default values."""
    return IncidentDetectorSettings()


@pytest.fixture
def metric_collector(settings: IncidentDetectorSettings) -> MetricCollector:
    """Return a fresh :class:`MetricCollector` bound to the fixture settings."""
    return MetricCollector(window_minutes=settings.detection_window_minutes)


# ------------------------------------------------------------------
# Sample metrics dictionaries used across rule tests
# ------------------------------------------------------------------


@pytest.fixture
def healthy_metrics() -> dict:
    """Metrics snapshot representing a completely healthy system."""
    return {
        "notification_failure_rate": 0.01,
        "consents_per_minute": 50.0,
        "errors_count": 2,
        "total_events": 750,
        "window_minutes": 15,
        "notification_total": 200,
        "notification_failures": 2,
        "consent_events": 750,
    }


@pytest.fixture
def high_failure_rate_metrics() -> dict:
    """Metrics snapshot with a critically high notification failure rate."""
    return {
        "notification_failure_rate": 0.75,
        "consents_per_minute": 45.0,
        "errors_count": 5,
        "total_events": 700,
        "window_minutes": 15,
        "notification_total": 200,
        "notification_failures": 150,
        "consent_events": 675,
    }


@pytest.fixture
def medium_failure_rate_metrics() -> dict:
    """Metrics snapshot with a moderately elevated failure rate."""
    return {
        "notification_failure_rate": 0.35,
        "consents_per_minute": 48.0,
        "errors_count": 3,
        "total_events": 720,
        "window_minutes": 15,
        "notification_total": 200,
        "notification_failures": 70,
        "consent_events": 720,
    }


@pytest.fixture
def high_error_count_metrics() -> dict:
    """Metrics snapshot with a spike in errors."""
    return {
        "notification_failure_rate": 0.05,
        "consents_per_minute": 50.0,
        "errors_count": 100,
        "total_events": 800,
        "window_minutes": 15,
        "notification_total": 200,
        "notification_failures": 10,
        "consent_events": 750,
    }


@pytest.fixture
def low_throughput_metrics() -> dict:
    """Metrics snapshot with drastically reduced consent throughput."""
    return {
        "notification_failure_rate": 0.02,
        "consents_per_minute": 5.0,
        "errors_count": 1,
        "total_events": 80,
        "window_minutes": 15,
        "notification_total": 30,
        "notification_failures": 1,
        "consent_events": 75,
    }
