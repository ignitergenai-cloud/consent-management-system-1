"""Configuration for the Incident Detector service."""

from cms_shared.config import Settings as BaseSettings


class IncidentDetectorSettings(BaseSettings):
    """Settings specific to the Incident Detector service.

    Extends the shared CMS settings with incident detection thresholds
    and service-specific configuration.
    """

    service_name: str = "incident-detector"
    service_port: int = 8003

    # Detection thresholds
    failure_rate_threshold: float = 0.3
    throughput_drop_threshold: float = 0.5
    error_spike_multiplier: float = 3.0

    # Detection scheduling
    detection_interval_seconds: int = 60
    detection_window_minutes: int = 15

    # Queue for incoming consent events to monitor
    incident_detection_queue_url: str = (
        "http://localhost:4566/000000000000/cms-incident-detection-queue"
    )

    # Table used exclusively by this service for storing incidents
    incidents_table_name: str = "cms-incidents"
