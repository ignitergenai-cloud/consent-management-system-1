# Consent Management System (CMS)

An event-driven microservices application for managing customer consent via SMS and Email, with integration into an external Major Incident Management System (MIMS).

## Architecture

```
                            ┌──────────────┐
                            │   React UI   │
                            │  (Port 3000) │
                            └──────┬───────┘
                                   │ REST
                                   ▼
┌──────────────┐    SNS/SQS   ┌──────────────┐    SNS/SQS   ┌──────────────────┐
│  incident-   │◄────────────►│  consent-api  │─────────────►│  notification-   │
│  bridge      │              │  (Port 8000)  │              │  service         │
│  (Port 8004) │              └──────┬────────┘              │  (Port 8002)     │
└──────┬───────┘                     │ SQS                   └────────┬─────────┘
       │ SNS/SQS                     ▼                                │ SNS/SES
       ▼                      ┌──────────────┐                        ▼
┌──────────────┐              │  consent-    │                ┌──────────────┐
│ EXTERNAL     │              │  processor   │                │  Customers   │
│ MIMS         │              │  (Port 8001) │                │  (SMS/Email) │
└──────────────┘              └──────┬───────┘                └──────────────┘
                                     │ SQS
                                     ▼
                              ┌──────────────┐
                              │  incident-   │
                              │  detector    │
                              │  (Port 8003) │
                              └──────────────┘
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.12, FastAPI, aioboto3 |
| Frontend | React 19, MUI v7, Recharts, Vite |
| Database | DynamoDB (single-table design) |
| Messaging | AWS SNS/SQS |
| Email | AWS SES |
| SMS | AWS SNS |
| Storage | AWS S3 |
| Local AWS | [Floci](https://github.com/floci-io/floci) (primary), LocalStack (fallback) |
| Container | Docker, Docker Compose |
| Orchestration | Kubernetes (Minikube / K3s), Helm |
| Logging | structlog (JSON), CloudWatch |

## Microservices

| Service | Port | Description |
|---------|------|-------------|
| **consent-api** | 8000 | Core REST API — consent CRUD, customer response, analytics |
| **consent-processor** | 8001 | SQS consumer — consent workflow state machine, expiry |
| **notification-service** | 8002 | SQS consumer — sends SMS (SNS) and Email (SES) |
| **incident-detector** | 8003 | Anomaly detection — failure rates, error spikes |
| **incident-bridge** | 8004 | Bidirectional bridge between CMS and external MIMS |
| **frontend** | 3000 | React dashboard — consent management, analytics, incidents |

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.12+
- Node.js 22+

### 1. Setup

```bash
# Clone and setup
cp .env.example .env

# Start infrastructure (Floci) and bootstrap AWS resources
make setup

# Or step by step:
docker-compose -f docker-compose.floci.yml up -d
./scripts/bootstrap-aws.sh
```

### 2. Run All Services

```bash
# Build and start everything
make up

# Or using docker-compose directly
docker-compose up --build
```

### 3. Access

| URL | Description |
|-----|-------------|
| http://localhost:3000 | Frontend Dashboard |
| http://localhost:8000/docs | Swagger API Documentation |
| http://localhost:8000/api/v1/health | Health Check |

### 4. Seed Test Data

```bash
python scripts/seed-data.py
```

## Development

### Install Dependencies

```bash
# Backend (shared library)
pip install -e services/shared[dev]

# Frontend
cd frontend && npm install
```

### Run Tests

```bash
# All tests
make test

# Unit tests only
make test-unit

# Integration tests (requires Floci running)
make test-integration
```

### Linting

```bash
make lint
```

## Kubernetes Deployment

### Minikube

```bash
make deploy-minikube
# Or: ./scripts/deploy-minikube.sh

# Access: add "$(minikube ip) cms.local" to /etc/hosts
# Visit http://cms.local
```

### K3s

```bash
make deploy-k3s
# Or: ./scripts/deploy-k3s.sh
```

### Helm

```bash
# Minikube
helm install cms ./infrastructure/helm/cms -f infrastructure/helm/cms/values-minikube.yaml

# K3s
helm install cms ./infrastructure/helm/cms -f infrastructure/helm/cms/values-k3s.yaml
```

## MIMS Integration

The CMS integrates with an external Major Incident Management System via SNS/SQS:

- **Outbound**: CMS detects incidents → publishes to `mims-inbound-incidents` SNS topic
- **Inbound**: MIMS sends commands → publishes to `cms-incident-commands` SNS topic

See [docs/INTEGRATION.md](docs/INTEGRATION.md) for full integration design.

## Design Documents

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture, components, data flows |
| [API_DESIGN.md](docs/API_DESIGN.md) | REST API endpoints, schemas |
| [INTEGRATION.md](docs/INTEGRATION.md) | MIMS integration, message schemas |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Kubernetes deployment guide |
| [INFRASTRUCTURE.md](docs/INFRASTRUCTURE.md) | Local AWS setup (Floci/LocalStack) |
| [DATA_MODEL.md](docs/DATA_MODEL.md) | DynamoDB table design |
| [SECURITY.md](docs/SECURITY.md) | Security considerations |

## Project Structure

```
consent-management-system/
├── docs/                          # Design documents
├── services/
│   ├── shared/                    # Shared Python library
│   ├── consent-api/               # Core REST API
│   ├── notification-service/      # SMS/Email sender
│   ├── consent-processor/         # Consent workflow processor
│   ├── incident-detector/         # Anomaly detection
│   └── incident-bridge/           # MIMS integration bridge
├── frontend/                      # React dashboard
├── infrastructure/
│   ├── floci/                     # Floci (local AWS) config
│   ├── localstack/                # LocalStack fallback
│   ├── k8s/                       # Raw Kubernetes manifests
│   └── helm/                      # Helm charts
├── docker/                        # Dockerfiles
├── scripts/                       # Setup & deploy scripts
├── tests/                         # Integration & E2E tests
├── docker-compose.yml             # Full stack
├── docker-compose.floci.yml       # Floci only
├── docker-compose.localstack.yml  # LocalStack fallback
└── Makefile                       # Dev commands
```

## License

MIT
