# TraceVeda Frontend

This frontend keeps the existing `index.html` experience as the source of truth. The page markup, design system, colour palette, typography, responsive layout, labels and feature workflows were retained. The large inline CSS and JavaScript blocks were moved into organised files so the frontend is easier to maintain without changing the current UI/UX.

## Run the frontend

1. Install Node.js (LTS) if it is not installed.
2. Open a terminal in the `Frontend` folder.
3. Run:

```bash
npm install
npm run dev
```

4. Open the local URL printed by Vite (normally `http://localhost:5173`).

Do not open `index.html` by double-clicking it. The app uses Vite to serve its organised CSS and JavaScript files.

## Backend connection

The default `.env` points to the deployed TraceVeda API:

```env
VITE_API_URL=https://traceveda.onrender.com
```

To use a backend running on your own computer, change `.env` to an empty value:

```env
VITE_API_URL=
```

The Vite development proxy will then forward `/api` requests to `http://127.0.0.1:8000`. Start the backend before testing login, database-backed screens, blockchain operations, QR verification, IoT readings or evidence submission. Restart `npm run dev` after changing `.env`.

For a different backend host, set `VITE_API_URL` to its base URL (without a trailing slash). Its CORS configuration must allow the frontend origin if it is a cross-origin request.

## Folder structure

```text
Frontend/
├── index.html                 Main page markup (preserved from the working HTML)
├── src/
│   ├── api/client.js          Shared API client, auth token and endpoint bridge
│   ├── config/
│   │   ├── runtime.js         Backend URL configuration
│   │   └── roles.js           Role menus and shared role state
│   ├── components/
│   │   ├── iot/monitor.js     Sensor readings and IoT evidence rendering
│   │   ├── layout/workspace.js Role workspace navigation and panel switching
│   │   └── ui/events.js      Shared document-level interactions
│   ├── lib/session.js         Session restoration after page refresh
│   ├── pages/
│   │   ├── auditor.js         Trace, evidence and investigations
│   │   ├── auth.js            Sign-in and access-request workflows
│   │   ├── consumer.js        QR verification and consumer reports
│   │   ├── demo.js            Guided product demo
│   │   ├── iot.js             Authenticated IoT data loading
│   │   ├── lab.js             Laboratory certification
│   │   ├── manufacturer.js   Batch, medicine and QR workflows
│   │   └── transporter.js    Geotagged transport evidence and ledger entry
│   └── styles/traceveda.css   Original stylesheet, extracted without redesign
├── archive/react-scaffold/   Previous separate React implementation kept for reference
├── .env                      Active API configuration
└── vite.config.js             Vite server/build configuration
```

The files in `src/` are intentionally loaded as classic browser scripts rather than ES modules. The existing HTML uses inline event handlers and shared global functions; keeping classic-script scope avoids breaking those existing buttons and forms while the code is organised by feature.

## Main product workflows retained

- Public landing page and role-based workspaces (administrator, auditor, laboratory, manufacturer, transporter and consumer).
- Dedicated Administrator Login (`admin-001` / `12345678`) and dashboard for account management, access requests, consumer safety reports and investigations.
- Public medicine verification uses the QR ID on the pack (not the medicine batch ID) and displays the backend verification result.
- Auditor trace search, evidence views, batch investigations and consumer reports.
- Laboratory test/certification forms and verification history.
- Manufacturer processing/medicine batch creation, QR generation, transport and storage monitoring.
- Transporter GPS/camera capture and geotagged evidence submission.
- Consumer QR verification and medicine issue reporting.
- IoT sensor evidence and the guided demo.

## Build for deployment

```bash
npm run build
npm run preview
```

The production files are written to `dist/`. Deploy the contents of that folder to your static hosting provider. Configure `VITE_API_URL` to the correct backend URL before building.

## Administrator access

The paired backend ensures `admin-001` exists with initial password `12345678` when it starts and MongoDB is reachable. The password is hashed in MongoDB. This is a demo credential and must be changed before public deployment. The admin can review access requests, approve/reject them, create stakeholder accounts, update consumer report statuses, and open/close investigations.
