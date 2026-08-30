"""
Authentication and authorisation, exercised over real HTTP.

Unlike tests/test_blockchain_integration.py, which calls route functions
directly, these go through the ASGI app so that FastAPI actually resolves the
Depends(...) chain. That is the only way to prove the gating works - a direct
call bypasses every dependency by definition.

Run with:
    python -m pytest tests/test_auth.py -v
"""

import mongo_harness  # noqa: F401  (must be imported before routes/services)

mongo_harness.install()

from datetime import date, datetime, timedelta, timezone  # noqa: E402

import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from config import settings  # noqa: E402
from services import accounts  # noqa: E402
from services.security import create_access_token  # noqa: E402


PASSWORD = "demo-password-123"


@pytest.fixture(autouse=True)
def fresh_database():
    mongo_harness.install()


@pytest.fixture
def client():
    return TestClient(mongo_harness.make_app())


# =========================
# HELPERS
# =========================

def make_user(username, role):

    accounts.create_user(
        username=username,
        password=PASSWORD,
        role=role,
        full_name=username.title()
    )


def auth_header(username):
    token, _ = create_access_token(username, accounts.get_user(username)["role"])
    return {"Authorization": f"Bearer {token}"}


def seed_reference_data():

    db = mongo_harness.current_db()
    db.farms.insert_one({"farm_id": "FARM-001", "farm_name": "Test Farm"})
    db.plants.insert_one({"plant_id": "PLANT-001", "common_name": "Ashwagandha"})


RAW_BATCH_BODY = {
    "farm_id": "FARM-001",
    "plant_id": "PLANT-001",
    "collection_date": "2026-08-26",
    "quantity": 100.0,
    "unit": "kg",
}


# =========================
# LOGIN
# =========================

def test_login_returns_a_usable_token(client):

    make_user("farmer", accounts.FARMER)

    response = client.post(
        "/api/auth/login",
        json={"username": "farmer", "password": PASSWORD},
    )

    assert response.status_code == 200, response.text

    body = response.json()

    assert body["token_type"] == "bearer"
    assert body["role"] == accounts.FARMER
    assert body["access_token"]

    me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )

    assert me.status_code == 200
    assert me.json()["username"] == "farmer"


def test_wrong_password_is_rejected(client):

    make_user("farmer", accounts.FARMER)

    response = client.post(
        "/api/auth/login",
        json={"username": "farmer", "password": "not-the-password"},
    )

    assert response.status_code == 401


def test_unknown_user_and_wrong_password_are_indistinguishable(client):
    """The login endpoint must not reveal which usernames exist."""

    make_user("farmer", accounts.FARMER)

    wrong_password = client.post(
        "/api/auth/login",
        json={"username": "farmer", "password": "nope"},
    )

    no_such_user = client.post(
        "/api/auth/login",
        json={"username": "ghost", "password": "nope"},
    )

    assert wrong_password.status_code == no_such_user.status_code == 401
    assert wrong_password.json()["detail"] == no_such_user.json()["detail"]


def test_login_never_returns_the_password_hash(client):

    make_user("farmer", accounts.FARMER)

    body = client.post(
        "/api/auth/login",
        json={"username": "farmer", "password": PASSWORD},
    ).json()

    assert "password_hash" not in body
    assert "password" not in body

    me = client.get("/api/auth/me", headers=auth_header("farmer")).json()

    assert "password_hash" not in me


# =========================
# THE CORE FIX
# =========================

def test_every_write_endpoint_rejects_anonymous_callers(client):
    """
    The whole point of this work: none of these were protected at all.

    A 401 here (not 403, not 404, not 201) is what proves an unauthenticated
    caller is stopped before the handler runs.
    """

    seed_reference_data()

    anonymous_writes = [
        ("post", "/api/batches/raw", RAW_BATCH_BODY),
        ("post", "/api/batches/processing", {
            "processor_id": "PROC-001",
            "processing_date": "2026-08-26",
            "output_quantity": 80.0,
            "unit": "kg",
            "processing_type": "DRYING",
        }),
        ("post", "/api/batches/relationships", {
            "parent_batch_id": "RAW-2026-001",
            "child_batch_id": "PROCESS-2026-001",
            "relationship_type": "RAW_TO_PROCESSING",
            "quantity_contributed": 10.0,
            "unit": "kg",
        }),
        ("post", "/api/lab/tests", {
            "batch_id": "PROCESS-2026-001",
            "lab_id": "LAB-001",
            "test_stage": "PRE_MANUFACTURING",
            "test_type": "PURITY",
            "test_parameters": {},
            "result": "PASS",
        }),
        ("post", "/api/medicine", {
            "processing_batch_id": "PROCESS-2026-001",
            "manufacturer_id": "MFG-001",
            "product_name": "Test",
            "manufacturing_date": "2026-08-26",
            "expiry_date": "2028-08-26",
        }),
        ("post", "/api/iot/readings", {
            "batch_id": "RAW-2026-001",
            "sensor_id": "S-1",
            "timestamp": "2026-08-26T12:00:00",
        }),
        ("post", "/api/transport/events", {
            "batch_id": "RAW-2026-001",
            "transport_id": "TRN-001",
            "event_type": "DISPATCH",
            "event_timestamp": "2026-08-26T12:00:00",
            "status": "IN_TRANSIT",
        }),
        ("post", "/api/storage/events", {
            "raw_batch_id": "RAW-2026-001",
            "storage_id": "STR-001",
            "event_type": "INTAKE",
            "event_timestamp": "2026-08-26T12:00:00",
            "status": "STORED",
        }),
        ("post", "/api/blockchain/events", {
            "event_type": "MANUAL",
            "entity_type": "RAW",
            "entity_id": "RAW-2026-001",
            "data": {},
        }),
        ("patch", "/api/consumer/reports/RPT-2026-001/status",
         {"status": "DISMISSED"}),
    ]

    for method, url, body in anonymous_writes:

        response = getattr(client, method)(url, json=body)

        assert response.status_code == 401, (
            f"{method.upper()} {url} returned {response.status_code}, "
            f"not 401 - it is reachable without credentials"
        )


def test_every_internal_read_endpoint_rejects_anonymous_callers(client):

    anonymous_reads = [
        "/api/batches/raw",
        "/api/batches/processing",
        "/api/batches/RAW-2026-001/relationships",
        "/api/medicine",
        "/api/lab/tests/PROCESS-2026-001",
        "/api/iot/readings/RAW-2026-001",
        "/api/iot/alerts/RAW-2026-001",
        "/api/transport/RAW-2026-001",
        "/api/storage/RAW-2026-001",
        "/api/trace/reverse/MED-2026-001",
        "/api/trace/forward/RAW-2026-001",
        "/api/trace/impact/RAW-2026-001",
        "/api/blockchain/events",
        "/api/blockchain/verify-chain",
        "/api/consumer/reports/RPT-2026-001",
    ]

    for url in anonymous_reads:

        response = client.get(url)

        assert response.status_code == 401, (
            f"GET {url} returned {response.status_code}, not 401"
        )


def test_roles_cannot_perform_each_others_writes(client):
    """A farmer may create a raw batch. A lab may not."""

    seed_reference_data()

    make_user("farmer", accounts.FARMER)
    make_user("lab", accounts.LAB)

    allowed = client.post(
        "/api/batches/raw", json=RAW_BATCH_BODY, headers=auth_header("farmer")
    )

    assert allowed.status_code == 201, allowed.text

    forbidden = client.post(
        "/api/batches/raw", json=RAW_BATCH_BODY, headers=auth_header("lab")
    )

    # 403, not 401: the credentials are perfectly valid, the role is wrong.
    assert forbidden.status_code == 403, forbidden.text
    assert "may not" in forbidden.json()["detail"]


def test_admin_may_act_for_every_role(client):

    seed_reference_data()

    make_user("admin", accounts.ADMIN)

    response = client.post(
        "/api/batches/raw", json=RAW_BATCH_BODY, headers=auth_header("admin")
    )

    assert response.status_code == 201, response.text


def test_only_a_regulator_may_close_a_consumer_report(client):

    db = mongo_harness.current_db()

    db.medicine_batches.insert_one({
        "medicine_batch_id": "MED-2026-001",
        "qr_id": "QR-2026-001",
        "product_name": "Test",
        "batch_status": "RELEASED",
    })

    db.consumer_reports.insert_one({
        "report_id": "RPT-2026-001",
        "medicine_batch_id": "MED-2026-001",
        "report_status": "OPEN",
    })

    make_user("farmer", accounts.FARMER)
    make_user("regulator", accounts.REGULATOR)

    refused = client.patch(
        "/api/consumer/reports/RPT-2026-001/status",
        json={"status": "DISMISSED"},
        headers=auth_header("farmer"),
    )

    assert refused.status_code == 403

    assert db.consumer_reports.find_one(
        {"report_id": "RPT-2026-001"}
    )["report_status"] == "OPEN"

    allowed = client.patch(
        "/api/consumer/reports/RPT-2026-001/status",
        json={"status": "DISMISSED"},
        headers=auth_header("regulator"),
    )

    assert allowed.status_code == 200, allowed.text

    assert db.consumer_reports.find_one(
        {"report_id": "RPT-2026-001"}
    )["report_status"] == "DISMISSED"


def test_report_status_must_be_a_known_value(client):

    db = mongo_harness.current_db()
    db.consumer_reports.insert_one({
        "report_id": "RPT-2026-001", "report_status": "OPEN"
    })

    make_user("regulator", accounts.REGULATOR)

    response = client.patch(
        "/api/consumer/reports/RPT-2026-001/status",
        json={"status": "WHATEVER_I_LIKE"},
        headers=auth_header("regulator"),
    )

    assert response.status_code == 422


# =========================
# PUBLIC SURFACE
# =========================

def test_the_consumer_journey_stays_public(client):
    """
    A shopper scanning a QR code has no account and must not need one.

    If this test starts failing, the consumer app is broken - not secured.
    """

    db = mongo_harness.current_db()

    db.medicine_batches.insert_one({
        "medicine_batch_id": "MED-2026-001",
        "qr_id": "QR-2026-001",
        "processing_batch_id": "PROCESS-2026-001",
        "product_name": "Ashwagandha Tablets",
        "batch_status": "RELEASED",
    })

    verify = client.get("/api/verify/QR-2026-001")

    assert verify.status_code == 200
    assert verify.json()["verified"] is True

    report = client.post("/api/consumer/reports", json={
        "medicine_batch_id": "MED-2026-001",
        "qr_id": "QR-2026-001",
        "reported_at": "2026-08-26T12:00:00",
        "issue_type": "headache",
        "symptoms": "Headache after use",
        "description": "Reported by a consumer",
    })

    assert report.status_code == 201, report.text
    assert report.json()["report_status"] == "OPEN"


def test_an_unknown_qr_does_not_leak_whether_the_batch_exists(client):

    response = client.get("/api/verify/QR-DOES-NOT-EXIST")

    assert response.status_code == 200
    assert response.json() == {"verified": False, "message": "Invalid QR"}


def test_a_consumer_cannot_file_a_pre_resolved_report(client):
    """report_status is not settable from the request body."""

    db = mongo_harness.current_db()

    db.medicine_batches.insert_one({
        "medicine_batch_id": "MED-2026-001",
        "qr_id": "QR-2026-001",
        "product_name": "Test",
    })

    response = client.post("/api/consumer/reports", json={
        "medicine_batch_id": "MED-2026-001",
        "qr_id": "QR-2026-001",
        "reported_at": "2026-08-26T12:00:00",
        "issue_type": "headache",
        "symptoms": "x",
        "description": "y",
        "report_status": "RESOLVED",
    })

    assert response.status_code == 201
    assert response.json()["report_status"] == "OPEN"

    stored = db.consumer_reports.find_one({})
    assert stored["report_status"] == "OPEN"


def test_a_report_needs_a_matching_batch_and_qr(client):

    db = mongo_harness.current_db()

    db.medicine_batches.insert_one({
        "medicine_batch_id": "MED-2026-001",
        "qr_id": "QR-2026-001",
        "product_name": "Test",
    })

    response = client.post("/api/consumer/reports", json={
        "medicine_batch_id": "MED-2026-001",
        "qr_id": "QR-2026-999",
        "reported_at": "2026-08-26T12:00:00",
        "issue_type": "headache",
        "symptoms": "x",
        "description": "y",
    })

    assert response.status_code == 404


# =========================
# TOKEN HANDLING
# =========================

def test_a_forged_token_is_rejected(client):
    """Signed with the wrong key."""

    make_user("regulator", accounts.REGULATOR)

    forged = jwt.encode(
        {
            "sub": "regulator",
            "role": "admin",
            "iss": settings.jwt_issuer,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        "not-the-real-signing-key",
        algorithm="HS256",
    )

    response = client.get(
        "/api/batches/raw", headers={"Authorization": f"Bearer {forged}"}
    )

    assert response.status_code == 401


def test_an_alg_none_token_is_rejected(client):
    """The classic JWT bypass: unsigned token claiming algorithm 'none'."""

    make_user("regulator", accounts.REGULATOR)

    unsigned = jwt.encode(
        {
            "sub": "regulator",
            "role": "admin",
            "iss": settings.jwt_issuer,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        key="",
        algorithm="none",
    )

    response = client.get(
        "/api/batches/raw", headers={"Authorization": f"Bearer {unsigned}"}
    )

    assert response.status_code == 401


def test_an_expired_token_is_rejected(client):

    make_user("farmer", accounts.FARMER)

    token, _ = create_access_token("farmer", accounts.FARMER, expires_minutes=-1)

    response = client.get(
        "/api/batches/raw", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


def test_a_deactivated_account_loses_access_immediately(client):
    """The account is re-read per request, not trusted from the token."""

    make_user("farmer", accounts.FARMER)

    headers = auth_header("farmer")

    assert client.get("/api/batches/raw", headers=headers).status_code == 200

    mongo_harness.current_db().users.update_one(
        {"username": "farmer"}, {"$set": {"is_active": False}}
    )

    assert client.get("/api/batches/raw", headers=headers).status_code == 401


def test_a_role_change_takes_effect_without_a_new_token(client):

    seed_reference_data()

    make_user("someone", accounts.LAB)

    headers = auth_header("someone")

    assert client.post(
        "/api/batches/raw", json=RAW_BATCH_BODY, headers=headers
    ).status_code == 403

    mongo_harness.current_db().users.update_one(
        {"username": "someone"}, {"$set": {"role": accounts.FARMER}}
    )

    assert client.post(
        "/api/batches/raw", json=RAW_BATCH_BODY, headers=headers
    ).status_code == 201


# =========================
# DEVICE INGEST
# =========================

def test_an_iot_node_authenticates_with_the_device_key(client):

    seed_reference_data()
    make_user("farmer", accounts.FARMER)

    created = client.post(
        "/api/batches/raw", json=RAW_BATCH_BODY, headers=auth_header("farmer")
    ).json()

    reading = {
        "batch_id": created["raw_batch_id"],
        "sensor_id": "IOT-TEST-001",
        "timestamp": "2026-08-26T12:00:00",
        "temperature_c": 22.0,
        "humidity_percent": 45.0,
    }

    accepted = client.post(
        "/api/iot/readings",
        json=reading,
        headers={"X-Device-Key": settings.device_api_key},
    )

    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["tamper_status"] == "NORMAL"

    rejected = client.post(
        "/api/iot/readings",
        json=reading,
        headers={"X-Device-Key": "wrong-key"},
    )

    assert rejected.status_code == 401


def test_a_logistics_operator_may_also_post_readings(client):

    seed_reference_data()
    make_user("farmer", accounts.FARMER)
    make_user("logistics", accounts.LOGISTICS)
    make_user("lab", accounts.LAB)

    created = client.post(
        "/api/batches/raw", json=RAW_BATCH_BODY, headers=auth_header("farmer")
    ).json()

    reading = {
        "batch_id": created["raw_batch_id"],
        "sensor_id": "IOT-TEST-001",
        "timestamp": "2026-08-26T12:00:00",
        "temperature_c": 22.0,
    }

    assert client.post(
        "/api/iot/readings", json=reading, headers=auth_header("logistics")
    ).status_code == 201

    assert client.post(
        "/api/iot/readings", json=reading, headers=auth_header("lab")
    ).status_code == 403


# =========================
# ACCOUNT RULES
# =========================

def test_passwords_are_never_stored_in_plaintext(client):

    make_user("farmer", accounts.FARMER)

    stored = mongo_harness.current_db().users.find_one({"username": "farmer"})

    assert PASSWORD not in str(stored)
    assert stored["password_hash"].startswith("pbkdf2_sha256$")


def test_duplicate_usernames_are_refused():

    make_user("farmer", accounts.FARMER)

    with pytest.raises(ValueError):
        make_user("farmer", accounts.LAB)


def test_an_unknown_role_is_refused():

    with pytest.raises(ValueError):
        accounts.create_user(
            username="x", password=PASSWORD, role="supreme-overlord"
        )


def test_a_short_password_is_refused():

    with pytest.raises(ValueError):
        accounts.create_user(username="x", password="short", role=accounts.LAB)


def test_usernames_are_case_insensitive(client):

    make_user("farmer", accounts.FARMER)

    response = client.post(
        "/api/auth/login", json={"username": "FARMER", "password": PASSWORD}
    )

    assert response.status_code == 200
