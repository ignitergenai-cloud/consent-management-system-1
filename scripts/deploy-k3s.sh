#!/bin/bash
set -euo pipefail

echo "Deploying CMS to K3s..."

# Check k3s is installed
which k3s || (echo "K3s not installed. Run: curl -sfL https://get.k3s.io | sh -" && exit 1)

# Build images and load into k3s
docker-compose build

for svc in consent-api notification-service consent-processor incident-detector incident-bridge frontend; do
    docker save cms/$svc:latest | sudo k3s ctr images import -
done

# Apply manifests
sudo k3s kubectl apply -f infrastructure/k8s/namespace.yaml
sudo k3s kubectl apply -f infrastructure/k8s/configmaps/
sudo k3s kubectl apply -f infrastructure/k8s/secrets/
sudo k3s kubectl apply -f infrastructure/k8s/deployments/
sudo k3s kubectl apply -f infrastructure/k8s/hpa/
sudo k3s kubectl apply -f infrastructure/k8s/ingress/

echo "CMS deployed to K3s!"
