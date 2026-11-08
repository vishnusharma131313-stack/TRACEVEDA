# TraceVeda Frontend

The TraceVeda frontend is the browser-based interface for the public website, stakeholder workspaces and traceability workflows. It communicates with the FastAPI backend through `/api` requests.

The active application uses the existing HTML/CSS interface with JavaScript files organised by feature and role. Vite is used as the development server and build tool.

## Contents

- [Features](#features)
- [Technology](#technology)
- [Project structure](#project-structure)
- [Requirements](#requirements)
- [Install and run](#install-and-run)
- [Backend connection](#backend-connection)
- [Build for deployment](#build-for-deployment)
- [Application areas](#application-areas)
- [Development notes](#development-notes)

## Features

- Public TraceVeda landing page and medicine-verification entry point.
- Stakeholder sign-in and role-specific workspaces.
- Administrator workspace and access-request management.
- Auditor traceability, IoT evidence and investigation views.
- Laboratory, transporter and manufacturer workflows.
- Consumer QR verification and issue reporting.
- IoT telemetry views for Storage and Truck Nodes.

The frontend requires the backend for live data, authentication and API-backed workflows. A page rendering in the browser does not mean that its backend services are connected.

## Technology

- HTML and CSS
- JavaScript (browser scripts)
- Vite 5
- Node.js and npm

The package also contains React-related dependencies and an archived React scaffold. The active application entry point is `index.html`; the archived scaffold under `archive/react-scaffold/` is retained for reference and is not the current page entry point.

## Project structure

```text
Frontend/
├── index.html                   # Active application entry point
├── public/
│   └── favicon.svg
├── src/
│   ├── config/                  # Runtime API and role configuration
│   ├── lib/                     # API client, auth, session and formatting
│   ├── components/
│   │   ├── blockchain/
│   │   ├── iot/
│   │   ├── layout/
│   │   ├── timeline/
│   │   └── ui/
│   ├── pages/                   # Role and feature-specific page logic
│   ├── role-scenes/             # Workspace illustration assets
│   └── styles/                  # TraceVeda stylesheets
├── archive/
│   └── react-scaffold/          # Earlier React implementation/reference
├── docs/                        # Frontend design and change notes
├── package.json
├── vite.config.js
└── .env.example
```

### Important source files

| File | Responsibility |
|---|---|
| `index.html` | Main page structure, public sections and workspace markup |
| `src/config/runtime.js` | Runtime API configuration |
| `src/config/roles.js` | Role configuration |
| `src/lib/api-client.js` | Shared API request handling |
| `src/lib/auth.js` and `src/lib/session.js` | Authentication/session helpers |
| `src/components/layout/workspace.js` | Workspace navigation and panel switching |
| `src/components/iot/monitor.js` | IoT monitoring behavior |
| `src/pages/auditor.js` | Auditor trace, evidence and investigation interactions |
| `src/pages/lab.js` | Laboratory workflow interactions |
| `src/pages/manufacturer.js` | Manufacturer batch and medicine workflows |
| `src/pages/transporter.js` | Transport workflow interactions |
| `src/pages/consumer.js` | Public QR and consumer-report interactions |
| `src/pages/admin.js` | Administrator workspace interactions |

## Requirements

- Node.js LTS (or a version compatible with the Vite version in `package.json`).
- npm.
- The TraceVeda backend running for live API functionality.

## Install and run

Open a terminal in the `Frontend/` directory.

### 1. Install dependencies

```bash
npm install
```

### 2. Configure the API URL

Copy `.env.example` to `.env`.

For local development with the backend running at `http://127.0.0.1:8000`, set:

```env
VITE_API_URL=
```

An empty `VITE_API_URL` allows the frontend to call the Vite origin. The Vite development server proxies `/api` requests to the local FastAPI backend.

For a deployed backend, set `VITE_API_URL` to the backend base URL, for example:

```env
VITE_API_URL=https://your-backend-domain.example
```

Use the actual backend URL for your deployment. Do not put private API keys or server secrets in frontend environment variables; values prefixed with `VITE_` are exposed to browser code.

Restart the Vite server after changing `.env`.

### 3. Start the development server

```bash
npm run dev
```

Vite normally serves the frontend at:

```text
http://localhost:5173
```

Keep the backend running in a separate terminal. The backend normally listens on port `8000`.

## Backend connection

The Vite configuration proxies requests beginning with `/api` to:

```text
http://127.0.0.1:8000
```

This proxy is intended for local development. In production, configure `VITE_API_URL` to the deployed backend URL and configure the backend's `TRACEVEDA_CORS_ORIGINS` to allow the deployed frontend origin.

The frontend does not connect directly to MongoDB. All application data access goes through backend API endpoints.

## Build for deployment

Run from `Frontend/`:

```bash
npm run build
```

The generated static production files are written to:

```text
Frontend/dist/
```

To preview the production build locally:

```bash
npm run preview
```

Vite normally serves the preview at `http://localhost:4173`.

Deploy the contents of `dist/` to a static hosting provider. Set the API base URL for the target environment and ensure the backend CORS configuration includes the deployed frontend origin.

## Application areas

| Area | Purpose |
|---|---|
| Public website | Project introduction and navigation |
| Verify Medicine | Consumer-facing QR verification |
| Consumer Reports | Submit product concerns after the relevant medicine has been verified |
| Laboratory workspace | Laboratory test and verification workflow |
| Transporter workspace | Transport records and transport-node monitoring |
| Manufacturer workspace | Batch, medicine and storage-monitoring workflows |
| Auditor workspace | Trace journey, batch records, IoT evidence, investigations and consumer reports |
| Administrator workspace | Administrative and access-management functions |

Exact permissions and available actions are enforced by the backend; the frontend should not be treated as the authority for access control.

## Development notes

- The active frontend uses classic browser script loading to preserve existing inline handlers and shared browser functions. Avoid converting scripts to ES modules or changing script-loading order without checking those dependencies.
- `vite.config.js` serves `src/` as a static public directory and configures the local `/api` proxy.
- `archive/react-scaffold/` is retained as a historical/reference implementation. It is not the current application entry point.
- Do not place secrets in frontend code or `VITE_` environment variables.
- When changing an existing workflow, keep the change scoped to the relevant page/script and test the affected role and adjacent workflows in a browser.

---

For backend setup and API details, see [`../BACKEND/README.md`](../BACKEND/README.md). For the overall project, see the [main README](../README.md).
