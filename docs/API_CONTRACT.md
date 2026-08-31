# TRACEVEDA API CONTRACT

## Core IDs

farmer_id
farm_id
plant_id
raw_batch_id
processing_batch_id
lab_id
transport_id
sensor_id
storage_id
manufacturer_id
medicine_batch_id
qr_id


## Core Flow

```text
FARMER
   ↓
FARM
   ↓
RAW MATERIAL BATCH
   ↓
PROCESSING BATCH
   ↓
MEDICINE BATCH
   ↓
   QR
```

## 0. Conventions

Base URL: `http://localhost:8000`

**Every endpoint below requires a bearer token** except the two marked
PUBLIC. Send it on every request:

```http
Authorization: Bearer <access_token>
```

| Status | Meaning |
|---|---|
| 200 | OK |
| 201 | Created (all POSTs) |
| 400 | The request is valid but the business rule refuses it |
| 401 | No credentials, or credentials that are not valid |
| 403 | Valid credentials belonging to a role that may not do this |
| 404 | No such record |
| 409 | Conflict — the record already exists |
| 422 | The request body failed validation |

Errors are always `{"detail": "..."}`.

List endpoints accept `?limit=` and `?offset=` and return
`{ "...": [...], "count": <returned>, "total": <in the collection> }`.


## 1. Authentication

```http
POST /api/auth/login
```

Request:

```json
{ "username": "regulator", "password": "..." }
```

Response:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_at": 1756598400,
  "username": "regulator",
  "role": "regulator",
  "full_name": "Ministry of AYUSH"
}
```

`401` for a bad username *or* a bad password — the same message for both, so
the endpoint cannot be used to discover which usernames exist.

```http
GET /api/auth/me
```

```json
{
  "username": "regulator",
  "role": "regulator",
  "full_name": "Ministry of AYUSH",
  "organisation_id": null
}
```

```http
GET /api/auth/roles                                            PUBLIC
```

Roles: `farmer`, `processor`, `lab`, `logistics`, `manufacturer`,
`regulator`, `admin`. Create the demo accounts with
`python seed_users.py`.

### Which role may write what

| Endpoint | Role |
|---|---|
| `POST /api/batches/raw` | farmer |
| `POST /api/batches/processing` | processor |
| `POST /api/batches/relationships` | processor |
| `POST /api/lab/tests` | lab |
| `POST /api/medicine` | manufacturer |
| `POST /api/transport/events` | logistics |
| `POST /api/storage/events` | logistics |
| `POST /api/iot/readings` | logistics, or `X-Device-Key` |
| `POST /api/blockchain/events` | regulator |
| `PATCH /api/consumer/reports/{id}/status` | regulator |

`admin` is admitted everywhere.

### IoT device ingest

An ESP32 node authenticates with a shared key instead of a token:

```http
POST /api/iot/readings
X-Device-Key: <TRACEVEDA_DEVICE_API_KEY>
```


## 2. Plants

Botanical reference data (2,300 rows from the BSI/NMPB dataset). Read-only,
any signed-in account.

```http
GET /api/plants?limit=&offset=
GET /api/plants/search?name={name}
GET /api/plants/{plant_id}
```

`search` is a case-insensitive substring match across `common_name`,
`scientific_name` and `vernacular_names`. The term is regex-escaped, so
punctuation in a name - "Abelmoschus esculentus (L.) Moench" - matches as
text rather than as pattern syntax.

```json
{
  "plant_id": "PLANT-0002",
  "scientific_name": "Withania somnifera (L.) Dunal",
  "common_name": "Ashwagandha",
  "family": "SOLANACEAE",
  "medicinal_system": "Ayurveda"
}
```


## 3. Create Raw Material Batch

POST /api/batches/raw

Request:

{
  "farm_id": "FARM-001",
  "plant_id": "PLANT-001",
  "collection_date": "2026-08-26",
  "quantity": 100,
  "unit": "kg"
}

Response:

{
  "raw_batch_id": "RAW-2026-001",
  "status": "CREATED",
  "blockchain_tx": "TX-2026-000001"
}


## 4. Raw Material Batch

GET /api/batches/raw/{raw_batch_id}


## 5. Create Processing Batch

POST /api/batches/processing

Request:

{
  "processor_id": "PROC-001",
  "processing_date": "2026-08-26",
  "output_quantity": 500,
  "unit": "kg",
  "processing_type": "DRYING_AND_GRINDING"
}

Response:

{
  "processing_batch_id": "PROCESS-2026-001",
  "status": "CREATED",
  "blockchain_tx": "TX-2026-000002"
}


## 6. Processing Batch

GET /api/batches/processing/{processing_batch_id}


## 7. Create Batch Relationship

POST /api/batches/relationships

Request:

{
  "parent_batch_id": "RAW-2026-001",
  "child_batch_id": "PROCESS-2026-001",
  "relationship_type": "RAW_TO_PROCESSING",
  "quantity_contributed": 250,
  "unit": "kg"
}

Response:

{
  "relationship_id": "REL-2026-001",
  "status": "CREATED",
  "blockchain_tx": "TX-2026-000003"
}


## 8. Batch Relationships

GET /api/batches/{batch_id}/relationships


## 9. Laboratory

POST /api/lab/tests

Request:

{
  "batch_id": "PROCESS-2026-001",
  "lab_id": "LAB-001",
  "test_stage": "PRE_MANUFACTURING",
  "test_type": "QUALITY_TEST",
  "test_parameters": {
    "identity": "PASS",
    "purity": "PASS",
    "moisture": "PASS"
  },
  "result": "PASS"
}

Response:

{
  "lab_test_id": "LABTEST-2026-001",
  "batch_id": "PROCESS-2026-001",
  "result": "PASS",
  "status": "VERIFIED",
  "batch_status": "APPROVED_FOR_MANUFACTURING",
  "blockchain_tx": "TX-2026-000004"
}

GET /api/lab/tests/{batch_id}


## Lab Business Rule

If test_stage = PRE_MANUFACTURING
and result = FAIL:

    batch_status = BLOCKED

If test_stage = PRE_MANUFACTURING
and result = PASS:

    batch_status = APPROVED_FOR_MANUFACTURING


## 10. Transport

POST /api/transport/events

GET /api/transport/{batch_id}


## 11. IoT Sensor Readings

POST /api/iot/readings

Common fields:

batch_id
transport_id
storage_id
sensor_id
timestamp

BH1750:

light_intensity_lux

Limit Switch:

switch_status

MPU6050:

accel_x_g
accel_y_g
accel_z_g
gyro_x_dps
gyro_y_dps
gyro_z_dps
shock_detected
tilt_angle_deg

Load Cell + HX711:

weight_kg
weight_change_kg

Response:

{
  "reading_id": "READ-2026-0001",
  "status": "STORED",
  "tamper_status": "CRITICAL",
  "gate_open": true,
  "weight_changed": true,
  "red_led": true,
  "alerts_generated": 1,
  "blockchain_tx": "TX-2026-000006"
}

blockchain_tx is null unless a CRITICAL alert was raised.


## 12. IoT Alerts

GET /api/iot/alerts/{batch_id}


## IoT Rule Engine

For every incoming IoT reading:

1. Identify the batch.
2. Identify the sensor.
3. Determine the applicable rule.
4. Compare the sensor value with the rule.
5. If within limits → NORMAL.
6. If outside limits → create an IoT alert.
7. Assign alert severity.
8. Store the alert.
9. If the event is critical → send the event to the blockchain layer.


## 13. Storage

POST /api/storage/events

GET /api/storage/{medicine_batch_id}


## 14. Traceability

GET /api/trace/reverse/{medicine_batch_id}

GET /api/trace/forward/{raw_batch_id}

GET /api/trace/impact/{raw_batch_id}


## 15. Create Medicine Batch

POST /api/medicine

Request:

{
  "processing_batch_id": "PROCESS-2026-001",
  "manufacturer_id": "MFG-001",
  "product_name": "Ashwagandha Tablets",
  "manufacturing_date": "2026-08-26",
  "expiry_date": "2028-08-26"
}

Response:

{
  "medicine_batch_id": "MED-2026-001",
  "qr_id": "QR-2026-001",
  "status": "CREATED",
  "blockchain_tx": "TX-2026-000005"
}


## 16. Medicine Batch

GET /api/medicine/{medicine_batch_id}


## 17. QR Verification

GET /api/verify/{qr_id}

Response:

{
  "verified": true,
  "medicine_batch_id": "MED-2026-001",
  "product_name": "Ashwagandha Tablets",
  "batch_status": "RELEASED",
  "traceability": {
    "processing_batch_id": "PROCESS-2026-001",
    "raw_batches": [
      "RAW-2026-001",
      "RAW-2026-002"
    ],
    "plant_id": "PLANT-001"
  }
}


## 18. Consumer Reports

```http
POST /api/consumer/reports                              PUBLIC
```

Request. `report_status` is NOT accepted - a new report always opens as
`OPEN`, so one cannot be filed already resolved:

```json
{
  "medicine_batch_id": "MED-2026-001",
  "qr_id": "QR-2026-001",
  "reported_at": "2026-08-29T09:00:00",
  "issue_type": "headache",
  "symptoms": "Headache after consumption",
  "description": "Reported by a consumer"
}
```

`404` if that batch id and QR id do not belong together. One lookup, one
message: separate errors would let an anonymous caller confirm which batch
ids exist.

```http
GET   /api/consumer/reports/{report_id}                 any signed-in account
GET   /api/consumer/reports/batch/{medicine_batch_id}   any signed-in account
PATCH /api/consumer/reports/{report_id}/status          regulator
```

The status update takes a body, not a query parameter:

```json
{ "status": "UNDER_INVESTIGATION" }
```

Allowed: `OPEN`, `UNDER_INVESTIGATION`, `RESOLVED`, `DISMISSED`, `CLOSED`.
Anything else is `422`.


## 19. Investigations

A regulator's side of the consumer-report loop. All four require the
`regulator` role.

```http
POST  /api/investigations
GET   /api/investigations?status=OPEN
GET   /api/investigations/{investigation_id}
PATCH /api/investigations/{investigation_id}/close
```

Opening one sets the linked report to `UNDER_INVESTIGATION`:

```json
{
  "report_id": "RPT-2026-001",
  "auditor_id": "AUD-001",
  "suspected_stage": "TRANSPORT",
  "evidence_summary": "IoT custody gap under review."
}
```

`409` if that report already has an investigation that is not closed.

Closing one records the outcome and sets the report to `RESOLVED`:

```json
{
  "root_cause": "NO_TRACEABILITY_ANOMALY_FOUND",
  "action_taken": "CONTINUE_MONITORING"
}
```


## 19a. Listings and health

```http
GET /api/batches/raw?limit=&offset=          any signed-in account
GET /api/batches/processing?limit=&offset=   any signed-in account
GET /api/medicine?limit=&offset=             any signed-in account
GET /api/blockchain/events?limit=&offset=    any signed-in account
GET /api/investigations?status=              regulator

GET /                                        PUBLIC
GET /api/health                              PUBLIC
```

`GET /api/health` also reports whether the deployment is configured with real
secrets:

```json
{
  "status": "healthy",
  "database": "connected",
  "version": "1.1.0",
  "hardened": false
}
```

`"hardened": false` means TRACEVEDA_JWT_SECRET or TRACEVEDA_DEVICE_API_KEY is
still running on a generated development value.


## 20. Blockchain

POST /api/blockchain/events

Manual / admin anchoring. Batch, lab, medicine and critical IoT
events anchor themselves - see "Automatic Anchoring" below.

Request:

{
  "event_type": "BATCH_CREATED",
  "entity_type": "RAW",
  "entity_id": "RAW-2026-001",
  "data": {}
}

Response:

{
  "transaction_id": "TX-2026-000001",
  "event_hash": "9f2b...",
  "previous_hash": "GENESIS",
  "blockchain_status": "ANCHORED"
}


GET /api/blockchain/events/{transaction_id}

One anchored event.


GET /api/blockchain/batch/{entity_id}

Full anchored trail for one batch or medicine id, in chain order.

Response:

{
  "entity_id": "PROCESS-2026-001",
  "event_count": 4,
  "events": [ ... ]
}


GET /api/blockchain/verify/{transaction_id}

Recompute one event's hash.


GET /api/blockchain/verify-chain

Walk every event in sequence order and prove the whole chain.

Response:

{
  "valid": true,
  "checked": 376,
  "broken_at": null,
  "reason": null
}


## Automatic Anchoring

These routes anchor to the chain on success and return the
transaction id as "blockchain_tx". The field is null if anchoring
failed - a ledger outage never fails the underlying write.

POST /api/batches/raw            -> BATCH_CREATED    (RAW)
POST /api/batches/processing     -> BATCH_CREATED    (PROCESSING)
POST /api/batches/relationships  -> BATCH_LINKED     (PROCESSING)
POST /api/lab/tests              -> QUALITY_STATUS   (PROCESSING, PASS and FAIL)
POST /api/medicine               -> MEDICINE_LINKED  (MEDICINE)
POST /api/iot/readings           -> TAMPER_EVENT     (CRITICAL alerts only)

On-chain / off-chain split: only dispute-relevant, state-changing
events are anchored. WARNING and YELLOW alerts and the raw
high-frequency sensor readings stay in MongoDB only.


## Blockchain Ordering

The chain is ordered by an integer "sequence" field and nothing
else. It comes from an atomic counter, so concurrent writers cannot
fork the chain or mint duplicate transaction ids. Timestamps are
informational - MongoDB datetimes are only millisecond-precise and
have no tiebreak.


## Seed Data

blockchain_events.csv ships in a legacy schema. Load and migrate it
before verify-chain will report a fully valid history:

    python import_csv.py
    python migrate_seed_blockchain_events.py
