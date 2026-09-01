"""Collects consent-related events and computes real-time metrics."""

from __future__ import annotations

import threading
import time
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class MetricCollector:
    """In-memory, time-windowed metric collector.

    Events are appended via :meth:`record_event` and stale entries are pruned
    automatically.  :meth:`get_metrics` returns a snapshot suitable for the
    anomaly detection engine.

    Parameters
    ----------
    window_minutes:
        How many minutes of history to keep.
    """

    def __init__(self, window_minutes: int = 15) -> None:
        self._window_minutes = window_minutes
        self._window_events: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_event(self, event_type: str, timestamp: float | None = None) -> None:
        """Record an incoming event.

        Parameters
        ----------
        event_type:
            A short label such as ``"consent_granted"`` or ``"error"``.
        timestamp:
            Unix epoch seconds.  Defaults to the current time.
        """
        ts = timestamp if timestamp is not None else time.time()
        with self._lock:
            self._window_events.append({"type": event_type, "timestamp": ts})
        logger.debug("event_recorded", event_type=event_type)

    def get_metrics(self) -> dict[str, Any]:
        """Return a metrics snapshot for the current detection window.

        The dict contains at least:

        * ``notification_failure_rate`` -- ratio of failures to total
          notification events (0.0 when no events).
        * ``consents_per_minute`` -- average consent events per minute
          inside the window.
        * ``errors_count`` -- absolute number of error events in the window.
        * ``total_events`` -- total events kept in the window.
        * ``window_minutes`` -- the configured window size.
        """
        with self._lock:
            self._prune_old_events()
            return self._recalculate()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _prune_old_events(self) -> None:
        """Remove events older than the configured window (caller holds lock)."""
        cutoff = time.time() - self._window_minutes * 60
        self._window_events = [
            e for e in self._window_events if e["timestamp"] >= cutoff
        ]

    def _recalculate(self) -> dict[str, Any]:
        """Derive metrics from the current window (caller holds lock)."""
        events = self._window_events

        total = len(events)
        notification_total = sum(
            1 for e in events if e["type"].startswith("notification_")
        )
        notification_failures = sum(
            1 for e in events if e["type"] == "notification_failed"
        )
        consent_events = sum(
            1 for e in events if e["type"].startswith("consent_")
        )
        errors = sum(1 for e in events if e["type"] == "error")

        failure_rate = (
            notification_failures / notification_total
            if notification_total > 0
            else 0.0
        )
        consents_per_minute = (
            consent_events / self._window_minutes
            if self._window_minutes > 0
            else 0.0
        )

        return {
            "notification_failure_rate": failure_rate,
            "consents_per_minute": consents_per_minute,
            "errors_count": errors,
            "total_events": total,
            "window_minutes": self._window_minutes,
            "notification_total": notification_total,
            "notification_failures": notification_failures,
            "consent_events": consent_events,
        }
