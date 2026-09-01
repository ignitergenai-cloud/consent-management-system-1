# Consent Management System -- API Design Document

## 1. Overview

The Consent Management System exposes a RESTful API following **OpenAPI 3.1** conventions. All services share common patterns for consistency and ease of integration.

| Attribute            | Value                                      |
|----------------------|--------------------------------------------|
| **Base URL**         | `/api/v1`                                  |
| **Content Type**     | `application/json` (request and response)  |
| **Pagination**       | Cursor-based via `next_token`              |
| **Date Format**      | ISO 8601 (`2026-08-30T14:22:00.000Z`)      |
| **ID Format**        | UUID v4                                    |
| **Character Encoding** | UTF-8                                    |

### Service Ports

| Service              | Port  | Visibility |
|----------------------|-------|------------|
| consent-api          | 8000  | Public     |
| notification-service | 8002  | Internal   |
| incident-detector    | 8003  | Internal   |
| incident-bridge      | 8004  | Internal   |

---

## 2. Authentication

### Local Development

No authentication is required. All endpoints are accessible without credentials.

### Production

Production deployments would use one of the following mechanisms:

- **JWT Bearer Tokens** -- Passed via the `Authorization: Bearer <token>` header. Tokens are issued by an external identity provider and validated by an API gateway.
- **API Keys** -- Passed via the `X-API-Key` header. Suitable for service-to-service communication.

> **Note:** The public customer-response endpoint (`POST /api/v1/consents/respond/{response_token}`) is always unauthenticated. Security is enforced through the cryptographic response token itself.

---

## 3. consent-api Endpoints (Port 8000)

### 3.1 Create Consent

Creates a new consent request and triggers the notification workflow.

| Attribute   | Value                      |
|-------------|----------------------------|
| **Method**  | `POST`                     |
| **Path**    | `/api/v1/consents`         |

#### Request Body

```json
{
  "customer_id": "cust_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "channel": "sms",
  "purpose": "marketing_promotions",
  "contact_info": {
    "phone": "+14155551234"
  },
  "metadata": {
    "campaign_id": "camp_2026_summer",
    "source": "web_signup",
    "region": "us-west-2"
  }
}
```

| Field          | Type   | Required | Description                                      |
|----------------|--------|----------|--------------------------------------------------|
| `customer_id`  | string | Yes      | Unique identifier for the customer               |
| `channel`      | string | Yes      | Communication channel: `sms` or `email`          |
| `purpose`      | string | Yes      | Reason for requesting consent                    |
| `contact_info` | object | Yes      | Contains `phone` (for sms) or `email` (for email)|
| `metadata`     | object | No       | Arbitrary key-value pairs for tracking            |

#### Response Body -- `201 Created`

```json
{
  "consent_id": "cons_7f3a92e1-4b8d-4c6f-9e2a-1d5b8c3f7a90",
  "customer_id": "cust_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "channel": "sms",
  "purpose": "marketing_promotions",
  "contact_info": {
    "phone": "+14155551234"
  },
  "status": "pending",
  "metadata": {
    "campaign_id": "camp_2026_summer",
    "source": "web_signup",
    "region": "us-west-2"
  },
  "response_token": "rtk_c8e4f2a1b3d5e6f7a8b9c0d1e2f3a4b5",
  "expires_at": "2026-09-06T14:22:00.000Z",
  "created_at": "2026-08-30T14:22:00.000Z",
  "updated_at": "2026-08-30T14:22:00.000Z"
}
```

#### Status Codes

| Code | Description                                          |
|------|------------------------------------------------------|
| 201  | Consent request created successfully                 |
| 400  | Malformed request body (invalid JSON, missing fields)|
| 422  | Validation error (invalid channel, bad phone format) |

---

### 3.2 List Consents

Retrieves a paginated list of consent records with optional filters.

| Attribute   | Value                      |
|-------------|----------------------------|
| **Method**  | `GET`                      |
| **Path**    | `/api/v1/consents`         |

#### Query Parameters

| Parameter    | Type   | Default | Description                                  |
|--------------|--------|---------|----------------------------------------------|
| `status`     | string | --      | Filter by status: `pending`, `granted`, `denied`, `revoked`, `expired` |
| `channel`    | string | --      | Filter by channel: `sms`, `email`            |
| `customer_id`| string | --      | Filter by customer identifier                |
| `from_date`  | string | --      | ISO 8601 start date (inclusive)              |
| `to_date`    | string | --      | ISO 8601 end date (inclusive)                |
| `page_size`  | int    | 20      | Number of items per page (max 100)           |
| `next_token` | string | --      | Cursor token for the next page               |

#### Example Request

```
GET /api/v1/consents?status=pending&channel=sms&page_size=2
```

#### Response Body -- `200 OK`

```json
{
  "items": [
    {
      "consent_id": "cons_7f3a92e1-4b8d-4c6f-9e2a-1d5b8c3f7a90",
      "customer_id": "cust_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "channel": "sms",
      "purpose": "marketing_promotions",
      "contact_info": {
        "phone": "+14155551234"
      },
      "status": "pending",
      "metadata": {
        "campaign_id": "camp_2026_summer"
      },
      "expires_at": "2026-09-06T14:22:00.000Z",
      "created_at": "2026-08-30T14:22:00.000Z",
      "updated_at": "2026-08-30T14:22:00.000Z"
    },
    {
      "consent_id": "cons_e4d8b2c6-1a3f-4e7d-8b9c-5f2a6d0e1b4c",
      "customer_id": "cust_b2c3d4e5-f6a7-8901-bcde-f23456789012",
      "channel": "sms",
      "purpose": "account_notifications",
      "contact_info": {
        "phone": "+14155559876"
      },
      "status": "pending",
      "metadata": {},
      "expires_at": "2026-09-07T09:15:00.000Z",
      "created_at": "2026-08-31T09:15:00.000Z",
      "updated_at": "2026-08-31T09:15:00.000Z"
    }
  ],
  "next_token": "eyJjb25zZW50X2lkIjoiY29uc19lNGQ4YjJjNi0xYTNmLTRlN2QtOGI5Yy01ZjJhNmQwZTFiNGMiLCJjcmVhdGVkX2F0IjoiMjAyNi0wOC0zMVQwOToxNTowMC4wMDBaIn0="
}
```

#### Status Codes

| Code | Description                |
|------|----------------------------|
| 200  | Successful retrieval       |

---

### 3.3 Get Consent by ID

Retrieves a single consent record by its unique identifier.

| Attribute   | Value                                |
|-------------|--------------------------------------|
| **Method**  | `GET`                                |
| **Path**    | `/api/v1/consents/{consent_id}`      |

#### Path Parameters

| Parameter    | Type   | Description                    |
|--------------|--------|--------------------------------|
| `consent_id` | string | UUID of the consent record    |

#### Response Body -- `200 OK`

```json
{
  "consent_id": "cons_7f3a92e1-4b8d-4c6f-9e2a-1d5b8c3f7a90",
  "customer_id": "cust_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "channel": "sms",
  "purpose": "marketing_promotions",
  "contact_info": {
    "phone": "+14155551234"
  },
  "status": "granted",
  "metadata": {
    "campaign_id": "camp_2026_summer",
    "source": "web_signup",
    "region": "us-west-2"
  },
  "response_token": "rtk_c8e4f2a1b3d5e6f7a8b9c0d1e2f3a4b5",
  "responded_at": "2026-08-30T16:45:12.000Z",
  "expires_at": "2026-09-06T14:22:00.000Z",
  "created_at": "2026-08-30T14:22:00.000Z",
  "updated_at": "2026-08-30T16:45:12.000Z"
}
```

#### Status Codes

| Code | Description                                  |
|------|----------------------------------------------|
| 200  | Consent record found                         |
| 404  | Consent with the specified ID does not exist |

---

### 3.4 Update Consent

Partially updates an existing consent record. Only the provided fields are modified.

| Attribute   | Value                                |
|-------------|--------------------------------------|
| **Method**  | `PATCH`                              |
| **Path**    | `/api/v1/consents/{consent_id}`      |

#### Path Parameters

| Parameter    | Type   | Description                    |
|--------------|--------|--------------------------------|
| `consent_id` | string | UUID of the consent record    |

#### Request Body

```json
{
  "purpose": "marketing_promotions_v2",
  "metadata": {
    "campaign_id": "camp_2026_summer",
    "source": "web_signup",
    "region": "us-west-2",
    "updated_reason": "campaign scope expanded"
  }
}
```

| Field      | Type   | Required | Description                          |
|------------|--------|----------|--------------------------------------|
| `purpose`  | string | No       | Updated purpose for the consent      |
| `metadata` | object | No       | Replaces existing metadata entirely  |

#### Response Body -- `200 OK`

```json
{
  "consent_id": "cons_7f3a92e1-4b8d-4c6f-9e2a-1d5b8c3f7a90",
  "customer_id": "cust_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "channel": "sms",
  "purpose": "marketing_promotions_v2",
  "contact_info": {
    "phone": "+14155551234"
  },
  "status": "pending",
  "metadata": {
    "campaign_id": "camp_2026_summer",
    "source": "web_signup",
    "region": "us-west-2",
    "updated_reason": "campaign scope expanded"
  },
  "expires_at": "2026-09-06T14:22:00.000Z",
  "created_at": "2026-08-30T14:22:00.000Z",
  "updated_at": "2026-08-30T17:30:45.000Z"
}
```

#### Status Codes

| Code | Description                                          |
|------|------------------------------------------------------|
| 200  | Consent updated successfully                         |
| 404  | Consent with the specified ID does not exist         |
| 422  | Validation error (invalid field value or type)       |

---

### 3.5 Revoke Consent (Soft Delete)

Revokes a consent record. The record is not physically deleted; its status is set to `revoked`.

| Attribute   | Value                                |
|-------------|--------------------------------------|
| **Method**  | `DELETE`                             |
| **Path**    | `/api/v1/consents/{consent_id}`      |

#### Path Parameters

| Parameter    | Type   | Description                    |
|--------------|--------|--------------------------------|
| `consent_id` | string | UUID of the consent record    |

#### Response Body -- `200 OK`

```json
{
  "consent_id": "cons_7f3a92e1-4b8d-4c6f-9e2a-1d5b8c3f7a90",
  "customer_id": "cust_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "channel": "sms",
  "purpose": "marketing_promotions",
  "contact_info": {
    "phone": "+14155551234"
  },
  "status": "revoked",
  "metadata": {
    "campaign_id": "camp_2026_summer",
    "source": "web_signup",
    "region": "us-west-2"
  },
  "revoked_at": "2026-08-30T18:00:00.000Z",
  "created_at": "2026-08-30T14:22:00.000Z",
  "updated_at": "2026-08-30T18:00:00.000Z"
}
```

#### Status Codes

| Code | Description                                  |
|------|----------------------------------------------|
| 200  | Consent revoked successfully                 |
| 404  | Consent with the specified ID does not exist |

---

### 3.6 Bulk Create Consents

Creates multiple consent requests in a single call. Each item is processed independently; partial failures are reported per item.

| Attribute   | Value                        |
|-------------|------------------------------|
| **Method**  | `POST`                       |
| **Path**    | `/api/v1/consents/bulk`      |

#### Request Body

```json
{
  "requests": [
    {
      "customer_id": "cust_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "channel": "sms",
      "purpose": "marketing_promotions",
      "contact_info": {
        "phone": "+14155551234"
      },
      "metadata": {
        "campaign_id": "camp_2026_summer"
      }
    },
    {
      "customer_id": "cust_b2c3d4e5-f6a7-8901-bcde-f23456789012",
      "channel": "email",
      "purpose": "product_updates",
      "contact_info": {
        "email": "jane.doe@example.com"
      },
      "metadata": {
        "campaign_id": "camp_2026_summer"
      }
    },
    {
      "customer_id": "cust_c3d4e5f6-a7b8-9012-cdef-345678901234",
      "channel": "fax",
      "purpose": "marketing_promotions",
      "contact_info": {
        "phone": "+14155550000"
      }
    }
  ]
}
```

#### Response Body -- `207 Multi-Status` (partial failure)

```json
{
  "results": [
    {
      "index": 0,
      "status": "success",
      "consent": {
        "consent_id": "cons_11111111-aaaa-4bbb-cccc-dddddddddddd",
        "customer_id": "cust_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "channel": "sms",
        "purpose": "marketing_promotions",
        "contact_info": {
          "phone": "+14155551234"
        },
        "status": "pending",
        "metadata": {
          "campaign_id": "camp_2026_summer"
        },
        "response_token": "rtk_aaa111bbb222ccc333ddd444eee555ff",
        "expires_at": "2026-09-06T14:22:00.000Z",
        "created_at": "2026-08-30T14:22:00.000Z",
        "updated_at": "2026-08-30T14:22:00.000Z"
      }
    },
    {
      "index": 1,
      "status": "success",
      "consent": {
        "consent_id": "cons_22222222-bbbb-4ccc-dddd-eeeeeeeeeeee",
        "customer_id": "cust_b2c3d4e5-f6a7-8901-bcde-f23456789012",
        "channel": "email",
        "purpose": "product_updates",
        "contact_info": {
          "email": "jane.doe@example.com"
        },
        "status": "pending",
        "metadata": {
          "campaign_id": "camp_2026_summer"
        },
        "response_token": "rtk_fff666ggg777hhh888iii999jjj000kk",
        "expires_at": "2026-09-06T14:22:00.000Z",
        "created_at": "2026-08-30T14:22:00.000Z",
        "updated_at": "2026-08-30T14:22:00.000Z"
      }
    },
    {
      "index": 2,
      "status": "failure",
      "error": {
        "code": "VALIDATION_ERROR",
        "message": "Invalid channel 'fax'. Allowed values: sms, email."
      }
    }
  ],
  "summary": {
    "total": 3,
    "succeeded": 2,
    "failed": 1
  }
}
```

#### Response Body -- `201 Created` (all items succeeded)

```json
{
  "results": [
    {
      "index": 0,
      "status": "success",
      "consent": { "..." : "..." }
    },
    {
      "index": 1,
      "status": "success",
      "consent": { "..." : "..." }
    }
  ],
  "summary": {
    "total": 2,
    "succeeded": 2,
    "failed": 0
  }
}
```

#### Status Codes

| Code | Description                                  |
|------|----------------------------------------------|
| 201  | All consent requests created successfully    |
| 207  | Partial success -- some items failed         |

---

### 3.7 Consent Audit History

Returns the full audit trail of changes for a specific consent record.

| Attribute   | Value                                          |
|-------------|------------------------------------------------|
| **Method**  | `GET`                                          |
| **Path**    | `/api/v1/consents/{consent_id}/history`        |

#### Path Parameters

| Parameter    | Type   | Description                    |
|--------------|--------|--------------------------------|
| `consent_id` | string | UUID of the consent record    |

#### Response Body -- `200 OK`

```json
{
  "consent_id": "cons_7f3a92e1-4b8d-4c6f-9e2a-1d5b8c3f7a90",
  "history": [
    {
      "history_id": "hist_00000001-aaaa-4bbb-cccc-dddddddddddd",
      "action": "created",
      "timestamp": "2026-08-30T14:22:00.000Z",
      "actor": "system:consent-api",
      "changes": {
        "status": {
          "old": null,
          "new": "pending"
        },
        "channel": {
          "old": null,
          "new": "sms"
        },
        "purpose": {
          "old": null,
          "new": "marketing_promotions"
        }
      }
    },
    {
      "history_id": "hist_00000002-bbbb-4ccc-dddd-eeeeeeeeeeee",
      "action": "notification_sent",
      "timestamp": "2026-08-30T14:22:05.000Z",
      "actor": "system:notification-service",
      "changes": {
        "notification_id": {
          "old": null,
          "new": "notif_abcdef12-3456-7890-abcd-ef1234567890"
        }
      }
    },
    {
      "history_id": "hist_00000003-cccc-4ddd-eeee-ffffffffffff",
      "action": "responded",
      "timestamp": "2026-08-30T16:45:12.000Z",
      "actor": "customer:cust_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "changes": {
        "status": {
          "old": "pending",
          "new": "granted"
        }
      }
    },
    {
      "history_id": "hist_00000004-dddd-4eee-ffff-aaaaaaaaaaaa",
      "action": "updated",
      "timestamp": "2026-08-30T17:30:45.000Z",
      "actor": "user:admin@example.com",
      "changes": {
        "purpose": {
          "old": "marketing_promotions",
          "new": "marketing_promotions_v2"
        }
      }
    }
  ]
}
```

#### Status Codes

| Code | Description                                  |
|------|----------------------------------------------|
| 200  | Audit history retrieved successfully         |
| 404  | Consent with the specified ID does not exist |

---

### 3.8 Customer Consent Response (PUBLIC)

Public endpoint used by customers to respond to a consent request via a unique response token. This endpoint requires no authentication -- the response token itself serves as proof of identity.

| Attribute   | Value                                              |
|-------------|----------------------------------------------------|
| **Method**  | `POST`                                             |
| **Path**    | `/api/v1/consents/respond/{response_token}`        |

#### Path Parameters

| Parameter        | Type   | Description                                  |
|------------------|--------|----------------------------------------------|
| `response_token` | string | Unique token sent to the customer via SMS/email |

#### Request Body

```json
{
  "decision": "granted",
  "responded_at": "2026-08-30T16:45:12.000Z"
}
```

| Field          | Type   | Required | Description                                       |
|----------------|--------|----------|---------------------------------------------------|
| `decision`     | string | Yes      | Customer's decision: `granted` or `denied`        |
| `responded_at` | string | No       | ISO 8601 timestamp (server time used if omitted)  |

#### Response Body -- `200 OK`

```json
{
  "message": "Thank you. Your consent decision has been recorded.",
  "consent_id": "cons_7f3a92e1-4b8d-4c6f-9e2a-1d5b8c3f7a90",
  "decision": "granted",
  "recorded_at": "2026-08-30T16:45:12.000Z"
}
```

#### Status Codes

| Code | Description                                                        |
|------|--------------------------------------------------------------------|
| 200  | Decision recorded successfully                                     |
| 400  | Invalid request (missing decision, invalid decision value)         |
| 404  | Response token not found or does not match any consent record      |
| 410  | Consent request has expired and can no longer accept a response    |

---

### 3.9 Get Consents by Customer

Retrieves all consent records for a specific customer.

| Attribute   | Value                                          |
|-------------|------------------------------------------------|
| **Method**  | `GET`                                          |
| **Path**    | `/api/v1/customers/{customer_id}/consents`     |

#### Path Parameters

| Parameter     | Type   | Description                     |
|---------------|--------|---------------------------------|
| `customer_id` | string | Unique identifier of the customer |

#### Query Parameters

| Parameter    | Type   | Default | Description                                  |
|--------------|--------|---------|----------------------------------------------|
| `status`     | string | --      | Filter by status: `pending`, `granted`, `denied`, `revoked`, `expired` |
| `channel`    | string | --      | Filter by channel: `sms`, `email`            |
| `page_size`  | int    | 20      | Number of items per page (max 100)           |
| `next_token` | string | --      | Cursor token for the next page               |

#### Example Request

```
GET /api/v1/customers/cust_a1b2c3d4-e5f6-7890-abcd-ef1234567890/consents?status=granted&channel=sms
```

#### Response Body -- `200 OK`

```json
{
  "customer_id": "cust_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "items": [
    {
      "consent_id": "cons_7f3a92e1-4b8d-4c6f-9e2a-1d5b8c3f7a90",
      "channel": "sms",
      "purpose": "marketing_promotions",
      "contact_info": {
        "phone": "+14155551234"
      },
      "status": "granted",
      "metadata": {
        "campaign_id": "camp_2026_summer"
      },
      "responded_at": "2026-08-30T16:45:12.000Z",
      "expires_at": "2026-09-06T14:22:00.000Z",
      "created_at": "2026-08-30T14:22:00.000Z",
      "updated_at": "2026-08-30T16:45:12.000Z"
    },
    {
      "consent_id": "cons_88888888-4444-4aaa-bbbb-cccccccccccc",
      "channel": "sms",
      "purpose": "account_alerts",
      "contact_info": {
        "phone": "+14155551234"
      },
      "status": "granted",
      "metadata": {},
      "responded_at": "2026-07-15T10:00:00.000Z",
      "expires_at": "2026-10-15T10:00:00.000Z",
      "created_at": "2026-07-08T10:00:00.000Z",
      "updated_at": "2026-07-15T10:00:00.000Z"
    }
  ],
  "next_token": null
}
```

#### Status Codes

| Code | Description          |
|------|----------------------|
| 200  | Successful retrieval |

---

### 3.10 Consent Analytics

Returns aggregate statistics about consent requests over a specified date range.

| Attribute   | Value                            |
|-------------|----------------------------------|
| **Method**  | `GET`                            |
| **Path**    | `/api/v1/analytics/consents`     |

#### Query Parameters

| Parameter   | Type   | Default       | Description                       |
|-------------|--------|---------------|-----------------------------------|
| `from_date` | string | 30 days ago   | ISO 8601 start date (inclusive)   |
| `to_date`   | string | now           | ISO 8601 end date (inclusive)     |

#### Example Request

```
GET /api/v1/analytics/consents?from_date=2026-08-01T00:00:00Z&to_date=2026-08-30T23:59:59Z
```

#### Response Body -- `200 OK`

```json
{
  "period": {
    "from_date": "2026-08-01T00:00:00.000Z",
    "to_date": "2026-08-30T23:59:59.000Z"
  },
  "total": 1542,
  "by_status": {
    "pending": 187,
    "granted": 1023,
    "denied": 198,
    "revoked": 89,
    "expired": 45
  },
  "by_channel": {
    "sms": 943,
    "email": 599
  },
  "response_rate": 0.792,
  "avg_response_time_seconds": 14523
}
```

| Field                       | Type   | Description                                          |
|-----------------------------|--------|------------------------------------------------------|
| `total`                     | int    | Total number of consent requests in the period       |
| `by_status`                 | object | Count of consents broken down by current status      |
| `by_channel`                | object | Count of consents broken down by channel             |
| `response_rate`             | float  | Fraction of consents that received a response (0-1)  |
| `avg_response_time_seconds` | int    | Average time between creation and customer response  |

#### Status Codes

| Code | Description          |
|------|----------------------|
| 200  | Successful retrieval |

---

### 3.11 Health Check

Basic liveness probe. Returns immediately if the service process is running.

| Attribute   | Value                  |
|-------------|------------------------|
| **Method**  | `GET`                  |
| **Path**    | `/api/v1/health`       |

#### Response Body -- `200 OK`

```json
{
  "status": "healthy",
  "version": "1.4.2",
  "timestamp": "2026-08-30T14:22:00.000Z"
}
```

#### Status Codes

| Code | Description            |
|------|------------------------|
| 200  | Service is alive       |

---

### 3.12 Readiness Check

Deep health check that verifies all downstream dependencies are reachable.

| Attribute   | Value                        |
|-------------|------------------------------|
| **Method**  | `GET`                        |
| **Path**    | `/api/v1/health/ready`       |

#### Response Body -- `200 OK` (all dependencies healthy)

```json
{
  "status": "ready",
  "timestamp": "2026-08-30T14:22:00.000Z",
  "checks": {
    "dynamodb": {
      "status": "healthy",
      "latency_ms": 12
    },
    "sns": {
      "status": "healthy",
      "latency_ms": 8
    },
    "sqs": {
      "status": "healthy",
      "latency_ms": 5
    }
  }
}
```

#### Response Body -- `503 Service Unavailable` (dependency failure)

```json
{
  "status": "not_ready",
  "timestamp": "2026-08-30T14:22:00.000Z",
  "checks": {
    "dynamodb": {
      "status": "healthy",
      "latency_ms": 12
    },
    "sns": {
      "status": "unhealthy",
      "latency_ms": null,
      "error": "Connection timeout after 5000ms"
    },
    "sqs": {
      "status": "healthy",
      "latency_ms": 5
    }
  }
}
```

#### Status Codes

| Code | Description                              |
|------|------------------------------------------|
| 200  | All dependencies are healthy             |
| 503  | One or more dependencies are unreachable |

---

## 4. notification-service Endpoints (Port 8002)

These endpoints are internal to the system and are not exposed publicly. They are consumed by other microservices for operational and debugging purposes.

### 4.1 Health Check

| Attribute   | Value                  |
|-------------|------------------------|
| **Method**  | `GET`                  |
| **Path**    | `/api/v1/health`       |

#### Response Body -- `200 OK`

```json
{
  "status": "healthy",
  "version": "1.2.0",
  "timestamp": "2026-08-30T14:22:00.000Z"
}
```

---

### 4.2 Get Notification Details

Retrieves the details and delivery status of a specific notification.

| Attribute   | Value                                              |
|-------------|----------------------------------------------------|
| **Method**  | `GET`                                              |
| **Path**    | `/api/v1/notifications/{notification_id}`          |

#### Path Parameters

| Parameter          | Type   | Description                         |
|--------------------|--------|-------------------------------------|
| `notification_id`  | string | UUID of the notification record     |

#### Response Body -- `200 OK`

```json
{
  "notification_id": "notif_abcdef12-3456-7890-abcd-ef1234567890",
  "consent_id": "cons_7f3a92e1-4b8d-4c6f-9e2a-1d5b8c3f7a90",
  "channel": "sms",
  "recipient": "+14155551234",
  "template_name": "consent_request_sms",
  "status": "delivered",
  "provider_message_id": "SM9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d",
  "attempts": 1,
  "sent_at": "2026-08-30T14:22:05.000Z",
  "delivered_at": "2026-08-30T14:22:08.000Z",
  "created_at": "2026-08-30T14:22:04.000Z",
  "updated_at": "2026-08-30T14:22:08.000Z"
}
```

#### Status Codes

| Code | Description                                        |
|------|----------------------------------------------------|
| 200  | Notification found                                 |
| 404  | Notification with the specified ID does not exist  |

---

### 4.3 List Templates

Returns all available notification templates.

| Attribute   | Value                      |
|-------------|----------------------------|
| **Method**  | `GET`                      |
| **Path**    | `/api/v1/templates`        |

#### Response Body -- `200 OK`

```json
{
  "templates": [
    {
      "template_id": "tmpl_001-sms-consent",
      "name": "consent_request_sms",
      "channel": "sms",
      "subject": null,
      "body": "Hi {{customer_name}}, please respond to grant or deny consent for {{purpose}}. Reply at: {{response_url}}",
      "created_at": "2026-01-15T10:00:00.000Z",
      "updated_at": "2026-06-20T12:30:00.000Z"
    },
    {
      "template_id": "tmpl_002-email-consent",
      "name": "consent_request_email",
      "channel": "email",
      "subject": "Action Required: Consent Request for {{purpose}}",
      "body": "<html><body><p>Dear {{customer_name}},</p><p>We are requesting your consent for <strong>{{purpose}}</strong>.</p><p><a href=\"{{response_url}}\">Click here to respond</a></p></body></html>",
      "created_at": "2026-01-15T10:00:00.000Z",
      "updated_at": "2026-07-01T09:00:00.000Z"
    }
  ]
}
```

---

### 4.4 Create Template

Creates a new notification template.

| Attribute   | Value                      |
|-------------|----------------------------|
| **Method**  | `POST`                     |
| **Path**    | `/api/v1/templates`        |

#### Request Body

```json
{
  "name": "consent_reminder_sms",
  "channel": "sms",
  "subject": null,
  "body": "Reminder: You have a pending consent request for {{purpose}}. Please respond at: {{response_url}}"
}
```

| Field     | Type        | Required | Description                                              |
|-----------|-------------|----------|----------------------------------------------------------|
| `name`    | string      | Yes      | Unique template name (snake_case recommended)            |
| `channel` | string      | Yes      | Channel this template is for: `sms` or `email`          |
| `subject` | string/null | No       | Email subject line (null for SMS templates)              |
| `body`    | string      | Yes      | Template body with `{{placeholder}}` variables           |

#### Response Body -- `201 Created`

```json
{
  "template_id": "tmpl_003-sms-reminder",
  "name": "consent_reminder_sms",
  "channel": "sms",
  "subject": null,
  "body": "Reminder: You have a pending consent request for {{purpose}}. Please respond at: {{response_url}}",
  "created_at": "2026-08-30T14:22:00.000Z",
  "updated_at": "2026-08-30T14:22:00.000Z"
}
```

#### Status Codes

| Code | Description                                  |
|------|----------------------------------------------|
| 201  | Template created successfully                |
| 400  | Malformed request body                       |
| 409  | Template with the same name already exists   |
| 422  | Validation error                             |

---

## 5. incident-detector Endpoints (Port 8003)

The incident detector monitors system metrics and automatically raises incidents when thresholds are breached.

### 5.1 Health Check

| Attribute   | Value                  |
|-------------|------------------------|
| **Method**  | `GET`                  |
| **Path**    | `/api/v1/health`       |

#### Response Body -- `200 OK`

```json
{
  "status": "healthy",
  "version": "1.1.0",
  "timestamp": "2026-08-30T14:22:00.000Z"
}
```

---

### 5.2 Get Current Metrics

Returns the latest values of all monitored metrics.

| Attribute   | Value                  |
|-------------|------------------------|
| **Method**  | `GET`                  |
| **Path**    | `/api/v1/metrics`      |

#### Response Body -- `200 OK`

```json
{
  "timestamp": "2026-08-30T14:22:00.000Z",
  "metrics": {
    "consent_request_rate": {
      "value": 42.5,
      "unit": "requests/min",
      "threshold_warning": 100.0,
      "threshold_critical": 200.0,
      "status": "normal"
    },
    "notification_failure_rate": {
      "value": 0.03,
      "unit": "ratio",
      "threshold_warning": 0.05,
      "threshold_critical": 0.15,
      "status": "normal"
    },
    "response_latency_p99": {
      "value": 2450,
      "unit": "ms",
      "threshold_warning": 3000,
      "threshold_critical": 5000,
      "status": "normal"
    },
    "dynamodb_consumed_capacity": {
      "value": 78.2,
      "unit": "percent",
      "threshold_warning": 80.0,
      "threshold_critical": 95.0,
      "status": "warning"
    },
    "sqs_queue_depth": {
      "value": 156,
      "unit": "messages",
      "threshold_warning": 500,
      "threshold_critical": 2000,
      "status": "normal"
    }
  }
}
```

#### Status Codes

| Code | Description          |
|------|----------------------|
| 200  | Metrics retrieved    |

---

### 5.3 List Detected Incidents

Returns incidents detected by the monitoring system.

| Attribute   | Value                    |
|-------------|--------------------------|
| **Method**  | `GET`                    |
| **Path**    | `/api/v1/incidents`      |

#### Query Parameters

| Parameter | Type   | Default | Description                                        |
|-----------|--------|---------|----------------------------------------------------|
| `status`  | string | --      | Filter: `open`, `acknowledged`, `resolved`         |
| `severity`| string | --      | Filter: `warning`, `critical`                      |

#### Response Body -- `200 OK`

```json
{
  "incidents": [
    {
      "incident_id": "inc_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "metric_name": "dynamodb_consumed_capacity",
      "severity": "warning",
      "status": "open",
      "message": "DynamoDB consumed capacity at 78.2%, approaching warning threshold of 80.0%",
      "metric_value": 78.2,
      "threshold_breached": 80.0,
      "detected_at": "2026-08-30T14:15:00.000Z",
      "acknowledged_at": null,
      "resolved_at": null,
      "acknowledged_by": null,
      "resolved_by": null
    },
    {
      "incident_id": "inc_b2c3d4e5-f6a7-8901-bcde-f23456789012",
      "metric_name": "notification_failure_rate",
      "severity": "critical",
      "status": "acknowledged",
      "message": "Notification failure rate spiked to 18.7%, exceeding critical threshold of 15.0%",
      "metric_value": 0.187,
      "threshold_breached": 0.15,
      "detected_at": "2026-08-30T12:00:00.000Z",
      "acknowledged_at": "2026-08-30T12:05:30.000Z",
      "resolved_at": null,
      "acknowledged_by": "ops:admin@example.com",
      "resolved_by": null
    }
  ]
}
```

#### Status Codes

| Code | Description          |
|------|----------------------|
| 200  | Incidents retrieved  |

---

### 5.4 Acknowledge Incident

Marks an incident as acknowledged, indicating an operator is aware and investigating.

| Attribute   | Value                                              |
|-------------|----------------------------------------------------|
| **Method**  | `POST`                                             |
| **Path**    | `/api/v1/incidents/{incident_id}/acknowledge`      |

#### Path Parameters

| Parameter     | Type   | Description                     |
|---------------|--------|---------------------------------|
| `incident_id` | string | UUID of the incident           |

#### Request Body

```json
{
  "acknowledged_by": "ops:admin@example.com",
  "note": "Investigating elevated DynamoDB usage. Likely due to bulk import job."
}
```

#### Response Body -- `200 OK`

```json
{
  "incident_id": "inc_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "acknowledged",
  "acknowledged_at": "2026-08-30T14:25:00.000Z",
  "acknowledged_by": "ops:admin@example.com",
  "note": "Investigating elevated DynamoDB usage. Likely due to bulk import job."
}
```

#### Status Codes

| Code | Description                                      |
|------|--------------------------------------------------|
| 200  | Incident acknowledged successfully               |
| 404  | Incident with the specified ID does not exist    |
| 409  | Incident is already resolved                     |

---

### 5.5 Resolve Incident

Marks an incident as resolved.

| Attribute   | Value                                          |
|-------------|------------------------------------------------|
| **Method**  | `POST`                                         |
| **Path**    | `/api/v1/incidents/{incident_id}/resolve`      |

#### Path Parameters

| Parameter     | Type   | Description                     |
|---------------|--------|---------------------------------|
| `incident_id` | string | UUID of the incident           |

#### Request Body

```json
{
  "resolved_by": "ops:admin@example.com",
  "resolution": "Bulk import job completed. DynamoDB capacity returned to normal levels."
}
```

#### Response Body -- `200 OK`

```json
{
  "incident_id": "inc_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "resolved",
  "acknowledged_at": "2026-08-30T14:25:00.000Z",
  "acknowledged_by": "ops:admin@example.com",
  "resolved_at": "2026-08-30T15:10:00.000Z",
  "resolved_by": "ops:admin@example.com",
  "resolution": "Bulk import job completed. DynamoDB capacity returned to normal levels."
}
```

#### Status Codes

| Code | Description                                      |
|------|--------------------------------------------------|
| 200  | Incident resolved successfully                   |
| 404  | Incident with the specified ID does not exist    |
| 409  | Incident is already resolved                     |

---

## 6. incident-bridge Endpoints (Port 8004)

The incident bridge connects the consent management system to the external Major Incident Management System (MIMS). These endpoints provide visibility into the bridge's operational state.

### 6.1 Health Check

| Attribute   | Value                  |
|-------------|------------------------|
| **Method**  | `GET`                  |
| **Path**    | `/api/v1/health`       |

#### Response Body -- `200 OK`

```json
{
  "status": "healthy",
  "version": "1.0.3",
  "timestamp": "2026-08-30T14:22:00.000Z"
}
```

---

### 6.2 Bridge Connection Status

Returns the current connection status to the external MIMS system.

| Attribute   | Value                        |
|-------------|------------------------------|
| **Method**  | `GET`                        |
| **Path**    | `/api/v1/bridge/status`      |

#### Response Body -- `200 OK`

```json
{
  "connected": true,
  "mims_endpoint": "https://mims.internal.example.com/api/v2",
  "last_heartbeat_at": "2026-08-30T14:21:55.000Z",
  "uptime_seconds": 86412,
  "reconnect_count": 0,
  "pending_events": 0,
  "last_event_forwarded_at": "2026-08-30T14:15:00.000Z"
}
```

#### Status Codes

| Code | Description            |
|------|------------------------|
| 200  | Status retrieved       |

---

### 6.3 Recent Bridge Events

Returns recent events that have been forwarded through the bridge to MIMS.

| Attribute   | Value                        |
|-------------|------------------------------|
| **Method**  | `GET`                        |
| **Path**    | `/api/v1/bridge/events`      |

#### Query Parameters

| Parameter   | Type | Default | Description                    |
|-------------|------|---------|--------------------------------|
| `limit`     | int  | 50      | Number of events to return (max 200) |

#### Response Body -- `200 OK`

```json
{
  "events": [
    {
      "event_id": "evt_11111111-aaaa-4bbb-cccc-dddddddddddd",
      "incident_id": "inc_b2c3d4e5-f6a7-8901-bcde-f23456789012",
      "event_type": "incident_created",
      "mims_ticket_id": "MIMS-2026-004721",
      "payload_summary": "Critical: notification_failure_rate at 18.7% (threshold: 15.0%)",
      "forwarded_at": "2026-08-30T12:00:05.000Z",
      "mims_acknowledged": true
    },
    {
      "event_id": "evt_22222222-bbbb-4ccc-dddd-eeeeeeeeeeee",
      "incident_id": "inc_b2c3d4e5-f6a7-8901-bcde-f23456789012",
      "event_type": "incident_acknowledged",
      "mims_ticket_id": "MIMS-2026-004721",
      "payload_summary": "Incident acknowledged by ops:admin@example.com",
      "forwarded_at": "2026-08-30T12:05:35.000Z",
      "mims_acknowledged": true
    },
    {
      "event_id": "evt_33333333-cccc-4ddd-eeee-ffffffffffff",
      "incident_id": "inc_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "event_type": "incident_created",
      "mims_ticket_id": "MIMS-2026-004722",
      "payload_summary": "Warning: dynamodb_consumed_capacity at 78.2% (threshold: 80.0%)",
      "forwarded_at": "2026-08-30T14:15:05.000Z",
      "mims_acknowledged": true
    }
  ]
}
```

#### Status Codes

| Code | Description          |
|------|----------------------|
| 200  | Events retrieved     |

---

## 7. Error Response Format

All errors across every service follow a consistent JSON envelope.

### Structure

```json
{
  "error": {
    "code": "CONSENT_NOT_FOUND",
    "message": "Consent with ID cons_7f3a92e1-4b8d-4c6f-9e2a-1d5b8c3f7a90 not found.",
    "correlation_id": "corr_d4e5f6a7-b8c9-0d1e-2f3a-4b5c6d7e8f90"
  }
}
```

| Field            | Type   | Description                                                     |
|------------------|--------|-----------------------------------------------------------------|
| `code`           | string | Machine-readable error code (UPPER_SNAKE_CASE)                  |
| `message`        | string | Human-readable description of the error                         |
| `correlation_id` | string | Unique identifier for tracing this request across services      |

### Common Error Codes

| Code                      | HTTP Status | Description                                                |
|---------------------------|-------------|------------------------------------------------------------|
| `VALIDATION_ERROR`        | 400 / 422   | Request body or query parameters failed validation         |
| `INVALID_JSON`            | 400         | Request body is not valid JSON                             |
| `MISSING_REQUIRED_FIELD`  | 400         | A required field is missing from the request body          |
| `CONSENT_NOT_FOUND`       | 404         | The specified consent_id does not exist                    |
| `CUSTOMER_NOT_FOUND`      | 404         | The specified customer_id does not exist                   |
| `NOTIFICATION_NOT_FOUND`  | 404         | The specified notification_id does not exist               |
| `TEMPLATE_NOT_FOUND`      | 404         | The specified template does not exist                      |
| `INCIDENT_NOT_FOUND`      | 404         | The specified incident_id does not exist                   |
| `TOKEN_NOT_FOUND`         | 404         | The response_token does not match any consent              |
| `CONSENT_EXPIRED`         | 410         | The consent request has expired and cannot accept responses|
| `TEMPLATE_ALREADY_EXISTS` | 409         | A template with the same name already exists               |
| `INCIDENT_ALREADY_RESOLVED`| 409        | The incident has already been resolved                     |
| `INVALID_CHANNEL`         | 422         | Channel must be `sms` or `email`                           |
| `INVALID_PHONE_FORMAT`    | 422         | Phone number does not match E.164 format                   |
| `INVALID_EMAIL_FORMAT`    | 422         | Email address is not valid                                 |
| `INVALID_DECISION`        | 422         | Decision must be `granted` or `denied`                     |
| `INTERNAL_ERROR`          | 500         | An unexpected server error occurred                        |
| `SERVICE_UNAVAILABLE`     | 503         | A downstream dependency is unreachable                     |

### Validation Error Example (multiple fields)

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed. See details.",
    "correlation_id": "corr_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "details": [
      {
        "field": "channel",
        "message": "Invalid channel 'fax'. Allowed values: sms, email."
      },
      {
        "field": "contact_info.phone",
        "message": "Phone number must be in E.164 format (e.g., +14155551234)."
      }
    ]
  }
}
```

---

## 8. Pagination

All list endpoints use **cursor-based pagination** built on top of DynamoDB's `LastEvaluatedKey`.

### How It Works

1. The client sends a request without a `next_token` to fetch the first page.
2. If there are more results beyond `page_size`, the response includes a non-null `next_token`.
3. The client passes `next_token` as a query parameter on the next request to fetch the subsequent page.
4. When `next_token` is `null` in the response, the client has reached the end of the result set.

### Token Encoding

The `next_token` is a **base64-encoded** representation of the DynamoDB `LastEvaluatedKey`. It is opaque to the client and should be treated as an immutable string.

```
Underlying DynamoDB LastEvaluatedKey:
{
  "consent_id": {"S": "cons_e4d8b2c6-1a3f-4e7d-8b9c-5f2a6d0e1b4c"},
  "created_at": {"S": "2026-08-31T09:15:00.000Z"}
}

Encoded next_token:
eyJjb25zZW50X2lkIjp7IlMiOiJjb25zX2U0ZDhiMmM2LTFhM2YtNGU3ZC04YjljLTVmMmE2ZDBlMWI0YyJ9LCJjcmVhdGVkX2F0Ijp7IlMiOiIyMDI2LTA4LTMxVDA5OjE1OjAwLjAwMFoifX0=
```

### Example Flow

**First request:**

```
GET /api/v1/consents?status=pending&page_size=2
```

```json
{
  "items": [ "...first 2 items..." ],
  "next_token": "eyJjb25zZW50X2lkIjp7IlMiOiJjb25zX2U0ZDhiMmM2In19"
}
```

**Second request:**

```
GET /api/v1/consents?status=pending&page_size=2&next_token=eyJjb25zZW50X2lkIjp7IlMiOiJjb25zX2U0ZDhiMmM2In19
```

```json
{
  "items": [ "...next 2 items..." ],
  "next_token": "eyJjb25zZW50X2lkIjp7IlMiOiJjb25zXzk5OTk5OTk5In19"
}
```

**Final request:**

```
GET /api/v1/consents?status=pending&page_size=2&next_token=eyJjb25zZW50X2lkIjp7IlMiOiJjb25zXzk5OTk5OTk5In19
```

```json
{
  "items": [ "...last item..." ],
  "next_token": null
}
```

### Important Notes

- Tokens are **not reusable** across different query parameter combinations. Changing a filter (e.g., `status`) invalidates any previously issued token.
- Tokens may **expire** after a period of inactivity (default: 1 hour). An expired token returns a `400` error with the code `INVALID_PAGE_TOKEN`.
- Clients should **never** attempt to decode, modify, or construct tokens manually.

---

## 9. Common Headers

### Request Headers

| Header             | Required | Description                                                        |
|--------------------|----------|--------------------------------------------------------------------|
| `Content-Type`     | Yes*     | Must be `application/json` for requests with a body               |
| `Accept`           | No       | Should be `application/json` (default if omitted)                 |
| `X-Correlation-ID` | No       | Client-generated UUID for distributed tracing. If omitted, the server generates one and returns it in the response. |

*Required only for `POST`, `PATCH`, and `PUT` requests.

### Response Headers

| Header             | Always Present | Description                                                  |
|--------------------|----------------|--------------------------------------------------------------|
| `Content-Type`     | Yes            | Always `application/json`                                    |
| `X-Correlation-ID` | Yes            | Echoes the request's correlation ID or provides a generated one |
| `X-Request-ID`     | Yes            | Server-generated unique identifier for this specific request |

### Example

**Request:**

```http
POST /api/v1/consents HTTP/1.1
Host: localhost:8000
Content-Type: application/json
Accept: application/json
X-Correlation-ID: corr_f1e2d3c4-b5a6-9788-6543-210fedcba987

{
  "customer_id": "cust_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "channel": "sms",
  "purpose": "marketing_promotions",
  "contact_info": {
    "phone": "+14155551234"
  }
}
```

**Response:**

```http
HTTP/1.1 201 Created
Content-Type: application/json
X-Correlation-ID: corr_f1e2d3c4-b5a6-9788-6543-210fedcba987
X-Request-ID: req_aabbccdd-eeff-0011-2233-445566778899

{
  "consent_id": "cons_7f3a92e1-4b8d-4c6f-9e2a-1d5b8c3f7a90",
  "...": "..."
}
```
