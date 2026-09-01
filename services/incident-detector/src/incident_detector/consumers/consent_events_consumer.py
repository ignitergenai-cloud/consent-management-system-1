"""SQS consumer that ingests consent-related events for anomaly detection."""

from __future__ import annotations

import time

import structlog

from cms_shared.aws.sqs import SQSConsumer

from incident_detector.config import IncidentDetectorSettings
from incident_detector.services.metric_collector import MetricCollector

logger = structlog.get_logger(__name__)


class ConsentEventsConsumer(SQSConsumer):
    """Consumes messages from the incident-detection SQS queue and records
    them in a :class:`MetricCollector` for downstream anomaly detection.

    Parameters
    ----------
    settings:
        Service settings (provides the queue URL and AWS config).
    metric_collector:
        The shared :class:`MetricCollector` where events are recorded.
    """

    def __init__(
        self,
        settings: IncidentDetectorSettings,
        metric_collector: MetricCollector,
    ) -> None:
        super().__init__(
            queue_url=settings.incident_detection_queue_url,
            settings=settings,
        )
        self._metric_collector = metric_collector

    async def handle_message(self, event: dict) -> None:
        """Process a single SQS message.

        The ``event`` dict is the parsed JSON body (already unwrapped from
        the SNS envelope by the base class).  We extract the ``event_type``
        and record it in the metric collector.
        """
        event_type: str = event.get("event_type", "unknown")
        timestamp: float = time.time()

        # Attempt to parse an ISO timestamp from the event payload.
        raw_ts = event.get("timestamp")
        if raw_ts is not None:
            try:
                from datetime import datetime, timezone

                dt = datetime.fromisoformat(str(raw_ts))
                timestamp = dt.timestamp()
            except (ValueError, TypeError):
                pass

        # Map well-known event types to metric labels understood by the
        # detection rules.
        metric_type = self._map_event_type(event_type)
        self._metric_collector.record_event(metric_type, timestamp)

        logger.debug(
            "consent_event_consumed",
            event_type=event_type,
            metric_type=metric_type,
        )

    @staticmethod
    def _map_event_type(event_type: str) -> str:
        """Translate an incoming event type string to an internal metric label."""
        mapping: dict[str, str] = {
            "ConsentCreated": "consent_created",
            "ConsentGranted": "consent_granted",
            "ConsentDenied": "consent_denied",
            "ConsentExpired": "consent_expired",
            "ConsentRevoked": "consent_revoked",
            "NotificationSent": "notification_sent",
            "NotificationFailed": "notification_failed",
        }
        return mapping.get(event_type, event_type.lower())
