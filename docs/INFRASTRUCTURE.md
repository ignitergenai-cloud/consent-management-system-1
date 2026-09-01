# Consent Management System -- Infrastructure & Local AWS Setup

## 1. Overview

The Consent Management System (CMS) uses local AWS emulation so that all development
and testing can happen without a real AWS account. Every AWS service the application
depends on runs behind a single endpoint at **http://localhost:4566**.

Two emulators are supported:

| Emulator | Role | Docker Image |
|-----------|------------|-------------------------------|
| **Floci** | Primary | `floci/floci:latest` |
| **LocalStack** | Fallback | `localstack/localstack:latest` |

Floci is the default choice. LocalStack is available as a drop-in replacement when
needed. Both expose the same port and accept the same AWS CLI commands, so application
code and bootstrap scripts work identically against either backend.

---

## 2. Floci

[Floci](https://github.com/floci/floci) is an MIT-licensed, lightweight local AWS
emulator built on **GraalVM + Quarkus**.

### Key characteristics

| Metric | Value |
|-----------------|-------------------------------|
| Startup time | ~24 ms |
| Idle memory | ~13 MiB |
| Services | 45+ on a single port (4566) |
| Docker image | `floci/floci:latest` |
| License | MIT |

Floci is a drop-in replacement for LocalStack with significantly lower resource
usage. It supports every service the CMS requires, including:

- **DynamoDB** -- primary data store
- **SNS** -- event fan-out
- **SQS** -- queue-based processing
- **SES** -- transactional email
- **S3** -- template storage

### Running Floci

```bash
docker run -d \
  --name floci \
  -p 4566:4566 \
  -v floci-data:/data \
  floci/floci:latest
```

---

## 3. LocalStack Fallback

Use LocalStack instead of Floci when:

- Floci has a compatibility issue with a specific AWS API call.
- The team has an existing LocalStack configuration or preference.
- You need a service that Floci does not yet emulate.

### Key characteristics

| Metric | Value |
|------------------|-------------------------------|
| Docker image | `localstack/localstack:latest` |
| Port | 4566 (same as Floci) |
| Idle memory | ~512 MB+ |
| Service coverage | Broader than Floci |

### Running LocalStack

```bash
docker run -d \
  --name localstack \
  -p 4566:4566 \
  -v localstack-data:/var/lib/localstack \
  localstack/localstack:latest
```

> **Note:** The same AWS CLI commands, bootstrap scripts, and application
> configuration work against both Floci and LocalStack. No code changes are
> required when switching between them.

---

## 4. AWS Resources

The bootstrap scripts create the following resources.

### 4.1 DynamoDB

| Property | Value |
|---------------|-------------------------------|
| Table name | `cms-consents` |
| Partition key | `PK` (String) |
| Sort key | `SK` (String) |
| Billing mode | `PAY_PER_REQUEST` |

**Global Secondary Indexes (GSIs):**

| GSI Name | Partition Key | Sort Key |
|----------|---------------|----------|
| GSI1 | `GSI1PK` (String) | `GSI1SK` (String) |
| GSI2 | `GSI2PK` (String) | `GSI2SK` (String) |
| GSI3 | `GSI3PK` (String) | `GSI3SK` (String) |

### 4.2 SNS Topics (7)

| # | Topic Name |
|---|-------------------------------|
| 1 | `cms-consent-events` |
| 2 | `cms-notification-commands` |
| 3 | `cms-notification-events` |
| 4 | `cms-consent-processing-events` |
| 5 | `cms-incident-events` |
| 6 | `mims-inbound-incidents` |
| 7 | `cms-incident-commands` |

### 4.3 SQS Queues (14 = 7 main + 7 DLQ)

Each main queue has a corresponding dead-letter queue (DLQ).

| # | Main Queue | Dead-Letter Queue |
|---|----------------------------------------|----------------------------------------|
| 1 | `cms-consent-processor-queue` | `cms-consent-processor-dlq` |
| 2 | `cms-notification-queue` | `cms-notification-dlq` |
| 3 | `cms-notification-events-queue` | `cms-notification-events-dlq` |
| 4 | `cms-incident-detector-queue` | `cms-incident-detector-dlq` |
| 5 | `cms-incident-bridge-queue` | `cms-incident-bridge-dlq` |
| 6 | `cms-mims-command-queue` | `cms-mims-command-dlq` |
| 7 | `cms-internal-command-queue` | `cms-internal-command-dlq` |

### 4.4 SNS-SQS Subscriptions (7)

| # | SNS Topic | SQS Queue |
|---|-------------------------------------|--------------------------------------|
| 1 | `cms-consent-events` | `cms-consent-processor-queue` |
| 2 | `cms-notification-commands` | `cms-notification-queue` |
| 3 | `cms-notification-events` | `cms-notification-events-queue` |
| 4 | `cms-consent-processing-events` | `cms-incident-detector-queue` |
| 5 | `cms-notification-events` | `cms-incident-detector-queue` |
| 6 | `cms-incident-events` | `cms-incident-bridge-queue` |
| 7 | `cms-incident-commands` | `cms-mims-command-queue` |

### 4.5 S3

| Resource | Name |
|----------|----------------|
| Bucket | `cms-templates` |

### 4.6 SES

| Resource | Value |
|-------------------|----------------------|
| Verified identity | `noreply@cms.local` |

---

## 5. Bootstrap Process

Infrastructure is created by shell scripts located in `infrastructure/init-aws.d/`.
The scripts run in alphanumeric order and are **idempotent** -- they are safe to
re-run at any time without side effects.

| Order | Script | Purpose |
|-------|------------------------------|-----------------------------------------------|
| 1 | `01-create-dynamodb.sh` | Creates the `cms-consents` DynamoDB table with all three GSIs |
| 2 | `02-create-sns-topics.sh` | Creates all 7 SNS topics |
| 3 | `03-create-sqs-queues.sh` | Creates 14 SQS queues (7 main + 7 DLQ) |
| 4 | `04-create-subscriptions.sh` | Subscribes SQS queues to their SNS topics |
| 5 | `05-create-s3.sh` | Creates the `cms-templates` S3 bucket |
| 6 | `06-create-ses.sh` | Verifies the SES email identity |
| 7 | `07-seed-data.sh` | Loads optional seed/test data |

### Running the bootstrap

```bash
# Run all scripts in order
for script in infrastructure/init-aws.d/*.sh; do
  echo "Running $script ..."
  bash "$script"
done
```

Or, if using Docker Compose, the init container runs the scripts automatically on
startup.

---

## 6. AWS CLI Configuration

Configure the AWS CLI to point at the local emulator (Floci or LocalStack):

```bash
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_DEFAULT_REGION=us-east-1
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
```

> The access key and secret can be any non-empty string. Both Floci and LocalStack
> accept dummy credentials.

### Verification commands

```bash
# List DynamoDB tables
aws dynamodb list-tables

# Describe the consents table
aws dynamodb describe-table --table-name cms-consents

# List SNS topics
aws sns list-topics

# List SQS queues
aws sqs list-queues

# List S3 buckets
aws s3 ls

# List SES identities
aws ses list-identities
```

Each command automatically uses the endpoint, region, and credentials set above.

---

## 7. Verifying Infrastructure

A verification script is provided to confirm that all resources were created
correctly.

### Running the verifier

```bash
python infrastructure/verify-infrastructure.py
```

### What it checks

| Check | Description |
|-------|-------------|
| DynamoDB table | `cms-consents` exists with `PK`/`SK` key schema |
| DynamoDB GSIs | GSI1, GSI2, and GSI3 are present and ACTIVE |
| SNS topics | All 7 topics exist |
| SQS queues | All 14 queues (7 main + 7 DLQ) exist |
| SNS-SQS subscriptions | All 7 subscriptions are in place and confirmed |
| S3 bucket | `cms-templates` bucket exists |
| SES identity | `noreply@cms.local` is verified |

### Sample output

```
Verifying CMS infrastructure on http://localhost:4566 ...

[OK] DynamoDB table 'cms-consents' exists
[OK]   GSI 'GSI1' is ACTIVE
[OK]   GSI 'GSI2' is ACTIVE
[OK]   GSI 'GSI3' is ACTIVE
[OK] SNS topic 'cms-consent-events' exists
[OK] SNS topic 'cms-notification-commands' exists
[OK] SNS topic 'cms-notification-events' exists
[OK] SNS topic 'cms-consent-processing-events' exists
[OK] SNS topic 'cms-incident-events' exists
[OK] SNS topic 'mims-inbound-incidents' exists
[OK] SNS topic 'cms-incident-commands' exists
[OK] SQS queue 'cms-consent-processor-queue' exists
[OK] SQS queue 'cms-consent-processor-dlq' exists
[OK] SQS queue 'cms-notification-queue' exists
[OK] SQS queue 'cms-notification-dlq' exists
[OK] SQS queue 'cms-notification-events-queue' exists
[OK] SQS queue 'cms-notification-events-dlq' exists
[OK] SQS queue 'cms-incident-detector-queue' exists
[OK] SQS queue 'cms-incident-detector-dlq' exists
[OK] SQS queue 'cms-incident-bridge-queue' exists
[OK] SQS queue 'cms-incident-bridge-dlq' exists
[OK] SQS queue 'cms-mims-command-queue' exists
[OK] SQS queue 'cms-mims-command-dlq' exists
[OK] SQS queue 'cms-internal-command-queue' exists
[OK] SQS queue 'cms-internal-command-dlq' exists
[OK] 7 SNS-SQS subscriptions confirmed
[OK] S3 bucket 'cms-templates' exists
[OK] SES identity 'noreply@cms.local' is verified

All checks passed (32/32).
```

---

## 8. Resource ARN/URL Reference

All ARNs and URLs use the local emulator's account ID `000000000000` and region
`us-east-1`.

### DynamoDB

| Resource | ARN |
|----------|-----|
| cms-consents table | `arn:aws:dynamodb:us-east-1:000000000000:table/cms-consents` |

### SNS Topic ARNs

| Topic | ARN |
|-------|-----|
| cms-consent-events | `arn:aws:sns:us-east-1:000000000000:cms-consent-events` |
| cms-notification-commands | `arn:aws:sns:us-east-1:000000000000:cms-notification-commands` |
| cms-notification-events | `arn:aws:sns:us-east-1:000000000000:cms-notification-events` |
| cms-consent-processing-events | `arn:aws:sns:us-east-1:000000000000:cms-consent-processing-events` |
| cms-incident-events | `arn:aws:sns:us-east-1:000000000000:cms-incident-events` |
| mims-inbound-incidents | `arn:aws:sns:us-east-1:000000000000:mims-inbound-incidents` |
| cms-incident-commands | `arn:aws:sns:us-east-1:000000000000:cms-incident-commands` |

### SQS Queue URLs

| Queue | URL |
|-------|-----|
| cms-consent-processor-queue | `http://localhost:4566/000000000000/cms-consent-processor-queue` |
| cms-consent-processor-dlq | `http://localhost:4566/000000000000/cms-consent-processor-dlq` |
| cms-notification-queue | `http://localhost:4566/000000000000/cms-notification-queue` |
| cms-notification-dlq | `http://localhost:4566/000000000000/cms-notification-dlq` |
| cms-notification-events-queue | `http://localhost:4566/000000000000/cms-notification-events-queue` |
| cms-notification-events-dlq | `http://localhost:4566/000000000000/cms-notification-events-dlq` |
| cms-incident-detector-queue | `http://localhost:4566/000000000000/cms-incident-detector-queue` |
| cms-incident-detector-dlq | `http://localhost:4566/000000000000/cms-incident-detector-dlq` |
| cms-incident-bridge-queue | `http://localhost:4566/000000000000/cms-incident-bridge-queue` |
| cms-incident-bridge-dlq | `http://localhost:4566/000000000000/cms-incident-bridge-dlq` |
| cms-mims-command-queue | `http://localhost:4566/000000000000/cms-mims-command-queue` |
| cms-mims-command-dlq | `http://localhost:4566/000000000000/cms-mims-command-dlq` |
| cms-internal-command-queue | `http://localhost:4566/000000000000/cms-internal-command-queue` |
| cms-internal-command-dlq | `http://localhost:4566/000000000000/cms-internal-command-dlq` |

### S3

| Resource | ARN |
|----------|-----|
| cms-templates bucket | `arn:aws:s3:::cms-templates` |

### SES

| Resource | ARN |
|----------|-----|
| noreply@cms.local identity | `arn:aws:ses:us-east-1:000000000000:identity/noreply@cms.local` |

---

## 9. Switching Between Floci and LocalStack

To switch emulators, change the `LOCALSTACK_IMAGE` variable in your `.env` file or
use a Docker Compose override.

### Option A: `.env` file

```bash
# Use Floci (default)
LOCALSTACK_IMAGE=floci/floci:latest

# Use LocalStack
LOCALSTACK_IMAGE=localstack/localstack:latest
```

### Option B: Docker Compose override

```yaml
# docker-compose.override.yml
services:
  localstack:
    image: localstack/localstack:latest
```

### What stays the same

| Aspect | Floci | LocalStack |
|----------------------|-------------------------------|-------------------------------|
| Endpoint URL | `http://localhost:4566` | `http://localhost:4566` |
| AWS CLI commands | Identical | Identical |
| Bootstrap scripts | Same scripts, same order | Same scripts, same order |
| Application config | No changes needed | No changes needed |
| Credentials | `test` / `test` | `test` / `test` |

After switching, restart the container and re-run the bootstrap scripts:

```bash
docker compose down
docker compose up -d
# Wait for the emulator to be ready, then bootstrap
for script in infrastructure/init-aws.d/*.sh; do
  bash "$script"
done
```

---

## 10. Persistent Data

By default, emulator data is stored in a Docker volume so it survives container
restarts.

### Floci volume mapping

```yaml
# docker-compose.yml
services:
  localstack:
    image: floci/floci:latest
    ports:
      - "4566:4566"
    volumes:
      - floci-data:/data

volumes:
  floci-data:
```

### LocalStack volume mapping

```yaml
# docker-compose.yml
services:
  localstack:
    image: localstack/localstack:latest
    ports:
      - "4566:4566"
    volumes:
      - localstack-data:/var/lib/localstack

volumes:
  localstack-data:
```

### Resetting data

To wipe all local AWS data and start fresh:

```bash
# Stop the container
docker compose down

# Remove the volume
docker volume rm <project>_floci-data    # for Floci
docker volume rm <project>_localstack-data  # for LocalStack

# Start fresh
docker compose up -d
```

After removing the volume, re-run the bootstrap scripts to recreate all resources.

### Ephemeral mode

If you do not want data to persist between restarts, remove the `volumes` section
from `docker-compose.yml`. Each container start will begin with a clean slate and
the bootstrap scripts will recreate everything.
