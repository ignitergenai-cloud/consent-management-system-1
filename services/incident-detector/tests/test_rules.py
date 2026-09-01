"""Tests for incident detection rules."""

import pytest
from incident_detector.rules.failure_rate_rule import FailureRateRule
from incident_detector.rules.throughput_rule import ThroughputDropRule
from incident_detector.rules.error_spike_rule import ErrorSpikeRule


class TestFailureRateRule:
    """Tests for FailureRateRule."""

    @pytest.mark.asyncio
    async def test_no_anomaly_below_threshold(self, healthy_metrics):
        rule = FailureRateRule(threshold=0.3)
        result = await rule.evaluate(healthy_metrics)
        assert result is None

    @pytest.mark.asyncio
    async def test_medium_severity_above_threshold(self):
        rule = FailureRateRule(threshold=0.3)
        metrics = {"notification_failure_rate": 0.35, "total_notifications_failed": 35}
        result = await rule.evaluate(metrics)
        assert result is not None
        assert result.severity == "MEDIUM"
        assert result.incident_type == "MASS_CONSENT_FAILURE"

    @pytest.mark.asyncio
    async def test_high_severity(self, high_failure_metrics):
        rule = FailureRateRule(threshold=0.3)
        result = await rule.evaluate(high_failure_metrics)
        assert result is not None
        assert result.severity == "HIGH"

    @pytest.mark.asyncio
    async def test_critical_severity(self, critical_failure_metrics):
        rule = FailureRateRule(threshold=0.3)
        result = await rule.evaluate(critical_failure_metrics)
        assert result is not None
        assert result.severity == "CRITICAL"

    @pytest.mark.asyncio
    async def test_zero_failure_rate(self):
        rule = FailureRateRule(threshold=0.3)
        metrics = {"notification_failure_rate": 0.0, "total_notifications_failed": 0}
        result = await rule.evaluate(metrics)
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_metric_key(self):
        rule = FailureRateRule(threshold=0.3)
        result = await rule.evaluate({})
        assert result is None


class TestThroughputDropRule:
    """Tests for ThroughputDropRule."""

    @pytest.mark.asyncio
    async def test_no_anomaly_above_threshold(self, healthy_metrics):
        rule = ThroughputDropRule(threshold=0.5)
        # Prime baseline
        for _ in range(5):
            await rule.evaluate({"consents_per_minute": 10.0})
        result = await rule.evaluate(healthy_metrics)
        assert result is None

    @pytest.mark.asyncio
    async def test_anomaly_on_throughput_drop(self):
        rule = ThroughputDropRule(threshold=0.5)
        # Build baseline
        for _ in range(10):
            await rule.evaluate({"consents_per_minute": 10.0})
        # Drop throughput
        result = await rule.evaluate({"consents_per_minute": 2.0})
        assert result is not None
        assert result.incident_type == "THROUGHPUT_DROP"

    @pytest.mark.asyncio
    async def test_no_anomaly_without_baseline(self):
        rule = ThroughputDropRule(threshold=0.5)
        result = await rule.evaluate({"consents_per_minute": 1.0})
        assert result is None


class TestErrorSpikeRule:
    """Tests for ErrorSpikeRule."""

    @pytest.mark.asyncio
    async def test_no_anomaly_normal_errors(self):
        rule = ErrorSpikeRule(multiplier=3.0)
        for _ in range(10):
            await rule.evaluate({"errors_count": 5})
        result = await rule.evaluate({"errors_count": 5})
        assert result is None

    @pytest.mark.asyncio
    async def test_anomaly_on_error_spike(self):
        rule = ErrorSpikeRule(multiplier=3.0)
        for _ in range(10):
            await rule.evaluate({"errors_count": 5})
        result = await rule.evaluate({"errors_count": 50})
        assert result is not None
        assert result.incident_type == "HIGH_ERROR_RATE"
        assert result.severity == "HIGH"

    @pytest.mark.asyncio
    async def test_no_anomaly_without_history(self):
        rule = ErrorSpikeRule(multiplier=3.0)
        result = await rule.evaluate({"errors_count": 100})
        assert result is None
