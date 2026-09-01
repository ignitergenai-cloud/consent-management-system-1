#!/bin/bash
set -euo pipefail

AWS_CMD="aws --endpoint-url=http://localhost:4566 --region us-east-1 --no-cli-pager"
REGION="us-east-1"
ACCOUNT="000000000000"

echo "========================================="
echo "  CMS AWS Resource Bootstrap"
echo "========================================="

# DynamoDB
echo ""
echo "Creating DynamoDB table..."
if $AWS_CMD dynamodb describe-table --table-name cms-consents > /dev/null 2>&1; then
    echo "  Table 'cms-consents' already exists, skipping."
else
    $AWS_CMD dynamodb create-table \
        --table-name cms-consents \
        --key-schema \
            AttributeName=PK,KeyType=HASH \
            AttributeName=SK,KeyType=RANGE \
        --attribute-definitions \
            AttributeName=PK,AttributeType=S \
            AttributeName=SK,AttributeType=S \
            AttributeName=GSI1PK,AttributeType=S \
            AttributeName=GSI1SK,AttributeType=S \
            AttributeName=GSI2PK,AttributeType=S \
            AttributeName=GSI2SK,AttributeType=S \
            AttributeName=GSI3PK,AttributeType=S \
            AttributeName=GSI3SK,AttributeType=S \
        --global-secondary-indexes \
            '[
                {
                    "IndexName": "GSI1",
                    "KeySchema": [
                        {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI1SK", "KeyType": "RANGE"}
                    ],
                    "Projection": {"ProjectionType": "ALL"}
                },
                {
                    "IndexName": "GSI2",
                    "KeySchema": [
                        {"AttributeName": "GSI2PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI2SK", "KeyType": "RANGE"}
                    ],
                    "Projection": {"ProjectionType": "ALL"}
                },
                {
                    "IndexName": "GSI3",
                    "KeySchema": [
                        {"AttributeName": "GSI3PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI3SK", "KeyType": "RANGE"}
                    ],
                    "Projection": {"ProjectionType": "ALL"}
                }
            ]' \
        --billing-mode PAY_PER_REQUEST
    echo "  Table 'cms-consents' created."
fi

# SNS Topics
echo ""
echo "Creating SNS topics..."
TOPICS=(
    "cms-consent-events"
    "cms-notification-commands"
    "cms-notification-events"
    "cms-incident-events"
    "cms-internal-commands"
    "mims-inbound-incidents"
    "cms-incident-commands"
)

for topic in "${TOPICS[@]}"; do
    echo "  Creating topic: $topic"
    $AWS_CMD sns create-topic --name "$topic" > /dev/null
done

# SQS Queues with DLQs
echo ""
echo "Creating SQS queues..."
QUEUES=(
    "cms-consent-processing-queue"
    "cms-notification-queue"
    "cms-notification-status-queue"
    "cms-incident-detection-queue"
    "cms-incident-bridge-queue"
    "cms-incident-commands-queue"
    "cms-internal-commands-queue"
)

for queue in "${QUEUES[@]}"; do
    dlq_name="${queue}-dlq"

    echo "  Creating DLQ: $dlq_name"
    $AWS_CMD sqs create-queue --queue-name "$dlq_name" > /dev/null

    dlq_arn=$($AWS_CMD sqs get-queue-attributes \
        --queue-url "http://localhost:4566/000000000000/$dlq_name" \
        --attribute-names QueueArn \
        --query 'Attributes.QueueArn' \
        --output text)

    echo "  Creating queue: $queue"
    $AWS_CMD sqs create-queue \
        --queue-name "$queue" \
        --attributes "{\"RedrivePolicy\":\"{\\\"deadLetterTargetArn\\\":\\\"$dlq_arn\\\",\\\"maxReceiveCount\\\":\\\"3\\\"}\"}" > /dev/null
done

# SNS Subscriptions
echo ""
echo "Creating SNS -> SQS subscriptions..."

subscribe() {
    local topic_name=$1
    local queue_name=$2
    local topic_arn="arn:aws:sns:${REGION}:${ACCOUNT}:${topic_name}"
    local queue_arn="arn:aws:sqs:${REGION}:${ACCOUNT}:${queue_name}"

    echo "  Subscribing $queue_name to $topic_name"
    $AWS_CMD sns subscribe \
        --topic-arn "$topic_arn" \
        --protocol sqs \
        --notification-endpoint "$queue_arn" > /dev/null
}

subscribe "cms-consent-events" "cms-consent-processing-queue"
subscribe "cms-consent-events" "cms-incident-detection-queue"
subscribe "cms-notification-commands" "cms-notification-queue"
subscribe "cms-notification-events" "cms-notification-status-queue"
subscribe "cms-incident-events" "cms-incident-bridge-queue"
subscribe "cms-internal-commands" "cms-internal-commands-queue"
subscribe "cms-incident-commands" "cms-incident-commands-queue"

# S3
echo ""
echo "Creating S3 buckets..."
if $AWS_CMD s3api head-bucket --bucket cms-consent-documents > /dev/null 2>&1; then
    echo "  Bucket 'cms-consent-documents' already exists, skipping."
else
    $AWS_CMD s3 mb s3://cms-consent-documents
    echo "  Bucket 'cms-consent-documents' created."
fi

# SES
echo ""
echo "Verifying SES identities..."
$AWS_CMD ses verify-email-identity --email-address no-reply@cms.example.com
echo "  Verified: no-reply@cms.example.com"

echo ""
echo "========================================="
echo "  All AWS resources created successfully!"
echo "========================================="
