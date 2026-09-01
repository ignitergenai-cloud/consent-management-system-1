#!/usr/bin/env python3
"""Verify all AWS resources exist for the Consent Management System."""

import asyncio
import sys

import aioboto3


ENDPOINT_URL = "http://localhost:4566"
REGION = "us-east-1"

EXPECTED_TABLE = "cms-consents"
EXPECTED_GSIS = ["GSI1", "GSI2", "GSI3"]

EXPECTED_TOPICS = [
    "cms-consent-events",
    "cms-notification-commands",
    "cms-notification-events",
    "cms-incident-events",
    "cms-internal-commands",
    "mims-inbound-incidents",
    "cms-incident-commands",
]

EXPECTED_QUEUES = [
    "cms-consent-processing-queue",
    "cms-notification-queue",
    "cms-notification-status-queue",
    "cms-incident-detection-queue",
    "cms-incident-bridge-queue",
    "cms-incident-commands-queue",
    "cms-internal-commands-queue",
]

EXPECTED_DLQS = [f"{q}-dlq" for q in EXPECTED_QUEUES]

EXPECTED_BUCKET = "cms-consent-documents"
EXPECTED_SES_EMAIL = "no-reply@cms.example.com"


GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"
CHECK = f"{GREEN}✓{RESET}"
CROSS = f"{RED}✗{RESET}"

passed = 0
failed = 0


def check(ok: bool, label: str):
    global passed, failed
    if ok:
        passed += 1
        print(f"  {CHECK} {label}")
    else:
        failed += 1
        print(f"  {CROSS} {label}")


async def verify():
    global passed, failed
    session = aioboto3.Session()

    print("\n=== DynamoDB ===")
    async with session.client(
        "dynamodb",
        endpoint_url=ENDPOINT_URL,
        region_name=REGION,
        aws_access_key_id="test",
        aws_secret_access_key="test",
    ) as dynamodb:
        try:
            resp = await dynamodb.describe_table(TableName=EXPECTED_TABLE)
            check(True, f"Table '{EXPECTED_TABLE}' exists")
            gsi_names = [
                g["IndexName"]
                for g in resp["Table"].get("GlobalSecondaryIndexes", [])
            ]
            for gsi in EXPECTED_GSIS:
                check(gsi in gsi_names, f"GSI '{gsi}' exists")
        except Exception:
            check(False, f"Table '{EXPECTED_TABLE}' exists")
            for gsi in EXPECTED_GSIS:
                check(False, f"GSI '{gsi}' exists")

    print("\n=== SNS Topics ===")
    async with session.client(
        "sns",
        endpoint_url=ENDPOINT_URL,
        region_name=REGION,
        aws_access_key_id="test",
        aws_secret_access_key="test",
    ) as sns:
        try:
            resp = await sns.list_topics()
            topic_arns = [t["TopicArn"] for t in resp.get("Topics", [])]
            topic_names = [arn.split(":")[-1] for arn in topic_arns]
            for topic in EXPECTED_TOPICS:
                check(topic in topic_names, f"Topic '{topic}'")
        except Exception:
            for topic in EXPECTED_TOPICS:
                check(False, f"Topic '{topic}'")

    print("\n=== SQS Queues ===")
    async with session.client(
        "sqs",
        endpoint_url=ENDPOINT_URL,
        region_name=REGION,
        aws_access_key_id="test",
        aws_secret_access_key="test",
    ) as sqs:
        try:
            resp = await sqs.list_queues()
            queue_urls = resp.get("QueueUrls", [])
            queue_names = [url.split("/")[-1] for url in queue_urls]
            for queue in EXPECTED_QUEUES:
                check(queue in queue_names, f"Queue '{queue}'")
            for dlq in EXPECTED_DLQS:
                check(dlq in queue_names, f"DLQ '{dlq}'")
        except Exception:
            for queue in EXPECTED_QUEUES:
                check(False, f"Queue '{queue}'")
            for dlq in EXPECTED_DLQS:
                check(False, f"DLQ '{dlq}'")

    print("\n=== S3 Buckets ===")
    async with session.client(
        "s3",
        endpoint_url=ENDPOINT_URL,
        region_name=REGION,
        aws_access_key_id="test",
        aws_secret_access_key="test",
    ) as s3:
        try:
            resp = await s3.list_buckets()
            bucket_names = [b["Name"] for b in resp.get("Buckets", [])]
            check(EXPECTED_BUCKET in bucket_names, f"Bucket '{EXPECTED_BUCKET}'")
        except Exception:
            check(False, f"Bucket '{EXPECTED_BUCKET}'")

    print("\n=== SES Identities ===")
    async with session.client(
        "ses",
        endpoint_url=ENDPOINT_URL,
        region_name=REGION,
        aws_access_key_id="test",
        aws_secret_access_key="test",
    ) as ses:
        try:
            resp = await ses.list_identities(IdentityType="EmailAddress")
            identities = resp.get("Identities", [])
            check(
                EXPECTED_SES_EMAIL in identities,
                f"SES Identity '{EXPECTED_SES_EMAIL}'",
            )
        except Exception:
            check(False, f"SES Identity '{EXPECTED_SES_EMAIL}'")

    print(f"\n{'=' * 40}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'=' * 40}\n")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(verify())
