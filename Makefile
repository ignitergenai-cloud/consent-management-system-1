.PHONY: help setup infra-up infra-down bootstrap up down build test test-unit test-integration seed logs clean deploy-minikube deploy-k3s lint

.DEFAULT_GOAL := help

help: ## Show help
	@echo "Consent Management System - Available Targets"
	@echo "=============================================="
	@echo ""
	@echo "  setup              Run full local setup (copy .env, start floci, bootstrap AWS, install deps)"
	@echo "  infra-up           Start Floci infrastructure only"
	@echo "  infra-down         Stop infrastructure"
	@echo "  bootstrap          Create AWS resources in Floci"
	@echo "  up                 Start all services with docker-compose"
	@echo "  down               Stop all services"
	@echo "  build              Build all Docker images"
	@echo "  test               Run all tests"
	@echo "  test-unit          Run unit tests"
	@echo "  test-integration   Run integration tests"
	@echo "  seed               Seed test data"
	@echo "  logs               Tail all service logs"
	@echo "  clean              Remove all containers, volumes, images"
	@echo "  deploy-minikube    Deploy to Minikube"
	@echo "  deploy-k3s         Deploy to K3s"
	@echo "  lint               Run linting"

setup: ## Run full local setup
	@echo "==> Copying .env.example to .env..."
	cp -n .env.example .env || true
	@echo "==> Starting Floci infrastructure..."
	$(MAKE) infra-up
	@echo "==> Waiting for Floci to be healthy..."
	sleep 10
	@echo "==> Bootstrapping AWS resources..."
	$(MAKE) bootstrap
	@echo "==> Installing dependencies..."
	pip install -r requirements.txt || true
	cd frontend && npm install || true
	@echo "==> Setup complete!"

infra-up: ## Start Floci infrastructure only
	@echo "==> Starting Floci..."
	docker-compose -f docker-compose.floci.yml up -d

infra-down: ## Stop infrastructure
	@echo "==> Stopping Floci..."
	docker-compose -f docker-compose.floci.yml down

bootstrap: ## Create AWS resources in Floci
	@echo "==> Bootstrapping AWS resources in Floci..."
	./infrastructure/floci/init-aws.d/01-create-resources.sh

up: ## Start all services with docker-compose
	@echo "==> Starting all services..."
	docker-compose up -d

down: ## Stop all services
	@echo "==> Stopping all services..."
	docker-compose down

build: ## Build all Docker images
	@echo "==> Building all Docker images..."
	docker-compose build

test: ## Run all tests
	@echo "==> Running all tests..."
	pytest tests/ -v

test-unit: ## Run unit tests
	@echo "==> Running unit tests..."
	pytest tests/unit/ -v

test-integration: ## Run integration tests
	@echo "==> Running integration tests..."
	pytest tests/integration/ -v

seed: ## Seed test data
	@echo "==> Seeding test data..."
	python scripts/seed_data.py

logs: ## Tail all service logs
	@echo "==> Tailing service logs..."
	docker-compose logs -f

clean: ## Remove all containers, volumes, images
	@echo "==> Cleaning up all containers, volumes, and images..."
	docker-compose down -v --rmi all --remove-orphans

deploy-minikube: ## Deploy to Minikube
	@echo "==> Deploying to Minikube..."
	powershell -ExecutionPolicy Bypass -File scripts/deploy-minikube.ps1

deploy-k3s: ## Deploy to K3s
	@echo "==> Deploying to K3s..."
	kubectl apply -f kubernetes/k3s/

lint: ## Run linting
	@echo "==> Running linting..."
	ruff check .
	cd frontend && npm run lint || true
