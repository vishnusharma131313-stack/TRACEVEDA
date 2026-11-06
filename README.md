# TRACEVEDA

### Blockchain- and IoT-enabled traceability for Ayurvedic herbs

TRACEVEDA is an end-to-end digital traceability platform designed to
connect medicinal-herb sourcing, processing, laboratory verification,
transportation, storage, manufacturing and consumer verification. It
combines batch lineage, IoT monitoring, QR-based verification, consumer
reporting and tamper-evident event records to support evidence-based
investigation across the supply chain.

------------------------------------------------------------------------

## Contents

-   [Problem addressed](#problem-addressed)
-   [Solution overview](#solution-overview)
-   [Key capabilities](#key-capabilities)
-   [System architecture](#system-architecture)
-   [IoT hardware](#iot-hardware)
-   [Technology stack](#technology-stack)
-   [Repository structure](#repository-structure)
-   [Getting started](#getting-started)
-   [Configuration and security](#configuration-and-security)
-   [Dataset and demo data](#dataset-and-demo-data)
-   [API documentation](#api-documentation)
-   [Testing](#testing)
-   [Current implementation and future
    work](#current-implementation-and-future-work)
-   [Contributors](#contributors)

## Problem addressed

Traceability information in a multi-stage herbal supply chain can be
distributed across sourcing, processing, laboratory testing, transport,
storage and manufacturing records. A laboratory result alone does not
describe the conditions a batch experiences after testing. When a
quality or safety concern is reported, investigators need to connect the
finished medicine to its upstream batches, review relevant evidence and
identify other products that may share an affected source.

## Solution overview

TRACEVEDA assigns digital identities to supply-chain batches and
maintains parent--child relationships as raw materials move through
processing and manufacturing. IoT nodes collect environmental and
handling data during storage and transportation. The backend links these
records with batch, laboratory, transport and manufacturing information.
QR verification provides consumers with access to relevant product
provenance and a channel to report concerns.

### End-to-end journey

``` text
Farm / Collection
       |
       v
Raw-material batch
       |
       v
Transport + IoT monitoring
       |
       v
Processing batch
       |
       v
Laboratory verification
       |
       v
Transport + IoT monitoring
       |
       v
Manufacturer storage / production
       |
       v
Medicine batch + QR
       |
       v
Consumer verification / issue report
       |
       v
Auditor investigation
       |
       +---- Reverse trace to source
       |
       +---- Forward impact analysis of related batches
```

## Key capabilities

-   **Batch identity and lineage:** Unique identifiers and parent--child
    batch relationships connect raw materials, processing batches and
    finished medicines.
-   **IoT monitoring:** ESP32-based nodes collect temperature, humidity,
    light, door-state, location and payload-weight readings, depending
    on the node.
-   **Storage and transport evidence:** Separate Storage and Truck nodes
    monitor different stages of the physical supply chain.
-   **Offline buffering:** Firmware uses ESP32 LittleFS storage to
    retain queued readings during network interruptions and upload them
    when connectivity returns.
-   **Backend ingestion:** Sensor readings are sent to the backend using
    HTTPS API requests and device-key authentication.
-   **Laboratory records:** Test results are associated with relevant
    batches.
-   **QR verification:** A medicine QR identifier can be used to
    retrieve its verification and traceability information.
-   **Consumer reporting:** Consumers can submit an issue report against
    a medicine/QR record.
-   **Reverse trace and forward impact analysis:** Investigators can
    trace a medicine upstream and identify downstream batches linked to
    an affected source.
-   **Tamper-evident event history:** Critical supply-chain events are
    recorded in a sequential SHA-256 hash-chain ledger.

## System architecture

``` text
ESP32 Storage Node                 ESP32 Truck Node
(DHT22, BH1750, limit switch)      (DHT22, BH1750, GPS,
          |                         limit switch, HX711/load cell)
          | HTTPS + device key              |
          +---------------+-----------------+
                          |
                          v
                  FastAPI backend
                          |
          +---------------+-------------------+
          |               |                   |
          v               v                   v
      MongoDB       Traceability/API     SHA-256 event
   operational data    workflows         hash-chain ledger
          |               |                   |
          +---------------+-------------------+
                          |
                          v
                 Web frontend / QR
                          |
        +-----------------+------------------+
        |                 |                  |
   Stakeholder        Consumer           Auditor /
   workspaces         verification       investigation
```

**Ledger clarification:** The current backend implements a sequential
SHA-256 hash-chain event ledger stored with MongoDB. This provides
tamper-evident event verification. It is not currently a deployed
Hyperledger Fabric network. A permissioned blockchain such as
Hyperledger Fabric is a possible future integration.

## IoT hardware

### Storage Node

  Component      Purpose                                    ESP32 connection
  -------------- ------------------------------------------ ---------------------
  ESP32          Sensor acquisition and API communication   Controller
  DHT22          Temperature and humidity                   DATA: GPIO 4
  BH1750         Light intensity                            I²C: SDA 21, SCL 22
  I²C LCD 20×4   Local readings and status                  I²C: SDA 21, SCL 22
  Limit switch   Storage-door state                         GPIO 27
  Red LED        Backend-directed alert indication          GPIO 25

### Truck Node

  Component           Purpose                                    ESP32 connection
  ------------------- ------------------------------------------ ---------------------------
  ESP32               Sensor acquisition and API communication   Controller
  DHT22               Temperature and humidity                   DATA: GPIO 4
  BH1750              Light intensity                            I²C: SDA 21, SCL 22
  I²C LCD 16×2        Local readings and status                  I²C: SDA 21, SCL 22
  GPS module          Geographic location                        UART2: ESP32 RX 16, TX 17
  Limit switch        Transport-compartment door state           GPIO 27
  HX711 + load cell   Payload weight measurement                 DT 32, SCK 33
  Red LED             Backend-directed alert indication          GPIO 25

The firmware in this repository currently uses DHT22 declarations. If a
DHT11 is substituted, update the DHT sensor type in both node sketches
and validate the resulting readings. Confirm the voltage requirements of
the exact breakout boards before wiring; ESP32 GPIOs are not 5 V
tolerant. The LCD I²C backpack may require level shifting if its
pull-ups drive SDA/SCL to 5 V.

### Firmware folders

-   `HARDWARE/Storage_Node/Storage_Node_Backend/`
-   `HARDWARE/Truck_Node/Truck_Node_Backend/`
-   `HARDWARE/Component_Testing/` contains individual sensor and
    peripheral test sketches.

## Technology stack

  -----------------------------------------------------------------------
  Layer                               Technologies
  ----------------------------------- -----------------------------------
  Microcontroller / firmware          ESP32, C++, Arduino framework

  Sensors                             DHT22, BH1750, GPS, limit switch,
                                      HX711/load cell

  Device connectivity                 Wi-Fi, HTTPS, REST API

  Offline device queue                LittleFS

  Backend                             Python, FastAPI, Pydantic, Uvicorn

  Database                            MongoDB, PyMongo

  Event integrity                     SHA-256 sequential hash-chain
                                      ledger

  Frontend                            HTML, CSS, JavaScript; Vite
                                      tooling; React dependencies are
                                      also present in the project

  API / data format                   REST, JSON

  Testing                             pytest, httpx, mongomock

  Version control                     Git and GitHub
  -----------------------------------------------------------------------

## Repository structure

``` text
TRACEVEDA/
├── BACKEND/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── dependencies.py
│   ├── models/
│   ├── routes/
│   ├── services/
│   ├── tests/
│   ├── TraceVeda_Master_Dataset/
│   ├── requirements.txt
│   └── .env.example
├── Frontend/
│   ├── index.html
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── .env.example
├── HARDWARE/
│   ├── Storage_Node/
│   ├── Truck_Node/
│   ├── Component_Testing/
│   └── Little_FS_Clear/
├── docs/
│   ├── API_CONTRACT.md
│   └── DATA_MODEL.md
└── README.md
```

## Getting started

### Prerequisites

-   Python 3.10+ (use a version compatible with the pinned backend
    dependencies)
-   Node.js LTS and npm
-   MongoDB local instance or MongoDB Atlas connection
-   Arduino IDE with ESP32 board support for firmware work

### 1. Clone the repository

``` bash
git clone <YOUR_REPOSITORY_URL>
cd TRACEVEDA
```

### 2. Configure and run the backend

``` bash
cd BACKEND
python -m venv .venv
```

Activate the environment:

``` bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

Install dependencies and configure environment variables:

``` bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env`, then set the MongoDB URI and strong
secrets. Do not commit `.env`.

For a local MongoDB instance, the URI commonly looks like:

``` env
MONGO_URI=mongodb://localhost:27017
DB_NAME=traceveda
TRACEVEDA_JWT_SECRET=<long-random-secret>
TRACEVEDA_DEVICE_API_KEY=<shared-device-key>
TRACEVEDA_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Load the sample dataset and prepare demo accounts if using the bundled
demo data:

``` bash
python import_csv.py
python migrate_seed_blockchain_events.py
python seed_users.py
```

Start the API:

``` bash
uvicorn main:app --reload
```

The API is normally available at `http://127.0.0.1:8000`. Interactive
API documentation is available at `http://127.0.0.1:8000/docs`.

### 3. Run the frontend

Open a second terminal:

``` bash
cd Frontend
npm install
npm run dev
```

Open the local URL printed by Vite (normally `http://localhost:5173`).

The frontend's `.env` should set `VITE_API_URL` to the backend base URL
when required. For local proxy-based development, follow the
instructions in `Frontend/README.md`. Restart the Vite server after
changing environment variables.

### 4. Build the frontend

``` bash
npm run build
npm run preview
```

The production build is written to `Frontend/dist/`.

### 5. Flash the ESP32 nodes

1.  Open the relevant `.ino` sketch from the Storage Node or Truck Node
    folder in Arduino IDE.
2.  Install the libraries included by the sketch.
3.  Select the correct ESP32 board and serial port.
4.  Configure Wi-Fi credentials, backend endpoint, batch/storage or
    transport identifiers, and the device API key.
5.  Ensure the device API key matches `TRACEVEDA_DEVICE_API_KEY` in the
    backend environment.
6.  Confirm the pin mapping and module voltage before powering the
    circuit.
7.  Upload the sketch and inspect the serial monitor and LCD.
8.  Verify that readings reach the backend. Test offline buffering only
    in a controlled way by interrupting connectivity and then restoring
    it.

Do not publish real Wi-Fi passwords, API keys, JWT secrets or other
credentials in source control, screenshots or demo videos.

## Configuration and security

The backend reads its configuration from environment variables. See
`BACKEND/.env.example`.

-   User authentication uses signed JWT access tokens.
-   Passwords are stored as hashes, not plaintext.
-   Role-based authorization is enforced by backend routes.
-   ESP32 nodes authenticate IoT ingestion using the `X-Device-Key`
    header.
-   Public consumer routes are limited to QR verification and consumer
    issue reporting.
-   Configure CORS origins for the frontend deployment.
-   Replace all development/demo credentials before any public
    deployment.

**Never commit `.env` files or real credentials.** The example file
contains placeholders only.

## Dataset and demo data

The backend includes `TraceVeda_Master_Dataset/`, containing reference
and demonstration CSV files for plants, farms, batches, batch
relationships, laboratory tests, IoT devices/readings, transport,
medicine batches, consumer reports, investigations and blockchain
events.

The dataset is intended for development and demonstration. It should not
be interpreted as live operational data or independently verified field
records unless separately validated.

Use the backend import scripts from the `BACKEND/` directory and review
their output before using the imported records in a demonstration.

## API documentation

-   `docs/API_CONTRACT.md` describes the principal API endpoints,
    request fields, roles and response examples.
-   `docs/DATA_MODEL.md` describes the core entities and relationships.
-   Once the backend is running, use `/docs` for interactive OpenAPI
    documentation.

Core API areas include authentication, plant references, raw and
processing batches, batch relationships, laboratory tests, transport and
storage events, IoT readings and alerts, medicine batches, QR
verification, consumer reports, investigations, traceability and
blockchain-event verification.

## Testing

Run the backend test suite from the `BACKEND/` directory:

``` bash
python -m pytest tests/ -q
```

The repository includes tests for authentication and authorization, data
integrity, supply-chain workflows, blockchain/hash-chain integration and
concurrency. Test results depend on the checked-out code, installed
dependencies and test environment; run the suite locally before quoting
a test count or claiming a passing build.

For a basic manual integration check:

1.  Start MongoDB and the backend.
2.  Confirm the backend health endpoint responds.
3.  Start the frontend and sign in with a configured demo account.
4.  Submit or inspect a batch workflow.
5.  Send a test IoT reading using a registered sensor and valid device
    key.
6.  Confirm the reading appears in the backend.
7.  Verify the batch trace and QR workflow.
8.  If testing offline buffering, disconnect the node from Wi-Fi, allow
    readings to queue, restore connectivity and confirm queued records
    upload.

## Current implementation and future work

The repository contains backend routes and data models for the broader
supply-chain workflow, a frontend with stakeholder workspaces, and
firmware for two ESP32 monitoring nodes. The firmware supports sensor
acquisition, LCD display, Wi-Fi/HTTPS communication and local buffering.

The backend's current event-integrity mechanism is a MongoDB-backed
SHA-256 hash chain. A full permissioned blockchain deployment (for
example, Hyperledger Fabric), field integration across all supply-chain
participants, and production-scale pilots are future
deployment/integration work unless separately demonstrated.

Potential next steps include:

-   Validate the full workflow with a real herb supply-chain partner.
-   Expand device deployment and test long-duration connectivity,
    calibration and power reliability.
-   Complete and validate all stakeholder data-entry and verification
    workflows.
-   Evaluate a permissioned ledger integration if deployment
    requirements justify it.
-   Conduct field testing and document measurable performance and
    operational outcomes.

## Contributors

| Team member | Contribution |
|---|---|
| **Ojaswi Gautam** | Dataset, Frontend & System Architecture |
| **Anirudh Khatavkar** | Hardware |
| **Vishnu Sharma** | Backend |
| **Raghav Gulati** | Blockchain |
| **Aishwarya Deshmukh** | Presenter |
| **Nandini Dua** | Presenter |

------------------------------------------------------------------------

**TRACEVEDA --- Connecting provenance, quality evidence and traceability
from plant to product.**
