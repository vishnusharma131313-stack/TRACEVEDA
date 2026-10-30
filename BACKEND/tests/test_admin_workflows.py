"""Admin bootstrap, access-request approval and administrator-only controls."""

import mongo_harness  # noqa: F401 - install mongomock before importing routes

mongo_harness.install()

import pytest
from fastapi.testclient import TestClient

from services import accounts
from services.security import create_access_token, hash_password


@pytest.fixture(autouse=True)
def fresh_database():
    mongo_harness.install()


@pytest.fixture
def client():
    return TestClient(mongo_harness.make_app())


def auth_header(username):
    user = accounts.get_user(username)
    token, _ = create_access_token(username, user["role"])
    return {"Authorization": f"Bearer {token}"}


def test_default_admin_is_created_with_requested_credentials():
    result = accounts.ensure_default_admin()
    assert result["username"] == "admin-001"
    user = accounts.authenticate("admin-001", "12345678")
    assert user is not None
    assert user["role"] == accounts.ADMIN
    stored = mongo_harness.current_db().users.find_one({"username": "admin-001"})
    assert stored["password_hash"] != "12345678"
    assert "password" not in stored


def test_default_admin_password_is_repaired_for_existing_seed_account():
    accounts.create_user("old-password-123", accounts.ADMIN, username="admin-001")
    accounts.ensure_default_admin()
    assert accounts.authenticate("admin-001", "12345678") is not None


def test_access_request_can_be_submitted_and_approved_by_admin(client):
    accounts.ensure_default_admin()

    submitted = client.post("/api/access-requests", json={
        "role": "transporter",
        "organisation_name": "North Logistics",
        "location": "Delhi, India",
        "contact_details": "north@example.com",
    })
    assert submitted.status_code == 201, submitted.text
    request_id = submitted.json()["request_id"]

    # The queue is private to administrators.
    denied = client.get("/api/access-requests")
    assert denied.status_code == 401

    admin_headers = auth_header("admin-001")
    queued = client.get("/api/access-requests", headers=admin_headers)
    assert queued.status_code == 200
    assert queued.json()["count"] == 1

    approved = client.patch(
        f"/api/access-requests/{request_id}/decision",
        headers=admin_headers,
        json={"decision": "APPROVE"},
    )
    assert approved.status_code == 200, approved.text
    credentials = approved.json()
    assert credentials["status"] == "APPROVED"
    assert credentials["username"].startswith("log-")
    authenticated = accounts.authenticate(credentials["username"], credentials["temporary_password"])
    assert authenticated is not None
    assert authenticated["role"] == accounts.LOGISTICS

    # Exercise the exact endpoint used by the frontend login form as well.
    login_response = client.post("/api/auth/login", json={
        "username": credentials["username"],
        "password": credentials["temporary_password"],
    })
    assert login_response.status_code == 200, login_response.text
    assert login_response.json()["role"] == accounts.LOGISTICS

    duplicate_decision = client.patch(
        f"/api/access-requests/{request_id}/decision",
        headers=admin_headers,
        json={"decision": "REJECT"},
    )
    assert duplicate_decision.status_code == 409


def test_non_admin_cannot_review_access_requests(client):
    accounts.create_user("auditor-password", accounts.REGULATOR, username="aud-900")
    response = client.get("/api/access-requests", headers=auth_header("aud-900"))
    assert response.status_code == 403


def test_legacy_transporter_role_is_normalized_for_login_and_authorization():
    password = "legacy-transporter-pass"
    mongo_harness.current_db().users.insert_one({
        "username": "log-legacy-001",
        "password_hash": hash_password(password),
        "role": "transporter",
        "full_name": "Legacy Transporter",
        "organisation_id": "LEGACY-LOGISTICS",
        "is_active": True,
    })

    authenticated = accounts.authenticate("LOG-LEGACY-001", password)
    assert authenticated is not None
    assert authenticated["role"] == accounts.LOGISTICS
    assert accounts.get_user("log-legacy-001")["role"] == accounts.LOGISTICS


def test_auditor_access_request_creates_regulator_account(client):
    accounts.ensure_default_admin()
    submitted = client.post("/api/access-requests", json={
        "role": "auditor",
        "organisation_name": "Independent Audit Group",
        "location": "Delhi, India",
        "contact_details": "audit@example.com",
    })
    assert submitted.status_code == 201, submitted.text
    request_id = submitted.json()["request_id"]

    approved = client.patch(
        f"/api/access-requests/{request_id}/decision",
        headers=auth_header("admin-001"),
        json={"decision": "APPROVE"},
    )
    assert approved.status_code == 200, approved.text
    credentials = approved.json()
    assert credentials["username"].startswith("aud-")
    assert credentials["role"] == accounts.REGULATOR

    login_response = client.post("/api/auth/login", json={
        "username": credentials["username"],
        "password": credentials["temporary_password"],
    })
    assert login_response.status_code == 200, login_response.text
    assert login_response.json()["role"] == accounts.REGULATOR
