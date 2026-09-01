"""Event models for SNS/SQS messaging."""

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class EventEnvelope(BaseModel):
    """Standard event envelope for all messages."""

    version: str = "1.0"
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    source: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))
    payload: dict


def create_event(
    event_type: str,
    source: str,
    payload: dict,
    correlation_id: str | None = None,
) -> EventEnvelope:
    """Create a new event envelope."""
    kwargs: dict = {
        "event_type": event_type,
        "source": source,
        "payload": payload,
    }
    if correlation_id is not None:
        kwargs["correlation_id"] = correlation_id
    return EventEnvelope(**kwargs)
