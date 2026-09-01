"""Test fixtures for incident-detector."""

import pytest
from incident_detector.config import IncidentDetectorSettings


@pytest.fixture
def settings():
    """Test settings."""
    return IncidentDetectorSettings(
        aws_endpoint_url="http://localhost:4566",
        aws_region="us-east-1",
        failure_rate_threshold=0.3,
        throughput_drop_threshold=0.5,
        error_spike_multiplier=3.0,
        detection_interval_seconds=60,
        detection_window_minutes=15,
    )


@pytest.fixture
def healthy_metrics():
    """Metrics within normal thresholds."""
    return {
        "total_notifications_sent": 100,
        "total_notifications_failed": 5,
        "notification_failure_rate": 0.05,
        "consents_per_minute": 10.0,
        "errors_count": 2,
    }


@pytest.fixture
def high_failure_metrics():
    """Metrics with high failure rate."""
    return {
        "total_notifications_sent": 50,
        "total_notifications_failed": 50,
        "notification_failure_rate": 0.5,
        "consents_per_minute": 10.0,
        "errors_count": 50,
    }


@pytest.fixture
def critical_failure_metrics():
    """Metrics with critical failure rate."""
    return {
        "total_notifications_sent": 20,
        "total_notifications_failed": 80,
        "notification_failure_rate": 0.8,
        "consents_per_minute": 2.0,
        "errors_count": 80,
    }
