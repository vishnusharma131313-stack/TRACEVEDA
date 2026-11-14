"""Public assistant, no-email access requests and admin approval tests."""

import mongo_harness  # noqa: F401 - install mongomock before importing routes/services

mongo_harness.install()

import hashlib  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from services import accounts  # noqa: E402
from services.security import create_access_token, hash_password  # noqa: E402


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


def application_payload(role="transporter", email="north@example.com", phone="+91 98765 43210"):
    return {
        "role": role,
        "full_name": "Applicant Person",
        "email": email,
        "phone": phone,
        "organisation_name": "TraceVeda Test Organisation",
        "location": "Delhi, India",
        "designation": "Operations Manager",
        "role_details": "Vehicle and fleet registration details available.",
        "reason": "Need access to the TraceVeda stakeholder workspace.",
    }


def submit_request(client, **kwargs):
    response = client.post("/api/access-requests", json=application_payload(**kwargs))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "PENDING"
    assert body.get("request_id")
    assert len(body.get("recovery_code", "")) >= 24
    return body


def test_default_admin_is_created_with_requested_credentials():
    result = accounts.ensure_default_admin()
    assert result["username"] == "admin-001"
    user = accounts.authenticate("admin-001", "12345678")
    assert user is not None and user["role"] == accounts.ADMIN
    stored = mongo_harness.current_db().users.find_one({"username": "admin-001"})
    assert stored["password_hash"] != "12345678"
    assert "password" not in stored


def test_default_admin_password_is_repaired_for_existing_seed_account():
    accounts.create_user("old-password-123", accounts.ADMIN, username="admin-001")
    accounts.ensure_default_admin()
    assert accounts.authenticate("admin-001", "12345678") is not None


def test_application_keeps_contact_fields_and_only_stores_recovery_hash(client):
    submitted = submit_request(client)
    stored = mongo_harness.current_db().access_requests.find_one({"request_id": submitted["request_id"]})
    assert stored["email"] == "north@example.com"
    assert stored["phone"] == "+91 98765 43210"
    assert stored["email_verified"] is False
    assert stored["phone_verified"] is False
    assert "claim_code_attempts" not in stored
    assert stored["claim_code_hash"] == hashlib.sha256(
        f"{submitted['request_id']}:{submitted['recovery_code']}".encode()
    ).hexdigest()
    assert submitted["recovery_code"] not in str(stored)
    assert "recovery_code" not in stored


def test_request_status_requires_request_id_and_recovery_code(client):
    submitted = submit_request(client)
    wrong = client.post("/api/access-requests/status", json={
        "request_id": submitted["request_id"], "recovery_code": "x" * 30
    })
    assert wrong.status_code == 404
    pending = client.post("/api/access-requests/status", json={
        "request_id": submitted["request_id"], "recovery_code": submitted["recovery_code"]
    })
    assert pending.status_code == 200
    assert pending.json()["status"] == "PENDING"


def test_no_email_admin_approval_and_one_time_password_activation(client):
    accounts.ensure_default_admin()
    submitted = submit_request(client)
    request_id, recovery_code = submitted["request_id"], submitted["recovery_code"]

    # Application review is private to administrators.
    assert client.get("/api/access-requests").status_code == 401
    admin_headers = auth_header("admin-001")
    queue = client.get("/api/access-requests", headers=admin_headers)
    assert queue.status_code == 200
    record = queue.json()["requests"][0]
    assert record["email"] == "north@example.com"
    assert record["phone"] == "+91 98765 43210"
    assert "claim_code_hash" not in record
    assert record["activation_ready"] is True

    approved = client.patch(
        f"/api/access-requests/{request_id}/decision",
        headers=admin_headers,
        json={"decision": "APPROVE"},
    )
    assert approved.status_code == 200, approved.text
    result = approved.json()
    assert result["status"] == "APPROVED"
    assert result["username"].startswith("log-")
    assert "password" not in result and "recovery_code" not in result
    assert "email" not in result or result.get("email") is None
    assert accounts.authenticate(result["username"], "not-the-password") is None

    status = client.post("/api/access-requests/status", json={
        "request_id": request_id, "recovery_code": recovery_code
    })
    assert status.status_code == 200
    assert status.json()["status"] == "APPROVED"
    assert status.json()["username"] == result["username"]

    activated = client.post("/api/auth/activate", json={
        "request_id": request_id,
        "recovery_code": recovery_code,
        "password": "new-secure-password-123",
    })
    assert activated.status_code == 200, activated.text
    assert activated.json()["username"] == result["username"]
    assert accounts.authenticate(result["username"], "new-secure-password-123") is not None

    login = client.post("/api/auth/login", json={
        "username": result["username"], "password": "new-secure-password-123"
    })
    assert login.status_code == 200, login.text

    second_activation = client.post("/api/auth/activate", json={
        "request_id": request_id,
        "recovery_code": recovery_code,
        "password": "another-password-123",
    })
    assert second_activation.status_code == 409

    activated_status = client.post("/api/access-requests/status", json={
        "request_id": request_id, "recovery_code": recovery_code
    })
    assert activated_status.status_code == 200
    assert activated_status.json()["status"] == "ACTIVATED"


def test_reject_does_not_create_an_account(client):
    accounts.ensure_default_admin()
    submitted = submit_request(client, role="lab", email="lab@example.com", phone="+91 98765 43211")
    rejected = client.patch(
        f"/api/access-requests/{submitted['request_id']}/decision",
        headers=auth_header("admin-001"),
        json={"decision": "REJECT", "admin_notes": "Please provide a valid laboratory registration."},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"
    status = client.post("/api/access-requests/status", json={
        "request_id": submitted["request_id"], "recovery_code": submitted["recovery_code"]
    })
    assert status.status_code == 200
    assert status.json()["status"] == "REJECTED"
    users = accounts.list_users()
    assert all(user["role"] == accounts.ADMIN for user in users)


def test_non_admin_cannot_review_access_requests(client):
    accounts.create_user("auditor-password", accounts.REGULATOR, username="aud-900")
    response = client.get("/api/access-requests", headers=auth_header("aud-900"))
    assert response.status_code == 403


def test_admin_role_cannot_be_requested_publicly(client):
    response = client.post("/api/access-requests", json=application_payload(role="admin"))
    assert response.status_code == 422


def test_duplicate_pending_contact_details_are_blocked(client):
    submit_request(client)
    duplicate_email = client.post("/api/access-requests", json=application_payload(email="north@example.com", phone="+91 98765 43219"))
    assert duplicate_email.status_code == 409
    duplicate_phone = client.post("/api/access-requests", json=application_payload(email="another@example.com", phone="+91 98765 43210"))
    assert duplicate_phone.status_code == 409


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


def test_gemini_adapter_formats_history_and_uses_system_prompt(monkeypatch):
    import routes.assistant as assistant_routes

    captured = {}

    class FakeModels:
        def generate_content(self, **kwargs):
            captured.update(kwargs)
            return type("FakeResponse", (), {"text": "Hello from Gemini"})()

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client_options"] = kwargs
            self.models = FakeModels()

    monkeypatch.setattr(assistant_routes.genai, "Client", FakeClient)
    monkeypatch.setattr(assistant_routes.settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(assistant_routes.settings, "gemini_model", "gemini-3.5-flash-lite")

    answer = assistant_routes._gemini_answer([
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
        {"role": "user", "content": "What is TraceVeda?"},
    ])

    assert answer == "Hello from Gemini"
    assert captured["model"] == "gemini-3.5-flash-lite"
    assert [item["role"] for item in captured["contents"]] == ["user", "model", "user"]
    assert captured["config"].system_instruction == assistant_routes.SYSTEM_PROMPT
    assert captured["client_options"]["http_options"].timeout == 25_000


def test_public_assistant_sessions_store_chat_history(client, monkeypatch):
    import routes.assistant as assistant_routes
    monkeypatch.setattr(assistant_routes, "_gemini_answer", lambda messages: "Namaste! TraceVeda tracks supply-chain events.")
    created = client.post("/api/assistant/session", json={})
    assert created.status_code == 201, created.text
    session_id = created.json()["session_id"]
    reply = client.post("/api/assistant/chat", json={"session_id": session_id, "message": "What is TraceVeda?"})
    assert reply.status_code == 200, reply.text
    assert reply.json()["provider"] == "gemini"
    history = client.get(f"/api/assistant/session/{session_id}")
    assert history.status_code == 200
    assert len(history.json()["messages"]) == 2


def test_visitor_can_delete_their_anonymous_chat(client):
    created = client.post("/api/assistant/session", json={})
    session_id = created.json()["session_id"]
    deleted = client.delete(f"/api/assistant/session/{session_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/assistant/session/{session_id}").status_code == 404


def test_legacy_request_cannot_be_approved_without_recovery_code(client):
    accounts.ensure_default_admin()
    db = mongo_harness.current_db()
    db.access_requests.insert_one({
        "request_id": "ACCESS-LEGACY-001",
        "role": accounts.LAB,
        "organisation_name": "Old applicant",
        "location": "Delhi",
        "contact_details": "old@example.com",
        "status": "PENDING",
        "submitted_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    })
    admin_headers = auth_header("admin-001")
    row = next(item for item in client.get("/api/access-requests", headers=admin_headers).json()["requests"] if item["request_id"] == "ACCESS-LEGACY-001")
    assert row["activation_ready"] is False
    response = client.patch(
        "/api/access-requests/ACCESS-LEGACY-001/decision",
        headers=admin_headers,
        json={"decision": "APPROVE"},
    )
    assert response.status_code == 400
    assert "legacy application" in response.json()["detail"].lower()
