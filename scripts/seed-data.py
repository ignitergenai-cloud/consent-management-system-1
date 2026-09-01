#!/usr/bin/env python3
"""Seed DynamoDB with test data for the Consent Management System."""

import asyncio
import uuid
import random
from datetime import datetime, timedelta, timezone

import aioboto3


ENDPOINT_URL = "http://localhost:4566"
REGION = "us-east-1"
TABLE_NAME = "cms-consents"

CONSENT_TYPES = ["marketing_email", "data_sharing", "analytics", "third_party", "profiling"]
CONSENT_STATUSES = ["active", "revoked", "pending", "expired"]
CHANNELS = ["web", "mobile", "api", "email"]


def generate_customer_id() -> str:
    return f"CUST#{uuid.uuid4().hex[:8]}"


def generate_timestamp(days_ago_max: int = 365) -> str:
    days_ago = random.randint(0, days_ago_max)
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.isoformat()


async def seed_data():
    session = aioboto3.Session()

    async with session.resource(
        "dynamodb",
        endpoint_url=ENDPOINT_URL,
        region_name=REGION,
        aws_access_key_id="test",
        aws_secret_access_key="test",
    ) as dynamodb:
        table = await dynamodb.Table(TABLE_NAME)

        customers = [generate_customer_id() for _ in range(10)]
        items_created = 0

        # Create consent records
        print("Creating consent records...")
        for i in range(50):
            customer_id = random.choice(customers)
            consent_type = random.choice(CONSENT_TYPES)
            status = random.choice(CONSENT_STATUSES)
            consent_id = f"CONSENT#{uuid.uuid4().hex[:12]}"
            created_at = generate_timestamp()
            channel = random.choice(CHANNELS)

            item = {
                "PK": customer_id,
                "SK": consent_id,
                "GSI1PK": f"TYPE#{consent_type}",
                "GSI1SK": created_at,
                "GSI2PK": f"STATUS#{status}",
                "GSI2SK": created_at,
                "GSI3PK": f"CHANNEL#{channel}",
                "GSI3SK": created_at,
                "consent_type": consent_type,
                "status": status,
                "channel": channel,
                "customer_id": customer_id.replace("CUST#", ""),
                "consent_id": consent_id.replace("CONSENT#", ""),
                "created_at": created_at,
                "updated_at": created_at,
                "ip_address": f"192.168.1.{random.randint(1, 254)}",
                "user_agent": "Mozilla/5.0 (seed-data)",
                "version": 1,
            }

            await table.put_item(Item=item)
            items_created += 1

        # Create notification log records
        print("Creating notification log records...")
        for i in range(15):
            customer_id = random.choice(customers)
            notification_id = f"NOTIF#{uuid.uuid4().hex[:12]}"
            created_at = generate_timestamp(days_ago_max=30)
            notif_type = random.choice(["consent_confirmation", "consent_expiry_reminder", "consent_revoked"])
            notif_status = random.choice(["sent", "delivered", "failed", "pending"])

            item = {
                "PK": customer_id,
                "SK": notification_id,
                "GSI1PK": f"NOTIF_TYPE#{notif_type}",
                "GSI1SK": created_at,
                "GSI2PK": f"NOTIF_STATUS#{notif_status}",
                "GSI2SK": created_at,
                "GSI3PK": f"NOTIF_CHANNEL#email",
                "GSI3SK": created_at,
                "notification_type": notif_type,
                "status": notif_status,
                "recipient_email": f"user{random.randint(1, 100)}@example.com",
                "created_at": created_at,
                "sent_at": created_at if notif_status in ("sent", "delivered") else None,
            }

            # Remove None values
            item = {k: v for k, v in item.items() if v is not None}

            await table.put_item(Item=item)
            items_created += 1

        print(f"\nSeeded {items_created} items successfully!")
        print(f"  - 10 customers")
        print(f"  - 50 consent records")
        print(f"  - 15 notification logs")
        print(f"\nCustomer IDs:")
        for cid in customers:
            print(f"  {cid}")


if __name__ == "__main__":
    asyncio.run(seed_data())
