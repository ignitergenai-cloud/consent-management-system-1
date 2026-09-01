#!/bin/bash
set -euo pipefail

AWS_CMD="aws --endpoint-url=http://localhost:4566 --region us-east-1 --no-cli-pager"

QUEUES=(
    "cms-consent-processing-queue"
    "cms-notification-queue"
    "cms-notification-status-queue"
    "cms-incident-detection-queue"
    "cms-incident-bridge-queue"
    "cms-incident-commands-queue"
    "cms-internal-commands-queue"
)

echo "Creating SQS queues with DLQs..."

for queue in "${QUEUES[@]}"; do
    dlq_name="${queue}-dlq"

    echo "  Creating DLQ: $dlq_name"
    $AWS_CMD sqs create-queue --queue-name "$dlq_name"

    dlq_arn=$($AWS_CMD sqs get-queue-attributes \
        --queue-url "http://localhost:4566/000000000000/$dlq_name" \
        --attribute-names QueueArn \
        --query 'Attributes.QueueArn' \
        --output text)

    echo "  Creating queue: $queue (DLQ ARN: $dlq_arn)"
    $AWS_CMD sqs create-queue \
        --queue-name "$queue" \
        --attributes "{\"RedrivePolicy\":\"{\\\"deadLetterTargetArn\\\":\\\"$dlq_arn\\\",\\\"maxReceiveCount\\\":\\\"3\\\"}\"}"
done

echo "All SQS queues created successfully."
