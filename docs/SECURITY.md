# Consent Management System -- Security Design Document

## 1. Overview

The Consent Management System handles **Personally Identifiable Information (PII)**, including phone numbers, email addresses, and consent records. Protecting this data is a primary concern across every layer of the architecture.

This document describes the **defense-in-depth** approach applied to the system. Security controls are not concentrated at a single boundary; instead, they are enforced across all layers:

| Layer | Controls |
|---|---|
| **Application** | Input validation, authentication, authorization, audit logging |
| **Container** | Non-root users, read-only filesystems, minimal base images |
| **Orchestration** | Network policies, RBAC, pod security standards, secrets management |
| **Data** | Encryption at rest and in transit, token hashing, PII masking in logs |

A compromise at any single layer should not result in full exposure of customer data. Each layer independently restricts what an attacker can access, escalate, or exfiltrate.

---

## 2. Authentication & Authorization

### Local Development

For development simplicity, **no authentication is enforced** in local environments. All API endpoints are accessible without credentials. This keeps the developer feedback loop fast and avoids the need to manage tokens or certificates locally.

> **Warning:** Never expose the local development configuration to any network beyond `localhost`.

### Production Recommendations

| Mechanism | Use Case |
|---|---|
| **JWT Tokens** | API access from `consent-ui` to `consent-api` |
| **API Keys** | Service-to-service communication between backend services |
| **OAuth 2.0 / OIDC** | User authentication for operators and administrators |
| **RBAC** | Fine-grained permission control per role |

#### Role-Based Access Control (RBAC)

| Role | Permissions |
|---|---|
| **Admin** | Full access: create, read, update, delete consents; manage users; view audit logs; system configuration |
| **Operator** | Read all consents + create new consents; cannot delete or modify system configuration |
| **Viewer** | Read-only access to consents and dashboards |
| **System** | Service-to-service role; scoped to specific inter-service operations only |

### Customer Consent Response Endpoint

The customer-facing consent response endpoint uses **token-based authentication** that does not require a login:

- A `response_token` is included in the URL sent to the customer (e.g., `/respond?token=<response_token>`).
- No username or password is required. The token itself authorizes the action.
- Tokens are **single-use** -- once a customer responds, the token is invalidated.
- Tokens are **time-limited** (72-hour default expiry).
- See [Section 3: Response Tokens](#response-tokens) for cryptographic details.

---

## 3. Data Protection

### Data Classification

All consent data is classified as **PII (Personally Identifiable Information)**. This includes:

- Phone numbers
- Email addresses
- Consent records linking identifiable individuals to specific purposes

### Data at Rest

| Store | Encryption |
|---|---|
| **DynamoDB** | Encryption at rest enabled by default (AWS-managed AES-256) |
| **S3 Buckets** | Server-Side Encryption with S3-managed keys (SSE-S3) |

### Data in Transit

| Environment | Protocol |
|---|---|
| **Production** | TLS 1.2+ required for all traffic between services, clients, and AWS resources |
| **Local Development** | HTTP (acceptable for development against LocalStack on `localhost`) |

### Response Tokens

Response tokens are the sole authentication mechanism for the customer consent response flow. They are treated as sensitive credentials:

- **Generation:** Cryptographically random UUIDs (`uuid4`), providing 122 bits of randomness.
- **Single-use:** A token is invalidated immediately after a successful consent response.
- **Time-limited:** Default expiry of **72 hours** from creation. Configurable per deployment.
- **Storage:** Tokens are **stored hashed** in DynamoDB (SHA-256). The plaintext token exists only in the URL sent to the customer and is never persisted.

### PII Handling

- Phone numbers and email addresses are stored in the `contact_info` attribute of the consent record.
- All access to PII fields is logged via the **audit trail** (see [Section 7](#7-audit-trail)), using the `ConsentHistory` entity.
- **No sensitive data in logs:** Phone numbers and emails are masked in structured log output (e.g., `+1******1234`, `j***@example.com`).

---

## 4. Container Security

All services follow container hardening best practices to minimize the attack surface.

### Principles

| Principle | Implementation |
|---|---|
| **Non-root execution** | All containers run as `USER 1000:1000` in their Dockerfiles |
| **Read-only root filesystem** | `readOnlyRootFilesystem: true` in Kubernetes SecurityContext |
| **No privileged containers** | `privileged: false` enforced on all pods |
| **No privilege escalation** | `allowPrivilegeEscalation: false` on all containers |
| **Minimal base images** | `python:3.12-slim` for backend services; `nginx:alpine` for frontend |
| **No unnecessary packages** | Only runtime dependencies are installed; build tools are excluded |
| **Multi-stage builds** | Build dependencies are discarded in the final image stage |

### Example Kubernetes SecurityContext

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: consent-api
spec:
  securityContext:
    runAsUser: 1000
    runAsGroup: 1000
    fsGroup: 1000
    runAsNonRoot: true
  containers:
    - name: consent-api
      image: consent-api:latest
      securityContext:
        allowPrivilegeEscalation: false
        privileged: false
        readOnlyRootFilesystem: true
        capabilities:
          drop:
            - ALL
      volumeMounts:
        - name: tmp
          mountPath: /tmp
  volumes:
    - name: tmp
      emptyDir: {}
```

---

## 5. Kubernetes Security

### Network Policies

The cluster enforces a **default-deny-all-ingress** posture. Each service explicitly declares what traffic it accepts.

| Service | Ingress Allowed From | Notes |
|---|---|---|
| **consent-ui** | Ingress controller only | Public-facing frontend |
| **consent-api** | `consent-ui`, ingress controller | API gateway for all consent operations |
| **consent-processor** | None (no external ingress) | Driven exclusively by SQS messages |
| **notification-service** | None (no external ingress) | Driven exclusively by SQS messages |
| **incident-detector** | None (no external ingress) | Driven exclusively by SQS messages |
| **incident-bridge** | None (no external ingress) | Driven exclusively by SQS messages |
| **All services** | -- | Egress allowed to LocalStack/AWS endpoint (port 4566) |

#### Example NetworkPolicy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all-ingress
  namespace: consent-system
spec:
  podSelector: {}
  policyTypes:
    - Ingress

---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-consent-api-ingress
  namespace: consent-system
spec:
  podSelector:
    matchLabels:
      app: consent-api
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: consent-ui
        - podSelector:
            matchLabels:
              app: ingress-controller
      ports:
        - protocol: TCP
          port: 8000

---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-egress-to-localstack
  namespace: consent-system
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: localstack
      ports:
        - protocol: TCP
          port: 4566
```

### Secrets Management

| Environment | Mechanism |
|---|---|
| **Local Development** | Kubernetes Secrets (base64-encoded, acceptable for dev) |
| **Production** | AWS Secrets Manager, HashiCorp Vault, or Sealed Secrets |

Production secrets must **never** be stored in plaintext in version control, Helm values, or ConfigMaps.

### RBAC

- Each service runs under a **dedicated ServiceAccount** with minimal permissions.
- No service account is granted cluster-wide privileges.
- The `default` ServiceAccount in the namespace has `automountServiceAccountToken: false`.

### Resource Limits

All pods define CPU and memory limits to prevent resource exhaustion and noisy-neighbor effects:

```yaml
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 512Mi
```

### Pod Security Standards

The namespace enforces the **restricted** Pod Security Standard profile, which requires:

- Running as non-root
- Dropping all capabilities
- Read-only root filesystem
- No privilege escalation
- Seccomp profile set to `RuntimeDefault`

---

## 6. Input Validation

### Pydantic Models

All API request payloads are validated using **Pydantic models with strict types**. Invalid requests are rejected with a `422 Unprocessable Entity` response before any business logic executes.

#### Example Pydantic Model

```python
import re
from pydantic import BaseModel, Field, field_validator

class CreateConsentRequest(BaseModel):
    """Validates incoming consent creation requests."""

    customer_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Full name of the customer",
    )
    email: str = Field(
        ...,
        max_length=254,
        description="Customer email address (RFC 5322)",
    )
    phone_number: str = Field(
        ...,
        max_length=16,
        description="Customer phone number (E.164 format)",
    )
    purpose: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Purpose for which consent is being collected",
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        # RFC 5322 compliant email validation
        pattern = r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email format")
        return v

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        # E.164 format: + followed by 1-15 digits
        pattern = r"^\+[1-9]\d{1,14}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid phone number format (expected E.164)")
        return v
```

### Injection and XSS Prevention

| Threat | Mitigation |
|---|---|
| **SQL Injection** | N/A -- DynamoDB is NoSQL with a structured API, not a query language. All inputs are sanitized regardless. |
| **XSS** | React's built-in output escaping; `Content-Security-Policy` headers configured on `consent-ui` |

### Rate Limiting

| Endpoint | Limit |
|---|---|
| Customer consent response (`/respond`) | **10 requests/minute** per IP |
| Consent creation (`POST /api/v1/consents`) | **100 requests/minute** |

### Request Size Limits

All API endpoints enforce a **maximum request body size of 1 MB**. Requests exceeding this limit are rejected with `413 Payload Too Large`.

---

## 7. Audit Trail

### ConsentHistory Entity

All consent state changes are recorded in the `ConsentHistory` entity. This provides an immutable, append-only log of every action taken on a consent record.

Each history entry includes:

| Field | Description |
|---|---|
| `action` | The operation performed (e.g., `CREATED`, `APPROVED`, `REVOKED`, `EXPIRED`) |
| `actor` | Identifier of the user or system that performed the action |
| `timestamp` | ISO 8601 timestamp of the action |
| `previous_status` | Consent status before the action |
| `new_status` | Consent status after the action |
| `changes` | Structured diff of fields that changed |

### Structured Logging

- **Correlation IDs:** Every request is tagged with an `X-Correlation-ID` header. This ID is propagated across all inter-service calls (HTTP, SQS messages) so that a single customer interaction can be traced end-to-end.
- **Log Format:** JSON via `structlog` for machine-parseable, searchable logs.

### Log Levels

| Level | Usage |
|---|---|
| `DEBUG` | Development only; includes verbose internal state |
| `INFO` | Normal operations: consent created, notification sent, response received |
| `WARNING` | Degraded state: high latency, retries, approaching rate limits |
| `ERROR` | Failures: unhandled exceptions, failed message processing, DLQ routing |
| `CRITICAL` | Outages: service unavailable, data store unreachable, incident triggered |

### Centralized Log Aggregation

In production, all service logs should be shipped to a centralized platform for monitoring, alerting, and forensic analysis:

- **AWS CloudWatch Logs** (native integration with EKS)
- **ELK Stack** (Elasticsearch, Logstash, Kibana)
- **Splunk**

---

## 8. Incident Response

### Automated Detection

The **incident-detector** service continuously monitors system health and automatically detects anomalies:

| Detection Rule | Trigger |
|---|---|
| **Failure rate spike** | Consent processing failure rate exceeds threshold within a rolling window |
| **Throughput drop** | Consent processing throughput falls below expected baseline |
| **Error count spike** | Sudden increase in error-level log events across services |
| **DLQ depth** | Messages accumulating in Dead Letter Queues indicate processing failures |

### Incident Management Integration

When an incident is detected:

1. The **incident-detector** publishes an event to the incident queue.
2. The **incident-bridge** forwards the event to **MIMS** (the external incident management system).
3. MIMS coordinates the response, including automated and human actions.

### Pause and Resume Capability

| Command | Effect |
|---|---|
| `PauseConsentCollection` | MIMS sends this command to halt all outbound customer notifications. No new consent requests are dispatched until the incident is resolved. In-flight requests continue to completion. |
| `ResumeConsentCollection` | MIMS sends this command when the incident is resolved. Normal consent collection and notification operations resume. |

This mechanism prevents customers from receiving notifications during system degradation, protecting both customer experience and data integrity.

### DLQ Monitoring

Dead Letter Queues (DLQs) are monitored for all SQS queues. Messages routed to a DLQ indicate a processing failure that exceeded the retry policy. DLQ depth is a key input to the incident detection rules.

---

## 9. Dependencies

### Vulnerability Scanning

| Ecosystem | Tool | Frequency |
|---|---|---|
| **Python (pip)** | `pip-audit`, `safety` | Every CI build + weekly scheduled scan |
| **JavaScript (npm)** | `npm audit` | Every CI build + weekly scheduled scan |
| **Docker base images** | Trivy, Snyk, or Docker Scout | Every image build |

### Image Pinning

- **Local development:** Using `:latest` or `:slim` tags is acceptable for convenience.
- **Production:** Pin images to specific digest or version tags (e.g., `python:3.12.4-slim@sha256:abcdef...`). Never use `:latest` in production Dockerfiles.

### Automated Dependency Updates

Use **Dependabot** or **Renovate** to:

- Automatically open pull requests when dependency updates are available.
- Flag security-critical updates for expedited review.
- Run the full CI test suite on every dependency update PR before merge.

### CI Pipeline Integration

The CI pipeline includes a dedicated dependency vulnerability scanning stage:

1. `pip-audit` checks Python dependencies against the OSV database.
2. `npm audit` checks frontend dependencies against the npm advisory database.
3. Container image scan checks base image layers for known CVEs.
4. The build **fails** if any critical or high severity vulnerabilities are found.

---

## 10. Compliance Considerations

### GDPR

The system is designed with GDPR principles in mind:

| GDPR Principle | Implementation |
|---|---|
| **Right to withdraw consent** | Consent revocation endpoint: `DELETE /api/v1/consents/{id}` transitions consent to `REVOKED` status |
| **Right to access** | Customer can view their consents: `GET /api/v1/customers/{id}/consents` |
| **Data minimization** | Only necessary contact information is collected (phone number and/or email as required by consent purpose) |
| **Purpose limitation** | The `purpose` field is required on every consent record; consent cannot be created without an explicit purpose |
| **Immutable records** | Consent records use **soft delete only**. Full history is preserved in the `ConsentHistory` entity. No consent record is ever physically deleted. |

### Data Retention

- Configurable via **DynamoDB TTL** (Time to Live) attributes.
- Expired records are automatically removed by DynamoDB after the configured retention period.
- Retention policies should align with legal and regulatory requirements for the jurisdiction.

### Audit Trail

- A complete history of all consent state changes is maintained (see [Section 7](#7-audit-trail)).
- Audit records are immutable and append-only.
- Sufficient for demonstrating compliance during regulatory audits.

### Data Portability

- Consent data is exportable via API endpoints.
- Standard JSON format enables interoperability with other systems.
- Bulk export capabilities support data portability requests at scale.
