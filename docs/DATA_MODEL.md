# Consent Management System -- Data Model Design

This document describes the complete data model for the Consent Management System (CMS). The system uses Amazon DynamoDB with a single-table design to store all entities related to consent management, including consent records, customer profiles, notification logs, incidents, and system metrics.

---

## 1. DynamoDB Single-Table Design

All entities in the Consent Management System are stored in a single DynamoDB table named **`cms-consents`**. This approach is chosen for several important reasons:

- **Fewer connections**: A single table means the application maintains only one connection endpoint, reducing operational overhead and connection management complexity.
- **Atomic transactions**: DynamoDB transactions can operate on up to 100 items within a single table. Storing related entities together allows us to perform atomic writes across entity types (e.g., creating a ConsentRecord and its first ConsentHistory entry in one transaction).
- **Cost efficiency**: One table eliminates the per-table base costs and reduces the number of CloudFormation resources to manage. Backup, restore, and monitoring are simplified.
- **Simplified operations**: A single table means one set of alarms, one backup configuration, one set of IAM policies, and one capacity plan to manage. This drastically reduces operational burden.

Every entity stored in the table is differentiated by its key patterns. The partition key (PK) and sort key (SK) use prefixes that encode the entity type, enabling multiple entity types to coexist without collision.

---

## 2. Key Schema

The table uses a **composite primary key** consisting of two String attributes:

| Attribute | Type   | Role          |
|-----------|--------|---------------|
| **PK**    | String | Partition Key |
| **SK**    | String | Sort Key      |

### Composite Key Strategy

The composite key strategy uses **entity prefixing** to distinguish between different entity types and to support multiple access patterns on the base table:

- The **PK** groups related items together under the same partition. For example, a consent record and all of its history entries and notification logs share the same PK value (`CONSENT#{consent_id}`), which allows retrieving all related data with a single query.
- The **SK** differentiates items within a partition. A fixed value like `METADATA` identifies the primary record, while prefixed values like `HISTORY#{timestamp}` or `NOTIF#{notification_id}` identify related child items.
- Prefixes such as `CONSENT#`, `CUSTOMER#`, `INCIDENT#`, and `METRIC#` are used to namespace the key space and prevent collisions between entity types.

This design allows both single-item gets (using exact PK + SK) and one-to-many queries (using PK + SK prefix) on the base table without any secondary indexes.

---

## 3. Global Secondary Indexes (GSIs)

Three Global Secondary Indexes support the additional query patterns that the base table keys cannot efficiently serve.

### GSI1 -- Query by Customer

| Attribute   | Type   | Role                |
|-------------|--------|---------------------|
| **GSI1PK**  | String | GSI1 Partition Key  |
| **GSI1SK**  | String | GSI1 Sort Key       |

**Purpose**: Enables looking up all consents, history entries, and notifications for a given customer. The customer ID is used as the partition key, and the sort key encodes the entity type and timestamp, allowing sorted retrieval and prefix-based filtering.

**Typical queries**:
- List all consents for a customer (GSI1SK begins_with `CONSENT#`)
- List all history for a customer (GSI1SK begins_with `HISTORY#`)
- List all notifications for a customer (GSI1SK begins_with `NOTIF#`)
- Retrieve a customer profile (GSI1SK = `PROFILE`)

### GSI2 -- Query by Status + Date

| Attribute   | Type   | Role                |
|-------------|--------|---------------------|
| **GSI2PK**  | String | GSI2 Partition Key  |
| **GSI2SK**  | String | GSI2 Sort Key       |

**Purpose**: Enables listing consents by their current status with date ordering. Also supports querying incidents by severity level. The partition key encodes the status or severity, and the sort key holds the timestamp for chronological ordering.

**Typical queries**:
- List all consents with status `granted` sorted by date
- List all consents with status `pending` in a specific date range
- List all incidents with severity `CRITICAL` sorted by detection time

### GSI3 -- Query by Channel + Date

| Attribute   | Type   | Role                |
|-------------|--------|---------------------|
| **GSI3PK**  | String | GSI3 Partition Key  |
| **GSI3SK**  | String | GSI3 Sort Key       |

**Purpose**: Enables listing consents and notifications by communication channel (e.g., `sms`, `email`). The partition key encodes the channel, and the sort key holds the timestamp for chronological ordering.

**Typical queries**:
- List all consents requested via SMS
- List all notifications sent via email sorted by date
- Count consents by channel over a date range

---

## 4. Entity Types

The following table shows the complete key patterns for every entity type stored in the `cms-consents` table. A `--` indicates that the attribute is not populated for that entity type.

| Entity | PK | SK | GSI1PK | GSI1SK | GSI2PK | GSI2SK | GSI3PK | GSI3SK |
|---|---|---|---|---|---|---|---|---|
| **ConsentRecord** | `CONSENT#{consent_id}` | `METADATA` | `CUSTOMER#{customer_id}` | `CONSENT#{created_at}` | `STATUS#{status}` | `{created_at}` | `CHANNEL#{channel}` | `{created_at}` |
| **ConsentHistory** | `CONSENT#{consent_id}` | `HISTORY#{timestamp}` | `CUSTOMER#{customer_id}` | `HISTORY#{timestamp}` | -- | -- | -- | -- |
| **Customer** | `CUSTOMER#{customer_id}` | `METADATA` | `CUSTOMER#{customer_id}` | `PROFILE` | -- | -- | -- | -- |
| **NotificationLog** | `CONSENT#{consent_id}` | `NOTIF#{notification_id}` | `CUSTOMER#{customer_id}` | `NOTIF#{sent_at}` | -- | -- | `CHANNEL#{channel}` | `{sent_at}` |
| **Incident** | `INCIDENT#{incident_id}` | `METADATA` | -- | -- | `SEVERITY#{level}` | `{detected_at}` | -- | -- |
| **SystemMetric** | `METRIC#{metric_name}` | `{timestamp}` | -- | -- | -- | -- | -- | -- |

### Key Pattern Notes

- **ConsentRecord** is the central entity. Its PK (`CONSENT#{consent_id}`) serves as the anchor for all related ConsentHistory and NotificationLog items, which share the same PK but use different SK prefixes.
- **ConsentHistory** items are stored under the same partition as their parent ConsentRecord, with the SK prefix `HISTORY#` followed by a timestamp, ensuring chronological ordering.
- **Customer** entities have their own PK namespace (`CUSTOMER#{customer_id}`) and use `METADATA` as the SK, keeping customer profile data separate from consent data.
- **NotificationLog** entries are co-located with their associated ConsentRecord (same PK), with the SK prefix `NOTIF#` followed by the notification ID.
- **Incident** entities use the `INCIDENT#` prefix in their PK and are queryable by severity through GSI2.
- **SystemMetric** entities use the metric name in the PK and the timestamp as the SK, forming a natural time-series layout that supports efficient range queries.

---

## 5. Access Patterns

The following table documents every supported access pattern, the table or index used, the key condition expression, and any relevant notes.

| Access Pattern | Table/Index | Key Condition | Notes |
|---|---|---|---|
| Get consent by ID | Table | `PK = CONSENT#{id}`, `SK = METADATA` | Single item get operation |
| Get consent with all related data | Table | `PK = CONSENT#{id}` | Query returns metadata + history + notifications in one round trip |
| List consents by customer | GSI1 | `GSI1PK = CUSTOMER#{id}`, `GSI1SK begins_with("CONSENT#")` | Sorted by created_at |
| List all data for customer | GSI1 | `GSI1PK = CUSTOMER#{id}` | Returns consents + history + notifications + profile |
| List consents by status | GSI2 | `GSI2PK = STATUS#{status}` | Sorted by created_at |
| List consents by status in date range | GSI2 | `GSI2PK = STATUS#{status}`, `GSI2SK between date1 and date2` | Date range filter using sort key condition |
| List consents by channel | GSI3 | `GSI3PK = CHANNEL#{channel}` | Sorted by created_at |
| Get consent history | Table | `PK = CONSENT#{id}`, `SK begins_with("HISTORY#")` | Sorted by timestamp |
| Get notifications for consent | Table | `PK = CONSENT#{id}`, `SK begins_with("NOTIF#")` | Sorted by notification_id |
| Get incidents by severity | GSI2 | `GSI2PK = SEVERITY#{level}` | Sorted by detected_at |
| Get system metrics in time range | Table | `PK = METRIC#{name}`, `SK between ts1 and ts2` | Time-series query over a specific metric |
| Get customer profile | Table | `PK = CUSTOMER#{id}`, `SK = METADATA` | Single item get operation |

### Query Examples

**Get consent by ID** (single item):
```
GetItem: PK = "CONSENT#abc-123", SK = "METADATA"
```

**Get all data for a consent** (metadata + history + notifications):
```
Query: PK = "CONSENT#abc-123"
```

**List a customer's consents sorted by date**:
```
Query on GSI1: GSI1PK = "CUSTOMER#cust-456", GSI1SK begins_with "CONSENT#"
```

**List pending consents created this month**:
```
Query on GSI2: GSI2PK = "STATUS#pending", GSI2SK between "2026-08-01" and "2026-08-31"
```

---

## 6. Attribute Definitions

### ConsentRecord

| Attribute | Type | Description |
|---|---|---|
| `PK` | S | Partition key: `CONSENT#{consent_id}` |
| `SK` | S | Sort key: `METADATA` |
| `consent_id` | S | Unique identifier for the consent record (UUID) |
| `customer_id` | S | Identifier of the customer this consent belongs to |
| `channel` | S | Communication channel: `sms` or `email` |
| `purpose` | S | Purpose of the consent request (e.g., `marketing`, `transactional`, `data_processing`) |
| `status` | S | Current consent status: `pending`, `sent`, `granted`, `denied`, `expired`, or `revoked` |
| `contact_info` | M | Map containing contact details: `phone` (String) and/or `email` (String) |
| `response_token` | S | Unique token used to authenticate consent responses |
| `created_at` | S | ISO 8601 timestamp of when the consent record was created |
| `updated_at` | S | ISO 8601 timestamp of the last update |
| `expires_at` | S | ISO 8601 timestamp of when the consent request expires |
| `responded_at` | S | ISO 8601 timestamp of when the customer responded (null if no response) |
| `metadata` | M | Map of arbitrary key-value metadata associated with this consent |
| `GSI1PK` | S | GSI1 partition key: `CUSTOMER#{customer_id}` |
| `GSI1SK` | S | GSI1 sort key: `CONSENT#{created_at}` |
| `GSI2PK` | S | GSI2 partition key: `STATUS#{status}` |
| `GSI2SK` | S | GSI2 sort key: `{created_at}` |
| `GSI3PK` | S | GSI3 partition key: `CHANNEL#{channel}` |
| `GSI3SK` | S | GSI3 sort key: `{created_at}` |
| `ttl` | N | Optional TTL value (epoch seconds) for automatic item expiration |

### ConsentHistory

| Attribute | Type | Description |
|---|---|---|
| `PK` | S | Partition key: `CONSENT#{consent_id}` |
| `SK` | S | Sort key: `HISTORY#{timestamp}` |
| `consent_id` | S | Identifier of the associated consent record |
| `customer_id` | S | Identifier of the associated customer |
| `action` | S | Action that occurred: `created`, `sent`, `granted`, `denied`, `expired`, `revoked`, or `updated` |
| `actor` | S | Identifier of who or what performed the action (user ID, system process, etc.) |
| `timestamp` | S | ISO 8601 timestamp of when the action occurred |
| `previous_status` | S | The consent status before this action |
| `new_status` | S | The consent status after this action |
| `changes` | M | Map describing what changed (attribute names to old/new value pairs) |
| `GSI1PK` | S | GSI1 partition key: `CUSTOMER#{customer_id}` |
| `GSI1SK` | S | GSI1 sort key: `HISTORY#{timestamp}` |

### Customer

| Attribute | Type | Description |
|---|---|---|
| `PK` | S | Partition key: `CUSTOMER#{customer_id}` |
| `SK` | S | Sort key: `METADATA` |
| `customer_id` | S | Unique identifier for the customer |
| `name` | S | Customer display name |
| `email` | S | Customer email address |
| `phone` | S | Customer phone number |
| `created_at` | S | ISO 8601 timestamp of when the customer record was created |
| `updated_at` | S | ISO 8601 timestamp of the last update |
| `consent_count` | N | Running count of consent records associated with this customer |
| `GSI1PK` | S | GSI1 partition key: `CUSTOMER#{customer_id}` |
| `GSI1SK` | S | GSI1 sort key: `PROFILE` |

### NotificationLog

| Attribute | Type | Description |
|---|---|---|
| `PK` | S | Partition key: `CONSENT#{consent_id}` |
| `SK` | S | Sort key: `NOTIF#{notification_id}` |
| `notification_id` | S | Unique identifier for the notification |
| `consent_id` | S | Identifier of the associated consent record |
| `customer_id` | S | Identifier of the associated customer |
| `channel` | S | Channel used to send the notification: `sms` or `email` |
| `status` | S | Delivery status: `pending`, `sent`, `delivered`, `failed`, or `bounced` |
| `sent_at` | S | ISO 8601 timestamp of when the notification was sent |
| `delivered_at` | S | ISO 8601 timestamp of when delivery was confirmed |
| `failed_at` | S | ISO 8601 timestamp of when the notification failed (if applicable) |
| `error_code` | S | Provider-specific error code (if applicable) |
| `error_message` | S | Human-readable error description (if applicable) |
| `provider_message_id` | S | Message ID returned by the notification provider (e.g., SNS Message ID) |
| `GSI1PK` | S | GSI1 partition key: `CUSTOMER#{customer_id}` |
| `GSI1SK` | S | GSI1 sort key: `NOTIF#{sent_at}` |
| `GSI3PK` | S | GSI3 partition key: `CHANNEL#{channel}` |
| `GSI3SK` | S | GSI3 sort key: `{sent_at}` |

### Incident

| Attribute | Type | Description |
|---|---|---|
| `PK` | S | Partition key: `INCIDENT#{incident_id}` |
| `SK` | S | Sort key: `METADATA` |
| `incident_id` | S | Unique identifier for the incident |
| `rule_name` | S | Name of the monitoring rule that triggered the incident |
| `severity` | S | Severity level: `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL` |
| `status` | S | Incident status: `detected`, `acknowledged`, or `resolved` |
| `description` | S | Human-readable description of the incident |
| `metrics` | M | Map of metric values that triggered the incident |
| `detected_at` | S | ISO 8601 timestamp of when the incident was detected |
| `acknowledged_at` | S | ISO 8601 timestamp of when the incident was acknowledged |
| `resolved_at` | S | ISO 8601 timestamp of when the incident was resolved |
| `acknowledged_by` | S | Identifier of the person who acknowledged the incident |
| `resolved_by` | S | Identifier of the person who resolved the incident |
| `resolution_notes` | S | Free-text notes describing how the incident was resolved |
| `GSI2PK` | S | GSI2 partition key: `SEVERITY#{level}` |
| `GSI2SK` | S | GSI2 sort key: `{detected_at}` |

### SystemMetric

| Attribute | Type | Description |
|---|---|---|
| `PK` | S | Partition key: `METRIC#{metric_name}` |
| `SK` | S | Sort key: `{timestamp}` (ISO 8601) |
| `metric_name` | S | Name of the metric (e.g., `consent_requests`, `notification_failures`) |
| `timestamp` | S | ISO 8601 timestamp of the metric data point |
| `value` | N | Numeric value of the metric |
| `unit` | S | Unit of measurement (e.g., `count`, `milliseconds`, `percent`) |
| `dimensions` | M | Map of dimension key-value pairs for metric segmentation |
| `ttl` | N | TTL value (epoch seconds) for automatic expiration |

---

## 7. Capacity Planning

The `cms-consents` table uses **on-demand (PAY_PER_REQUEST)** billing mode.

| Setting | Value |
|---|---|
| Billing Mode | `PAY_PER_REQUEST` (On-Demand) |
| Provisioned Read Capacity | N/A |
| Provisioned Write Capacity | N/A |

### Why On-Demand

- **No provisioned capacity needed**: There is no requirement to estimate or pre-allocate read/write capacity units. DynamoDB handles all capacity management automatically.
- **Scales automatically**: The table scales up instantly to accommodate traffic spikes (e.g., a batch consent request campaign) and scales back down during quiet periods, with no manual intervention.
- **Suitable for unpredictable workloads**: Consent management traffic can be highly variable -- marketing campaigns may generate bursts of consent requests, while baseline traffic remains low.
- **Cost-effective for development**: During development and testing, you pay only for the reads and writes you actually perform, avoiding the cost of idle provisioned capacity.

If the workload becomes predictable and sustained at high volume, switching to provisioned capacity with auto-scaling can be evaluated for cost optimization.

---

## 8. TTL (Time to Live)

The table supports an optional **TTL** attribute (type Number, epoch seconds) that enables automatic item expiration. When an item's TTL value is in the past, DynamoDB marks it for deletion.

| Entity | TTL Policy | Retention Period |
|---|---|---|
| **SystemMetric** | Auto-expire after 30 days | 30 days from creation |
| **Incident** (resolved) | Auto-expire after 90 days | 90 days from resolution |
| **ConsentRecord** | Optional, based on data retention policy | Configurable per policy |

### TTL Behavior

- The `ttl` attribute must contain a **Unix epoch timestamp** (number of seconds since January 1, 1970 00:00:00 UTC).
- DynamoDB typically deletes expired items **within 48 hours** of the TTL expiry time. Expired items may still appear in queries until they are physically deleted.
- TTL deletions do **not** consume write capacity units and are performed at no additional cost.
- Deleted items are removed from both the base table and all GSIs.
- TTL deletions can be captured via DynamoDB Streams for audit logging or downstream processing.

### TTL Calculation Examples

```
SystemMetric TTL  = created_at_epoch + (30 * 24 * 60 * 60)   // 30 days = 2,592,000 seconds
Incident TTL      = resolved_at_epoch + (90 * 24 * 60 * 60)  // 90 days = 7,776,000 seconds
```

---

## 9. Example DynamoDB Item

The following JSON shows what a fully populated **ConsentRecord** item looks like when stored in the `cms-consents` table.

```json
{
  "PK": {
    "S": "CONSENT#550e8400-e29b-41d4-a716-446655440000"
  },
  "SK": {
    "S": "METADATA"
  },
  "consent_id": {
    "S": "550e8400-e29b-41d4-a716-446655440000"
  },
  "customer_id": {
    "S": "cust-78291-abc"
  },
  "channel": {
    "S": "sms"
  },
  "purpose": {
    "S": "marketing"
  },
  "status": {
    "S": "granted"
  },
  "contact_info": {
    "M": {
      "phone": {
        "S": "+1-555-123-4567"
      },
      "email": {
        "S": "jane.doe@example.com"
      }
    }
  },
  "response_token": {
    "S": "tok_a3f8c91b2d4e6f7890abcdef12345678"
  },
  "created_at": {
    "S": "2026-08-15T10:30:00.000Z"
  },
  "updated_at": {
    "S": "2026-08-16T14:22:31.000Z"
  },
  "expires_at": {
    "S": "2026-09-15T10:30:00.000Z"
  },
  "responded_at": {
    "S": "2026-08-16T14:22:31.000Z"
  },
  "metadata": {
    "M": {
      "campaign_id": {
        "S": "camp-summer-2026"
      },
      "source": {
        "S": "web-signup"
      },
      "ip_address": {
        "S": "192.168.1.100"
      }
    }
  },
  "GSI1PK": {
    "S": "CUSTOMER#cust-78291-abc"
  },
  "GSI1SK": {
    "S": "CONSENT#2026-08-15T10:30:00.000Z"
  },
  "GSI2PK": {
    "S": "STATUS#granted"
  },
  "GSI2SK": {
    "S": "2026-08-15T10:30:00.000Z"
  },
  "GSI3PK": {
    "S": "CHANNEL#sms"
  },
  "GSI3SK": {
    "S": "2026-08-15T10:30:00.000Z"
  },
  "ttl": {
    "N": "1758020400"
  }
}
```

### Key Observations

- All attributes use the DynamoDB JSON wire format with explicit type descriptors (`S` for String, `N` for Number, `M` for Map).
- The `PK` and `SK` values follow the entity prefix pattern (`CONSENT#` + UUID, `METADATA`).
- All six GSI key attributes are populated, allowing this item to be queried through any of the three GSIs.
- The `contact_info` and `metadata` attributes are Maps, allowing flexible nested structures.
- The `ttl` value is a Unix epoch timestamp representing the expiration time.
- Timestamps throughout use ISO 8601 format with UTC timezone for consistency and lexicographic sorting.
