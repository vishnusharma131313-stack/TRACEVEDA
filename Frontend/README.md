# TraceVeda Frontend

The active frontend is the existing TraceVeda HTML experience. Its visual design, CSS, layout and feature identity remain the source of truth; feature scripts are organised under `src/` and loaded as classic browser scripts so the existing inline buttons and form handlers continue to work.

## Start TraceVeda locally

Keep the backend and frontend running in **two separate terminals**.

**Terminal 1 — Backend** (from the `Backend` folder):

```powershell
.\venv\Scripts\python.exe -m uvicorn main:app --reload
```

**Terminal 2 — Frontend** (from the `Frontend` folder):

```powershell
npm install
npm run dev
```

Open the Vite URL shown in the frontend terminal, normally `http://localhost:5173`. Port `8000` is the FastAPI backend; use it for `/docs`, not for the frontend website. Do not double-click `index.html`.

## Backend connection

The included frontend `.env` contains `VITE_API_URL=`. An empty value makes API calls use the Vite origin. `vite.config.js` forwards `/api` calls to `http://127.0.0.1:8000`. Restart Vite after changing `.env`.

## Important user flows

- **Public landing page:** every browser load starts here. A saved `AUD-001` profile in localStorage no longer forces the browser into the Auditor workspace.
- **Stakeholder sign-in:** Sign In opens the role selector for Auditor, Laboratory, Manufacturer and Transporter. The server-issued account role is checked before its workspace opens.
- **Administrator:** use the dedicated **Admin Login** button in the public header. The backend automatically ensures the demo administrator `admin-001` exists with password `12345678` (the password is hashed in MongoDB). The dashboard manages stakeholder accounts, access requests, consumer safety reports and investigations. Approving an access request creates an account and reveals a temporary password once.
- **Consumer medicine check:** this is public and does not require login. Enter the **QR ID printed on the medicine pack**, not the medicine batch ID. The frontend calls `GET /api/verify/{qrId}` and displays the backend's real verified / not verified result. A QR ID is different from a medicine batch ID.
- **Consumer reports:** a medicine QR must be verified before the report form submits a report against that QR and medicine batch.

## Project structure

```text
Frontend/
├── index.html
├── src/
│   ├── config/                 Runtime API and role configuration
│   ├── lib/                    Shared API client and session handling
│   ├── components/
│   │   ├── iot/                IoT monitoring components
│   │   ├── layout/             Workspace navigation and panel switching
│   │   └── ui/                 Shared interactions
│   ├── pages/
│   │   ├── admin.js            Administrator dashboard and user management
│   │   ├── auditor.js          Audit, trace and investigation features
│   │   ├── auth.js             Stakeholder and administrator sign-in
│   │   ├── consumer.js         Public QR verification and consumer reports
│   │   ├── lab.js              Laboratory certification
│   │   ├── manufacturer.js     Batch, medicine and QR workflows
│   │   └── transporter.js      Geotagged transport evidence
│   └── styles/                 Existing TraceVeda stylesheet
├── archive/react-scaffold/     Previous React implementation kept for reference
├── .env
└── vite.config.js
```

## Build for deployment

```bash
npm run build
npm run preview
```

The production files are written to `dist/`. Set `VITE_API_URL` to the deployed backend URL before building for production.

## Scope and verification

This folder is packaged alongside the updated Python backend in `TraceVeda-Admin-Upgrade.zip`. Live login, request approval, report management and investigations require the backend and MongoDB to be running. The original HTML/CSS design remains the source of truth.
