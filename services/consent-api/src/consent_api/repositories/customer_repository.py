"""DynamoDB repository for customer records."""

from __future__ import annotations

from typing import Any

import structlog
from boto3.dynamodb.conditions import Attr, Key

from cms_shared.aws.dynamodb import DynamoDBManager
from cms_shared.middleware.error_handler import ItemNotFoundError

logger = structlog.get_logger()


class CustomerRepository:
    """Data-access layer for customer records in DynamoDB."""

    def __init__(self, dynamo_manager: DynamoDBManager) -> None:
        self._dynamo = dynamo_manager

    @property
    def _table(self):
        return self._dynamo.table

    async def get_customer(self, customer_id: str) -> dict[str, Any]:
        """Retrieve a customer record by ID."""
        response = await self._table.get_item(
            Key={"PK": f"CUSTOMER#{customer_id}", "SK": "PROFILE"},
        )
        item = response.get("Item")
        if not item:
            raise ItemNotFoundError(f"Customer {customer_id} not found")
        return item

    async def create_customer(self, customer: dict[str, Any]) -> dict[str, Any]:
        """Persist a new customer record."""
        customer_id = customer["customer_id"]
        item = {
            "PK": f"CUSTOMER#{customer_id}",
            "SK": "PROFILE",
            **customer,
        }
        logger.info("creating_customer", customer_id=customer_id)
        await self._table.put_item(Item=item)
        return item

    async def list_customers(self, page_size: int = 20) -> list[dict[str, Any]]:
        """List customer records (scan-based, suitable for demo workloads)."""
        response = await self._table.scan(
            FilterExpression=Attr("SK").eq("PROFILE")
            & Attr("PK").begins_with("CUSTOMER#"),
            Limit=page_size,
        )
        return response.get("Items", [])
