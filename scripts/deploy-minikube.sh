#!/bin/bash
set -euo pipefail

echo "Deploying CMS to Minikube..."

# Start minikube if not running
minikube status || minikube start --cpus=4 --memory=8192

# Enable addons
minikube addons enable ingress
minikube addons enable metrics-server

# Set docker env to use minikube's Docker daemon
eval $(minikube docker-env)

# Build images
docker-compose build

# Apply K8s manifests
kubectl apply -f infrastructure/k8s/namespace.yaml
kubectl apply -f infrastructure/k8s/configmaps/
kubectl apply -f infrastructure/k8s/secrets/
kubectl apply -f infrastructure/k8s/deployments/
kubectl apply -f infrastructure/k8s/hpa/
kubectl apply -f infrastructure/k8s/ingress/

# Wait for pods
kubectl wait --for=condition=ready pod -l app=consent-api -n cms --timeout=120s

echo "CMS deployed to Minikube!"
echo "Add '$(minikube ip) cms.local' to /etc/hosts"
echo "Access at http://cms.local"
