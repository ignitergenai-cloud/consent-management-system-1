"""Anomaly detection engine that evaluates metrics against a set of rules."""

from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from typing import Optional

import structlog

from cms_shared.models.incident import IncidentSeverity, IncidentType

logger = structlog.get_logger(__name__)


@dataclasses.dataclass
class AnomalyResult:
    """Represents a single detected anomaly produced by a detection rule."""

    severity: IncidentSeverity
    incident_type: IncidentType
    title: str
    description: str
    metrics: dict
    recommended_action: str
    affected_customer_count: int = 0


class DetectionRule(ABC):
    """Abstract base class for anomaly detection rules.

    Each rule inspects the current metrics snapshot and optionally returns
    an ``AnomalyResult`` when an anomaly is present.
    """

    @abstractmethod
    def evaluate(self, metrics: dict) -> Optional[AnomalyResult]:
        """Evaluate the rule against the given *metrics* dict.

        Returns an ``AnomalyResult`` if an anomaly is detected, otherwise
        ``None``.
        """


class AnomalyDetector:
    """Runs a collection of :class:`DetectionRule` instances against a metrics
    snapshot and aggregates the results.

    Parameters
    ----------
    rules:
        An ordered list of detection rules to evaluate on each cycle.
    """

    def __init__(self, rules: list[DetectionRule]) -> None:
        self._rules = rules

    def detect(self, metrics: dict) -> list[AnomalyResult]:
        """Run every registered rule and return all detected anomalies.

        Parameters
        ----------
        metrics:
            A metrics snapshot as returned by
            :pymethod:`MetricCollector.get_metrics`.

        Returns
        -------
        list[AnomalyResult]
            Zero or more anomaly results.
        """
        anomalies: list[AnomalyResult] = []
        for rule in self._rules:
            try:
                result = rule.evaluate(metrics)
                if result is not None:
                    logger.warning(
                        "anomaly_detected",
                        rule=rule.__class__.__name__,
                        severity=result.severity.value,
                        incident_type=result.incident_type.value,
                    )
                    anomalies.append(result)
            except Exception:
                logger.exception(
                    "rule_evaluation_failed",
                    rule=rule.__class__.__name__,
                )
        return anomalies
