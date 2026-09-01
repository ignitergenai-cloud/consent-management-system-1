"""Bootstrap AWS resources in moto server for local development."""
import boto3
import json

ENDPOINT = "http://localhost:4565"
REGION = "us-east-1"
ACCOUNT = "123456789012"
KWARGS = dict(
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test",
)


def main():
    # DynamoDB
    print("=== DynamoDB ===")
    ddb = boto3.client("dynamodb", **KWARGS)
    try:
        ddb.describe_table(TableName="cms-consents")
        print("  Table 'cms-consents' already exists")
    except ddb.exceptions.ResourceNotFoundException:
        ddb.create_table(
            TableName="cms-consents",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
                {"AttributeName": "GSI1PK", "AttributeType": "S"},
                {"AttributeName": "GSI1SK", "AttributeType": "S"},
                {"AttributeName": "GSI2PK", "AttributeType": "S"},
                {"AttributeName": "GSI2SK", "AttributeType": "S"},
                {"AttributeName": "GSI3PK", "AttributeType": "S"},
                {"AttributeName": "GSI3SK", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "GSI1",
                    "KeySchema": [
                        {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "GSI2",
                    "KeySchema": [
                        {"AttributeName": "GSI2PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI2SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "GSI3",
                    "KeySchema": [
                        {"AttributeName": "GSI3PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI3SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        print("  Table 'cms-consents' created")

    # SNS Topics
    print("\n=== SNS Topics ===")
    sns = boto3.client("sns", **KWARGS)
    topic_names = [
        "cms-consent-events",
        "cms-notification-commands",
        "cms-notification-events",
        "cms-incident-events",
        "cms-internal-commands",
        "mims-inbound-incidents",
        "cms-incident-commands",
    ]
    topic_arns = {}
    for name in topic_names:
        resp = sns.create_topic(Name=name)
        topic_arns[name] = resp["TopicArn"]
        print(f"  Created: {name}")

    # SQS Queues with DLQs
    print("\n=== SQS Queues ===")
    sqs = boto3.client("sqs", **KWARGS)
    queue_names = [
        "cms-consent-processing-queue",
        "cms-notification-queue",
        "cms-notification-status-queue",
        "cms-incident-detection-queue",
        "cms-incident-bridge-queue",
        "cms-incident-commands-queue",
        "cms-internal-commands-queue",
    ]
    for name in queue_names:
        dlq_name = f"{name}-dlq"
        sqs.create_queue(QueueName=dlq_name)
        dlq_attrs = sqs.get_queue_attributes(
            QueueUrl=f"{ENDPOINT}/{ACCOUNT}/{dlq_name}",
            AttributeNames=["QueueArn"],
        )
        dlq_arn = dlq_attrs["Attributes"]["QueueArn"]
        sqs.create_queue(
            QueueName=name,
            Attributes={
                "RedrivePolicy": json.dumps(
                    {"deadLetterTargetArn": dlq_arn, "maxReceiveCount": "3"}
                )
            },
        )
        print(f"  Created: {name} (with DLQ)")

    # SNS -> SQS Subscriptions
    print("\n=== SNS Subscriptions ===")
    subscriptions = [
        ("cms-consent-events", "cms-consent-processing-queue"),
        ("cms-consent-events", "cms-incident-detection-queue"),
        ("cms-notification-commands", "cms-notification-queue"),
        ("cms-notification-events", "cms-notification-status-queue"),
        ("cms-incident-events", "cms-incident-bridge-queue"),
        ("cms-internal-commands", "cms-internal-commands-queue"),
        ("cms-incident-commands", "cms-incident-commands-queue"),
    ]
    for topic_name, queue_name in subscriptions:
        topic_arn = topic_arns[topic_name]
        queue_arn = f"arn:aws:sqs:{REGION}:{ACCOUNT}:{queue_name}"
        sns.subscribe(TopicArn=topic_arn, Protocol="sqs", Endpoint=queue_arn)
        print(f"  {queue_name} -> {topic_name}")

    # S3
    print("\n=== S3 ===")
    s3 = boto3.client("s3", **KWARGS)
    try:
        s3.head_bucket(Bucket="cms-consent-documents")
        print("  Bucket 'cms-consent-documents' already exists")
    except Exception:
        s3.create_bucket(Bucket="cms-consent-documents")
        print("  Bucket 'cms-consent-documents' created")

    # SES
    print("\n=== SES ===")
    ses = boto3.client("ses", **KWARGS)
    ses.verify_email_identity(EmailAddress="no-reply@cms.example.com")
    print("  Verified: no-reply@cms.example.com")

    print("\n✅ All AWS resources bootstrapped successfully!")


if __name__ == "__main__":
    main()
