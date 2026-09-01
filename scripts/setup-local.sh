#!/bin/bash
set -euo pipefail

echo "========================================="
echo "  CMS Local Development Setup"
echo "========================================="

# Check Docker is running
echo ""
echo "Checking Docker..."
if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker is not running. Please start Docker and try again."
    exit 1
fi
echo "Docker is running."

# Copy .env.example to .env if not exists
echo ""
echo "Setting up environment..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example"
else
    echo ".env already exists, skipping."
fi

# Start Floci
echo ""
echo "Starting Floci infrastructure..."
docker-compose -f docker-compose.floci.yml up -d

# Wait for Floci to be healthy
echo ""
echo "Waiting for Floci to be healthy..."
RETRIES=30
until docker-compose -f docker-compose.floci.yml exec -T floci curl -sf http://localhost:4566/_localstack/health > /dev/null 2>&1; do
    RETRIES=$((RETRIES - 1))
    if [ $RETRIES -le 0 ]; then
        echo "ERROR: Floci did not become healthy in time."
        exit 1
    fi
    echo "  Waiting... ($RETRIES retries left)"
    sleep 2
done
echo "Floci is healthy!"

# Bootstrap AWS resources
echo ""
echo "Bootstrapping AWS resources..."
bash scripts/bootstrap-aws.sh

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
if [ -d "services/shared" ]; then
    pip install -e "services/shared[dev]"
fi

# Install frontend dependencies
echo ""
echo "Installing frontend dependencies..."
if [ -d "frontend" ] && [ -f "frontend/package.json" ]; then
    cd frontend && npm install && cd ..
fi

echo ""
echo "========================================="
echo "  Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  make up        - Start all services"
echo "  make logs      - View service logs"
echo "  make seed      - Seed test data"
echo "  make test      - Run tests"
echo ""
