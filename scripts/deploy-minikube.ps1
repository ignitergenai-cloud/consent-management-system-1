<#
.SYNOPSIS
    Deploy the Consent Management System to Minikube.
.DESCRIPTION
    Checks prerequisites, starts Minikube, builds Docker images inside
    Minikube's Docker daemon, and applies all Kubernetes manifests.
#>

param(
    [switch]$SkipBuild,
    [switch]$DeleteFirst
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot  # repo root
$K8S  = Join-Path $ROOT "infrastructure\k8s"

# ── Helpers ──────────────────────────────────────────────────────────
function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    $msg" -ForegroundColor Yellow }

function Assert-Command($name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Write-Host "ERROR: '$name' not found. Install it first." -ForegroundColor Red
        Write-Host "  choco install docker-desktop minikube kubernetes-cli -y" -ForegroundColor Yellow
        exit 1
    }
}

# ── 1. Check prerequisites ──────────────────────────────────────────
Write-Step "Checking prerequisites"
Assert-Command "minikube"
Assert-Command "kubectl"
Assert-Command "docker"
Write-Ok "All prerequisites found"

# ── 2. Start Minikube if not running ─────────────────────────────────
Write-Step "Checking Minikube status"
$status = minikube status --format "{{.Host}}" 2>$null
if ($status -ne "Running") {
    Write-Warn "Minikube not running — starting..."
    minikube start --driver=docker --cpus=4 --memory=8192
} else {
    Write-Ok "Minikube already running"
}

# Enable required addons
Write-Step "Enabling Minikube addons"
minikube addons enable ingress
minikube addons enable metrics-server
Write-Ok "Addons enabled"

# ── 3. Point Docker CLI at Minikube's daemon ─────────────────────────
Write-Step "Configuring Docker to use Minikube daemon"
$envLines = minikube docker-env --shell powershell
foreach ($line in $envLines) {
    if ($line -match '^\$Env:') {
        Invoke-Expression $line
    }
}
Write-Ok "Docker CLI now targets Minikube"

# ── 4. Build Docker images ───────────────────────────────────────────
if (-not $SkipBuild) {
    Write-Step "Building Docker images"

    $images = @(
        @{ Name = "cms/consent-api";          File = "docker/Dockerfile.consent-api" },
        @{ Name = "cms/consent-processor";    File = "docker/Dockerfile.consent-processor" },
        @{ Name = "cms/notification-service"; File = "docker/Dockerfile.notification-service" },
        @{ Name = "cms/incident-detector";    File = "docker/Dockerfile.incident-detector" },
        @{ Name = "cms/incident-bridge";      File = "docker/Dockerfile.incident-bridge" },
        @{ Name = "cms/frontend";             File = "docker/Dockerfile.frontend" }
    )

    Push-Location $ROOT
    foreach ($img in $images) {
        Write-Host "  Building $($img.Name)..." -NoNewline
        docker build -t "$($img.Name):latest" -f $img.File .
        if ($LASTEXITCODE -ne 0) {
            Write-Host " FAILED" -ForegroundColor Red
            Pop-Location
            exit 1
        }
        Write-Host " OK" -ForegroundColor Green
    }
    Pop-Location
    Write-Ok "All images built"
} else {
    Write-Warn "Skipping image build (-SkipBuild)"
}

# ── 5. (Optional) Delete existing resources first ────────────────────
if ($DeleteFirst) {
    Write-Step "Deleting existing CMS resources"
    kubectl delete namespace cms --ignore-not-found
    Start-Sleep -Seconds 5
}

# ── 6. Apply K8s manifests in order ──────────────────────────────────
Write-Step "Applying Kubernetes manifests"

# Namespace
kubectl apply -f "$K8S\namespace.yaml"
Write-Ok "Namespace"

# ConfigMaps
kubectl apply -f "$K8S\configmaps\aws-config.yaml"
kubectl apply -f "$K8S\configmaps\service-config.yaml"
kubectl apply -f "$K8S\configmaps\floci-init-scripts.yaml"
Write-Ok "ConfigMaps"

# Secrets
kubectl apply -f "$K8S\secrets\aws-credentials.yaml"
Write-Ok "Secrets"

# Floci (LocalStack) — must be up before other services
kubectl apply -f "$K8S\deployments\floci.yaml"
Write-Ok "Floci deployment"

Write-Step "Waiting for Floci to be ready (up to 120s)"
kubectl rollout status deployment/floci -n cms --timeout=120s
Write-Ok "Floci is ready"

# Wait a bit for init scripts to bootstrap AWS resources
Write-Warn "Waiting 15s for AWS resource bootstrap..."
Start-Sleep -Seconds 15

# Application services
kubectl apply -f "$K8S\deployments\consent-api.yaml"
kubectl apply -f "$K8S\deployments\consent-processor.yaml"
kubectl apply -f "$K8S\deployments\notification-service.yaml"
kubectl apply -f "$K8S\deployments\incident-detector.yaml"
kubectl apply -f "$K8S\deployments\incident-bridge.yaml"
kubectl apply -f "$K8S\deployments\frontend.yaml"
Write-Ok "Application deployments"

# HPAs
kubectl apply -f "$K8S\hpa\consent-api-hpa.yaml"
kubectl apply -f "$K8S\hpa\consent-processor-hpa.yaml"
kubectl apply -f "$K8S\hpa\notification-service-hpa.yaml"
Write-Ok "HPAs"

# Ingress
kubectl apply -f "$K8S\ingress\ingress.yaml"
Write-Ok "Ingress"

# Network Policies
kubectl apply -f "$K8S\network-policies\"
Write-Ok "Network Policies"

# ── 7. Wait for rollouts ────────────────────────────────────────────
Write-Step "Waiting for all deployments to be ready"
$deployments = @("consent-api", "consent-processor", "notification-service",
                 "incident-detector", "incident-bridge", "frontend")

foreach ($dep in $deployments) {
    Write-Host "  Waiting for $dep..." -NoNewline
    kubectl rollout status "deployment/$dep" -n cms --timeout=120s 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host " Ready" -ForegroundColor Green
    } else {
        Write-Host " TIMEOUT" -ForegroundColor Yellow
    }
}

# ── 8. Show status ──────────────────────────────────────────────────
Write-Step "Deployment status"
kubectl get pods -n cms -o wide
Write-Host ""
kubectl get svc -n cms
Write-Host ""
kubectl get ingress -n cms

# ── 9. Print access instructions ────────────────────────────────────
$minikubeIp = minikube ip
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " Consent Management System deployed!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Minikube IP: $minikubeIp"
Write-Host ""
Write-Host "Add this to your hosts file (run as Admin):" -ForegroundColor Yellow
Write-Host "  Add-Content C:\Windows\System32\drivers\etc\hosts '$minikubeIp cms.local'"
Write-Host ""
Write-Host "Then open: http://cms.local"
Write-Host ""
Write-Host "Or use minikube tunnel (alternative):" -ForegroundColor Yellow
Write-Host "  minikube tunnel"
Write-Host "  Then open: http://cms.local"
Write-Host ""
