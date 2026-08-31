"""
The demo, end to end, against the REAL shipped CSV dataset.

Every other test builds its own two-document fixture. This one loads
TraceVeda_Master_Dataset exactly as `python import_csv.py` does, migrates the
seeded ledger, creates the accounts, and then walks the whole judge-facing
path over HTTP:

    log in -> register a harvest -> process it -> link them -> lab PASS ->
    manufacture -> scan the QR as an anonymous consumer -> file a report ->
    close it as a regulator -> verify the hash chain end to end

If the dataset and the code disagree anywhere, this is where it shows up.

Slower than the rest of the suite (it imports ~14k documents into mongomock),
so it is marked and can be skipped with:

    python -m pytest -m "not slow"
"""

import mongo_harness  # noqa: F401  (must be imported before routes/services)

mongo_harness.install()

import importlib  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from config import settings  # noqa: E402


DATASET = Path(__file__).resolve().parents[1] / "TraceVeda_Master_Dataset"

PASSWORD = "demo-password-123"

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def seeded():
    """
    One import for the whole module - it is the expensive part.

    Returns (client, tokens). Tests here read far more than they write, and
    the few writes append rather than mutate shared state.
    """

    mongo_harness.install()

    import import_csv
    import migrate_seed_blockchain_events
    import seed_users
    from services import ids
    from services.indexes import ensure_indexes

    importlib.reload(import_csv)
    importlib.reload(migrate_seed_blockchain_events)
    importlib.reload(seed_users)

    for csv_file in sorted(DATASET.glob("*.csv")):
        import_csv.import_csv(csv_file)

    ids.sync_counters()
    ensure_indexes(mongo_harness.current_db())

    migrate_seed_blockchain_events.migrate()

    seed_users.seed(PASSWORD)

    client = TestClient(mongo_harness.make_app())

    tokens = {}

    for username in ("farmer", "processor", "lab", "manufacturer",
                     "logistics", "regulator", "admin"):

        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": PASSWORD},
        )

        assert response.status_code == 200, response.text
        tokens[username] = {
            "Authorization": f"Bearer {response.json()['access_token']}"
        }

    return client, tokens


# ============================================================
# THE SEED DATA ITSELF
# ============================================================

def test_the_dataset_loaded(seeded):

    db = mongo_harness.current_db()

    assert db.raw_material_batches.count_documents({}) == 70
    assert db.processing_batches.count_documents({}) == 45
    assert db.medicine_batches.count_documents({}) == 42
    assert db.iot_readings.count_documents({}) == 11128
    assert db.plants.count_documents({}) == 2300
    assert db.users.count_documents({}) == 7


def test_the_migrated_seed_chain_verifies(seeded):
    """375 seeded ledger rows, rebuilt into one continuous hash chain."""

    client, tokens = seeded

    result = client.get(
        "/api/blockchain/verify-chain", headers=tokens["regulator"]
    ).json()

    assert result["valid"] is True, result
    assert result["checked"] == 375
    assert result["broken_at"] is None


def test_seeded_storage_events_are_visible(seeded):
    """The medicine_batch_id / raw_batch_id key mismatch."""

    client, tokens = seeded

    response = client.get(
        "/api/storage/MED-2026-001", headers=tokens["regulator"]
    )

    assert response.status_code == 200
    assert response.json()["count"] >= 1


def test_seeded_alerts_are_visible(seeded):
    """The alerts / iot_alerts collection mismatch."""

    client, tokens = seeded

    response = client.get(
        "/api/iot/alerts/MED-2026-001", headers=tokens["regulator"]
    )

    assert response.status_code == 200

    alerts = response.json()["alerts"]

    assert len(alerts) >= 1
    assert any(alert["source"] == "seed" for alert in alerts)


def test_seeded_transport_events_come_back_in_order(seeded):

    client, tokens = seeded

    response = client.get(
        "/api/transport/ASH-2026-001", headers=tokens["regulator"]
    )

    assert response.status_code == 200

    events = response.json()["events"]

    assert len(events) >= 1

    departures = [
        event.get("departure_time") for event in events
        if event.get("departure_time")
    ]

    assert departures == sorted(departures)


def test_seeded_telemetry_is_capped(seeded):

    client, tokens = seeded

    body = client.get(
        "/api/iot/readings/MED-2026-001?limit=100", headers=tokens["regulator"]
    ).json()

    assert body["count"] <= 100
    assert body["total"] >= body["count"]


def test_reverse_trace_reaches_the_farm(seeded):

    client, tokens = seeded

    body = client.get(
        "/api/trace/reverse/MED-2026-001", headers=tokens["regulator"]
    ).json()

    assert body["medicine_batch"]["medicine_batch_id"] == "MED-2026-001"
    assert body["processing_batch"] is not None
    assert len(body["raw_batches"]) >= 1
    assert body["raw_batches"][0]["farm"] is not None


# ============================================================
# THE FULL LIVE FLOW, ON TOP OF THE SEED DATA
# ============================================================

def test_the_whole_supply_chain_runs_on_top_of_the_seed_data(seeded):

    client, tokens = seeded

    # ---- 1. harvest -------------------------------------------------
    raw = client.post("/api/batches/raw", json={
        "farm_id": "FARM-001",
        "plant_id": "PLANT-0001",
        "collection_date": "2026-08-26",
        "quantity": 500.0,
        "unit": "kg",
    }, headers=tokens["farmer"])

    assert raw.status_code == 201, raw.text

    raw_id = raw.json()["raw_batch_id"]

    # Continues past the seeded ASH-2026-070 rather than colliding with it.
    assert raw_id == "RAW-2026-071"
    assert raw.json()["blockchain_tx"]

    # ---- 2. processing ----------------------------------------------
    processing = client.post("/api/batches/processing", json={
        "processor_id": "PROC-001",
        "processing_date": "2026-08-27",
        "output_quantity": 400.0,
        "unit": "kg",
        "processing_type": "DRYING_AND_GRINDING",
    }, headers=tokens["processor"])

    assert processing.status_code == 201, processing.text

    processing_id = processing.json()["processing_batch_id"]

    # ---- 3. linkage -------------------------------------------------
    link = client.post("/api/batches/relationships", json={
        "parent_batch_id": raw_id,
        "child_batch_id": processing_id,
        "relationship_type": "RAW_TO_PROCESSING",
        "quantity_contributed": 500.0,
        "unit": "kg",
    }, headers=tokens["processor"])

    assert link.status_code == 201, link.text

    # ---- 4. quality gate --------------------------------------------
    # A manufacturer cannot get past this on their own.
    premature = client.post("/api/medicine", json={
        "processing_batch_id": processing_id,
        "manufacturer_id": "MFG-001",
        "product_name": "Ashwagandha Tablets",
        "manufacturing_date": "2026-08-28",
        "expiry_date": "2028-08-28",
    }, headers=tokens["manufacturer"])

    assert premature.status_code == 400

    lab_test = client.post("/api/lab/tests", json={
        "batch_id": processing_id,
        "lab_id": "LAB-001",
        "test_stage": "PRE_MANUFACTURING",
        "test_type": "Identity/Purity/Moisture",
        "test_parameters": {"identity": "PASS", "purity": "PASS"},
        "result": "PASS",
    }, headers=tokens["lab"])

    assert lab_test.status_code == 201, lab_test.text
    assert lab_test.json()["batch_status"] == "APPROVED_FOR_MANUFACTURING"

    # ---- 5. manufacture ---------------------------------------------
    medicine = client.post("/api/medicine", json={
        "processing_batch_id": processing_id,
        "manufacturer_id": "MFG-001",
        "product_name": "Ashwagandha Tablets",
        "manufacturing_date": "2026-08-28",
        "expiry_date": "2028-08-28",
    }, headers=tokens["manufacturer"])

    assert medicine.status_code == 201, medicine.text

    medicine_id = medicine.json()["medicine_batch_id"]
    qr_id = medicine.json()["qr_id"]

    assert medicine_id == "MED-2026-043"
    assert qr_id == "QR-2026-043"

    # ---- 6. the consumer, with no account at all --------------------
    verify = client.get(f"/api/verify/{qr_id}")

    assert verify.status_code == 200
    assert verify.json()["verified"] is True
    assert verify.json()["traceability"]["raw_batches"] == [raw_id]

    report = client.post("/api/consumer/reports", json={
        "medicine_batch_id": medicine_id,
        "qr_id": qr_id,
        "reported_at": "2026-08-29T09:00:00",
        "issue_type": "headache",
        "symptoms": "Headache after consumption",
        "description": "Filed from the public QR page",
    })

    assert report.status_code == 201, report.text

    report_id = report.json()["report_id"]

    # ---- 7. tamper on the road --------------------------------------
    tamper = client.post("/api/iot/readings", json={
        "batch_id": medicine_id,
        "sensor_id": "IOT-DEMO-001",
        "timestamp": "2026-08-29T10:00:00",
        "switch_status": "OPEN",
        "weight_kg": 4.18,
        "weight_change_kg": -0.82,
        "temperature_c": 24.6,
    }, headers={"X-Device-Key": settings.device_api_key})

    assert tamper.status_code == 201, tamper.text
    assert tamper.json()["tamper_status"] == "CRITICAL"
    assert tamper.json()["red_led"] is True
    assert tamper.json()["blockchain_tx"]

    # ---- 8. the regulator closes the loop ----------------------------
    closed = client.patch(
        f"/api/consumer/reports/{report_id}/status",
        json={"status": "UNDER_INVESTIGATION"},
        headers=tokens["regulator"],
    )

    assert closed.status_code == 200, closed.text

    # ---- 9. the chain is still whole --------------------------------
    chain = client.get(
        "/api/blockchain/verify-chain", headers=tokens["regulator"]
    ).json()

    assert chain["valid"] is True, chain

    # 375 seeded + raw + processing + link + lab + medicine + tamper
    assert chain["checked"] == 381

    # ---- 10. the trail for the new medicine -------------------------
    trail = client.get(
        f"/api/blockchain/batch/{medicine_id}", headers=tokens["regulator"]
    ).json()

    event_types = [event["event_type"] for event in trail["events"]]

    assert "MEDICINE_LINKED" in event_types
    assert "TAMPER_EVENT" in event_types

    sequences = [event["sequence"] for event in trail["events"]]
    assert sequences == sorted(sequences)


def test_the_new_batch_appears_in_the_dashboard_listing(seeded):

    client, tokens = seeded

    body = client.get("/api/batches/raw", headers=tokens["farmer"]).json()

    assert body["total"] >= 71
    assert any(
        batch["raw_batch_id"] == "RAW-2026-071" for batch in body["batches"]
    )


def test_roles_are_still_enforced_against_the_real_dataset(seeded):

    client, tokens = seeded

    forbidden = client.post("/api/lab/tests", json={
        "batch_id": "ASH-P-2026-001",
        "lab_id": "LAB-001",
        "test_stage": "PRE_MANUFACTURING",
        "test_type": "PURITY",
        "test_parameters": {},
        "result": "PASS",
    }, headers=tokens["farmer"])

    assert forbidden.status_code == 403
