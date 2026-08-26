# TRACEVEDA DATA MODEL

## 1. Master Data

users
plants
farms
manufacturers


## 2. Supply Chain

raw_material_batches
transport_events
processing_batches
batch_relationships
lab_tests
medicine_batches


## 3. IoT & Monitoring

iot_devices
iot_readings
iot_alerts
storage_events


## 4. Consumer & Investigation

consumer_reports
investigations


## 5. Blockchain

blockchain_events


# CORE RELATIONSHIPS

Farmer
  ↓
Farm
  ↓
Raw Material Batch
  ↓
Processing Batch
  ↓
Medicine Batch
  ↓
QR


Raw Batch
  ↓
Batch Relationship
  ↓
Processing Batch


Batch
  ↓
Transport Event
  ↓
IoT Reading
  ↓
IoT Alert


Medicine Batch
  ↓
Storage Event


Medicine Batch
  ↓
Consumer Report
  ↓
Investigation


# ID MAP

farmer_id          → Farmer
farm_id            → Farm
plant_id           → Plant / Species
raw_batch_id       → Raw Material Batch
processing_batch_id → Processing Batch
lab_id             → Laboratory
transport_id       → Transport Journey
sensor_id          → IoT Device / Sensor
storage_id         → Storage Monitoring Event
manufacturer_id    → Manufacturer
medicine_batch_id  → Finished Medicine Batch
qr_id              → Consumer Verification