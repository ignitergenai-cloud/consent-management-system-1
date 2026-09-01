"""Token and ID generation utilities."""

import secrets
from uuid import uuid4


def generate_response_token() -> str:
    """Generate a secure response token for consent URLs.

    Returns:
        A URL-safe token string (32 bytes).
    """
    return secrets.token_urlsafe(32)


def generate_consent_id() -> str:
    """Generate a unique consent ID.

    Returns:
        A UUID4 string.
    """
    return str(uuid4())
