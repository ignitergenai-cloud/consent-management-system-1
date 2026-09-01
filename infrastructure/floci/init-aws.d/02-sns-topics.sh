#!/bin/bash
set -euo pipefail

AWS_CMD="aws --endpoint-url=http://localhost:4566 --region us-east-1 --no-cli-pager"

TOPICS=(
    "cms-consent-events"
    "cms-notification-commands"
    "cms-notification-events"
    "cms-incident-events"
    "cms-internal-commands"
    "mims-inbound-incidents"
    "cms-incident-commands"
)

echo "Creating SNS topics..."

for topic in "${TOPICS[@]}"; do
    echo "  Creating topic: $topic"
    $AWS_CMD sns create-topic --name "$topic"
done

echo "All SNS topics created successfully."
