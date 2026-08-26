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
- SHA-256 hash-based blockchain prototype

---

## Backend Structure

```text
BACKEND/
│
├── main.py
├── database.py
├── import_csv.py
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
│
└── TraceVeda_Master_Dataset_Updated/