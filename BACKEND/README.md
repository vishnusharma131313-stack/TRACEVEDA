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
- Consumer QR verification and consumer-submitted reports.
- Auditor investigation and traceability workflows.
- MongoDB-backed event records with sequential SHA-256 hash-chain verification.
- Seed-data import and migration utilities.
- Automated tests using pytest, httpx and mongomock.

## Technology

- Python
- FastAPI and Uvicorn
- Pydantic
- MongoDB and PyMongo
- PyJWT
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
```

`TRACEVEDA_CORS_ORIGINS` is a comma-separated list. Add the deployed frontend origin when hosting the frontend separately.

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
| `routes/access_requests.py` | Stakeholder access requests |
| `routes/plants.py` | Botanical reference data |
| `routes/batches.py` | Raw/processing batches and relationships |
| `routes/lab.py` | Laboratory tests and certification records |
| `routes/transport.py` | Transport events |
| `routes/storage.py` | Storage events |
| `routes/iot.py` | IoT telemetry and alert evaluation |
| `routes/medicine.py` | Finished medicine records and QR-related workflows |
| `routes/trace.py` | Batch traceability queries |
| `routes/blockchain.py` | Hash-chain event operations and verification |
| `routes/consumer.py` | Public medicine verification and consumer reports |
| `routes/investigations.py` | Investigation workflows |

For request fields, roles, examples and endpoint details, see [`../docs/API_CONTRACT.md`](../docs/API_CONTRACT.md). The live `/docs` page is the most direct reference for the API version currently running.

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
