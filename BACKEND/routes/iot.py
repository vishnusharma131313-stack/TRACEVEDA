from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from database import db
from dependencies import require_authenticated, require_device_or_roles
from services import blockchain_service, ids
from services.accounts import LOGISTICS
from services.timeutils import sort_key, to_utc_iso

router = APIRouter(
    prefix="/api/iot",
    tags=["IoT"]
)


# =========================
# REQUEST MODEL
# =========================

class IoTReadingRequest(BaseModel):
    batch_id: str = Field(min_length=1, max_length=64)
    transport_id: Optional[str] = Field(default=None, max_length=64)
    storage_id: Optional[str] = Field(default=None, max_length=64)
    sensor_id: str = Field(min_length=1, max_length=64)
    timestamp: datetime

    # Environmental
    temperature_c: Optional[float] = Field(default=None, ge=-90, le=150)
    humidity_percent: Optional[float] = Field(default=None, ge=0, le=100)

    # GPS
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    gps_valid: Optional[bool] = None

    # BH1750
    light_intensity_lux: Optional[float] = Field(default=None, ge=0)

    # Limit Switch
    switch_status: Optional[str] = Field(default=None, max_length=32)

    # MPU6050
    accel_x_g: Optional[float] = None
    accel_y_g: Optional[float] = None
    accel_z_g: Optional[float] = None

    gyro_x_dps: Optional[float] = None
    gyro_y_dps: Optional[float] = None
    gyro_z_dps: Optional[float] = None

    shock_detected: Optional[bool] = None
    tilt_angle_deg: Optional[float] = Field(default=None, ge=-180, le=180)

    # Load Cell + HX711
    weight_kg: Optional[float] = None
    weight_change_kg: Optional[float] = None


# =========================
# DEMO CONFIGURABLE RULES
# =========================
# Mirrored in Frontend/src/lib/iot.js so a gauge turns amber at exactly the
# value that makes this route raise an alert. If these move, move those.

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


# One row per threshold check, replacing five near-identical if-blocks.
# `use_abs` marks the parameters whose sign carries no meaning: a 50 degree
# tilt is as bad in either direction.
THRESHOLD_CHECKS = (
    ("temperature_c", "CRITICAL", "Temperature outside allowed range", False),
    ("humidity_percent", "WARNING", "Humidity outside allowed range", False),
    ("light_intensity_lux", "WARNING", "Light intensity above allowed limit", False),
    ("tilt_angle_deg", "WARNING", "Excessive tilt detected", True),
)


# Ignore small HX711/load-cell fluctuations.
# Changes smaller than 0.1 kg are treated as sensor noise.
WEIGHT_CHANGE_TOLERANCE_KG = 0.1

GATE_OPEN_VALUES = ("OPEN", "TAMPER", "TRIGGERED")

SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_WARNING = "WARNING"
SEVERITY_YELLOW = "YELLOW"


# =========================
# HELPERS
# =========================

def resolve_entity_type(batch_id: str):
    """
    Which collection owns this batch id: RAW, PROCESSING, MEDICINE or None.

    Doubles as the existence check and as the entity_type used when
    anchoring a critical alert.
    """

    lookups = (
        ("raw_material_batches", "raw_batch_id", "RAW"),
        ("processing_batches", "processing_batch_id", "PROCESSING"),
        ("medicine_batches", "medicine_batch_id", "MEDICINE"),
    )

    for collection, field, entity_type in lookups:

        if db[collection].find_one({field: batch_id}, {"_id": 1}):
            return entity_type

    return None


def batch_exists(batch_id: str):

    return resolve_entity_type(batch_id) is not None


def _breaches(value, rule, use_abs):
    """True when a reading falls outside its configured rule."""

    if value is None:
        return False

    minimum = rule.get("min")
    maximum = rule.get("max")

    if minimum is not None and value < minimum:
        return True

    compared = abs(value) if use_abs else value

    return maximum is not None and compared > maximum


def evaluate_rules(data):
    """
    Every alert this reading raises, plus the two tamper factors.

    Split out of the route so the rule engine can be exercised directly,
    without a database or an HTTP request.
    """

    alerts = []

    for parameter, severity, message, use_abs in THRESHOLD_CHECKS:

        value = getattr(data, parameter)

        if _breaches(value, IOT_RULES[parameter], use_abs):

            alerts.append({
                "parameter": parameter,
                "value": value,
                "message": message,
                "severity": severity
            })

    if data.shock_detected is True:

        alerts.append({
            "parameter": "shock_detected",
            "value": True,
            "message": "Shock event detected",
            "severity": SEVERITY_CRITICAL
        })

    # =================================
    # 2FA TAMPER DETECTION
    # =================================
    # Two independent physical signals. Either alone is suspicious; both
    # together is a break-in.

    gate_open = (
        data.switch_status is not None
        and data.switch_status.upper() in GATE_OPEN_VALUES
    )

    weight_changed = (
        data.weight_change_kg is not None
        and abs(data.weight_change_kg) >= WEIGHT_CHANGE_TOLERANCE_KG
    )

    if gate_open or weight_changed:

        if gate_open and weight_changed:
            severity = SEVERITY_CRITICAL
            message = (
                "Critical tampering detected: "
                "gate opened and weight changed"
            )

        elif gate_open:
            severity = SEVERITY_YELLOW
            message = "Gate opened but no significant weight change detected"

        else:
            severity = SEVERITY_YELLOW
            message = "Significant weight change detected without gate opening"

        alerts.append({
            "parameter": "tamper_2fa",
            "value": {
                "gate_open": gate_open,
                "weight_changed": weight_changed,
                "weight_change_kg": data.weight_change_kg
            },
            "message": message,
            "severity": severity
        })

    return alerts, gate_open, weight_changed


# =========================
# CREATE IOT READING
# =========================

@router.post("/readings", status_code=201)
def create_iot_reading(
    data: IoTReadingRequest,
    caller: dict = Depends(require_device_or_roles(LOGISTICS)),
):

    # Validate batch, and remember which collection owns it so critical
    # alerts can be anchored with the right entity_type.
    entity_type = resolve_entity_type(data.batch_id)

    if entity_type is None:
        raise HTTPException(
            status_code=404,
            detail="Batch not found"
        )

    reading_id = ids.mint("iot_reading")

    reading = data.model_dump()

    reading["reading_id"] = reading_id
    # Normalised to UTC so string ordering equals chronological ordering;
    # see services/timeutils.
    reading["timestamp"] = to_utc_iso(data.timestamp)
    reading["recorded_by"] = caller.get("username")
    reading["created_at"] = datetime.now(timezone.utc)

    db.iot_readings.insert_one(reading)

    alerts, gate_open, weight_changed = evaluate_rules(data)

    red_led = any(
        alert["severity"] == SEVERITY_CRITICAL
        for alert in alerts
    )

    # =========================
    # STORE ALERTS
    # =========================

    blockchain_tx = None
    now = datetime.now(timezone.utc)

    for alert in alerts:

        alert_id = ids.mint("iot_alert")

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
            "created_at": now
        })

        # ON-CHAIN / OFF-CHAIN SPLIT
        # Only CRITICAL, dispute-relevant alerts are anchored.
        # WARNING and YELLOW alerts, and the raw high-frequency readings
        # themselves, stay in MongoDB only.
        if alert["severity"] != SEVERITY_CRITICAL:
            continue

        transaction_id = blockchain_service.safe_anchor(
            "TAMPER_EVENT",
            entity_type,
            data.batch_id,
            {
                "alert_id": alert_id,
                "reading_id": reading_id,
                "sensor_id": data.sensor_id,
                "parameter": alert["parameter"],
                "value": alert["value"],
                "message": alert["message"],
                "severity": alert["severity"]
            }
        )

        # A single reading can raise several critical alerts; the response
        # carries the first anchored transaction id.
        if transaction_id and blockchain_tx is None:
            blockchain_tx = transaction_id

    # =========================
    # DETERMINE TAMPER STATUS
    # =========================

    if gate_open and weight_changed:
        tamper_status = SEVERITY_CRITICAL

    elif gate_open or weight_changed:
        tamper_status = SEVERITY_YELLOW

    else:
        tamper_status = "NORMAL"

    return {
        "reading_id": reading_id,
        "status": "STORED",
        "tamper_status": tamper_status,
        "gate_open": gate_open,
        "weight_changed": weight_changed,
        "red_led": red_led,
        "alerts_generated": len(alerts),
        "blockchain_tx": blockchain_tx
    }


# =========================
# GET READINGS
# =========================

@router.get("/readings/{batch_id}")
def get_iot_readings(
    batch_id: str,
    limit: int = Query(default=500, ge=1, le=5000),
    user: dict = Depends(require_authenticated),
):
    """
    Telemetry for one batch, oldest first.

    The seeded dataset holds 11k+ readings across all batches, so this is
    capped. The cap takes the NEWEST `limit` readings and then reverses them
    into ascending order: truncating from the other end would leave the live
    gauges showing telemetry from weeks ago.
    """

    total = db.iot_readings.count_documents({"batch_id": batch_id})

    newest_first = list(
        db.iot_readings.find(
            {"batch_id": batch_id},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit)
    )

    readings = list(reversed(newest_first))

    return {
        "batch_id": batch_id,
        "readings": readings,
        "count": len(readings),
        "total": total,
        "truncated": total > len(readings)
    }


# =========================
# GET ALERTS
# =========================

@router.get("/alerts/{batch_id}")
def get_iot_alerts(
    batch_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    user: dict = Depends(require_authenticated),
):
    """
    Alerts for one batch, newest first.

    Reads TWO collections. `iot_alerts` is what this route writes; `alerts`
    is what import_csv.py builds from the shipped alerts.csv, whose columns
    (alert_type / observed_value / threshold_value) differ. Querying only the
    first returned an empty list for every seeded batch, which made the demo
    dataset look as though it had never raised an alert in its life.
    """

    live = list(
        db.iot_alerts.find({"batch_id": batch_id}, {"_id": 0}).limit(limit)
    )

    for alert in live:
        alert["source"] = "live"

    seeded = list(
        db.alerts.find({"batch_id": batch_id}, {"_id": 0}).limit(limit)
    )

    for alert in seeded:
        alert["source"] = "seed"

    merged = live + seeded

    merged.sort(
        key=lambda alert: sort_key(
            alert.get("created_at") or alert.get("timestamp")
        ),
        reverse=True
    )

    merged = merged[:limit]

    return {
        "batch_id": batch_id,
        "alerts": merged,
        "count": len(merged)
    }
