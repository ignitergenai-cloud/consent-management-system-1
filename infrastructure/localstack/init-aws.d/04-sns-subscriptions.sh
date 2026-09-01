#!/bin/bash
set -euo pipefail

AWS_CMD="aws --endpoint-url=http://localhost:4566 --region us-east-1 --no-cli-pager"

REGION="us-east-1"
ACCOUNT="000000000000"

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
        --notification-endpoint "$queue_arn"
}

subscribe "cms-consent-events" "cms-consent-processing-queue"
subscribe "cms-consent-events" "cms-incident-detection-queue"
subscribe "cms-notification-commands" "cms-notification-queue"
subscribe "cms-notification-events" "cms-notification-status-queue"
subscribe "cms-incident-events" "cms-incident-bridge-queue"
subscribe "cms-internal-commands" "cms-internal-commands-queue"
subscribe "cms-incident-commands" "cms-incident-commands-queue"

echo "All SNS subscriptions created successfully."
