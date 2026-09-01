#!/bin/bash
set -euo pipefail

AWS_CMD="aws --endpoint-url=http://localhost:4566 --region us-east-1 --no-cli-pager"

echo "Verifying SES email identities..."

echo "  Verifying: no-reply@cms.example.com"
$AWS_CMD ses verify-email-identity --email-address no-reply@cms.example.com

echo "All SES identities verified successfully."
