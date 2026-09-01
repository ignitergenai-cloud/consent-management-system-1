"""Customer models."""

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class Customer(BaseModel):
    """Customer model."""

    customer_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    email: str | None = None
    phone: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict = Field(default_factory=dict)
