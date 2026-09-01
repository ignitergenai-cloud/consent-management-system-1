"""In-memory event log for tracking bridge activity."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class BridgeEvent:
    """A single recorded bridge event."""

    direction: str
    event_type: str
    incident_id: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class BridgeEventLog:
    """Bounded in-memory log of events flowing through the incident bridge.

    Events are stored in a :class:`collections.deque` with a fixed maximum
    length so that the log never grows unbounded.

    Args:
        max_size: Maximum number of events to retain.  Defaults to ``100``.
    """

    def __init__(self, max_size: int = 100) -> None:
        self._events: deque[BridgeEvent] = deque(maxlen=max_size)
        self._total_count: int = 0

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        direction: str,
        event_type: str,
        incident_id: str,
        status: str = "processed",
        details: dict[str, Any] | None = None,
    ) -> BridgeEvent:
        """Record a new bridge event.

        Args:
            direction: ``"outbound"`` (CMS -> MIMS) or ``"inbound"``
                (MIMS -> CMS).
            event_type: The event or command type string.
            incident_id: Identifier of the related incident.
            status: Processing status (e.g. ``"processed"``,
                ``"published"``, ``"error"``).
            details: Optional extra context to attach to the event.

        Returns:
            The newly created :class:`BridgeEvent`.
        """
        event = BridgeEvent(
            direction=direction,
            event_type=event_type,
            incident_id=incident_id,
            status=status,
            details=details or {},
        )
        self._events.append(event)
        self._total_count += 1
        return event

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def get_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent events as plain dictionaries.

        Args:
            limit: Maximum number of events to return.

        Returns:
            A list of event dictionaries, newest first.
        """
        recent = list(self._events)[-limit:]
        recent.reverse()
        return [asdict(e) for e in recent]

    @property
    def total_count(self) -> int:
        """Total number of events recorded since the service started."""
        return self._total_count

    # ------------------------------------------------------------------
    # Container protocol
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Return the number of events currently stored in the log."""
        return len(self._events)

    def __repr__(self) -> str:
        return (
            f"BridgeEventLog(stored={len(self._events)}, "
            f"total={self._total_count})"
        )
