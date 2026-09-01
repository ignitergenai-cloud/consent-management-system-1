# Consent Management System -- Deployment Guide

This guide covers every supported deployment target for the Consent Management System (CMS): local Docker Compose, Minikube, K3s, and Helm-based installations. Follow the section that matches your environment.

---

## 1. Prerequisites

Ensure the following tools are installed and available on your `PATH` before proceeding.

| Tool | Minimum Version | Purpose |
|------|----------------|---------|
| Docker Desktop | 24+ | Container runtime |
| Docker Compose | v2 | Multi-container orchestration |
| kubectl | 1.28+ | Kubernetes CLI |
| Minikube | 1.32+ | Local Kubernetes cluster (option A) |
| K3s | 1.28+ | Lightweight Kubernetes cluster (option B) |
| Helm | 3.14+ | Kubernetes package manager (optional) |
| Python | 3.12+ | Backend services |
| Node.js | 22+ | Frontend build toolchain |
| Make | any | Task runner for convenience targets |

Verify versions:

```bash
docker --version
docker compose version
kubectl version --client
minikube version        # if using Minikube
k3s --version           # if using K3s
helm version            # if using Helm
python3 --version
node --version
make --version
```

---

## 2. Local Development (Docker Compose)

### Quick Start

```bash
make setup && make up
```

This single command copies the example environment file, pulls base images, builds every service, and starts the full stack.

### Step-by-Step Walkthrough

If you prefer to understand each stage, follow the steps below.

#### Step 1 -- Clone the Repository

```bash
git clone <repository-url> consent-management-system
cd consent-management-system
```

#### Step 2 -- Create the Environment File

```bash
cp .env.example .env
```

Edit `.env` to override any defaults (see the environment variables table below).

#### Step 3 -- Start Floci (LocalStack)

Floci emulates AWS services locally (S3, SQS, DynamoDB, SNS).

```bash
docker-compose up -d floci
```

Wait until the container reports healthy:

```bash
docker-compose ps floci
```

#### Step 4 -- Bootstrap AWS Resources

The `init-aws` service creates the required buckets, queues, tables, and topics inside Floci.

```bash
docker-compose up init-aws
```

This container runs to completion and exits with code 0 on success.

#### Step 5 -- Build Service Images

```bash
docker-compose build
```

#### Step 6 -- Start All Services

```bash
docker-compose up -d
```

#### Step 7 -- Verify

```bash
docker-compose ps
```

All services should show a status of `Up` (or `Up (healthy)` for those with health checks).

### Service URLs

| Service | URL | Description |
|---------|-----|-------------|
| consent-ui | http://localhost:3000 | React frontend |
| consent-api | http://localhost:8000 | REST API gateway |
| Swagger UI | http://localhost:8000/docs | Interactive API documentation |
| consent-processor | http://localhost:8001 | Consent event processor |
| notification-service | http://localhost:8002 | Email and push notifications |
| incident-detector | http://localhost:8003 | Anomaly and incident detection |
| incident-bridge | http://localhost:8004 | Incident routing and escalation |
| Floci | http://localhost:4566 | Local AWS emulator (LocalStack) |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_REGION` | `us-east-1` | AWS region used by all services |
| `AWS_ACCESS_KEY_ID` | `test` | Floci access key |
| `AWS_SECRET_ACCESS_KEY` | `test` | Floci secret key |
| `FLOCI_ENDPOINT` | `http://floci:4566` | Endpoint for the local AWS emulator |
| `DATABASE_URL` | `postgresql://cms:cms@db:5432/consent` | PostgreSQL connection string |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string |
| `CONSENT_API_PORT` | `8000` | Port for the consent API |
| `CONSENT_UI_PORT` | `3000` | Port for the frontend |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `NOTIFICATION_FROM_EMAIL` | `noreply@cms.local` | Sender address for notifications |
| `INCIDENT_DETECTION_INTERVAL` | `60` | Seconds between incident detection sweeps |

---

## 3. Minikube Deployment

### Start the Cluster

```bash
minikube start --cpus=4 --memory=8192 --driver=docker
```

### Enable Required Addons

```bash
minikube addons enable ingress
minikube addons enable metrics-server
```

### Build Images Inside Minikube

Point your local Docker client at the Minikube daemon so that built images are immediately available to the cluster (no registry push required).

```bash
eval $(minikube docker-env)
docker-compose build
```

### Create the Namespace

```bash
kubectl create namespace cms
```

### Deploy Resources (in order)

The resources must be applied in dependency order so that config, secrets, and infrastructure are available before the application services start.

#### 1. Namespace

```bash
kubectl apply -f infrastructure/k8s/namespace.yaml
```

#### 2. ConfigMaps

```bash
kubectl apply -f infrastructure/k8s/configmaps/
```

#### 3. Secrets

```bash
kubectl apply -f infrastructure/k8s/secrets/
```

#### 4. Floci (LocalStack)

```bash
kubectl apply -f infrastructure/k8s/floci/
```

#### 5. Wait for Floci to Become Ready

```bash
kubectl wait --for=condition=ready pod -l app=floci -n cms --timeout=120s
```

#### 6. AWS Resource Initialization Job

```bash
kubectl apply -f infrastructure/k8s/init-aws/
```

Wait for the job to complete:

```bash
kubectl wait --for=condition=complete job/init-aws -n cms --timeout=120s
```

#### 7. Application Services

```bash
kubectl apply -f infrastructure/k8s/services/
```

#### 8. Ingress

```bash
kubectl apply -f infrastructure/k8s/ingress/
```

### Verify the Deployment

```bash
kubectl get pods -n cms
kubectl get svc -n cms
```

All pods should reach `Running` status with `READY` showing all containers up (e.g., `1/1`).

### Access the Application

Add an entry to your hosts file so that the ingress hostname resolves to the Minikube IP:

```bash
echo "$(minikube ip) cms.local" | sudo tee -a /etc/hosts
```

Then visit http://cms.local in your browser.

### Troubleshooting

| Symptom | Likely Cause | Resolution |
|---------|-------------|------------|
| Pod stuck in `Pending` | Insufficient cluster resources | Increase Minikube CPU/memory or reduce replica counts |
| Pod not starting (no events) | Check logs for the specific pod | `kubectl logs <pod-name> -n cms` |
| `ImagePullBackOff` | Image not present in Minikube daemon | Re-run `eval $(minikube docker-env)` and rebuild images |
| `CrashLoopBackOff` | Init container or dependency failure | Inspect init container logs: `kubectl logs <pod-name> -c <init-container> -n cms` |
| Service unavailable via ingress | Ingress controller misconfigured | Verify addon: `minikube addons list`; check ingress resource: `kubectl describe ingress -n cms` |

---

## 4. K3s Deployment

K3s is a lightweight, production-grade Kubernetes distribution suitable for edge, CI, and resource-constrained environments.

### Install K3s

```bash
curl -sfL https://get.k3s.io | sh -
```

After installation, verify:

```bash
sudo k3s kubectl get nodes
```

### Build and Import Images

K3s uses `containerd` rather than Docker, so images must be exported and imported.

```bash
docker build -t consent-api:latest ./services/consent-api
docker save consent-api:latest -o consent-api.tar
sudo k3s ctr images import consent-api.tar
```

Repeat for every service image:

```bash
docker build -t consent-ui:latest ./services/consent-ui
docker save consent-ui:latest -o consent-ui.tar
sudo k3s ctr images import consent-ui.tar

docker build -t consent-processor:latest ./services/consent-processor
docker save consent-processor:latest -o consent-processor.tar
sudo k3s ctr images import consent-processor.tar

docker build -t notification-service:latest ./services/notification-service
docker save notification-service:latest -o notification-service.tar
sudo k3s ctr images import notification-service.tar

docker build -t incident-detector:latest ./services/incident-detector
docker save incident-detector:latest -o incident-detector.tar
sudo k3s ctr images import incident-detector.tar

docker build -t incident-bridge:latest ./services/incident-bridge
docker save incident-bridge:latest -o incident-bridge.tar
sudo k3s ctr images import incident-bridge.tar
```

### Deploy Resources

Apply manifests in the same dependency order as the Minikube deployment:

```bash
sudo k3s kubectl apply -f infrastructure/k8s/namespace.yaml
sudo k3s kubectl apply -f infrastructure/k8s/configmaps/
sudo k3s kubectl apply -f infrastructure/k8s/secrets/
sudo k3s kubectl apply -f infrastructure/k8s/floci/
sudo k3s kubectl wait --for=condition=ready pod -l app=floci -n cms --timeout=120s
sudo k3s kubectl apply -f infrastructure/k8s/init-aws/
sudo k3s kubectl wait --for=condition=complete job/init-aws -n cms --timeout=120s
sudo k3s kubectl apply -f infrastructure/k8s/services/
sudo k3s kubectl apply -f infrastructure/k8s/ingress/
```

### Ingress Differences -- Traefik vs. Nginx

K3s ships with **Traefik** as the default ingress controller, while Minikube uses **nginx**. Key differences:

- K3s Traefik ingress annotations use the `traefik.ingress.kubernetes.io/` prefix instead of `nginx.ingress.kubernetes.io/`.
- For advanced routing, K3s supports the `IngressRoute` CRD (Traefik-native) in addition to standard `Ingress` resources.
- TLS termination, rate limiting, and middleware configuration follow Traefik conventions. Refer to the Traefik documentation for CRD schema details.

If your manifests under `infrastructure/k8s/ingress/` target nginx, either:
1. Use the K3s-specific ingress files (if provided), or
2. Install nginx in K3s: `sudo k3s kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/cloud/deploy.yaml` and disable Traefik at install time: `curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable traefik" sh -`

### Access via Node IP

```bash
sudo k3s kubectl get svc -n cms
```

Services of type `NodePort` are reachable at `<node-ip>:<node-port>`. For `ClusterIP` services, use `kubectl port-forward`:

```bash
sudo k3s kubectl port-forward svc/consent-ui 3000:3000 -n cms
```

---

## 5. Helm Deployment

Helm charts provide a single, parameterized installation path for both Minikube and K3s.

### Install with Defaults

```bash
helm install cms ./infrastructure/helm/cms -n cms --create-namespace
```

### Install with Minikube-Specific Values

```bash
helm install cms ./infrastructure/helm/cms \
  -f infrastructure/helm/cms/values-minikube.yaml \
  -n cms --create-namespace
```

### Install with K3s-Specific Values

```bash
helm install cms ./infrastructure/helm/cms \
  -f infrastructure/helm/cms/values-k3s.yaml \
  -n cms --create-namespace
```

### Key Helm Values

| Value | Default | Description |
|-------|---------|-------------|
| `replicaCount` | `1` | Number of pod replicas per service |
| `image.tag` | `latest` | Docker image tag for all CMS services |
| `resources.requests.cpu` | `100m` | CPU request per pod |
| `resources.requests.memory` | `128Mi` | Memory request per pod |
| `resources.limits.cpu` | `500m` | CPU limit per pod |
| `resources.limits.memory` | `512Mi` | Memory limit per pod |
| `ingress.enabled` | `true` | Whether to create Ingress resources |
| `ingress.className` | `nginx` | Ingress class (`nginx` for Minikube, `traefik` for K3s) |
| `floci.enabled` | `true` | Deploy Floci (LocalStack) as part of the release |

Override any value at install time with `--set`:

```bash
helm install cms ./infrastructure/helm/cms \
  -n cms --create-namespace \
  --set replicaCount=3 \
  --set image.tag=v1.2.0
```

### Upgrading

```bash
helm upgrade cms ./infrastructure/helm/cms -n cms
```

To upgrade with a new values file:

```bash
helm upgrade cms ./infrastructure/helm/cms \
  -f infrastructure/helm/cms/values-production.yaml -n cms
```

### Rollback

Roll back to a previous release revision:

```bash
helm rollback cms 1 -n cms
```

View release history to find the target revision:

```bash
helm history cms -n cms
```

---

## 6. Monitoring

### View Logs for a Single Service

```bash
kubectl logs -f deployment/consent-api -n cms
```

### View Logs for All CMS Services

```bash
kubectl logs -f -l app.kubernetes.io/part-of=cms -n cms
```

### Resource Usage

Requires the metrics-server addon (enabled by default in Minikube after `minikube addons enable metrics-server`):

```bash
kubectl top pods -n cms
```

### Kubernetes Dashboard (Minikube)

```bash
minikube dashboard
```

This opens the Kubernetes dashboard in your default browser, providing a graphical overview of workloads, pods, services, and events.

### Cluster Events

View recent events sorted by timestamp to diagnose scheduling and runtime issues:

```bash
kubectl get events -n cms --sort-by=.metadata.creationTimestamp
```

To watch events in real time:

```bash
kubectl get events -n cms --watch
```

---

## 7. Scaling

### Horizontal Pod Autoscaler (HPA)

The following services have HPA resources pre-configured:

- **consent-api** -- scales based on CPU utilization
- **notification-service** -- scales based on CPU utilization
- **consent-processor** -- scales based on CPU and memory utilization

### View HPA Status

```bash
kubectl get hpa -n cms
```

Example output:

```
NAME                    REFERENCE                          TARGETS   MINPODS   MAXPODS   REPLICAS   AGE
consent-api             Deployment/consent-api             45%/70%   2         10        3          12m
notification-service    Deployment/notification-service    30%/70%   2         8         2          12m
consent-processor       Deployment/consent-processor       60%/80%   1         5         2          12m
```

### Manual Scaling

Override the current replica count for any deployment:

```bash
kubectl scale deployment consent-api --replicas=5 -n cms
```

> **Note:** Manual scaling is overridden by HPA once the autoscaler reconciles. To hold a fixed replica count, delete or suspend the corresponding HPA.

### Scaling Guidelines

| Service | Min Replicas | Max Replicas | Notes |
|---------|-------------|-------------|-------|
| consent-api | 2 | 10 | Primary user-facing service; scale aggressively under load |
| notification-service | 2 | 8 | Bursty during batch consent campaigns |
| consent-processor | 1 | 5 | CPU-intensive; scale based on queue depth |
| incident-detector | 1 | 3 | Lightweight; rarely needs more than 1 replica |
| incident-bridge | 1 | 3 | Scales with incident volume |
| consent-ui | 1 | 5 | Static assets; scale only under extreme traffic |

---

## 8. Teardown

### Docker Compose

Stop and remove all containers, networks, and volumes:

```bash
make down
```

Or manually:

```bash
docker-compose down -v
```

### Full Cleanup (Docker Compose)

Remove volumes, built images, and all local data:

```bash
make clean
```

### Minikube

Delete only the CMS namespace (preserves the cluster):

```bash
kubectl delete namespace cms
```

Delete the entire Minikube cluster:

```bash
minikube delete
```

### K3s

Delete the CMS namespace:

```bash
sudo k3s kubectl delete namespace cms
```

Uninstall K3s entirely:

```bash
/usr/local/bin/k3s-uninstall.sh
```

### Helm

Uninstall the Helm release (removes all CMS resources from the namespace):

```bash
helm uninstall cms -n cms
```

To also delete the namespace:

```bash
helm uninstall cms -n cms
kubectl delete namespace cms
```
