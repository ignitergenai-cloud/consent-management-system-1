"""Rule that fires when the notification failure rate exceeds a threshold."""

from __future__ import annotations

from typing import Optional

import structlog

from cms_shared.models.incident import IncidentSeverity, IncidentType

from incident_detector.services.anomaly_detector import AnomalyResult, DetectionRule

logger = structlog.get_logger(__name__)


class FailureRateRule(DetectionRule):
    """Detects elevated notification failure rates.

    Severity is graduated:

    * **CRITICAL** when the failure rate exceeds 0.7
    * **HIGH** when it exceeds 0.5
    * **MEDIUM** when it exceeds the configured *threshold* (default 0.3)

    Parameters
    ----------
    threshold:
        The minimum failure rate that triggers an anomaly.
    """

    def __init__(self, threshold: float = 0.3) -> None:
        self._threshold = threshold

    def evaluate(self, metrics: dict) -> Optional[AnomalyResult]:
        """Return an anomaly if the notification failure rate is above threshold."""
        failure_rate: float = metrics.get("notification_failure_rate", 0.0)

        if failure_rate < self._threshold:
            return None

        severity = self._classify_severity(failure_rate)

        logger.info(
            "failure_rate_rule_triggered",
            failure_rate=failure_rate,
            threshold=self._threshold,
            severity=severity.value,
        )

        return AnomalyResult(
            severity=severity,
            incident_type=IncidentType.HIGH_ERROR_RATE,
            title="Elevated notification failure rate",
            description=(
                f"Notification failure rate is {failure_rate:.1%}, "
                f"exceeding the {self._threshold:.1%} threshold."
            ),
            metrics={
                "notification_failure_rate": failure_rate,
                "threshold": self._threshold,
            },
            recommended_action=(
                "Investigate the notification delivery pipeline. "
                "Check downstream service health and retry queues."
            ),
        )

    @staticmethod
    def _classify_severity(rate: float) -> IncidentSeverity:
        """Map the failure rate to an incident severity level."""
        if rate > 0.7:
            return IncidentSeverity.CRITICAL
        if rate > 0.5:
            return IncidentSeverity.HIGH
        return IncidentSeverity.MEDIUM
