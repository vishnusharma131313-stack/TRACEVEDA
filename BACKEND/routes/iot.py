from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from database import db

router = APIRouter(
    prefix="/api/iot",
    tags=["IoT"]
)


# =========================
# REQUEST MODEL
# =========================

class IoTReadingRequest(BaseModel):
    batch_id: str
    transport_id: Optional[str] = None
    storage_id: Optional[str] = None
    sensor_id: str
    timestamp: datetime

    # Environmental
    temperature_c: Optional[float] = None
    humidity_percent: Optional[float] = None
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None

    # BH1750
    light_intensity_lux: Optional[float] = None

    # Limit Switch
    switch_status: Optional[str] = None

    # MPU6050
    accel_x_g: Optional[float] = None
    accel_y_g: Optional[float] = None
    accel_z_g: Optional[float] = None
    gyro_x_dps: Optional[float] = None
    gyro_y_dps: Optional[float] = None
    gyro_z_dps: Optional[float] = None
    shock_detected: Optional[bool] = None
    tilt_angle_deg: Optional[float] = None

    # Load Cell + HX711
    weight_kg: Optional[float] = None
    weight_change_kg: Optional[float] = None


# =========================
# DEMO CONFIGURABLE RULES
# =========================

# These are prototype configuration values.
# Later they can be moved to an iot_rules collection.

IOT_RULES = {
    "temperature_c": {
        "min": 10,
        "max": 35
    },
    "humidity_percent": {
        "min": 20,
        "max": 70
    },
    "light_intensity_lux": {
        "max": 1000
    },
    "tilt_angle_deg": {
        "max": 45
    },
    "weight_change_kg": {
        "max": 10
    }
}


# =========================
# HELPER
# =========================

def batch_exists(batch_id: str):

    if db.raw_material_batches.find_one({
        "raw_batch_id": batch_id
    }):
        return True

    if db.processing_batches.find_one({
        "processing_batch_id": batch_id
    }):
        return True

    if db.medicine_batches.find_one({
        "medicine_batch_id": batch_id
    }):
        return True

    return False


# =========================
# CREATE IOT READING
# =========================

@router.post("/readings")
def create_iot_reading(data: IoTReadingRequest):

    # Validate batch
    if not batch_exists(data.batch_id):
        raise HTTPException(
            status_code=404,
            detail="Batch not found"
        )

    # Create reading ID
    count = db.iot_readings.count_documents({}) + 1

    reading_id = f"READ-{datetime.now().year}-{count:04d}"

    reading = data.model_dump()

    reading["reading_id"] = reading_id
    reading["timestamp"] = data.timestamp.isoformat()
    reading["created_at"] = datetime.utcnow()

    # Store original reading
    db.iot_readings.insert_one(reading)

    # =========================
    # RULE ENGINE
    # =========================

    alerts = []

    # Temperature
    if data.temperature_c is not None:

        rule = IOT_RULES["temperature_c"]

        if (
            data.temperature_c < rule["min"]
            or data.temperature_c > rule["max"]
        ):
            alerts.append({
                "parameter": "temperature_c",
                "value": data.temperature_c,
                "message": "Temperature outside allowed range",
                "severity": "CRITICAL"
            })

    # Humidity
    if data.humidity_percent is not None:

        rule = IOT_RULES["humidity_percent"]

        if (
            data.humidity_percent < rule["min"]
            or data.humidity_percent > rule["max"]
        ):
            alerts.append({
                "parameter": "humidity_percent",
                "value": data.humidity_percent,
                "message": "Humidity outside allowed range",
                "severity": "WARNING"
            })

    # Light
    if data.light_intensity_lux is not None:

        rule = IOT_RULES["light_intensity_lux"]

        if data.light_intensity_lux > rule["max"]:
            alerts.append({
                "parameter": "light_intensity_lux",
                "value": data.light_intensity_lux,
                "message": "Light intensity above allowed limit",
                "severity": "WARNING"
            })

    # Tilt
    if data.tilt_angle_deg is not None:

        rule = IOT_RULES["tilt_angle_deg"]

        if abs(data.tilt_angle_deg) > rule["max"]:
            alerts.append({
                "parameter": "tilt_angle_deg",
                "value": data.tilt_angle_deg,
                "message": "Excessive tilt detected",
                "severity": "WARNING"
            })

    # Shock
    if data.shock_detected is True:

        alerts.append({
            "parameter": "shock_detected",
            "value": True,
            "message": "Shock event detected",
            "severity": "CRITICAL"
        })

    # Tamper / limit switch
    if data.switch_status is not None:

        if data.switch_status.upper() in [
            "OPEN",
            "TAMPER",
            "TRIGGERED"
        ]:
            alerts.append({
                "parameter": "switch_status",
                "value": data.switch_status,
                "message": "Possible tampering detected",
                "severity": "CRITICAL"
            })

    # Weight change
    if data.weight_change_kg is not None:

        rule = IOT_RULES["weight_change_kg"]

        if abs(data.weight_change_kg) > rule["max"]:
            alerts.append({
                "parameter": "weight_change_kg",
                "value": data.weight_change_kg,
                "message": "Abnormal weight change detected",
                "severity": "WARNING"
            })

    # =========================
    # STORE ALERTS
    # =========================

    for alert in alerts:

        alert_count = db.iot_alerts.count_documents({}) + 1

        alert_id = (
            f"ALERT-{datetime.now().year}-{alert_count:04d}"
        )

        db.iot_alerts.insert_one({
            "alert_id": alert_id,
            "reading_id": reading_id,
            "batch_id": data.batch_id,
            "sensor_id": data.sensor_id,
            "parameter": alert["parameter"],
            "value": alert["value"],
            "message": alert["message"],
            "severity": alert["severity"],
            "status": "OPEN",
            "created_at": datetime.utcnow()
        })

    return {
        "reading_id": reading_id,
        "status": "STORED",
        "alerts_generated": len(alerts)
    }


# =========================
# GET READINGS
# =========================

@router.get("/readings/{batch_id}")
def get_iot_readings(batch_id: str):

    readings = list(
        db.iot_readings.find(
            {"batch_id": batch_id},
            {"_id": 0}
        ).sort("timestamp", 1)
    )

    return {
        "batch_id": batch_id,
        "readings": readings
    }


# =========================
# GET ALERTS
# =========================

@router.get("/alerts/{batch_id}")
def get_iot_alerts(batch_id: str):

    alerts = list(
        db.iot_alerts.find(
            {"batch_id": batch_id},
            {"_id": 0}
        ).sort("created_at", -1)
    )

    return {
        "batch_id": batch_id,
        "alerts": alerts
    }