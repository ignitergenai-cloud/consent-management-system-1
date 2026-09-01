"""Rule that fires when the error count spikes above a rolling average."""

from __future__ import annotations

from collections import deque
from typing import Optional

import structlog

from cms_shared.models.incident import IncidentSeverity, IncidentType

from incident_detector.services.anomaly_detector import AnomalyResult, DetectionRule

logger = structlog.get_logger(__name__)

_MAX_HISTORY_SAMPLES = 60


class ErrorSpikeRule(DetectionRule):
    """Detects sudden spikes in the error count.

    A rolling history of ``errors_count`` values is maintained.  An anomaly
    is raised when the current count exceeds
    ``average_errors * multiplier``.

    Parameters
    ----------
    multiplier:
        How many times above the historical average constitutes a spike.
    """

    def __init__(self, multiplier: float = 3.0) -> None:
        self._multiplier = multiplier
        self._error_history: deque[int] = deque(maxlen=_MAX_HISTORY_SAMPLES)

    def evaluate(self, metrics: dict) -> Optional[AnomalyResult]:
        """Return an anomaly if the current error count is a spike."""
        current_errors: int = metrics.get("errors_count", 0)

        # Not enough data yet -- record and skip.
        if len(self._error_history) < 3:
            self._error_history.append(current_errors)
            return None

        avg_errors = sum(self._error_history) / len(self._error_history)

        # Record after comparison so current value does not inflate the
        # baseline it is evaluated against.
        self._error_history.append(current_errors)

        # If the average is practically zero, require at least a few errors
        # to avoid false positives on the very first spike.
        threshold = max(avg_errors * self._multiplier, 1.0)

        if current_errors < threshold:
            return None

        logger.info(
            "error_spike_rule_triggered",
            current_errors=current_errors,
            avg_errors=avg_errors,
            multiplier=self._multiplier,
            threshold=threshold,
        )

        return AnomalyResult(
            severity=IncidentSeverity.HIGH,
            incident_type=IncidentType.HIGH_ERROR_RATE,
            title="Error spike detected",
            description=(
                f"Error count spiked to {current_errors} (historical average "
                f"{avg_errors:.1f}, threshold {threshold:.1f})."
            ),
            metrics={
                "errors_count": current_errors,
                "average_errors": avg_errors,
                "multiplier": self._multiplier,
                "threshold": threshold,
            },
            recommended_action=(
                "Examine recent error logs for root cause. "
                "Check for upstream service failures or data quality issues."
            ),
        )
