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

    # For Storage Node:
    # batch_id = RAW MATERIAL BATCH ID
    batch_id: str

    transport_id: Optional[str] = None
    storage_id: Optional[str] = None

    sensor_id: str
    timestamp: datetime

    # Environmental Sensors
    temperature_c: Optional[float] = None
    humidity_percent: Optional[float] = None

    # GPS
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
# BACKEND RULES
# =========================

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

    reading_id = (
        f"READ-{datetime.now().year}-{count:04d}"
    )

    # Prepare reading
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


    # -------------------------
    # TEMPERATURE
    # -------------------------

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


    # -------------------------
    # HUMIDITY
    # -------------------------

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


    # -------------------------
    # LIGHT
    # -------------------------

    if data.light_intensity_lux is not None:

        rule = IOT_RULES["light_intensity_lux"]

        if data.light_intensity_lux > rule["max"]:

            alerts.append({
                "parameter": "light_intensity_lux",
                "value": data.light_intensity_lux,
                "message": "Light intensity above allowed limit",
                "severity": "WARNING"
            })


    # -------------------------
    # TILT
    # -------------------------

    if data.tilt_angle_deg is not None:

        rule = IOT_RULES["tilt_angle_deg"]

        if abs(data.tilt_angle_deg) > rule["max"]:

            alerts.append({
                "parameter": "tilt_angle_deg",
                "value": data.tilt_angle_deg,
                "message": "Excessive tilt detected",
                "severity": "WARNING"
            })


    # -------------------------
    # SHOCK
    # -------------------------

    if data.shock_detected is True:

        alerts.append({
            "parameter": "shock_detected",
            "value": True,
            "message": "Shock event detected",
            "severity": "CRITICAL"
        })


    # =========================
    # 2FA TAMPER DETECTION
    # =========================

    gate_open = False
    weight_changed = False

    # Factor 1: Gate
    if data.switch_status is not None:

        gate_open = data.switch_status.upper() in [
            "OPEN",
            "TAMPER",
            "TRIGGERED"
        ]

    # Factor 2: Weight
    if data.weight_change_kg is not None:

        weight_changed = (
            abs(data.weight_change_kg) > 0
        )


    # =========================
    # 2FA DECISION
    # =========================

    # Gate OPEN + Weight changed
    if gate_open and weight_changed:

        alerts.append({
            "parameter": "tamper_2fa",
            "value": {
                "gate_open": True,
                "weight_changed": True,
                "weight_change_kg": data.weight_change_kg
            },
            "message": (
                "Critical tampering detected: "
                "gate opened and weight changed"
            ),
            "severity": "CRITICAL"
        })


    # Gate OPEN + No weight change
    elif gate_open and not weight_changed:

        alerts.append({
            "parameter": "tamper_2fa",
            "value": {
                "gate_open": True,
                "weight_changed": False,
                "weight_change_kg": data.weight_change_kg
            },
            "message": (
                "Gate opened but no weight change detected"
            ),
            "severity": "YELLOW"
        })


    # Gate CLOSED + Weight changed
    elif not gate_open and weight_changed:

        alerts.append({
            "parameter": "tamper_2fa",
            "value": {
                "gate_open": False,
                "weight_changed": True,
                "weight_change_kg": data.weight_change_kg
            },
            "message": (
                "Weight change detected without gate opening"
            ),
            "severity": "YELLOW"
        })


    # =========================
    # RED LED STATUS
    # =========================
    #
    # IMPORTANT:
    # Red LED turns ON whenever ANY
    # CRITICAL alert is generated from
    # the CURRENT IoT reading.
    #
    # This includes:
    # - Temperature violations
    # - Critical tampering
    # - Shock
    # - Any future CRITICAL rule
    # =========================

    red_led = any(
        alert["severity"] == "CRITICAL"
        for alert in alerts
    )


    # =========================
    # STORE ALERTS
    # =========================

    for alert in alerts:

        alert_count = (
            db.iot_alerts.count_documents({})
            + 1
        )

        alert_id = (
            f"ALERT-{datetime.now().year}-"
            f"{alert_count:04d}"
        )

        db.iot_alerts.insert_one({

            "alert_id": alert_id,
            "reading_id": reading_id,
            "batch_id": data.batch_id,
            "storage_id": data.storage_id,
            "sensor_id": data.sensor_id,

            "parameter": alert["parameter"],
            "value": alert["value"],
            "message": alert["message"],
            "severity": alert["severity"],

            "status": "OPEN",
            "created_at": datetime.utcnow()
        })


    # =========================
    # DETERMINE TAMPER STATUS
    # =========================

    tamper_status = "NORMAL"

    if gate_open and weight_changed:

        tamper_status = "CRITICAL"

    elif gate_open or weight_changed:

        tamper_status = "YELLOW"


    # =========================
    # FIND HIGHEST ALERT
    # =========================

    alert_status = "NORMAL"
    alert_message = None

    if alerts:

        severity_priority = {
            "CRITICAL": 3,
            "YELLOW": 2,
            "WARNING": 1,
            "NORMAL": 0
        }

        highest_alert = max(
            alerts,
            key=lambda x: severity_priority.get(
                x["severity"],
                0
            )
        )

        alert_status = highest_alert["severity"]
        alert_message = highest_alert["message"]


    # =========================
    # RESPONSE
    # =========================

    return {

        "reading_id": reading_id,
        "status": "STORED",

        "batch_id": data.batch_id,
        "storage_id": data.storage_id,
        "sensor_id": data.sensor_id,

        "tamper_status": tamper_status,

        "alert_status": alert_status,
        "alert_message": alert_message,

        # ESP32 uses this directly
        "red_led": red_led,

        "gate_open": gate_open,
        "weight_changed": weight_changed,

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
        ).sort(
            "timestamp",
            1
        )
    )

    return {
        "batch_id": batch_id,
        "readings": readings
    }


# =========================
# GET ALL ALERTS
# =========================

@router.get("/alerts/{batch_id}")
def get_iot_alerts(batch_id: str):

    alerts = list(
        db.iot_alerts.find(
            {"batch_id": batch_id},
            {"_id": 0}
        ).sort(
            "created_at",
            -1
        )
    )

    return {
        "batch_id": batch_id,
        "alerts": alerts
    }


# =========================
# GET ACTIVE ALERTS
# =========================

@router.get("/alerts/active/{batch_id}")
def get_active_iot_alerts(batch_id: str):

    alerts = list(
        db.iot_alerts.find(
            {
                "batch_id": batch_id,
                "status": "OPEN"
            },
            {
                "_id": 0
            }
        ).sort(
            "created_at",
            -1
        )
    )

    critical_alert = any(
        alert.get("severity") == "CRITICAL"
        for alert in alerts
    )

    return {

        "batch_id": batch_id,

        "active": len(alerts) > 0,

        "red_led": critical_alert,

        "alerts": alerts,

        "count": len(alerts)
    }