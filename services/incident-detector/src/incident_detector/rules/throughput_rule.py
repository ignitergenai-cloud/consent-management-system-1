"""Rule that fires when consent throughput drops significantly below baseline."""

from __future__ import annotations

from collections import deque
from typing import Optional

import structlog

from cms_shared.models.incident import IncidentSeverity, IncidentType

from incident_detector.services.anomaly_detector import AnomalyResult, DetectionRule

logger = structlog.get_logger(__name__)

_MAX_BASELINE_SAMPLES = 60


class ThroughputDropRule(DetectionRule):
    """Detects sudden drops in consent throughput.

    A rolling baseline of the last ``_MAX_BASELINE_SAMPLES`` observations of
    ``consents_per_minute`` is maintained.  An anomaly is raised when the
    current value drops below ``(1 - threshold) * baseline_average``.

    Severity is graduated:

    * **HIGH** when the drop exceeds 80 %
    * **MEDIUM** otherwise

    Parameters
    ----------
    threshold:
        Fractional drop that triggers an anomaly (e.g. 0.5 = 50 % drop).
    """

    def __init__(self, threshold: float = 0.5) -> None:
        self._threshold = threshold
        self._baseline_samples: deque[float] = deque(maxlen=_MAX_BASELINE_SAMPLES)

    def evaluate(self, metrics: dict) -> Optional[AnomalyResult]:
        """Return an anomaly if throughput has dropped below the baseline."""
        current_cpm: float = metrics.get("consents_per_minute", 0.0)

        # Not enough history to establish a meaningful baseline.
        if len(self._baseline_samples) < 3:
            self._baseline_samples.append(current_cpm)
            return None

        baseline_avg = sum(self._baseline_samples) / len(self._baseline_samples)

        # Record after computing the comparison so the current value does not
        # bias the baseline it is being compared against.
        self._baseline_samples.append(current_cpm)

        # Avoid division-by-zero when baseline is effectively zero.
        if baseline_avg <= 0.0:
            return None

        drop_ratio = 1.0 - (current_cpm / baseline_avg)

        if drop_ratio < self._threshold:
            return None

        severity = (
            IncidentSeverity.HIGH if drop_ratio > 0.8 else IncidentSeverity.MEDIUM
        )

        logger.info(
            "throughput_drop_rule_triggered",
            current_cpm=current_cpm,
            baseline_avg=baseline_avg,
            drop_ratio=drop_ratio,
            severity=severity.value,
        )

        return AnomalyResult(
            severity=severity,
            incident_type=IncidentType.THROUGHPUT_DROP,
            title="Consent throughput drop detected",
            description=(
                f"Consent throughput dropped to {current_cpm:.1f}/min from a "
                f"baseline of {baseline_avg:.1f}/min ({drop_ratio:.0%} decrease)."
            ),
            metrics={
                "consents_per_minute": current_cpm,
                "baseline_average": baseline_avg,
                "drop_ratio": drop_ratio,
                "threshold": self._threshold,
            },
            recommended_action=(
                "Check upstream consent API health and database connectivity. "
                "Review recent deployments for regressions."
            ),
        )
