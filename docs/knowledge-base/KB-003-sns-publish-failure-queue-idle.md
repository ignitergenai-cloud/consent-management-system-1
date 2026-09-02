# KB-003: SNS Publish Failures and Processing Queue Idle

**Article ID:** KB-003  
**Application:** consent-management-system / consent-api / consent-processor  
**Severity:** HIGH  
**Affected Components:** SNS topic `cms-consent-events`, SQS queue `cms-consent-processing-queue`  
**Last Updated:** 2026-09-02

---

## Summary

When `consent-api` fails to create a consent record (for any reason — see KB-001, KB-002), it never reaches the SNS publish step. The log entry reads: *"SNS publish skipped — upstream consent creation failed before reaching SNS."* This causes the `cms-consent-processing-queue` to go idle. After 15 minutes of no new messages, the consent-processor emits an idle warning. This pattern can also occur if SNS itself is unreachable while the DB write succeeds — in that case the consent is created but never processed.

---

## Observed Symptoms

| Signal | Detail |
|---|---|
| Error log | `SNS publish skipped — upstream consent creation failed before reaching SNS` |
| Log field | `topic: cms-consent-events`, `reason: consent_service.create_consent raised RuntimeError` |
| Queue warning | `Consent processor queue idle — no new PENDING events received in 15 minutes` |
| Queue name | `cms-consent-processing-queue` |
| Side effect | Consents stuck in PENDING state with no notification sent to customer |
| Side effect | incident-detector receives no new events → anomaly detection may not fire on zero-event windows |

---

## Root Cause Scenarios

### Scenario A — Upstream consent creation failure (most common)
The consent record was never written to the database. `create_consent` raised an exception (DynamoDB not found, chaos mode, validation error) before SNS publish was attempted. The SNS skip is a correct side effect — not a separate failure.

**Fix:** Resolve the upstream creation failure (see KB-001 or KB-002). SNS publishes will resume automatically.

### Scenario B — Consent written to DB but SNS publish failed
The consent record exists in the DB (status=PENDING) but the `ConsentRequested` event was never published to `cms-consent-events`. This consent is orphaned — it will never transition through the workflow.

**Indicators:**
- No "SNS publish skipped" log (that message is from the failure path)
- A consent record exists with status=PENDING and no corresponding processor log
- SNS publish error in `consent-api` logs: `botocore.exceptions.ClientError`, `sns.publish` failing

**Fix:** See Resolution → Scenario B below.

### Scenario C — SNS/SQS infrastructure down (LocalStack or AWS)
The messaging layer itself is unavailable. All services that depend on SQS consumers (consent-processor, notification-service, incident-detector) are stalled.

**Indicators:**
- Multiple queues idle simultaneously
- `botocore.exceptions.EndpointResolutionError` or connection refused in consumer logs
- LocalStack container not running (local dev)

---

## Impact

- **Consents stuck in PENDING** — customers never receive notification requests; consent collection stalls.
- **Notification pipeline stalled** — no `SendNotification` commands reach notification-service.
- **Incident detection blind** — incident-detector receives no events to analyze during the outage window.
- **No DLQ growth** — because no messages are being enqueued, the DLQ does not fill up; queue silence is the signal.

---

## Diagnosis Steps

### Step 1 — Identify which scenario applies

Check for the SNS skip log:
```
service:consent-api "SNS publish skipped"
```
If present → **Scenario A** (upstream creation failure). Go to KB-001 or KB-002.

Check for orphaned PENDING consents (DB query, Vercel/Supabase mode):
```sql
SELECT id, created_at, status, customer_id 
FROM consents 
WHERE status = 'PENDING' 
  AND created_at < NOW() - INTERVAL '30 minutes'
ORDER BY created_at ASC;
```
PENDING consents older than 30 minutes with no processor log → **Scenario B**.

Check SNS/SQS health:
```bash
# LocalStack:
aws --endpoint-url http://localhost:4566 sns list-topics
aws --endpoint-url http://localhost:4566 sqs list-queues

# AWS:
aws sns list-topics --region <region>
aws sqs list-queues --region <region>
```

### Step 2 — Check queue depth
```bash
aws --endpoint-url http://localhost:4566 sqs get-queue-attributes \
    --queue-url http://localhost:4566/000000000000/cms-consent-processing-queue \
    --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible

# Also check DLQ:
aws --endpoint-url http://localhost:4566 sqs get-queue-attributes \
    --queue-url http://localhost:4566/000000000000/cms-consent-processing-queue-dlq \
    --attribute-names ApproximateNumberOfMessages
```

### Step 3 — Verify SNS subscriptions are intact
```bash
aws --endpoint-url http://localhost:4566 sns list-subscriptions-by-topic \
    --topic-arn arn:aws:sns:us-east-1:000000000000:cms-consent-events
```
Expected: two subscriptions — `cms-consent-processing-queue` and `cms-incident-detection-queue`.

### Step 4 — Check consent-processor consumer logs
```
service:consent-processor "polling" OR "consumer" OR "idle"
```
A healthy processor logs each batch poll. If logs stop, the consumer loop may have crashed.

---

## Resolution

### Scenario A — Fix upstream failure
Resolve KB-001 (DynamoDB not found) or KB-002 (chaos mode). New consent creation requests will resume publishing to SNS normally.

### Scenario B — Re-publish orphaned PENDING consents
For consents that were written to DB but never published to SNS:

1. Identify orphaned consents (see Step 1 query above).
2. For each orphaned consent, manually publish a `ConsentRequested` event:
   ```bash
   aws --endpoint-url http://localhost:4566 sns publish \
     --topic-arn arn:aws:sns:us-east-1:000000000000:cms-consent-events \
     --message '{
       "version": "1.0",
       "event_id": "<new-uuid>",
       "event_type": "ConsentRequested",
       "source": "ops-recovery",
       "timestamp": "<ISO-timestamp>",
       "correlation_id": "<new-uuid>",
       "payload": {
         "consent_id": "<consent-id>",
         "customer_id": "<customer-id>",
         "channel": "<channel>",
         "consent_type": "<type>"
       }
     }'
   ```
3. Alternatively, if many consents are affected, use the bulk endpoint (`POST /api/v1/consents/bulk`) after fixing the underlying issue — but note this creates new records, not re-drives existing ones.

### Scenario C — Restore SNS/SQS infrastructure
```bash
# LocalStack (local dev):
docker compose restart floci
# Wait for container to be healthy, then re-run init scripts:
bash infrastructure/localstack/init-aws.d/02-sns-topics.sh
bash infrastructure/localstack/init-aws.d/03-sqs-queues.sh
bash infrastructure/localstack/init-aws.d/04-sns-subscriptions.sh

# Restart consumers to reconnect:
docker compose restart consent-processor notification-service incident-detector
```

For AWS production — check SNS/SQS service health in AWS Console and review IAM permissions for the service role.

---

## Prevention

- Add an **SNS publish confirmation log** after successful publish in `consent-api`. Its absence alongside a consent creation success log is a direct signal for Scenario B.
- Implement a **reconciliation cron job** that identifies consents in PENDING status for > 20 minutes and re-drives them into the pipeline. The existing `check-expired-consents` cron is a reference pattern.
- Add a **New Relic alert** on `cms-consent-processing-queue` `ApproximateNumberOfMessages` = 0 for > 10 minutes during business hours (08:00–20:00 UTC).
- Consider wrapping the `create_consent` + `sns.publish` in an outbox pattern (write event to DB atomically with the consent record) to eliminate the gap between Scenario A and B.

---

## Related Articles
- KB-001: DynamoDB Table Not Found
- KB-002: Consent Creation Intermittent 500 Failures
- KB-005: Processing Queue DLQ Growth (to be created)
