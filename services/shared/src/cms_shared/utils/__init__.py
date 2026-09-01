"""Utility functions for the Consent Management System."""

from cms_shared.utils.pagination import decode_next_token, encode_next_token
from cms_shared.utils.serialization import (
    from_dynamodb_item,
    model_from_json,
    model_to_json,
    to_dynamodb_item,
)
from cms_shared.utils.tokens import generate_consent_id, generate_response_token

__all__ = [
    "decode_next_token",
    "encode_next_token",
    "from_dynamodb_item",
    "generate_consent_id",
    "generate_response_token",
    "model_from_json",
    "model_to_json",
    "to_dynamodb_item",
]
