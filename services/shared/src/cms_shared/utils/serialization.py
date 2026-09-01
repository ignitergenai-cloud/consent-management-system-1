"""DynamoDB <-> Pydantic serialization utilities."""

import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def _convert_to_dynamodb(value: Any) -> Any:
    """Convert a Python value to a DynamoDB-compatible value."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _convert_to_dynamodb(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_convert_to_dynamodb(v) for v in value]
    if isinstance(value, (int, str, bool, Decimal)):
        return value
    # Enum or other types - convert to string
    return str(value)


def _convert_from_dynamodb(value: Any) -> Any:
    """Convert a DynamoDB value back to a Python-native value."""
    if isinstance(value, Decimal):
        if value == int(value):
            return int(value)
        return float(value)
    if isinstance(value, dict):
        return {k: _convert_from_dynamodb(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_convert_from_dynamodb(v) for v in value]
    return value


def to_dynamodb_item(model: BaseModel) -> dict[str, Any]:
    """Convert a Pydantic model to a DynamoDB-compatible dict.

    Handles:
    - datetime -> ISO 8601 string
    - float -> Decimal
    - None values removed
    - Enum -> string value
    """
    data = model.model_dump(mode="python")
    result = {}
    for key, value in data.items():
        converted = _convert_to_dynamodb(value)
        if converted is not None:
            result[key] = converted
    return result


def from_dynamodb_item(item: dict[str, Any], model_class: Type[T]) -> T:
    """Convert a DynamoDB item back to a Pydantic model.

    Handles:
    - Decimal -> int/float
    - ISO 8601 string -> datetime (via Pydantic validation)
    - String -> Enum (via Pydantic validation)
    """
    converted = _convert_from_dynamodb(item)
    return model_class.model_validate(converted)


def model_to_json(model: BaseModel) -> str:
    """Serialize a Pydantic model to a JSON string for SNS/SQS messages."""
    return model.model_dump_json()


def model_from_json(json_str: str, model_class: Type[T]) -> T:
    """Deserialize a JSON string to a Pydantic model."""
    return model_class.model_validate_json(json_str)
