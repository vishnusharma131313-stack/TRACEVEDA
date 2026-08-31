"""
The two routers that docs/API_CONTRACT.md promised and main.py never mounted.

`/api/plants` and `/api/investigations` were both documented from the start
and both had seed data loaded by import_csv.py, so the rows were sitting in
MongoDB with no route able to reach them.

Run with:
    python -m pytest tests/test_reference_routes.py -v
"""

import mongo_harness  # noqa: F401  (must be imported before routes/services)

mongo_harness.install()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from services import accounts  # noqa: E402
from services.security import create_access_token  # noqa: E402


PASSWORD = "demo-password-123"


@pytest.fixture(autouse=True)
def fresh_database():
    mongo_harness.install()


@pytest.fixture
def client():
    return TestClient(mongo_harness.make_app())


def auth_header(username, role):
    accounts.create_user(username=username, password=PASSWORD, role=role)
    token, _ = create_access_token(username, role)
    return {"Authorization": f"Bearer {token}"}


def seed_plants():

    mongo_harness.current_db().plants.insert_many([
        {
            "plant_id": "PLANT-0001",
            "scientific_name": "Abelmoschus esculentus (L.) Moench",
            "common_name": "Bhindi, Bhindi tori",
            "family": "MALVACEAE",
            "vernacular_names": "Bhindi; Bhendi",
            "medicinal_system": "Ayurveda",
            "source_bsi_s_no": 1,
        },
        {
            "plant_id": "PLANT-0002",
            "scientific_name": "Withania somnifera (L.) Dunal",
            "common_name": "Ashwagandha",
            "family": "SOLANACEAE",
            "vernacular_names": "Asgandh",
            "medicinal_system": "Ayurveda",
        },
    ])


# ============================================================
# PLANTS
# ============================================================

def test_plants_require_authentication(client):

    assert client.get("/api/plants").status_code == 401
    assert client.get("/api/plants/PLANT-0001").status_code == 401
    assert client.get("/api/plants/search?name=ash").status_code == 401


def test_plants_can_be_listed_and_fetched(client):

    seed_plants()

    headers = auth_header("farmer", accounts.FARMER)

    listing = client.get("/api/plants", headers=headers)

    assert listing.status_code == 200
    assert listing.json()["total"] == 2

    one = client.get("/api/plants/PLANT-0002", headers=headers)

    assert one.status_code == 200
    assert one.json()["common_name"] == "Ashwagandha"

    assert client.get(
        "/api/plants/PLANT-9999", headers=headers
    ).status_code == 404


def test_plant_search_matches_common_and_scientific_names(client):

    seed_plants()

    headers = auth_header("farmer", accounts.FARMER)

    by_common = client.get("/api/plants/search?name=ashwa", headers=headers)

    assert by_common.status_code == 200
    assert by_common.json()["count"] == 1
    assert by_common.json()["plants"][0]["plant_id"] == "PLANT-0002"

    by_scientific = client.get(
        "/api/plants/search?name=withania", headers=headers
    )

    assert by_scientific.json()["count"] == 1


def test_plant_search_escapes_regex_metacharacters(client):
    """
    An unescaped term would let a caller send a pathological pattern, and
    would make punctuation in a real plant name behave as syntax. The shipped
    dataset is full of names like "Abelmoschus esculentus (L.) Moench".
    """

    seed_plants()

    headers = auth_header("farmer", accounts.FARMER)

    # Parentheses as literal text: this name really does contain "(L.)".
    literal = client.get("/api/plants/search?name=(L.)", headers=headers)

    assert literal.status_code == 200
    assert literal.json()["count"] == 2

    # A catastrophic-backtracking pattern is matched as text, and finds nothing.
    hostile = client.get(
        "/api/plants/search?name=(a%2B)%2B%24", headers=headers
    )

    assert hostile.status_code == 200
    assert hostile.json()["count"] == 0


def test_plant_listing_is_paginated(client):

    db = mongo_harness.current_db()

    db.plants.insert_many([
        {"plant_id": f"PLANT-{n:04d}", "common_name": f"Plant {n}"}
        for n in range(1, 251)
    ])

    headers = auth_header("farmer", accounts.FARMER)

    page = client.get("/api/plants?limit=10&offset=20", headers=headers).json()

    assert page["count"] == 10
    assert page["total"] == 250
    assert page["plants"][0]["plant_id"] == "PLANT-0021"


# ============================================================
# INVESTIGATIONS
# ============================================================

def seed_report():

    db = mongo_harness.current_db()

    db.medicine_batches.insert_one({
        "medicine_batch_id": "MED-2026-001", "qr_id": "QR-2026-001"
    })

    db.consumer_reports.insert_one({
        "report_id": "RPT-2026-001",
        "medicine_batch_id": "MED-2026-001",
        "report_status": "OPEN",
    })


OPEN_BODY = {
    "report_id": "RPT-2026-001",
    "auditor_id": "AUD-001",
    "suspected_stage": "TRANSPORT",
    "evidence_summary": "IoT custody gap under review.",
}


def test_investigations_are_regulator_only(client):

    seed_report()

    assert client.post("/api/investigations", json=OPEN_BODY).status_code == 401

    refused = client.post(
        "/api/investigations",
        json=OPEN_BODY,
        headers=auth_header("farmer", accounts.FARMER),
    )

    assert refused.status_code == 403


def test_opening_an_investigation_moves_the_report(client):

    seed_report()

    headers = auth_header("regulator", accounts.REGULATOR)

    opened = client.post("/api/investigations", json=OPEN_BODY, headers=headers)

    assert opened.status_code == 201, opened.text
    assert opened.json()["investigation_id"] == "INV-2026-001"

    report = mongo_harness.current_db().consumer_reports.find_one(
        {"report_id": "RPT-2026-001"}
    )

    assert report["report_status"] == "UNDER_INVESTIGATION"


def test_an_investigation_needs_a_real_report(client):

    headers = auth_header("regulator", accounts.REGULATOR)

    response = client.post(
        "/api/investigations",
        json={**OPEN_BODY, "report_id": "RPT-DOES-NOT-EXIST"},
        headers=headers,
    )

    assert response.status_code == 404


def test_a_report_cannot_have_two_open_investigations(client):

    seed_report()

    headers = auth_header("regulator", accounts.REGULATOR)

    assert client.post(
        "/api/investigations", json=OPEN_BODY, headers=headers
    ).status_code == 201

    duplicate = client.post(
        "/api/investigations", json=OPEN_BODY, headers=headers
    )

    assert duplicate.status_code == 409
    assert "INV-2026-001" in duplicate.json()["detail"]


def test_closing_an_investigation_resolves_the_report(client):

    seed_report()

    headers = auth_header("regulator", accounts.REGULATOR)

    investigation_id = client.post(
        "/api/investigations", json=OPEN_BODY, headers=headers
    ).json()["investigation_id"]

    closed = client.patch(
        f"/api/investigations/{investigation_id}/close",
        json={
            "root_cause": "NO_TRACEABILITY_ANOMALY_FOUND",
            "action_taken": "CONTINUE_MONITORING",
        },
        headers=headers,
    )

    assert closed.status_code == 200, closed.text
    assert closed.json()["investigation_status"] == "CLOSED"

    report = mongo_harness.current_db().consumer_reports.find_one(
        {"report_id": "RPT-2026-001"}
    )

    assert report["report_status"] == "RESOLVED"

    # Closing twice is a conflict, not a silent no-op.
    again = client.patch(
        f"/api/investigations/{investigation_id}/close",
        json={"root_cause": "X", "action_taken": "Y"},
        headers=headers,
    )

    assert again.status_code == 409


def test_a_closed_report_can_be_investigated_again(client):
    """A reopened complaint must not be blocked by the old, closed case."""

    seed_report()

    headers = auth_header("regulator", accounts.REGULATOR)

    first = client.post(
        "/api/investigations", json=OPEN_BODY, headers=headers
    ).json()["investigation_id"]

    client.patch(
        f"/api/investigations/{first}/close",
        json={"root_cause": "X", "action_taken": "Y"},
        headers=headers,
    )

    second = client.post("/api/investigations", json=OPEN_BODY, headers=headers)

    assert second.status_code == 201
    assert second.json()["investigation_id"] == "INV-2026-002"


def test_investigations_can_be_listed_and_filtered(client):

    seed_report()

    headers = auth_header("regulator", accounts.REGULATOR)

    investigation_id = client.post(
        "/api/investigations", json=OPEN_BODY, headers=headers
    ).json()["investigation_id"]

    assert client.get(
        "/api/investigations?status=OPEN", headers=headers
    ).json()["total"] == 1

    assert client.get(
        "/api/investigations?status=CLOSED", headers=headers
    ).json()["total"] == 0

    detail = client.get(
        f"/api/investigations/{investigation_id}", headers=headers
    )

    assert detail.status_code == 200
    assert detail.json()["report"]["report_id"] == "RPT-2026-001"
