"""DynamoDB repository for consent records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from boto3.dynamodb.conditions import Attr, Key

from cms_shared.aws.dynamodb import DynamoDBManager
from cms_shared.middleware.error_handler import ItemNotFoundError
from cms_shared.models.consent import (
    ConsentRecord,
    ListConsentsQuery,
    PaginatedConsentsResponse,
)
from cms_shared.utils.pagination import decode_next_token, encode_next_token
from cms_shared.utils.serialization import from_dynamodb_item, to_dynamodb_item

logger = structlog.get_logger()


class ConsentRepository:
    """Data-access layer for consent records in DynamoDB."""

    def __init__(self, dynamo_manager: DynamoDBManager) -> None:
        self._dynamo = dynamo_manager

    @property
    def _table(self):
        return self._dynamo.table

    # ------------------------------------------------------------------
    # Core CRUD
    # ------------------------------------------------------------------

    async def create_consent(self, consent: ConsentRecord) -> ConsentRecord:
        """Persist a new consent record with all required keys."""
        item = to_dynamodb_item(consent)
        item["PK"] = f"CONSENT#{consent.consent_id}"
        item["SK"] = "METADATA"
        # GSI keys
        item["GSI1PK"] = f"CUSTOMER#{consent.customer_id}"
        item["GSI1SK"] = consent.created_at.isoformat()
        item["GSI2PK"] = f"STATUS#{consent.status.value}"
        item["GSI2SK"] = consent.created_at.isoformat()
        item["GSI3PK"] = f"CHANNEL#{consent.channel.value}"
        item["GSI3SK"] = consent.created_at.isoformat()

        logger.info(
            "creating_consent",
            consent_id=consent.consent_id,
            customer_id=consent.customer_id,
        )
        await self._table.put_item(Item=item)
        return consent

    async def get_consent(self, consent_id: str) -> ConsentRecord:
        """Retrieve a single consent record by ID."""
        response = await self._table.get_item(
            Key={"PK": f"CONSENT#{consent_id}", "SK": "METADATA"},
        )
        item = response.get("Item")
        if not item:
            raise ItemNotFoundError(f"Consent {consent_id} not found")
        return from_dynamodb_item(item, ConsentRecord)

    async def get_consent_by_token(self, response_token: str) -> ConsentRecord:
        """Find a consent record by its response token.

        NOTE: This uses a table scan with a filter expression. In production
        this should be backed by a GSI on ``response_token`` for efficient
        look-ups.
        """
        response = await self._table.scan(
            FilterExpression=Attr("response_token").eq(response_token)
            & Attr("SK").eq("METADATA"),
        )
        items = response.get("Items", [])
        if not items:
            raise ItemNotFoundError("Consent not found for the provided response token")
        return from_dynamodb_item(items[0], ConsentRecord)

    async def update_consent(
        self, consent_id: str, updates: dict[str, Any]
    ) -> ConsentRecord:
        """Apply partial updates to a consent record."""
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Build UpdateExpression dynamically
        expr_parts: list[str] = []
        attr_names: dict[str, str] = {}
        attr_values: dict[str, Any] = {}

        for idx, (key, value) in enumerate(updates.items()):
            placeholder_name = f"#attr{idx}"
            placeholder_value = f":val{idx}"
            expr_parts.append(f"{placeholder_name} = {placeholder_value}")
            attr_names[placeholder_name] = key
            attr_values[placeholder_value] = value

        # Also update GSI2 key when status changes
        if "status" in updates:
            expr_parts.append("#gsi2pk = :gsi2pk")
            attr_names["#gsi2pk"] = "GSI2PK"
            attr_values[":gsi2pk"] = f"STATUS#{updates['status']}"

        update_expression = "SET " + ", ".join(expr_parts)

        logger.info("updating_consent", consent_id=consent_id, fields=list(updates.keys()))

        response = await self._table.update_item(
            Key={"PK": f"CONSENT#{consent_id}", "SK": "METADATA"},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=attr_names,
            ExpressionAttributeValues=attr_values,
            ReturnValues="ALL_NEW",
        )
        return from_dynamodb_item(response["Attributes"], ConsentRecord)

    async def list_consents(
        self, query: ListConsentsQuery
    ) -> PaginatedConsentsResponse:
        """List consents with optional filters and pagination.

        Uses GSI2 (by status) or GSI3 (by channel) when the corresponding
        filter is provided.  Falls back to a table scan otherwise.
        """
        kwargs: dict[str, Any] = {"Limit": query.page_size}
        exclusive_start = decode_next_token(query.next_token)
        if exclusive_start:
            kwargs["ExclusiveStartKey"] = exclusive_start

        if query.customer_id:
            kwargs["IndexName"] = "GSI1"
            kwargs["KeyConditionExpression"] = Key("GSI1PK").eq(
                f"CUSTOMER#{query.customer_id}"
            )
            response = await self._table.query(**kwargs)
        elif query.status:
            kwargs["IndexName"] = "GSI2"
            kwargs["KeyConditionExpression"] = Key("GSI2PK").eq(
                f"STATUS#{query.status.value}"
            )
            response = await self._table.query(**kwargs)
        elif query.channel:
            kwargs["IndexName"] = "GSI3"
            kwargs["KeyConditionExpression"] = Key("GSI3PK").eq(
                f"CHANNEL#{query.channel.value}"
            )
            response = await self._table.query(**kwargs)
        else:
            kwargs["FilterExpression"] = Attr("SK").eq("METADATA")
            response = await self._table.scan(**kwargs)

        items = [
            from_dynamodb_item(item, ConsentRecord)
            for item in response.get("Items", [])
        ]
        next_token = encode_next_token(response.get("LastEvaluatedKey"))
        return PaginatedConsentsResponse(
            items=items,
            count=len(items),
            next_token=next_token,
        )

    async def list_by_customer(
        self,
        customer_id: str,
        page_size: int = 20,
        next_token: str | None = None,
    ) -> PaginatedConsentsResponse:
        """Query GSI1 to list consents belonging to a customer."""
        kwargs: dict[str, Any] = {
            "IndexName": "GSI1",
            "KeyConditionExpression": Key("GSI1PK").eq(f"CUSTOMER#{customer_id}"),
            "Limit": page_size,
        }
        exclusive_start = decode_next_token(next_token)
        if exclusive_start:
            kwargs["ExclusiveStartKey"] = exclusive_start

        response = await self._table.query(**kwargs)
        items = [
            from_dynamodb_item(item, ConsentRecord)
            for item in response.get("Items", [])
        ]
        return PaginatedConsentsResponse(
            items=items,
            count=len(items),
            next_token=encode_next_token(response.get("LastEvaluatedKey")),
        )

    # ------------------------------------------------------------------
    # History / audit trail
    # ------------------------------------------------------------------

    async def add_history_entry(
        self, consent_id: str, action: str, details: dict[str, Any]
    ) -> None:
        """Append an audit-trail entry to the consent's history."""
        timestamp = datetime.now(timezone.utc).isoformat()
        item = {
            "PK": f"CONSENT#{consent_id}",
            "SK": f"HISTORY#{timestamp}",
            "action": action,
            "timestamp": timestamp,
            **details,
        }
        logger.info("adding_history_entry", consent_id=consent_id, action=action)
        await self._table.put_item(Item=item)

    async def get_history(self, consent_id: str) -> list[dict[str, Any]]:
        """Return the full audit history for a consent record."""
        response = await self._table.query(
            KeyConditionExpression=(
                Key("PK").eq(f"CONSENT#{consent_id}")
                & Key("SK").begins_with("HISTORY#")
            ),
        )
        return response.get("Items", [])

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    async def get_analytics(
        self, from_date: str | None, to_date: str | None
    ) -> dict[str, Any]:
        """Aggregate consent counts by status, channel, and type.

        Scans the table for METADATA items.  Date filtering is applied when
        ``from_date`` / ``to_date`` are provided.
        """
        filter_expr = Attr("SK").eq("METADATA")
        if from_date:
            filter_expr = filter_expr & Attr("created_at").gte(from_date)
        if to_date:
            filter_expr = filter_expr & Attr("created_at").lte(to_date)

        by_status: dict[str, int] = {}
        by_channel: dict[str, int] = {}
        by_type: dict[str, int] = {}
        total = 0
        granted_count = 0
        total_response_time = 0.0
        response_count = 0

        scan_kwargs: dict[str, Any] = {"FilterExpression": filter_expr}
        while True:
            response = await self._table.scan(**scan_kwargs)
            for item in response.get("Items", []):
                total += 1
                status = str(item.get("status", "UNKNOWN"))
                channel = str(item.get("channel", "UNKNOWN"))
                consent_type = str(item.get("consent_type", "UNKNOWN"))
                by_status[status] = by_status.get(status, 0) + 1
                by_channel[channel] = by_channel.get(channel, 0) + 1
                by_type[consent_type] = by_type.get(consent_type, 0) + 1

                if status == "GRANTED":
                    granted_count += 1
                    if item.get("granted_at") and item.get("created_at"):
                        try:
                            created = datetime.fromisoformat(str(item["created_at"]))
                            granted = datetime.fromisoformat(str(item["granted_at"]))
                            diff_hours = (granted - created).total_seconds() / 3600
                            total_response_time += diff_hours
                            response_count += 1
                        except (ValueError, TypeError):
                            pass

            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            scan_kwargs["ExclusiveStartKey"] = last_key

        return {
            "total": total,
            "by_status": by_status,
            "by_channel": by_channel,
            "by_type": by_type,
            "granted_count": granted_count,
            "total_response_time": total_response_time,
            "response_count": response_count,
        }
