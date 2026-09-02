# KB-001: DynamoDB Table Not Found — ResourceNotFoundException

**Article ID:** KB-001  
**Application:** consent-management-system / consent-api  
**Severity:** CRITICAL  
**Related Incident:** Q1VCBWZ6D0NL1N  
**Last Updated:** 2026-09-02

---

## Summary

The `consent-api` service throws a `ResourceNotFoundException` and returns HTTP 500 on every `POST /api/v1/consents` request when the DynamoDB table `cms-consents` does not exist or is not reachable. This causes a 100% consent creation failure rate, which also silently halts the downstream SNS → SQS pipeline because no events are published upstream.

---

## Observed Symptoms

| Signal | Detail |
|---|---|
| Error log | `ResourceNotFoundException: DynamoDB table 'cms-consents' not found` |
| Stack trace origin | `consent_api/services/consent_service.py`, line 62, `create_consent` |
| HTTP response | `POST /api/v1/consents` → 500 in ~1–2 ms (instant fail, no DB round-trip) |
| Downstream effect | `SNS publish skipped — upstream consent creation failed before reaching SNS` |
| Queue signal | `cms-consent-processing-queue` idle warning after 15 minutes of no new PENDING events |
| Health check | `GET /api/v1/health` → 200 (liveness passes; it does NOT check DynamoDB) |

> **Important:** The `/api/v1/health` liveness endpoint does **not** verify DynamoDB connectivity. The service appears healthy while consent creation is completely broken. The readiness probe at `/api/v1/health/ready` does check DynamoDB and will return non-200 — monitor both endpoints.

---

## Root Cause

The DynamoDB table `cms-consents` was either:

1. **Never provisioned** — infrastructure init scripts (`infrastructure/localstack/init-aws.d/01-dynamodb.sh`) did not run or failed silently.
2. **Deleted** — manual or automated teardown removed the table.
3. **Wrong endpoint/region** — `AWS_ENDPOINT_URL` or `AWS_DEFAULT_REGION` misconfiguration causes the SDK to target a different environment where the table does not exist.
4. **Chaos mode active on the microservices stack** — `services/consent-api/src/consent_api/services/consent_service.py` contains a hardcoded chaos mode block (lines 57–67) that raises `RuntimeError("DynamoDB table 'cms-consents' not found")` unconditionally when `CHAOS_MODE=true`.

The error is raised before any SNS publish attempt, so no `ConsentRequested` events enter the pipeline. This causes the `cms-consent-processing-queue` to go idle and any consent-processor workers to sit idle consuming no messages.

---

## Impact

- **All consent creation requests fail** — 100% failure rate on `POST /api/v1/consents`.
- **No SNS events published** — downstream consent-processor, incident-detector, and notification-service receive zero new work.
- **Processing queue idle** — `cms-consent-processing-queue` shows no new PENDING events; idle warning fires after 15 minutes.
- **No data loss on existing consents** — read operations (`GET /api/v1/consents`, analytics) continue to function if the table exists for reads.
- **PagerDuty alert fires** — auto-incident creation triggers on first 500 (rate-limited to one alert per 5 minutes per service+path).

---

## Diagnosis Steps

### Step 1 — Confirm the error
Search New Relic Logs:
```
service:consent-api level:CRITICAL ResourceNotFoundException
```
Or filter by `incident_id` if known.

### Step 2 — Check DynamoDB table existence
```bash
# LocalStack / local dev
aws --endpoint-url http://localhost:4566 dynamodb describe-table \
    --table-name cms-consents

# AWS production
aws dynamodb describe-table --table-name cms-consents --region <region>
```
Expected: `TableStatus: ACTIVE`. If the command returns `ResourceNotFoundException`, the table does not exist.

### Step 3 — Check chaos mode
```bash
grep CHAOS_MODE .env
# or check the running container:
docker exec consent-api env | grep CHAOS_MODE
```
If `CHAOS_MODE=true`, the microservices consent-api will always raise this error regardless of actual DynamoDB state.

### Step 4 — Check readiness probe
```bash
curl -s http://localhost:8000/api/v1/health/ready
```
Non-200 confirms DynamoDB is unreachable from the service.

### Step 5 — Verify queue is idle
```bash
aws --endpoint-url http://localhost:4566 sqs get-queue-attributes \
    --queue-url http://localhost:4566/000000000000/cms-consent-processing-queue \
    --attribute-names ApproximateNumberOfMessages
```

---

## Resolution

### If chaos mode is the cause (microservices stack):
```bash
# In .env:
CHAOS_MODE=false
# Restart the consent-api service:
docker compose restart consent-api
```

### If the DynamoDB table is missing (local/staging):
```bash
# Re-run the infrastructure init script:
bash infrastructure/localstack/init-aws.d/01-dynamodb.sh
# Verify:
aws --endpoint-url http://localhost:4566 dynamodb list-tables
```

### If the DynamoDB table is missing (production AWS):
1. Check AWS Console → DynamoDB → Tables for the target region.
2. If deleted, restore from Point-in-Time Recovery (PITR) if enabled, or re-create via Terraform/CloudFormation.
3. Validate all GSIs are present: `GSI1`, `GSI2`, `GSI3`.
4. Re-check `AWS_ENDPOINT_URL` and `AWS_DEFAULT_REGION` in service environment.

### If endpoint/region misconfiguration:
```bash
# Check current config in shared/config.py defaults:
# aws_endpoint_url (should be empty for production AWS)
# aws_region (must match where table was created)
```
Correct the environment variable and redeploy.

---

## Prevention

- Add DynamoDB table existence to the **readiness probe** response and ensure load balancers use `/api/v1/health/ready`, not `/api/v1/health`.
- Add a startup check that calls `describe_table` and refuses to start if the table is missing.
- Never deploy with `CHAOS_MODE=true` in production. Add a CI check that fails if `.env` contains `CHAOS_MODE=true`.
- Enable DynamoDB PITR on the `cms-consents` table in all non-ephemeral environments.
- Add a CloudWatch / New Relic alert on `ApproximateNumberOfMessages` for `cms-consent-processing-queue` going to zero for > 10 minutes during business hours.

---

## Related Articles
- KB-002: Consent Creation Intermittent 500 Failures (Chaos Mode — Vercel)
- KB-003: SNS Publish Failures and Processing Queue Idle
