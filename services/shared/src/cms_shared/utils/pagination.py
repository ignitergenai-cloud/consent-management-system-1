"""DynamoDB pagination helpers."""

import base64
import json


def encode_next_token(last_evaluated_key: dict | None) -> str | None:
    """Encode a DynamoDB LastEvaluatedKey as a base64 pagination token.

    Args:
        last_evaluated_key: The LastEvaluatedKey from a DynamoDB query/scan.

    Returns:
        Base64-encoded token string, or None if input is None.
    """
    if last_evaluated_key is None:
        return None
    json_bytes = json.dumps(last_evaluated_key).encode("utf-8")
    return base64.urlsafe_b64encode(json_bytes).decode("utf-8")


def decode_next_token(token: str | None) -> dict | None:
    """Decode a base64 pagination token back to a DynamoDB ExclusiveStartKey.

    Args:
        token: The base64-encoded pagination token.

    Returns:
        The decoded dictionary, or None if input is None.
    """
    if token is None:
        return None
    json_bytes = base64.urlsafe_b64decode(token.encode("utf-8"))
    return json.loads(json_bytes)
