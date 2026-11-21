# TraceVeda Backend

FastAPI service for TraceVeda's batch traceability, stakeholder workflows, IoT ingestion, QR verification, consumer reports and investigation features.

The backend uses MongoDB for application records and a sequential SHA-256 hash chain for selected tamper-evident events.

## Contents

- [Features](#features)
- [Technology](#technology)
- [Project structure](#project-structure)
- [Requirements](#requirements)
- [Local setup](#local-setup)
- [Environment configuration](#environment-configuration)
- [Load demonstration data](#load-demonstration-data)
- [Run the API](#run-the-api)
- [API areas](#api-areas)
- [IoT device integration](#iot-device-integration)
- [Tests](#tests)
- [Security and operational notes](#security-and-operational-notes)

## Features

- JWT-based user authentication and role-aware route authorization.
- Batch, plant, laboratory, transport, storage and medicine workflows.
- IoT telemetry ingestion and threshold-based alert generation.
- Public AI website assistant powered by the Gemini Developer API, with a built-in FAQ fallback when Gemini is not configured or temporarily unavailable.
- Consumer QR verification and consumer-submitted reports.
- Auditor investigation and traceability workflows.
- MongoDB-backed event records with sequential SHA-256 hash-chain verification.
- Private laboratory PDF reports stored in MongoDB GridFS, with authenticated downloads and SHA-256 report fingerprints.
- Seed-data import and migration utilities.
- Automated tests using pytest, httpx and mongomock.

## Technology

- Python
- FastAPI and Uvicorn
- Pydantic
- MongoDB and PyMongo
- PyJWT
- Google Gen AI SDK (Gemini-powered public website assistant)
- pytest, httpx and mongomock

Dependencies and pinned versions are listed in `requirements.txt`.

## Project structure

```text
BACKEND/
├── main.py                         # FastAPI app and router registration
├── config.py                       # Environment-based settings
├── database.py                     # MongoDB connection
├── dependencies.py                 # Authentication/authorization dependencies
├── models/
│   └── schemas.py                  # Shared request/response schemas
├── routes/                         # API route modules
├── services/                       # Accounts, IDs, indexes, security, hash chain
├── tests/                          # Backend automated tests
├── TraceVeda_Master_Dataset/       # CSV reference/demo dataset
├── import_csv.py                   # Import CSV data
├── migrate_seed_blockchain_events.py
├── seed_users.py                   # Create demonstration users
├── requirements.txt
├── pytest.ini
└── .env.example
```

## Requirements

- Python 3.10 or later, compatible with the pinned packages.
- MongoDB running locally or accessible through MongoDB Atlas.
- Git, if cloning the repository.

## Local setup

Run these commands from the `BACKEND/` directory.

### 1. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

On macOS/Linux:

```bash
source .venv/bin/activate
```

### 2. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Configure environment variables

Copy `.env.example` to `.env`:

```powershell
# Windows PowerShell
Copy-Item .env.example .env
```

```bash
# macOS/Linux
cp .env.example .env
```

Edit `.env` and configure the values for your environment. At minimum, set a reachable MongoDB URI, a strong JWT secret and a device API key.

Example:

```env
MONGO_URI=mongodb://localhost:27017
DB_NAME=traceveda
TRACEVEDA_JWT_SECRET=<long-random-secret>
TRACEVEDA_DEVICE_API_KEY=<shared-device-key>
TRACEVEDA_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
GEMINI_API_KEY=<your-gemini-api-key>
GEMINI_MODEL=gemini-3.5-flash-lite
TRACEVEDA_MAX_LAB_REPORT_BYTES=10485760
```

`TRACEVEDA_CORS_ORIGINS` is a comma-separated list. Add the deployed frontend origin when hosting the frontend separately.

The public website assistant uses the Gemini Developer API. Set `GEMINI_API_KEY` on the backend only; do not put it in Vercel frontend variables. `GEMINI_MODEL` defaults to `gemini-3.5-flash-lite`. If the Gemini key is missing or the provider is temporarily unavailable, the assistant falls back to its built-in FAQ responses.

Laboratory PDF reports are stored in the same MongoDB database using GridFS (the `lab_reports.files` and `lab_reports.chunks` collections). This avoids relying on Render's ephemeral application filesystem. The default upload limit is 10 MiB; override it with `TRACEVEDA_MAX_LAB_REPORT_BYTES`. The upload endpoint accepts the lab test fields as JSON in a multipart `payload` field and the optional file in a multipart `report` field. The response includes `report.download_url`; downloading that URL requires an authenticated TraceVeda bearer token.

Do not commit `.env`. Keep real secrets outside source control.

## Load demonstration data

If you want to initialise a local database with the repository's demonstration dataset, run the scripts from `BACKEND/` in this order:

```bash
python import_csv.py
python migrate_seed_blockchain_events.py
python seed_users.py
```

- `import_csv.py` imports the CSV collections from `TraceVeda_Master_Dataset/`.
- `migrate_seed_blockchain_events.py` prepares the seeded events for the hash-chain ledger.
- `seed_users.py` creates the project's demonstration user accounts.

Review script output and the target database before rerunning import or migration scripts. These scripts are intended for controlled setup/demo workflows, not blind execution against a production database.

## Run the API

Start the development server from `BACKEND/`:

```bash
uvicorn main:app --reload
```

Useful local URLs:

| URL | Purpose |
|---|---|
| `http://127.0.0.1:8000/` | API welcome response |
| `http://127.0.0.1:8000/api/health` | API and database health |
| `http://127.0.0.1:8000/docs` | Interactive Swagger/OpenAPI docs |
| `http://127.0.0.1:8000/redoc` | ReDoc API reference |

The health endpoint reports whether MongoDB is connected and whether the configured security secrets are hardened. A running API process does not by itself guarantee database connectivity.

## API areas

The application registers route modules for the following areas:

| Route module | Main responsibility |
|---|---|
| `routes/auth.py` | Login, current-user information and role discovery |
| `routes/assistant.py` | Anonymous public assistant sessions and chat responses using Gemini or the built-in FAQ fallback |
| `routes/access_requests.py` | Stakeholder access requests |
| `routes/plants.py` | Botanical reference data |
| `routes/batches.py` | Raw/processing batches and relationships |
| `routes/lab.py` | Laboratory tests, PDF certificates (GridFS), and authenticated report downloads |
| `routes/transport.py` | Transport events |
| `routes/storage.py` | Storage events |
| `routes/iot.py` | IoT telemetry and alert evaluation |
| `routes/medicine.py` | Finished medicine records and QR-related workflows |
| `routes/trace.py` | Batch traceability queries |
| `routes/blockchain.py` | Hash-chain event operations and verification |
| `routes/consumer.py` | Public medicine verification and consumer reports |
| `routes/investigations.py` | Investigation workflows |

For request fields, roles, examples and endpoint details, see [`../docs/API_CONTRACT.md`](../docs/API_CONTRACT.md). The live `/docs` page is the most direct reference for the API version currently running.

## Public AI assistant integration

The public website assistant is implemented in `routes/assistant.py` under
`/api/assistant`. It answers questions about TraceVeda's website and platform
features. It supports English, Hindi and Hinglish responses and is designed as
a public website guide, not as an authenticated stakeholder agent.

The assistant uses the Google Gemini Developer API through the Google Gen AI
SDK. Configure `GEMINI_API_KEY` and, optionally, `GEMINI_MODEL` in the backend
`.env` file. The default model is `gemini-3.5-flash-lite`. The Gemini key must
remain on the backend and must never be exposed through frontend code or
`VITE_` variables.

If the Gemini key is missing or the provider request fails, the backend
returns a built-in FAQ response. The response includes a `provider` field
(`gemini` or `fallback`) so the caller can identify which response path was
used.

### Assistant endpoints

| Endpoint | Purpose |
|---|---|
| `POST /api/assistant/session` | Create an anonymous assistant conversation and return its session ID and expiry |
| `GET /api/assistant/session/{session_id}` | Retrieve the conversation history for a valid session |
| `DELETE /api/assistant/session/{session_id}` | Delete an anonymous conversation |
| `POST /api/assistant/chat` | Submit a message and receive a Gemini-generated or FAQ fallback reply |

The chat request contains a `session_id` and a non-empty `message` (maximum
1,200 characters). A session is limited to 40 messages per hour. Conversation
history is retained for the configured session period, which defaults to
30 days and can be changed with `TRACEVEDA_ASSISTANT_SESSION_DAYS`. The chat
keeps a bounded recent message history for context.

The assistant is intentionally restricted to public website guidance. It
cannot access private account data, live telemetry, private batch records or
administrator actions; it cannot create accounts, approve access requests,
change roles or modify supply-chain records. Account requests and approval
remain separate application workflows. It must not be used for medical advice
or as a guarantee that a medicine is safe.

## IoT device integration

The ESP32 Storage and Truck Nodes submit telemetry to:

```http
POST /api/iot/readings
Content-Type: application/json
X-Device-Key: <TRACEVEDA_DEVICE_API_KEY>
```

The device key sent by the firmware must match `TRACEVEDA_DEVICE_API_KEY` in the backend environment.

The request model supports fields including:

- Batch, storage/transport and sensor identifiers.
- Timestamp.
- Temperature and humidity.
- GPS latitude, longitude and GPS validity.
- Light intensity.
- Limit-switch status.
- Weight and weight change.
- Legacy motion-related fields retained in the API schema.

The final integrated hardware firmware does not use the MPU motion sensor. Its presence as optional fields in the backend request schema does not mean that an MPU sensor is part of the final hardware build.

The backend validates incoming readings, evaluates configured rules and may return an alert/LED state to the device. See `routes/iot.py` and the hardware guide for the current device implementation.

## Tests

Run the test suite from `BACKEND/`:

```bash
python -m pytest tests/ -q
```

To run a specific test file:

```bash
python -m pytest tests/test_auth.py -q
```

Tests cover areas such as authentication, data integrity, seeded workflows, reference routes and hash-chain behavior. Run the tests in your own environment before reporting a pass; results can depend on dependency versions and database/test configuration.

## Security and operational notes

- Set `TRACEVEDA_JWT_SECRET` and `TRACEVEDA_DEVICE_API_KEY` explicitly before deployment.
- The application can generate/use development fallback values when secrets are missing. Startup warnings and `/api/health` expose this condition; fallback values are for local development only.
- The device key is a shared credential. Do not publish it in a public firmware repository or expose it in screenshots.
- Configure CORS with explicit frontend origins. Avoid wildcard origins for deployments.
- Keep MongoDB credentials and `.env` files private.
- Use a separate database for tests and demos. Do not run seed/import scripts against production data without reviewing their behavior.
- The SHA-256 hash chain is a tamper-evident application mechanism; it should not be described as a deployed decentralised blockchain network.

---

For the full project overview and setup, see the [main repository README](../README.md).
