# TRACEVEDA API CONTRACT

## Core IDs

farmer_id
farm_id
plant_id
raw_batch_id
processing_batch_id
lab_id
transport_id
sensor_id
storage_id
manufacturer_id
medicine_batch_id
qr_id


## Core Flow

```text
FARMER
   ↓
FARM
   ↓
RAW MATERIAL BATCH
   ↓
PROCESSING BATCH
   ↓
MEDICINE BATCH
   ↓
   QR
```

## 1. Authentication

POST /api/auth/login
GET /api/auth/me


## 2. Plants

GET /api/plants
GET /api/plants/{plant_id}
GET /api/plants/search?name={name}


## 3. Create Raw Material Batch

POST /api/batches/raw

Request:

{
  "farm_id": "FARM-001",
  "plant_id": "PLANT-001",
  "collection_date": "2026-08-26",
  "quantity": 100,
  "unit": "kg"
}

Response:

{
  "raw_batch_id": "RAW-2026-001",
  "status": "CREATED"
}


## 4. Raw Material Batch

GET /api/batches/raw/{raw_batch_id}


## 5. Create Processing Batch

POST /api/batches/processing

Request:

{
  "processor_id": "PROC-001",
  "processing_date": "2026-08-26",
  "output_quantity": 500,
  "unit": "kg",
  "processing_type": "DRYING_AND_GRINDING"
}

Response:

{
  "processing_batch_id": "PROCESS-2026-001",
  "status": "CREATED"
}


## 6. Processing Batch

GET /api/batches/processing/{processing_batch_id}


## 7. Create Batch Relationship

POST /api/batches/relationships

Request:

{
  "parent_batch_id": "RAW-2026-001",
  "child_batch_id": "PROCESS-2026-001",
  "relationship_type": "RAW_TO_PROCESSING",
  "quantity_contributed": 250,
  "unit": "kg"
}

Response:

{
  "relationship_id": "REL-2026-001",
  "status": "CREATED"
}


## 8. Batch Relationships

GET /api/batches/{batch_id}/relationships


## 9. Laboratory

POST /api/lab/tests

Request:

{
  "batch_id": "PROCESS-2026-001",
  "lab_id": "LAB-001",
  "test_stage": "PRE_MANUFACTURING",
  "test_type": "QUALITY_TEST",
  "test_parameters": {
    "identity": "PASS",
    "purity": "PASS",
    "moisture": "PASS"
  },
  "result": "PASS"
}

Response:

{
  "lab_test_id": "LABTEST-2026-001",
  "batch_id": "PROCESS-2026-001",
  "result": "PASS",
  "status": "VERIFIED"
}

GET /api/lab/tests/{batch_id}


## Lab Business Rule

If test_stage = PRE_MANUFACTURING
and result = FAIL:

    batch_status = BLOCKED

If test_stage = PRE_MANUFACTURING
and result = PASS:

    batch_status = APPROVED_FOR_MANUFACTURING


## 10. Transport

POST /api/transport/events

GET /api/transport/{batch_id}


## 11. IoT Sensor Readings

POST /api/iot/readings

Common fields:

batch_id
transport_id
storage_id
sensor_id
timestamp

BH1750:

light_intensity_lux

Limit Switch:

switch_status

MPU6050:

accel_x_g
accel_y_g
accel_z_g
gyro_x_dps
gyro_y_dps
gyro_z_dps
shock_detected
tilt_angle_deg

Load Cell + HX711:

weight_kg
weight_change_kg

Response:

{
  "reading_id": "READ-2026-0001",
  "status": "STORED"
}


## 12. IoT Alerts

GET /api/iot/alerts/{batch_id}


## IoT Rule Engine

For every incoming IoT reading:

1. Identify the batch.
2. Identify the sensor.
3. Determine the applicable rule.
4. Compare the sensor value with the rule.
5. If within limits → NORMAL.
6. If outside limits → create an IoT alert.
7. Assign alert severity.
8. Store the alert.
9. If the event is critical → send the event to the blockchain layer.


## 13. Storage

POST /api/storage/events

GET /api/storage/{medicine_batch_id}


## 14. Traceability

GET /api/trace/reverse/{medicine_batch_id}

GET /api/trace/forward/{raw_batch_id}

GET /api/trace/impact/{raw_batch_id}


## 15. Create Medicine Batch

POST /api/medicine

Request:

{
  "processing_batch_id": "PROCESS-2026-001",
  "manufacturer_id": "MFG-001",
  "product_name": "Ashwagandha Tablets",
  "manufacturing_date": "2026-08-26",
  "expiry_date": "2028-08-26"
}

Response:

{
  "medicine_batch_id": "MED-2026-001",
  "qr_id": "QR-2026-001",
  "status": "CREATED"
}


## 16. Medicine Batch

GET /api/medicine/{medicine_batch_id}


## 17. QR Verification

GET /api/verify/{qr_id}

Response:

{
  "verified": true,
  "medicine_batch_id": "MED-2026-001",
  "product_name": "Ashwagandha Tablets",
  "batch_status": "RELEASED",
  "traceability": {
    "processing_batch_id": "PROCESS-2026-001",
    "raw_batches": [
      "RAW-2026-001",
      "RAW-2026-002"
    ],
    "plant_id": "PLANT-001"
  }
}


## 18. Consumer Reports

POST /api/consumer/reports

GET /api/consumer/reports/{medicine_batch_id}


## 19. Investigations

POST /api/investigations

GET /api/investigations/{investigation_id}


## 20. Blockchain

POST /api/blockchain/events

GET /api/blockchain/events/{batch_id}
