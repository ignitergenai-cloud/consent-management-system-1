# start.ps1 - Start all Consent Management System services locally
# Usage: powershell -ExecutionPolicy Bypass -File scripts\start.ps1

$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

# ---------------------------------------------------------------------------
# Port configuration
# ---------------------------------------------------------------------------
$MotoPort = 4566
$Services = @(
    @{ Name = "consent-api";          Port = 8000; Module = "consent_api.main:app";          Dir = "consent-api"          },
    @{ Name = "consent-processor";    Port = 8001; Module = "consent_processor.main:app";    Dir = "consent-processor"    },
    @{ Name = "notification-service"; Port = 8002; Module = "notification_service.main:app"; Dir = "notification-service" },
    @{ Name = "incident-detector";    Port = 8003; Module = "incident_detector.main:app";    Dir = "incident-detector"    },
    @{ Name = "incident-bridge";      Port = 8004; Module = "incident_bridge.main:app";      Dir = "incident-bridge"      }
)
$FrontendPort = 3000

# ---------------------------------------------------------------------------
# Helper: kill all processes listening on a port, then wait until it is free
# ---------------------------------------------------------------------------
function Stop-Port {
    param([int]$Port, [int]$TimeoutSec = 10)
    # Kill owners
    $ids = (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue).OwningProcess
    foreach ($id in ($ids | Sort-Object -Unique)) {
        try { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue } catch {}
    }
    # Wait until free
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $still = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if (-not $still) { return }
        Start-Sleep -Milliseconds 300
    }
}

# ---------------------------------------------------------------------------
# Helper: wait until a TCP port enters Listen state
# ---------------------------------------------------------------------------
function Wait-Port {
    param([int]$Port, [int]$TimeoutSec = 30)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($conn) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

Write-Host ""
Write-Host "============================================================"
Write-Host "  Consent Management System - Local Startup"
Write-Host "============================================================"
Write-Host ""

# ---------------------------------------------------------------------------
# Step 1: Stop any existing processes and wait for ports to be free
# ---------------------------------------------------------------------------
Write-Host "[1/5] Stopping existing processes on CMS ports..."
Stop-Port $MotoPort
foreach ($svc in $Services) { Stop-Port $svc.Port }
Stop-Port $FrontendPort

# ---------------------------------------------------------------------------
# Step 2: Start Moto (AWS emulator)
# ---------------------------------------------------------------------------
Write-Host "[2/5] Starting Moto AWS emulator on port $MotoPort..."
Start-Process powershell -ArgumentList "-NoProfile", "-WindowStyle", "Hidden", "-Command", "python -m moto.server -p $MotoPort" -WorkingDirectory $Root

if (-not (Wait-Port $MotoPort 40)) {
    Write-Host "  ERROR: Moto did not start within 40s. Aborting." -ForegroundColor Red
    exit 1
}
# Brief pause to let Moto finish initialising before bootstrap
Start-Sleep -Seconds 2
Write-Host "  Moto ready." -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 3: Bootstrap AWS resources
# ---------------------------------------------------------------------------
Write-Host "[3/5] Bootstrapping AWS resources (DynamoDB, SNS, SQS)..."
$output = & python -u "$Root\scripts\bootstrap_moto.py" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Bootstrap failed." -ForegroundColor Red
    Write-Host $output
    exit 1
}
Write-Host "  Bootstrap complete." -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 4: Start backend services
# ---------------------------------------------------------------------------
Write-Host "[4/5] Starting backend services..."
foreach ($svc in $Services) {
    $pyPath = "services\shared\src;services\" + $svc.Dir + "\src"
    $cmd = "Set-Location '$Root'; `$env:PYTHONPATH='$pyPath'; python -m uvicorn " + $svc.Module + " --host 0.0.0.0 --port " + $svc.Port
    Start-Process powershell -ArgumentList "-NoProfile", "-WindowStyle", "Hidden", "-Command", $cmd
    Write-Host ("  Started " + $svc.Name + " on port " + $svc.Port)
}

Write-Host "  Waiting for all services to be healthy..."
$allHealthy = $true
foreach ($svc in $Services) {
    $ok = Wait-Port $svc.Port 30
    if ($ok) {
        Write-Host ("  [OK]   " + $svc.Name + ":" + $svc.Port) -ForegroundColor Green
    } else {
        Write-Host ("  [FAIL] " + $svc.Name + ":" + $svc.Port + " did not respond in time") -ForegroundColor Red
        $allHealthy = $false
    }
}

# ---------------------------------------------------------------------------
# Step 5: Start frontend
# ---------------------------------------------------------------------------
Write-Host "[5/5] Starting frontend on port $FrontendPort..."
Start-Process powershell -ArgumentList "-NoProfile", "-WindowStyle", "Hidden", "-Command", "Set-Location '$Root\frontend'; npm run dev"

Write-Host ""
if ($allHealthy) {
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  All services started successfully!" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
} else {
    Write-Host "============================================================" -ForegroundColor Yellow
    Write-Host "  Some services failed to start - check the errors above." -ForegroundColor Yellow
    Write-Host "============================================================" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  Moto (AWS emulator)      : http://localhost:$MotoPort"
foreach ($svc in $Services) {
    Write-Host ("  " + $svc.Name.PadRight(24) + ": http://localhost:" + $svc.Port + "/health")
}
Write-Host "  Frontend                 : http://localhost:$FrontendPort"
Write-Host ""
