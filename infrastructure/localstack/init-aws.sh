#!/bin/bash
set -euo pipefail

echo "========================================="
echo "  CMS AWS Resource Bootstrap (LocalStack)"
echo "========================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for script in "$SCRIPT_DIR/init-aws.d"/*.sh; do
    if [ -f "$script" ]; then
        echo ""
        echo "Running: $(basename "$script")"
        echo "-----------------------------------------"
        bash "$script"
    fi
done

echo ""
echo "========================================="
echo "  All AWS resources created successfully!"
echo "========================================="
