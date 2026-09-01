"""Unit tests for the anomaly detection rules."""

from __future__ import annotations

import pytest

from cms_shared.models.incident import IncidentSeverity, IncidentType

from incident_detector.rules.error_spike_rule import ErrorSpikeRule
from incident_detector.rules.failure_rate_rule import FailureRateRule
from incident_detector.rules.throughput_rule import ThroughputDropRule


# =====================================================================
# FailureRateRule
# =====================================================================


class TestFailureRateRule:
    """Tests for :class:`FailureRateRule`."""

    def test_below_threshold_returns_none(self, healthy_metrics: dict) -> None:
        """No anomaly when the failure rate is below the threshold."""
        rule = FailureRateRule(threshold=0.3)
        assert rule.evaluate(healthy_metrics) is None

    def test_above_threshold_returns_anomaly(
        self, medium_failure_rate_metrics: dict,
    ) -> None:
        """An anomaly is returned when the failure rate exceeds the threshold."""
        rule = FailureRateRule(threshold=0.3)
        result = rule.evaluate(medium_failure_rate_metrics)
        assert result is not None
        assert result.incident_type == IncidentType.HIGH_ERROR_RATE
        assert result.severity == IncidentSeverity.MEDIUM

    def test_critical_severity_above_70(
        self, high_failure_rate_metrics: dict,
    ) -> None:
        """Severity should be CRITICAL for rates above 0.7."""
        rule = FailureRateRule(threshold=0.3)
        result = rule.evaluate(high_failure_rate_metrics)
        assert result is not None
        assert result.severity == IncidentSeverity.CRITICAL

    def test_high_severity_above_50(self) -> None:
        """Severity should be HIGH for rates between 0.5 and 0.7."""
        rule = FailureRateRule(threshold=0.3)
        metrics = {"notification_failure_rate": 0.6}
        result = rule.evaluate(metrics)
        assert result is not None
        assert result.severity == IncidentSeverity.HIGH

    def test_exact_threshold_triggers(self) -> None:
        """The rule fires when the rate exactly equals the threshold."""
        rule = FailureRateRule(threshold=0.3)
        # 0.3 is NOT less than 0.3, so the rule should trigger.
        metrics = {"notification_failure_rate": 0.3}
        result = rule.evaluate(metrics)
        assert result is not None

    def test_zero_failure_rate(self) -> None:
        """No anomaly when there are zero failures."""
        rule = FailureRateRule(threshold=0.3)
        metrics = {"notification_failure_rate": 0.0}
        assert rule.evaluate(metrics) is None

    def test_custom_threshold(self) -> None:
        """A custom threshold is respected."""
        rule = FailureRateRule(threshold=0.1)
        metrics = {"notification_failure_rate": 0.15}
        result = rule.evaluate(metrics)
        assert result is not None


# =====================================================================
# ThroughputDropRule
# =====================================================================


class TestThroughputDropRule:
    """Tests for :class:`ThroughputDropRule`."""

    def _prime_baseline(
        self, rule: ThroughputDropRule, value: float, count: int = 5,
    ) -> None:
        """Feed *count* metric snapshots at a steady *value* to build a baseline."""
        for _ in range(count):
            rule.evaluate({"consents_per_minute": value})

    def test_insufficient_history_returns_none(self) -> None:
        """No anomaly when the baseline has fewer than 3 samples."""
        rule = ThroughputDropRule(threshold=0.5)
        metrics = {"consents_per_minute": 50.0}
        assert rule.evaluate(metrics) is None
        assert rule.evaluate(metrics) is None

    def test_stable_throughput_returns_none(self) -> None:
        """No anomaly when throughput is stable."""
        rule = ThroughputDropRule(threshold=0.5)
        self._prime_baseline(rule, 50.0)
        result = rule.evaluate({"consents_per_minute": 48.0})
        assert result is None

    def test_significant_drop_returns_anomaly(self) -> None:
        """An anomaly is returned when throughput drops significantly."""
        rule = ThroughputDropRule(threshold=0.5)
        self._prime_baseline(rule, 100.0, count=10)
        result = rule.evaluate({"consents_per_minute": 20.0})
        assert result is not None
        assert result.incident_type == IncidentType.THROUGHPUT_DROP
        assert result.severity in (IncidentSeverity.MEDIUM, IncidentSeverity.HIGH)

    def test_high_severity_for_extreme_drop(self) -> None:
        """Severity should be HIGH for drops exceeding 80%."""
        rule = ThroughputDropRule(threshold=0.5)
        self._prime_baseline(rule, 100.0, count=10)
        result = rule.evaluate({"consents_per_minute": 5.0})
        assert result is not None
        assert result.severity == IncidentSeverity.HIGH

    def test_zero_baseline_returns_none(self) -> None:
        """No anomaly when the baseline average is zero."""
        rule = ThroughputDropRule(threshold=0.5)
        self._prime_baseline(rule, 0.0, count=5)
        result = rule.evaluate({"consents_per_minute": 0.0})
        assert result is None


# =====================================================================
# ErrorSpikeRule
# =====================================================================


class TestErrorSpikeRule:
    """Tests for :class:`ErrorSpikeRule`."""

    def _prime_history(
        self, rule: ErrorSpikeRule, value: int, count: int = 5,
    ) -> None:
        """Feed *count* metric snapshots at a steady *value* to build history."""
        for _ in range(count):
            rule.evaluate({"errors_count": value})

    def test_insufficient_history_returns_none(self) -> None:
        """No anomaly when fewer than 3 history samples exist."""
        rule = ErrorSpikeRule(multiplier=3.0)
        assert rule.evaluate({"errors_count": 100}) is None
        assert rule.evaluate({"errors_count": 100}) is None

    def test_stable_errors_returns_none(self) -> None:
        """No anomaly when error count is stable."""
        rule = ErrorSpikeRule(multiplier=3.0)
        self._prime_history(rule, 10)
        result = rule.evaluate({"errors_count": 12})
        assert result is None

    def test_spike_returns_anomaly(self) -> None:
        """An anomaly is returned when error count spikes."""
        rule = ErrorSpikeRule(multiplier=3.0)
        self._prime_history(rule, 5, count=10)
        result = rule.evaluate({"errors_count": 50})
        assert result is not None
        assert result.incident_type == IncidentType.HIGH_ERROR_RATE
        assert result.severity == IncidentSeverity.HIGH

    def test_just_below_multiplier_returns_none(self) -> None:
        """No anomaly when errors are just below the multiplier threshold."""
        rule = ErrorSpikeRule(multiplier=3.0)
        self._prime_history(rule, 10, count=10)
        # threshold = 10 * 3.0 = 30; 29 is below
        result = rule.evaluate({"errors_count": 29})
        assert result is None

    def test_zero_history_needs_minimum(self) -> None:
        """When history is all zeros the minimum threshold of 1.0 applies."""
        rule = ErrorSpikeRule(multiplier=3.0)
        self._prime_history(rule, 0, count=5)
        # threshold = max(0 * 3.0, 1.0) = 1.0; 0 < 1.0 so no anomaly
        result = rule.evaluate({"errors_count": 0})
        assert result is None

    def test_custom_multiplier(self) -> None:
        """A custom multiplier is respected."""
        rule = ErrorSpikeRule(multiplier=2.0)
        self._prime_history(rule, 10, count=10)
        # threshold = 10 * 2.0 = 20; 25 >= 20 => anomaly
        result = rule.evaluate({"errors_count": 25})
        assert result is not None
