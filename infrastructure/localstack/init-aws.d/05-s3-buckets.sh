#!/bin/bash
set -euo pipefail

AWS_CMD="aws --endpoint-url=http://localhost:4566 --region us-east-1 --no-cli-pager"

echo "Creating S3 buckets..."

echo "  Creating bucket: cms-consent-documents"
$AWS_CMD s3 mb s3://cms-consent-documents

echo "All S3 buckets created successfully."
