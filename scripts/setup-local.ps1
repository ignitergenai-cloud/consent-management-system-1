Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  CMS Local Development Setup" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# Check Docker is running
Write-Host ""
Write-Host "Checking Docker..."
try {
    docker info | Out-Null
    Write-Host "Docker is running." -ForegroundColor Green
} catch {
    Write-Host "ERROR: Docker is not running. Please start Docker and try again." -ForegroundColor Red
    exit 1
}

# Copy .env.example to .env if not exists
Write-Host ""
Write-Host "Setting up environment..."
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example" -ForegroundColor Green
} else {
    Write-Host ".env already exists, skipping." -ForegroundColor Yellow
}

# Start Floci
Write-Host ""
Write-Host "Starting Floci infrastructure..."
docker-compose -f docker-compose.floci.yml up -d

# Wait for Floci to be healthy
Write-Host ""
Write-Host "Waiting for Floci to be healthy..."
$retries = 30
$healthy = $false
while ($retries -gt 0 -and -not $healthy) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:4566/_localstack/health" -UseBasicParsing -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            $healthy = $true
        }
    } catch {
        $retries--
        Write-Host "  Waiting... ($retries retries left)"
        Start-Sleep -Seconds 2
    }
}

if (-not $healthy) {
    Write-Host "ERROR: Floci did not become healthy in time." -ForegroundColor Red
    exit 1
}
Write-Host "Floci is healthy!" -ForegroundColor Green

# Bootstrap AWS resources
Write-Host ""
Write-Host "Bootstrapping AWS resources..."
& "$PSScriptRoot\bootstrap-aws.ps1"

# Install Python dependencies
Write-Host ""
Write-Host "Installing Python dependencies..."
if (Test-Path "services\shared") {
    pip install -e "services\shared[dev]"
}

# Install frontend dependencies
Write-Host ""
Write-Host "Installing frontend dependencies..."
if (Test-Path "frontend\package.json") {
    Push-Location frontend
    npm install
    Pop-Location
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  Setup Complete!" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:"
Write-Host "  make up        - Start all services"
Write-Host "  make logs      - View service logs"
Write-Host "  make seed      - Seed test data"
Write-Host "  make test      - Run tests"
Write-Host ""
