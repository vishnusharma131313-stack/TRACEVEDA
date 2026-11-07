# TraceVeda Frontend Updates --- Backend Integration Notes

> **Audience:** TraceVeda backend developer\
> **Comparison:** Previous `Frontend(2).zip` vs current
> `Frontend(4).zip`\
> **Purpose:** Identify frontend changes and the backend API work /
> contract checks needed for end-to-end integration.

------------------------------------------------------------------------

## 1. Executive summary

The current frontend is primarily an update to the existing
`Frontend/index.html` application. A file-by-file comparison of the two
ZIPs shows:

-   `Frontend/index.html` is the **only changed application
    source/documentation file**.
-   The current `index.html` is approximately **12,249 lines / 269.5
    KB**, compared with **8,176 lines / 163.8 KB** previously.
-   The other 40 non-binary project files in the previous archive are
    unchanged in the current archive, including `src/`,
    `src/api/client.js`, React pages/components, `FRONTEND_README.md`,
    `package.json`, and `.env.example`.
-   The current ZIP also contains `node_modules`; this is dependency
    output, not a source-code change. It should generally not be
    committed or sent as part of source handoff.

**Important:** The current ZIP therefore contains two frontend tracks:
the existing React/Vite source tree and a substantially expanded
standalone `index.html`. The new work described below is in that HTML
file. Do not assume that the React API client automatically covers the
new HTML workflows: the HTML has its own `fetch`/`apiRequest`
integration code.

The new HTML adds or expands transport evidence, geotagged evidence, QR
generation, access-request onboarding, two-stage lab certification,
transport investigation, and consumer reporting. Some are already wired
to HTTP requests; others are explicitly temporary or require backend
implementation/contract confirmation.

------------------------------------------------------------------------

## 2. Changes made in the frontend

### 2.1 Transport and logistics workflow

The current frontend adds/expands transport ledger submission for two
stages:

1.  **Raw batch → Processor**
    -   Captures crop, raw batch ID, farm name, quantity, destination,
        and transport date.
    -   Submits `transport_stage: "RAW_BATCH_TO_PROCESSOR"`.
2.  **Lab → Manufacturer**
    -   Captures processing batch ID, manufacturer organisation,
        quantity, and transport date.
    -   Submits `transport_stage: "LAB_TO_MANUFACTURER"`.

Both paths call `POST /api/transport` through `apiRequest()`.

**Backend integration:** confirm that `/api/transport` accepts both
stage values and the corresponding stage-specific fields. Confirm how
`batch_id` is resolved for raw vs processing batches, and return the
created transport record (including its ID and timestamp) so the UI can
show a persisted record rather than only a success alert.

### 2.2 Transport IoT evidence panel

The transport view now presents sensor-specific values for:

-   DHT22 temperature and humidity
-   BH1750 light intensity
-   Limit-switch / cargo-seal state
-   GPS / truck location
-   HX711 load-cell weight

The evidence loader calls:

-   `GET /api/iot/readings/{batch_id}`
-   `GET /api/iot/alerts/{batch_id}`

The UI expects `readingsData.readings` and `alertsData.alerts` arrays.
Alert-fetch failure is currently caught separately and treated as an
empty alert list, while reading-fetch failure is shown as an error.

**Backend integration:** ensure the readings endpoint returns the sensor
fields and units required by the panel, and that each record can be
associated with the requested batch/transport. Confirm the alert
response shape and whether alerts are filtered by batch ID. The frontend
should not display fabricated live readings.

### 2.3 Geotagged transport evidence

A new geotagged evidence flow captures an image and GPS coordinates,
then submits multipart form data to:

-   `POST /api/transport/geotag`

The request uses `FormData` and bearer authorization. **Do not require
`Content-Type: application/json` for this endpoint**; the browser must
set the multipart boundary automatically.

**Backend integration:** confirm the exact multipart field names,
required/optional fields, image type/size limits, coordinate format,
transport/batch association, authenticated transporter identity,
persistence location, and response shape. The backend should return a
stable evidence ID and stored metadata. If this evidence is meant to be
ledger-anchored, return the transaction/hash or a clear anchoring
status; the frontend currently shows a success message after a
successful HTTP response.

### 2.4 Medicine QR generation and retrieval

A new manufacturer QR panel supports:

-   Loading registered medicine batches.
-   Selecting a medicine batch.
-   Checking whether a QR already exists.
-   Displaying an existing QR.
-   Generating and displaying a new QR.

Requests used:

-   `GET /api/medicine`
-   `GET /api/medicine/{batch_id}/qr`
-   `POST /api/medicine/{batch_id}/qr`

The list loader accepts either a top-level array or `medicines` /
`batches` arrays. It reads batch IDs from `medicine_batch_id` or
`batch_id`.

The QR lookup UI expects a response containing at least: - `exists` -
`medicine_batch_id` - `qr_id` - `qr_code_data_url` (for displaying the
stored QR image)

The generation UI requires `qr_id`; it displays the returned QR data.

**Backend integration:** these three routes and their response formats
must be implemented or confirmed. QR creation must be idempotent /
uniqueness-safe: repeated clicks or retries must not create multiple QR
IDs for the same medicine batch. Generate and persist the QR ID
server-side. Return the same existing QR on subsequent lookup. Confirm
whether the image is returned as `qr_code_data_url`, a URL, or another
format, and align the frontend accordingly.

**Data consistency check:** the dropdown currently inserts a demo option
`MED-2026-001` in addition to backend results. Remove that hardcoded
option for production, or guard it behind an explicit demo mode. When
the backend returns no batches, the current code replaces the dropdown
with a "No registered medicine batches found" option.

### 2.5 Two-phase laboratory certification

The lab workflow now distinguishes two test phases:

-   `RAW_BATCH_TEST` --- raw-material testing; intended ID prefix
    `LABTEST-PRE-`
-   `FINAL_PRODUCT_QUALITY_TEST` --- finished-product testing; intended
    ID prefix `LABTEST-POST-`

The frontend expects the backend to generate sequential `lab_test_id`
values independently for the two phases. The frontend must not generate
these IDs.

The request is sent to:

-   `POST /api/lab/tests`

The current actual JSON body is:

``` json
{
  "batch_id": "<selected batch>",
  "lab_id": "<certificate input, or LAB-001>",
  "test_date": "<date selected in UI>",
  "test_type": "<display label for selected phase>",
  "result": "PASS or FAIL",
  "certificate_id": "<certificate input>"
}
```

The source comments describe a desired contract that also includes
`test_phase`, but **the actual request currently does not send
`test_phase`**. It sends `test_type` as a display label
(`Raw batch test` / `Final Product Quality test`), not the enum values
above. Also, `lab_id` is currently populated from the certificate input
(`cert || "LAB-001"`), which appears to be a frontend mapping error and
must be corrected before integration. The current request does not send
`test_parameters`.

**Backend + frontend action required:** 1. Agree on one canonical
request schema. 2. Add/send `test_phase` with the exact enum values if
the backend needs phase-specific ID generation. 3. Populate `lab_id`
from the authenticated user's organisation/lab identity, not from the
certificate field. 4. Decide whether `test_type` is needed separately
from `test_phase`. 5. Define `test_parameters` requirements (if any). 6.
Generate `lab_test_id` atomically on the backend, with separate PRE and
POST sequences. 7. Persist the user-entered `test_date`; maintain a
separate server-side verification/creation timestamp. 8. Return
`lab_test_id`, `batch_id`, `certificate_id`, `test_date`, `test_phase`,
`result`, and optional blockchain transaction/hash.

The frontend comments also say not to reintroduce legacy fields
`test_stage` or `verified_by`. Treat that as a frontend-side schema note
and confirm against the backend's actual model.

### 2.6 Transport batch investigation

The current UI includes an investigation panel that asks for a
processing batch ID and is intended to determine whether a transport
casualty/anomaly occurred using IoT evidence, including:

-   Limit-switch state
-   Latest alert status
-   Weight before/after and weight change
-   Latest reading for the requested processing batch

The frontend comments propose:

-   `GET /api/transport/investigate/{batch_id}`

with a structured response such as:

``` json
{
  "batch_id": "ASH-P-2026-001",
  "switch_status": "OPEN",
  "last_alert_status": "WARNING",
  "weight_before": 5.0,
  "weight_after": 4.6,
  "weight_change": -0.4,
  "casualty_detected": true,
  "investigation_status": "CASUALTY DETECTED"
}
```

**Critical current limitation:** `investigateBatch()` does **not** call
this endpoint yet. It contains explicitly marked temporary frontend
behaviour and currently displays "No casualty detected" without
consulting backend data. This must be replaced with the API call before
the UI can be used for real investigations.

**Backend integration:** implement/confirm the proposed endpoint, filter
readings by the requested processing batch, select the latest record
using its timestamp, apply the backend investigation rule, and return a
structured result. The frontend must display the backend's result only;
it must not decide casualty status itself.

### 2.7 Request Access onboarding

The sign-in modal now has a separate **Request Access** flow. It
collects stakeholder role and organisation/contact/location details. The
frontend comments explicitly specify a new endpoint:

-   `POST /api/access-requests`

Proposed body:

``` json
{
  "role": "<selected stakeholder role>",
  "organisation_name": "<organisation>",
  "location": "<location>",
  "contact_details": "<contact details>"
}
```

Expected backend workflow described in the frontend: 1. Validate and
store the request as `PENDING`. 2. Make it available to Admin/Auditor
for review. 3. On approval, assign/create the stakeholder ID. 4. Create
the corresponding user account. 5. Issue/provide TraceVeda credentials.

**Important:** the frontend explicitly says not to use
`POST /api/auth/signup` for this public Request Access form. It should
not create an active account immediately.

**Current limitation:** the request-access form is present, but its
integration comment says to replace temporary frontend handling with the
API. Treat this endpoint as pending until the submit handler is verified
to make the POST request.

### 2.8 Consumer medicine verification and reporting

The consumer flow now supports:

-   QR verification using `GET /api/verify/{qr_id}`.
-   Saving the verified QR ID in browser session storage.
-   Auto-filling the associated medicine batch into the report form.
-   Submitting a consumer report using `POST /api/consumer/reports`.
-   Auditor report listing using `GET /api/consumer/reports?limit=200`.

The report POST body currently includes:

``` json
{
  "medicine_batch_id": "<verified medicine batch>",
  "qr_id": "<previously verified QR ID>",
  "reported_at": "<ISO timestamp>",
  "issue_type": "<selected issue>",
  "symptoms": "<symptoms>",
  "description": "<description>",
  "is_synthetic": false
}
```

The frontend checks that the QR was verified before accepting a report.
The report-list view reads `data.reports` and displays report ID,
medicine batch, issue type, description/symptoms, and reported time.

**Backend integration:** confirm the verification response returns
`verified` and `qr_id` plus `medicine_batch_id` (or `batch_id`). Confirm
report creation validates that the QR belongs to the submitted medicine
batch; do not trust the browser-provided `is_synthetic` flag as an
authorization/security decision. Confirm the list endpoint is
role-protected for Admin/Auditor and supports `limit`.

### 2.9 Authentication and role handling

The HTML frontend now has role selection and maps frontend role labels
to backend roles. It calls:

-   `POST /api/auth/login`
-   `GET /api/auth/me`
-   `GET /api/auth/roles` (exposed through `window.TraceVedaAPI`)

The login request sends username/password. It stores `access_token` as
`traceveda_token` and user information as `traceveda_user`.

**Important integration concerns:** - There is a temporary hardcoded
transporter demo login (`tra-001` / `123`) that bypasses the backend and
stores a local user without an access token. Remove this for
production. - The role map includes `transporter`, but maps only the
roles shown in `getBackendRole()`; it currently maps `logistics` to
`logistics`, while the temporary transporter path uses `transporter`.
Backend and frontend must agree on the canonical transporter/logistics
role. - Role selection in the UI must not grant permissions. The backend
must derive the authenticated role from the token and enforce
authorization on every protected route. - Confirm the login response
contract. The frontend accepts either `data.user` or top-level
`username`, `role`, `full_name`, and `organisation_id`.

### 2.10 Processing batch UI helpers

The current HTML adds helper functions for adding/removing
processing-batch rows and updating lab/manufacturer batch field formats.
These are UI-side interactions. The comparison does not establish a new
confirmed backend route for these helpers; ensure the final submit
action is wired to the existing processing-batch creation contract and
that the backend validates parent raw-batch relationships and generated
IDs.

------------------------------------------------------------------------

## 3. Backend API integration matrix

The table distinguishes **HTTP calls already present in the current
HTML** from **proposed/pending integration**. An endpoint appearing in
frontend code does not prove that the backend route exists or that its
schema matches.

  --------------------------------------------------------------------------------------------------------
  Priority          Endpoint                                      Frontend usage     Status / backend
                                                                                     action
  ----------------- --------------------------------------------- ------------------ ---------------------
  P0                `POST /api/lab/tests`                         Submit lab         HTTP call exists;
                                                                  certification      **payload
                                                                                     mismatch/bug**:
                                                                                     missing `test_phase`,
                                                                                     `lab_id` is populated
                                                                                     from certificate
                                                                                     input, `test_type` is
                                                                                     a display label.
                                                                                     Finalize schema and
                                                                                     correct frontend.

  P0                `GET /api/transport/investigate/{batch_id}`   Transport casualty Documented as
                                                                  investigation      expected; **not
                                                                                     called**. UI
                                                                                     currently returns a
                                                                                     hardcoded "No
                                                                                     casualty detected".
                                                                                     Implement endpoint
                                                                                     and wire the call.

  P0                `POST /api/access-requests`                   Public stakeholder Documented as
                                                                  onboarding         required;
                                                                                     verify/implement
                                                                                     submit call. Must
                                                                                     create PENDING
                                                                                     request, not active
                                                                                     user.

  P0                `POST /api/transport/geotag`                  Upload photo + GPS HTTP call exists;
                                                                  evidence           confirm multipart
                                                                                     field names, file
                                                                                     handling,
                                                                                     authentication,
                                                                                     persistence and
                                                                                     ledger response.

  P1                `GET /api/medicine`                           Populate QR batch  HTTP call exists;
                                                                  dropdown           confirm list shape
                                                                                     (`[]`, `medicines`,
                                                                                     or `batches`) and ID
                                                                                     field.

  P1                `GET /api/medicine/{batch_id}/qr`             Check/retrieve     HTTP call exists;
                                                                  existing QR        confirm `exists`,
                                                                                     `qr_id`, and QR image
                                                                                     field/format.

  P1                `POST /api/medicine/{batch_id}/qr`            Generate QR        HTTP call exists;
                                                                                     implement server-side
                                                                                     unique/idempotent
                                                                                     generation and
                                                                                     persistence.

  P1                `POST /api/transport`                         Record             HTTP call exists;
                                                                  raw→processor and  confirm both
                                                                  lab→manufacturer   `transport_stage`
                                                                  transport          payload variants and
                                                                                     return shape.

  P1                `GET /api/iot/readings/{batch_id}`            Load transport     HTTP call exists;
                                                                  sensor readings    confirm response
                                                                                     `readings` and sensor
                                                                                     field names/units.

  P1                `GET /api/iot/alerts/{batch_id}`              Load transport     HTTP call exists;
                                                                  alerts             confirm response
                                                                                     `alerts` and batch
                                                                                     filtering.

  P1                `GET /api/verify/{qr_id}`                     Consumer QR        HTTP call exists;
                                                                  verification       confirm `verified`,
                                                                                     `qr_id`, and medicine
                                                                                     batch ID fields.

  P1                `POST /api/consumer/reports`                  Submit consumer    HTTP call exists;
                                                                  issue report       validate QR↔medicine
                                                                                     relationship and
                                                                                     persist report.

  P1                `GET /api/consumer/reports?limit=200`         Auditor/Admin      HTTP call exists;
                                                                  report list        confirm `reports`
                                                                                     response and role
                                                                                     permissions.

  P1                `POST /api/auth/login`                        Sign in            HTTP call exists;
                                                                                     confirm token and
                                                                                     user response fields.
                                                                                     Remove demo bypass.

  P2                `GET /api/auth/me`                            Session/user       Exposed in API
                                                                  identity helper    bridge; confirm
                                                                                     token-authenticated
                                                                                     response.

  P2                `GET /api/auth/roles`                         Role metadata      Exposed in API
                                                                  helper             bridge; confirm
                                                                                     canonical role names.
  --------------------------------------------------------------------------------------------------------

### Existing API calls retained in the HTML API bridge

`window.TraceVedaAPI` also exposes:

-   `GET /api/batches/raw`
-   `GET /api/batches/processing`
-   `GET /api/blockchain/events`
-   `GET /api/blockchain/verify-chain`
-   `GET /api/trace/reverse/{id}`
-   `GET /api/trace/forward/{id}`
-   `GET /api/trace/impact/{id}`
-   `GET /api/transport/{id}`
-   `GET /api/storage/{id}`

These helpers are defined near the end of `index.html`. Their presence
is not evidence that every visible panel is already using them.

------------------------------------------------------------------------

## 4. Shared API client / deployment considerations

The current standalone HTML defines its own API helper:

-   API origin is hardcoded as `https://traceveda.onrender.com`.
-   `apiRequest()` adds `Content-Type: application/json` by default,
    attaches `Authorization: Bearer <token>` when `traceveda_token`
    exists, parses JSON, and throws on non-2xx responses.
-   The geotag upload uses a separate `fetch()` path so it can send
    `FormData` without forcing a JSON content type.

**Recommended integration cleanup:** 1. Move the API origin to
environment/configuration rather than hardcoding the Render URL. 2. Keep
the JSON helper for JSON endpoints and the separate multipart upload
behaviour for geotagging. 3. Standardize token and user storage keys
across the standalone HTML and React app. The React app's
`src/lib/auth.js` should be checked before assuming the two tracks share
compatible session storage. 4. Standardize error parsing for FastAPI
validation errors (`detail` may be a string or an array). 5. Confirm
CORS for the deployed frontend origin and local Vite origin. 6. Avoid
success messages until the backend response confirms
persistence/anchoring.

------------------------------------------------------------------------

## 5. Backend contract decisions required before final integration

Please coordinate and freeze these contracts with the frontend:

1.  **Role vocabulary:** is the transport stakeholder role `transporter`
    or `logistics`? The current HTML uses both concepts in different
    places.
2.  **Lab test schema:** canonical `test_phase` enum, `test_type`,
    `test_parameters`, `lab_id` source, certificate validation, and
    response shape.
3.  **Lab test ID generation:** atomic sequential PRE and POST series,
    generated only by backend.
4.  **Access requests:** pending/approved/rejected lifecycle, admin
    review endpoints, stakeholder ID assignment, and credential
    issuance.
5.  **Transport records:** accepted stage values, required fields for
    each stage, and linkage to raw/processing batch IDs.
6.  **Geotag evidence:** multipart field names, image storage, GPS
    coordinate format, identity and batch association, and blockchain
    anchoring response.
7.  **QR lifecycle:** uniqueness, idempotency, image representation, and
    response for already-existing QR.
8.  **Transport investigation:** source collections, latest-reading
    selection, casualty rules, and structured response.
9.  **Consumer reports:** QR-to-batch validation, user/public submission
    policy, and auditor listing permissions.
10. **IoT response schema:** exact names/units for temperature,
    humidity, light, switch, GPS, weight, and alert severity.

------------------------------------------------------------------------

## 6. Suggested integration test sequence

Run these in order against the actual backend and a non-production test
dataset:

1.  Sign in with a real backend-issued account; verify token storage and
    protected endpoint access.
2.  Submit one raw→processor transport record and one lab→manufacturer
    transport record; confirm both are persisted and linked to the
    correct batch.
3.  Upload one geotagged photo with GPS coordinates; verify file
    metadata and evidence record are retrievable.
4.  Load IoT readings and alerts for a batch; confirm sensor names,
    units, timestamps, and alert association.
5.  Run transport investigation for a batch with a known anomaly and one
    known-safe batch; confirm the UI displays backend results, not the
    temporary hardcoded result.
6.  Submit raw-phase and final-product lab tests; verify correct phase,
    correct lab identity, unique PRE/POST IDs, persisted dates, and
    returned ledger metadata.
7.  Generate a medicine QR; repeat lookup and generation to verify the
    same QR is returned rather than creating duplicates.
8.  Verify the QR through the public consumer flow; confirm the response
    resolves the correct medicine batch.
9.  Submit a consumer report using that verified QR; confirm the backend
    rejects a mismatched QR/batch pair.
10. Sign in as Admin/Auditor and load consumer reports; verify access
    control and pagination/limit behaviour.
11. Submit a Request Access form; confirm it creates a PENDING request
    and does not create an active account before approval.

------------------------------------------------------------------------

## 7. Important limitations / do not assume

-   The comparison is based on the frontend ZIPs only. It does **not**
    verify the currently deployed backend routes or database schema.
-   Several endpoint descriptions are comments/specifications inside the
    frontend, not proof that those endpoints have been implemented.
-   Transport investigation is explicitly still temporary and currently
    displays a fixed "No casualty detected" result.
-   The lab POST body does not yet match the contract described in its
    own comments; fix the `lab_id` mapping and include the agreed phase
    field.
-   The QR dropdown contains a demo medicine batch ID; production should
    use backend data only.
-   The transporter demo login bypasses backend authentication and must
    be removed before production.
-   The React/Vite source tree and its API client were unchanged in this
    comparison. New standalone HTML requests are not automatically
    integrated into React routes or `src/api/client.js`.

------------------------------------------------------------------------

## 8. Files changed

  -----------------------------------------------------------------------
  File                                Change
  ----------------------------------- -----------------------------------
  `Frontend/index.html`               Expanded standalone frontend:
                                      transport stages, transport IoT
                                      display, geotag evidence upload, QR
                                      generation/retrieval, Request
                                      Access UI, lab test phases,
                                      transport investigation panel,
                                      consumer report flow, and API
                                      bridge.

  All other non-binary project files  No content changes detected
                                      compared with the previous ZIP.

  `Frontend/node_modules/`            Present in the current ZIP;
                                      generated dependencies, not
                                      application source changes.
  -----------------------------------------------------------------------

**Primary file for backend integration review:** `Frontend/index.html`.
