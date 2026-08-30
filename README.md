# TraceVeda

## AI + IoT + Blockchain Based Herbal Medicine Traceability System

TraceVeda is a supply-chain traceability platform designed to track herbal medicines from their raw-material origin to the final consumer.

The system combines:

- IoT-based monitoring
- MongoDB-based traceability
- Blockchain event verification
- QR-based medicine verification
- Consumer reporting
- End-to-end batch traceability

---

## System Flow

Farm
↓
Plant / Raw Material
↓
Processing
↓
Laboratory Verification
↓
IoT Monitoring
↓
Medicine Manufacturing
↓
Transport
↓
Storage
↓
QR Verification
↓
Consumer
↓
Traceability / Reports

---

## Backend Technology

- Python
- FastAPI
- MongoDB / MongoDB Atlas
- Pydantic
- Uvicorn
- SHA-256 cryptographic hash-chain ledger

---

## Blockchain Layer

### What it is

TraceVeda anchors every critical supply-chain action to a **cryptographic
hash chain** — an append-only ledger where each event carries the fingerprint
of the event before it.

This makes the supply-chain history **tamper-evident**: once an event is
anchored, it cannot be edited, reordered or removed without the system being
able to prove that it happened.

The ledger is implemented as a SHA-256 hash chain over MongoDB, following the
architecture recommended in the project research dossier — the same chaining
primitive that underpins permissioned ledgers, with none of the operational
overhead of running a consensus network during development.

### How the chain works

Every anchored event is fingerprinted together with the fingerprint of its
predecessor:

```text
event_hash = SHA256(
    event_type + entity_type + entity_id +
    event_data + timestamp + previous_hash
)
                     ▲
                     └── the previous event's event_hash
```

Because each hash feeds into the next, the events form a continuous chain:

```text
GENESIS ──▶ Event 1 ──▶ Event 2 ──▶ Event 3 ──▶ Event 4
             hash A       hash B       hash C      hash D
                          prev: A      prev: B     prev: C
```

Change anything inside Event 2 and its hash no longer recomputes. Correct that
hash and Event 3's `previous_hash` no longer matches. Remove Event 2 entirely
and a gap appears in the sequence. **Every route to altering history leaves a
mark the verifier can find.**

### What gets anchored, automatically

Anchoring is built into the supply-chain routes themselves — there is no
separate step to remember and nothing to wire up by hand. Each of these
endpoints anchors on success and returns the ledger transaction id as
`blockchain_tx`:

| Action | Endpoint | Event type | Entity |
|---|---|---|---|
| Raw batch created | `POST /api/batches/raw` | `BATCH_CREATED` | RAW |
| Processing batch created | `POST /api/batches/processing` | `BATCH_CREATED` | PROCESSING |
| Manufacturing linkage | `POST /api/batches/relationships` | `BATCH_LINKED` | PROCESSING |
| Lab result recorded | `POST /api/lab/tests` | `QUALITY_STATUS` | PROCESSING |
| Medicine manufactured | `POST /api/medicine` | `MEDICINE_LINKED` | MEDICINE |
| Critical tamper alert | `POST /api/iot/readings` | `TAMPER_EVENT` | resolved automatically |

Example response — the anchor is visible the instant the action completes:

```json
{
  "raw_batch_id": "RAW-2026-001",
  "status": "CREATED",
  "blockchain_tx": "TX-2026-000001"
}
```

Laboratory results are anchored for **both PASS and FAIL** outcomes, so the
quality record a dispute would turn on is always on the ledger.

### On-chain / off-chain split

The ledger carries what matters and stays lean by design:

**Anchored** — dispute-relevant, state-changing events: batch creation,
manufacturing linkage, quality status, medicine release, and CRITICAL tamper
alerts.

**Kept in MongoDB** — high-frequency telemetry: routine sensor readings, and
WARNING / YELLOW advisory alerts.

A transport node streaming temperature every few seconds produces thousands of
readings nobody will ever litigate. Keeping them off the ledger keeps
verification fast and the chain focused on evidence, which is standard practice
for production traceability systems.

### Race-free ordering

The chain is ordered by an **atomic sequence counter**, not by timestamps.

Multiple IoT devices reporting simultaneously — or a batch creation immediately
followed by a lab test — receive strictly increasing, collision-free sequence
numbers from a single atomic operation. Transaction ids are derived from the
same counter, so they are unique by construction.

The result: the chain stays correct and linear under concurrent load, and every
event has one unambiguous place in history.

### Verification

A single call proves the integrity of the entire recorded history:

```http
GET /api/blockchain/verify-chain
```

```json
{
  "valid": true,
  "checked": 376,
  "broken_at": null,
  "reason": null
}
```

The verifier walks every event in sequence order and confirms that each hash
recomputes correctly and that each event links to its true predecessor. If
anything is ever off, the response names the exact transaction and the reason —
turning verification into an actionable audit rather than a yes/no answer.

### Blockchain endpoints

```http
POST /api/blockchain/events              # manual / admin anchoring
GET  /api/blockchain/events/{tx_id}      # one anchored event
GET  /api/blockchain/batch/{entity_id}   # full anchored trail for a batch
GET  /api/blockchain/verify/{tx_id}      # verify a single event
GET  /api/blockchain/verify-chain        # verify the entire chain
```

`GET /api/blockchain/batch/{entity_id}` returns the complete anchored history
of any batch or medicine id in chain order — the audit trail behind the QR
verification and reverse-trace flows:

```json
{
  "entity_id": "PROCESS-2026-001",
  "event_count": 4,
  "events": [
    { "sequence": 2, "transaction_id": "TX-2026-000002", "event_type": "BATCH_CREATED"  },
    { "sequence": 3, "transaction_id": "TX-2026-000003", "event_type": "BATCH_LINKED"   },
    { "sequence": 4, "transaction_id": "TX-2026-000004", "event_type": "QUALITY_STATUS" },
    { "sequence": 6, "transaction_id": "TX-2026-000006", "event_type": "TAMPER_EVENT"   }
  ]
}
```

### Ledger event schema

```text
transaction_id     TX-<year>-<sequence>   unique ledger reference
sequence           int                    atomic, strictly increasing
event_type         str                    BATCH_CREATED, QUALITY_STATUS, ...
entity_type        str                    RAW | PROCESSING | MEDICINE
entity_id          str                    batch / medicine this event is about
event_data         dict                   event payload
timestamp          str                    ISO8601 UTC
previous_hash      str                    prior event's hash, or GENESIS
event_hash         str                    SHA-256 of the canonical payload
blockchain_status  str                    ANCHORED
```

### Built to scale up

The ledger is isolated behind a single service
(`services/blockchain_service.py`). The event vocabulary, the on-chain /
off-chain split and every anchor point are already in place and stable, so
moving to a full permissioned ledger such as Hyperledger Fabric is a change
inside one service — the supply-chain routes stay exactly as they are.

### Verified by tests

The blockchain layer ships with **17 automated tests**, running against an
in-memory MongoDB so no database server is required:

- Full supply-chain flow, asserting every step anchors and the chain verifies
- **50-thread concurrency stress test** proving the chain stays valid and
  linear under simultaneous writes
- Tamper-detection coverage for edited, deleted and re-hashed events
- Seed-data migration verified against the real 375-event dataset

```bash
cd BACKEND
python -m pytest tests/ -q
```

---

## Backend Structure

```text
BACKEND/
│
├── main.py
├── database.py
├── import_csv.py
├── migrate_seed_blockchain_events.py
├── requirements.txt
│
├── models/
│   └── schemas.py
│
├── routes/
│   ├── batches.py
│   ├── blockchain.py
│   ├── consumer.py
│   ├── iot.py
│   ├── lab.py
│   ├── medicine.py
│   ├── storage.py
│   ├── trace.py
│   └── transport.py
│
├── services/
│   └── blockchain_service.py
│
├── tests/
│   ├── mongo_harness.py
│   ├── test_blockchain_integration.py
│   ├── test_blockchain_concurrency.py
│   └── test_seed_migration.py
│
└── TraceVeda_Master_Dataset/
```

---

## Setup

```bash
cd BACKEND
pip install -r requirements.txt
```

Load the dataset and prepare the ledger:

```bash
python import_csv.py                       # load the master dataset
python migrate_seed_blockchain_events.py   # prepare the seeded ledger history
```

Run the API:

```bash
uvicorn main:app --reload
```

Confirm the ledger is healthy:

```http
GET /api/blockchain/verify-chain
```

Run the test suite:

```bash
python -m pytest tests/ -q
```