# TRACEVEDA DATA MODEL

## 1. Master Data

users
plants
farms
manufacturers


## 2. Supply Chain

raw_material_batches
transport_events
processing_batches
batch_relationships
lab_tests
medicine_batches


## 3. IoT & Monitoring

iot_devices
iot_readings
iot_alerts
storage_events


## 4. Consumer & Investigation

consumer_reports
investigations


## 5. Blockchain

blockchain_events


# CORE RELATIONSHIPS

Farmer
  ↓
Farm
  ↓
Raw Material Batch
  ↓
Processing Batch
  ↓
Medicine Batch
  ↓
QR


Raw Batch
  ↓
Batch Relationship
  ↓
Processing Batch


Batch
  ↓
Transport Event
  ↓
IoT Reading
  ↓
IoT Alert


Medicine Batch
  ↓
Storage Event


Medicine Batch
  ↓
Consumer Report
  ↓
Investigation


# ID MAP

farmer_id          → Farmer
farm_id            → Farm
plant_id           → Plant / Species
raw_batch_id       → Raw Material Batch
processing_batch_id → Processing Batch
lab_id             → Laboratory
transport_id       → Transport Journey
sensor_id          → IoT Device / Sensor
storage_id         → Storage Monitoring Event
manufacturer_id    → Manufacturer
medicine_batch_id  → Finished Medicine Batch
qr_id              → Consumer Verification

## 6. Public Assistant Conversations

`assistant_conversations` stores anonymous public website assistant sessions.
It is separate from `users` and does not represent a stakeholder account.

Each conversation document contains the following fields:

| Field | Purpose |
|---|---|
| `session_id` | Opaque session identifier; unique index |
| `messages` | Bounded transcript entries containing `role`, `content` and `created_at` |
| `message_count` | Count of submitted user messages recorded for the session |
| `rate_window_started_at` | Start time of the current hourly rate-limit window |
| `rate_window_count` | Number of user messages submitted in the current rate window |
| `created_at` | Session creation timestamp |
| `updated_at` | Most recent successful chat update |
| `expires_at` | Session expiry timestamp; MongoDB TTL index field |

A session is created without a user login. The API defaults to a 30-day
retention period, configurable with `TRACEVEDA_ASSISTANT_SESSION_DAYS`.
Successful chat activity refreshes `expires_at` using the configured period.
MongoDB has a TTL index on `expires_at` with `expireAfterSeconds=0`; physical
document deletion is asynchronous. The API independently rejects expired
sessions.

The session ID has a unique index. The implementation stores at most the most
recent 40 transcript entries and uses up to 16 recent entries as context for a
Gemini request. The per-session rate limit is 40 submitted user messages per
hour.

Relationship overview:

```text
Public Website Visitor
        |
        | no stakeholder login
        v
Assistant Session
        |
        v
assistant_conversations
  - session_id
  - messages[]
  - message_count
  - rate_window_*
  - created_at / updated_at
  - expires_at (TTL index)
        |
        +--> Gemini Developer API
        |
        +--> Built-in FAQ fallback
```

The assistant conversation collection does not grant access to private
stakeholder records, telemetry or administrator functions. It is not linked
to the stakeholder `users` collection as an authenticated account.
