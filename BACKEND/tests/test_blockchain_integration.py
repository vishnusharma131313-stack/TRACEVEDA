"""
End-to-end check that the supply-chain routes anchor to the chain.

Run with:
    python -m pytest tests/test_blockchain_integration.py -v
or:
    python tests/test_blockchain_integration.py
"""

import mongo_harness  # noqa: F401  (must be imported before routes/services)

mongo_harness.install()

from datetime import date, datetime  # noqa: E402

import pytest  # noqa: E402

from routes import batches, iot, lab, medicine  # noqa: E402
from services import blockchain_service  # noqa: E402


# These tests call the route functions directly rather than over HTTP, so
# they supply the identity that Depends(require_roles(...)) would inject.
# Enforcement of those dependencies is covered by tests/test_auth.py,
# which drives the real ASGI app.
TEST_USER = {"username": "pytest", "role": "admin"}


@pytest.fixture(autouse=True)
def fresh_database():
    """A clean chain per test - see mongo_harness for why this is per-test."""

    mongo_harness.install()


# =========================
# HELPERS
# =========================

def seed_reference_data():

    db = mongo_harness.current_db()

    db.farms.insert_one({
        "farm_id": "FARM-001",
        "farm_name": "Test Farm"
    })

    db.plants.insert_one({
        "plant_id": "PLANT-001",
        "plant_name": "Ashwagandha"
    })


def make_raw_batch(day=26, quantity=100.0):

    return batches.create_raw_batch(
        batches.RawBatchRequest(
            farm_id="FARM-001",
            plant_id="PLANT-001",
            collection_date=date(2026, 8, day),
            quantity=quantity,
            unit="kg"
        ),
        user=TEST_USER
    )


def make_processing_batch():

    return batches.create_processing_batch(
        batches.ProcessingBatchRequest(
            processor_id="PROC-001",
            processing_date=date(2026, 8, 26),
            output_quantity=80.0,
            unit="kg",
            processing_type="DRYING_AND_GRINDING"
        ),
        user=TEST_USER
    )


# =========================
# TESTS
# =========================

def test_full_supply_chain_anchors_every_step():

    seed_reference_data()

    # ---------------------------------------------
    # 1. RAW BATCH
    # ---------------------------------------------

    raw = make_raw_batch()

    assert raw["blockchain_tx"], "raw batch was not anchored"

    raw_batch_id = raw["raw_batch_id"]

    # ---------------------------------------------
    # 2. PROCESSING BATCH
    # ---------------------------------------------

    processing = make_processing_batch()

    assert processing["blockchain_tx"], "processing batch was not anchored"

    processing_batch_id = processing["processing_batch_id"]

    # ---------------------------------------------
    # 3. BATCH RELATIONSHIP (manufacturing linkage)
    # ---------------------------------------------

    relationship = batches.create_batch_relationship(
        batches.BatchRelationshipRequest(
            parent_batch_id=raw_batch_id,
            child_batch_id=processing_batch_id,
            relationship_type="RAW_TO_PROCESSING",
            quantity_contributed=100.0,
            unit="kg"
        ),
        user=TEST_USER
    )

    assert relationship["blockchain_tx"], "batch linkage was not anchored"

    # ---------------------------------------------
    # 4. LAB TEST (PASS)
    # ---------------------------------------------

    lab_test = lab.create_lab_test(
        lab.LabTestRequest(
            batch_id=processing_batch_id,
            lab_id="LAB-001",
            test_stage="PRE_MANUFACTURING",
            test_type="QUALITY_TEST",
            test_parameters={
                "identity": "PASS",
                "purity": "PASS",
                "moisture": "PASS"
            },
            result="PASS"
        ),
        user=TEST_USER
    )

    assert lab_test["blockchain_tx"], "lab test was not anchored"
    assert lab_test["batch_status"] == "APPROVED_FOR_MANUFACTURING"

    # ---------------------------------------------
    # 5. MEDICINE BATCH
    # ---------------------------------------------

    med = medicine.create_medicine_batch(
        medicine.MedicineBatchRequest(
            processing_batch_id=processing_batch_id,
            manufacturer_id="MFG-001",
            product_name="Ashwagandha Tablets",
            manufacturing_date=date(2026, 8, 26),
            expiry_date=date(2028, 8, 26)
        ),
        user=TEST_USER
    )

    assert med["blockchain_tx"], "medicine batch was not anchored"

    medicine_batch_id = med["medicine_batch_id"]

    # entity_type resolution across all three collections
    assert iot.resolve_entity_type(raw_batch_id) == "RAW"
    assert iot.resolve_entity_type(processing_batch_id) == "PROCESSING"
    assert iot.resolve_entity_type(medicine_batch_id) == "MEDICINE"
    assert iot.resolve_entity_type("NOPE-000") is None

    # ---------------------------------------------
    # 6. IOT READING -> CRITICAL TAMPER
    # gate open + weight change beyond tolerance
    # ---------------------------------------------

    reading = iot.create_iot_reading(
        iot.IoTReadingRequest(
            batch_id=processing_batch_id,
            sensor_id="SENSOR-001",
            timestamp=datetime(2026, 8, 26, 12, 0, 0),
            temperature_c=25.0,
            humidity_percent=50.0,
            switch_status="OPEN",
            weight_kg=75.0,
            weight_change_kg=(
                iot.WEIGHT_CHANGE_TOLERANCE_KG + 5.0
            )
        ),
        caller=TEST_USER
    )

    assert reading["tamper_status"] == "CRITICAL"
    assert reading["red_led"] is True
    assert reading["blockchain_tx"], "critical tamper was not anchored"

    # Existing response fields must survive untouched.
    assert reading["status"] == "STORED"
    assert reading["gate_open"] is True
    assert reading["weight_changed"] is True

    # ---------------------------------------------
    # 7. WHOLE-CHAIN VERIFICATION
    # ---------------------------------------------

    result = blockchain_service.verify_chain()

    assert result["valid"] is True, result
    assert result["checked"] == 6, result
    assert result["broken_at"] is None

    # ---------------------------------------------
    # 8. TRAIL FOR THE PROCESSING BATCH
    # ---------------------------------------------

    trail = blockchain_service.get_events_for_entity(
        processing_batch_id
    )

    event_types = [event["event_type"] for event in trail]

    assert "BATCH_CREATED" in event_types
    assert "BATCH_LINKED" in event_types
    assert "QUALITY_STATUS" in event_types
    assert "TAMPER_EVENT" in event_types

    # Ordered by sequence, never by timestamp.
    sequences = [event["sequence"] for event in trail]
    assert sequences == sorted(sequences)

    for event in trail:
        assert event["entity_id"] == processing_batch_id
        assert event["blockchain_status"] == "ANCHORED"

    print(f"OK  chain valid, {result['checked']} events checked")
    print(f"OK  trail for {processing_batch_id}: {event_types}")


def test_failed_lab_test_is_also_anchored():
    """A failed quality test is exactly the record a dispute turns on."""

    seed_reference_data()

    processing_batch_id = make_processing_batch()["processing_batch_id"]

    lab_test = lab.create_lab_test(
        lab.LabTestRequest(
            batch_id=processing_batch_id,
            lab_id="LAB-001",
            test_stage="PRE_MANUFACTURING",
            test_type="QUALITY_TEST",
            test_parameters={"purity": "FAIL"},
            result="FAIL"
        ),
        user=TEST_USER
    )

    assert lab_test["blockchain_tx"], "failed lab test was not anchored"
    assert lab_test["batch_status"] == "BLOCKED"

    trail = blockchain_service.get_events_for_entity(processing_batch_id)

    quality = [
        event for event in trail
        if event["event_type"] == "QUALITY_STATUS"
    ]

    assert len(quality) == 1
    assert quality[0]["event_data"]["result"] == "FAIL"
    assert quality[0]["event_data"]["batch_status"] == "BLOCKED"

    assert blockchain_service.verify_chain()["valid"] is True

    print("OK  FAIL result anchored with batch_status BLOCKED")


def test_warning_alerts_are_not_anchored():
    """Only CRITICAL alerts belong on the ledger."""

    seed_reference_data()

    raw = make_raw_batch(day=27, quantity=50.0)

    before = blockchain_service.verify_chain()["checked"]

    # Humidity out of range -> WARNING, and gate open without a weight
    # change -> YELLOW. Neither may reach the chain.
    reading = iot.create_iot_reading(
        iot.IoTReadingRequest(
            batch_id=raw["raw_batch_id"],
            sensor_id="SENSOR-002",
            timestamp=datetime(2026, 8, 27, 12, 0, 0),
            temperature_c=25.0,
            humidity_percent=95.0,
            switch_status="OPEN",
            weight_change_kg=0.0
        ),
        caller=TEST_USER
    )

    assert reading["alerts_generated"] >= 2
    assert reading["tamper_status"] == "YELLOW"
    assert reading["blockchain_tx"] is None, (
        "non-critical alerts must not be anchored"
    )

    after = blockchain_service.verify_chain()

    # Nothing new on the chain at all.
    assert after["checked"] == before, after
    assert after["valid"] is True

    # The alerts themselves are still stored off-chain.
    assert mongo_harness.current_db().iot_alerts.count_documents({}) >= 2

    print("OK  WARNING/YELLOW alerts stored off-chain only")


def test_raw_sensor_readings_are_never_anchored():
    """High-frequency telemetry stays in MongoDB, per the on/off-chain split."""

    seed_reference_data()

    raw = make_raw_batch()

    before = blockchain_service.verify_chain()["checked"]

    for minute in range(5):

        iot.create_iot_reading(
            iot.IoTReadingRequest(
                batch_id=raw["raw_batch_id"],
                sensor_id="SENSOR-003",
                timestamp=datetime(2026, 8, 26, 12, minute, 0),
                temperature_c=22.0,
                humidity_percent=45.0
            ),
            caller=TEST_USER
        )

    db = mongo_harness.current_db()

    assert db.iot_readings.count_documents({}) == 5

    after = blockchain_service.verify_chain()

    assert after["checked"] == before, "readings must not be anchored"
    assert after["valid"] is True

    print("OK  5 normal readings stored, 0 anchored")


def test_tampering_with_a_stored_event_breaks_the_chain():
    """The whole point of the module: edits after the fact are detectable."""

    seed_reference_data()

    make_raw_batch()
    make_processing_batch()
    make_raw_batch(day=27)

    db = mongo_harness.current_db()

    events = list(db.blockchain_events.find({}).sort("sequence", 1))

    assert len(events) == 3

    victim = events[1]

    db.blockchain_events.update_one(
        {"_id": victim["_id"]},
        {"$set": {"event_data.output_quantity": 999999}}
    )

    result = blockchain_service.verify_chain()

    assert result["valid"] is False
    assert result["broken_at"] == victim["transaction_id"]
    assert "modified after anchoring" in result["reason"]

    # One valid event was checked before the break.
    assert result["checked"] == 1

    print(f"OK  tamper detected at {result['broken_at']}")


def test_rehashing_a_forged_event_still_breaks_the_link():
    """Recomputing the forged event's own hash does not save the forgery."""

    seed_reference_data()

    make_raw_batch()
    make_processing_batch()
    make_raw_batch(day=27)

    db = mongo_harness.current_db()

    events = list(db.blockchain_events.find({}).sort("sequence", 1))

    victim = events[1]

    forged_data = dict(victim["event_data"])
    forged_data["output_quantity"] = 999999

    # Forge the payload AND recompute a self-consistent hash.
    forged_hash = blockchain_service.compute_event_hash(
        victim["event_type"],
        victim["entity_type"],
        victim["entity_id"],
        forged_data,
        victim["timestamp"],
        victim["previous_hash"]
    )

    db.blockchain_events.update_one(
        {"_id": victim["_id"]},
        {
            "$set": {
                "event_data": forged_data,
                "event_hash": forged_hash
            }
        }
    )

    result = blockchain_service.verify_chain()

    assert result["valid"] is False
    # The forged event verifies against itself; its successor does not.
    assert result["broken_at"] == events[2]["transaction_id"]
    assert "Broken link" in result["reason"]

    print(f"OK  re-hashed forgery caught at {result['broken_at']}")


def test_deleting_an_event_breaks_the_chain():
    """A removed event shows up as a sequence gap."""

    seed_reference_data()

    make_raw_batch()
    make_processing_batch()
    make_raw_batch(day=27)

    db = mongo_harness.current_db()

    events = list(db.blockchain_events.find({}).sort("sequence", 1))

    victim = events[1]

    db.blockchain_events.delete_one({"_id": victim["_id"]})

    result = blockchain_service.verify_chain()

    assert result["valid"] is False
    assert "Sequence gap" in result["reason"]

    print(f"OK  deletion detected: {result['reason']}")


def test_anchor_failure_does_not_break_the_route():
    """A ledger outage must not 500 a write that already succeeded."""

    seed_reference_data()

    original = blockchain_service.anchor_event

    def exploding_anchor(*args, **kwargs):
        raise RuntimeError("simulated ledger outage")

    blockchain_service.anchor_event = exploding_anchor

    try:
        raw = make_raw_batch()
    finally:
        blockchain_service.anchor_event = original

    # The batch is still created and the response shape is intact.
    assert raw["raw_batch_id"]
    assert raw["status"] == "CREATED"
    assert raw["blockchain_tx"] is None

    assert mongo_harness.current_db().raw_material_batches.count_documents(
        {}
    ) == 1

    print("OK  ledger outage degraded to blockchain_tx: null")


if __name__ == "__main__":

    mongo_harness.run_standalone(
        test_full_supply_chain_anchors_every_step,
        test_failed_lab_test_is_also_anchored,
        test_warning_alerts_are_not_anchored,
        test_raw_sensor_readings_are_never_anchored,
        test_tampering_with_a_stored_event_breaks_the_chain,
        test_rehashing_a_forged_event_still_breaks_the_link,
        test_deleting_an_event_breaks_the_chain,
        test_anchor_failure_does_not_break_the_route
    )
