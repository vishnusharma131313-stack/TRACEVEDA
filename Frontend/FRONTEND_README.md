# TraceVeda — Frontend

React + Vite frontend for the TraceVeda blockchain + IoT traceability platform.

---

## Run it

```bash
cd TRACEVEDA/Frontend
npm install
npm run dev          # http://localhost:5173
```

The backend must be running for anything to load — this app ships **no mock
data**. If the API is down, every screen shows an explicit "could not reach the
backend" state rather than inventing rows.

```bash
cd TRACEVEDA/BACKEND
pip install -r requirements.txt
python import_csv.py                       # load the master dataset
python migrate_seed_blockchain_events.py   # migrate the seeded ledger history
uvicorn main:app --reload                  # http://localhost:8000
```

`migrate_seed_blockchain_events.py` is not optional. Until it runs,
`GET /api/blockchain/verify-chain` reports the chain as broken (the seeded rows
carry a legacy schema with no `sequence` field), and the header integrity badge
will correctly show red.

### Environment

| Variable | Default | Description |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | Backend base URL. Set in `.env`. |

`vite.config.js` also proxies `/api` to `localhost:8000`, so leaving
`VITE_API_URL` empty works for local development too.

```bash
npm run build        # production bundle into dist/
npm run preview      # serve the built bundle
```

---

## Screens

| Route | Screen | What it is for |
|---|---|---|
| `/login` | Sign in | Username + password against `POST /api/auth/login` |
| `/dashboard` | Batch command center | Every raw / processing / medicine batch |
| `/batch/:kind/:id` | **Batch detail** | Lineage, timeline, lab, IoT — the main screen |
| `/blockchain` | Blockchain explorer | Ledger list, per-event verify, whole-chain verify |
| `/trace` | Trace & recall | Reverse trace and the recall simulator |
| `/iot` | IoT live monitor | Gauges, history, and the demo tamper trigger |
| `/verify/:qrId` | Consumer QR view | **Public** — no login, mobile first |

`:kind` is one of `raw`, `processing`, `medicine`.

---

## Demo path

The seeded dataset is the one to demo against. Useful ids:

- Medicine `MED-2026-001` (QR `QR-2026-001`)
- Processing `ASH-P-2026-001`
- Raw `ASH-2026-001`, farm `FARM-001`

A run that hits every claim in about two minutes:

1. **`/blockchain` → "Verify entire chain".** 375 seeded events walk in
   sequence order and come back valid. This is the strongest ten seconds
   available — press it live.
2. **`/dashboard` → open `MED-2026-001`.** The lineage graph draws
   farm → raw → processing → medicine from real `batch_relationships` rows.
   Every node is click-through.
3. **On that page, expand a ledger entry in the timeline → "Verify this
   event".** Stored hash and recomputed hash appear side by side.
4. **`/iot` → select `MED-2026-001` → "Trigger tamper event".** Gate `OPEN`
   plus a `-0.82 kg` weight change is exactly what the backend's 2FA rule
   treats as CRITICAL, so it anchors. The block animation plays in place and
   the returned `blockchain_tx` is verifiable without leaving the screen.
5. **`/trace` → recall mode → `ASH-2026-001`.** Forward trace plus impact
   analysis: the exact set of finished batches to pull, and nothing more.
6. **`/verify/QR-2026-001`** in a phone-sized window — the public view, with
   no internal ids anywhere on it.

---

## How it is put together

```
src/
├── api/client.js              every endpoint, returning response BODIES
├── lib/
│   ├── batches.js             one batch shape across three collections
│   ├── status.js              the real status vocabulary + colour tone
│   ├── iot.js                 sensor thresholds mirrored from the backend
│   ├── format.js              dates, hashes, JSON-string coercion
│   ├── roles.js               which screens each server-issued role sees
│   └── auth.js                token storage and session restore
├── components/
│   ├── blockchain/            BlockAnchor, TxHashChip, VerifyEventButton
│   ├── trace/LineageGraph     the lineage tree + one builder per endpoint
│   ├── timeline/EventTimeline the merged on-chain / off-chain timeline
│   ├── iot/                   Gauge, SensorStrip
│   ├── layout/                AppShell, ChainIntegrityBadge
│   └── ui/                    Card, StatusChip, EmptyState, Skeleton, Icons
└── pages/                     one file per screen
```

### Things worth knowing before you edit

**`api/client.js` returns response bodies, not axios envelopes.** No caller
writes `.data`. Forgetting it was the single biggest source of blank screens in
the earlier draft of this app.

**The backend is not internally consistent, and `lib/batches.js` is where that
is absorbed.** Raw and medicine batches carry `batch_status`; processing
batches carry `status`. Read status through `statusOf()`, never directly.

**The seeded dataset does not match the live API shapes.** Both are real things
a judge can hit, so both are handled:

| | Seeded (`import_csv.py`) | Live API |
|---|---|---|
| raw status | `VERIFIED` | `CREATED` |
| processing status | `COMPLETED` | `CREATED` / `APPROVED_FOR_MANUFACTURING` / `BLOCKED` |
| batch ids | `ASH-2026-001`, `ASH-P-2026-001` | `RAW-2026-001`, `PROCESS-2026-001` |
| `lab_tests.test_parameters` | JSON **string** | `dict` |
| transport rows | `departure_time`, `transport_stage` | `event_timestamp`, `event_type` |
| ledger event types | + `MEDICINE_LINKAGE`, `SHIPMENT_MILESTONE`, `ENVIRONMENTAL_ALERT` | `MEDICINE_LINKED`, `BATCH_LINKED` |

Nothing may assume an id prefix, and `format.asObject()` exists specifically to
absorb the `test_parameters` split.

**Indigo means the ledger, and only the ledger.** `chain-*` is never used for
anything that is not tamper-evidence. That association is what makes the
on-chain / off-chain split legible without a caption.

**`lib/iot.js` mirrors `routes/iot.py`.** Gauges turn amber at exactly the
value that makes the server raise an alert. If the backend rules move, move
these.

**Ordering the ledger by timestamp is a bug.** The chain is ordered by
`sequence` and nothing else — the backend's own contract says timestamps are
informational and have no millisecond tiebreak. The explorer never re-sorts by
time.

---

## Known gaps, and why

### Closed

These were real backend gaps that the UI used to work around. They are fixed,
and the workarounds are gone:

| Was | Now |
|---|---|
| No `POST /api/auth/login` — role selection was client-side | Real sign-in. The role comes from the server inside a signed token and is re-checked on every request. |
| No `GET /api/plants` | Implemented, with search. Available as `plantAPI` in `api/client.js`. |
| No `GET /api/investigations` | Implemented, regulator-only, as `investigationAPI`. |
| Seeded alerts loaded into `alerts`, but the endpoint read `iot_alerts` | `GET /api/iot/alerts/{id}` reads both and tags each row with `source: "live" \| "seed"`. |
| `GET /api/storage/{id}` keyed only on `raw_batch_id` | Matches `raw_batch_id` **or** `medicine_batch_id`, so seeded storage rows are visible. |

### Still open

| Gap | What the UI does |
|---|---|
| No trace endpoint accepts a processing batch id | Processing lineage is assembled from `/relationships` plus `/api/medicine`. |
| No screen consumes `plantAPI` or `investigationAPI` yet | The endpoints and client methods exist; wiring them into the batch detail and consumer-report screens is the next UI change. |

---

## Verification

All harnesses live in the session scratchpad, not in this repo — they are dev
tools, and no fixture data ships in `src/`.

| Harness | Assertions | Result |
|---|---|---|
| Data layer vs. the real seed CSVs | 63 | pass |
| Lineage + timeline builders vs. reconstructed trace responses | 32 | pass |
| API client + data layer vs. a **live backend** | 72 | pass |
| Headless browser render of all 11 routes (Edge via CDP) | 98 | pass |

`npm run build` compiles clean and every module transforms without error
through the dev server.

The live runs used the real backend code against an in-memory MongoDB
(`mongomock`, which the repo already depends on for its test suite) seeded from
`TraceVeda_Master_Dataset`. Only the storage driver was substituted — the
routers, `blockchain_service`, the SHA-256 chain, the atomic sequence counter
and the IoT rule engine were all the production code path.

Confirmed live, end to end:

- `verify-chain` walks 375 seeded events and returns valid.
- The tamper trigger posts the payload from `lib/iot.js`, the backend's 2FA
  rule raises a CRITICAL `tamper_2fa` alert, it anchors as `TAMPER_EVENT`, the
  returned transaction verifies (stored hash == recomputed hash), and the chain
  re-verifies at 376. The WARNING alert raised by the same reading stays
  off-chain — the split the timeline claims is real.
- A nominal reading raises no alert and is not anchored.
- The consumer QR page renders `Authentic` for `QR-2026-001` and leaks no
  internal ids (asserted: no `ASH-*`, `ASH-P-*` or `TX-*` anywhere in its text).
- Every route renders with **zero console errors and zero exceptions**.

Still worth doing before demo day: the same pass against a real MongoDB
instance rather than `mongomock`, since only the driver differed.
