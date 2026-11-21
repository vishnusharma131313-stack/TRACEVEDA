"""Regression coverage for lab PDF storage and multi-parent medicine lots."""

import json
import mongo_harness  # noqa: F401 - install mongomock before importing routes/services

mongo_harness.install()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from services import accounts  # noqa: E402
from services.security import create_access_token  # noqa: E402


PASSWORD = "regression-password-123"


@pytest.fixture(autouse=True)
def fresh_database():
    mongo_harness.install()


@pytest.fixture
def client():
    return TestClient(mongo_harness.make_app())


def auth_header(username, role, organisation_id=None):
    accounts.create_user(
        username=username,
        password=PASSWORD,
        role=role,
        organisation_id=organisation_id,
    )
    token, _ = create_access_token(username, role)
    return {"Authorization": f"Bearer {token}"}


def test_lab_can_submit_raw_and_final_product_tests(client):
    db = mongo_harness.current_db()
    headers = auth_header("lab-regression", accounts.LAB, "LAB-ORG-01")
    db.raw_material_batches.insert_one({"raw_batch_id": "ASH-2026-001", "status": "REGISTERED"})
    db.medicine_batches.insert_one({"medicine_batch_id": "MED-2026-001", "batch_status": "RELEASED"})

    raw_response = client.post("/api/lab/tests", json={
        "batch_id": "ASH-2026-001",
        "test_phase": "RAW_BATCH_TEST",
        "test_type": "RAW_MATERIAL_QUALITY",
        "test_date": "2026-11-20",
        "certificate_id": "CERT-PRE-0001",
        "test_parameters": {"moisture": "within limits"},
        "result": "PASS",
    }, headers=headers)
    assert raw_response.status_code == 201, raw_response.text
    raw_test = raw_response.json()
    assert raw_test["lab_id"] == "LAB-ORG-01"
    assert raw_test["test_phase"] == "RAW_BATCH_TEST"
    assert raw_test["certificate_id"] == "CERT-PRE-0001"
    assert raw_test["test_date"] == "2026-11-20"

    final_response = client.post("/api/lab/tests", json={
        "batch_id": "MED-2026-001",
        "test_phase": "FINAL_PRODUCT_QUALITY_TEST",
        "test_type": "FINAL_PRODUCT_QUALITY",
        "test_date": "2026-11-21",
        "certificate_id": "CERT-POST-0001",
        "test_parameters": {},
        "result": "PASS",
    }, headers=headers)
    assert final_response.status_code == 201, final_response.text
    assert final_response.json()["batch_type"] == "MEDICINE"

    saved = list(db.lab_tests.find({}, {"_id": 0}))
    assert len(saved) == 2
    assert {item["certificate_id"] for item in saved} == {"CERT-PRE-0001", "CERT-POST-0001"}


def test_medicine_registration_persists_all_processing_parents_and_trace_links(client):
    db = mongo_harness.current_db()
    headers = auth_header("manufacturer-regression", accounts.MANUFACTURER, "MFG-ORG-01")

    for index in (1, 2):
        processing_id = f"PROCESS-2026-00{index}"
        raw_id = f"ASH-2026-00{index}"
        db.processing_batches.insert_one({
            "processing_batch_id": processing_id,
            "status": "APPROVED_FOR_MANUFACTURING",
        })
        db.raw_material_batches.insert_one({"raw_batch_id": raw_id, "plant_id": f"PLANT-{index}"})
        db.batch_relationships.insert_one({
            "relationship_id": f"REL-RAW-{index}",
            "parent_batch_id": raw_id,
            "child_batch_id": processing_id,
            "relationship_type": "RAW_TO_PROCESSING",
        })

    response = client.post("/api/medicine", json={
        "medicine_batch_id": "MED-2026-099",
        "source_processing_batches": ["PROCESS-2026-001", "PROCESS-2026-002"],
        "manufacturer_id": "MFG-ORG-01",
        "product_name": "TraceVeda Herbal Tablets",
        "manufacturing_date": "2026-11-20",
        "expiry_date": "2028-11-20",
    }, headers=headers)
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["processing_batch_ids"] == ["PROCESS-2026-001", "PROCESS-2026-002"]

    medicine = db.medicine_batches.find_one({"medicine_batch_id": "MED-2026-099"})
    assert medicine["processing_batch_ids"] == ["PROCESS-2026-001", "PROCESS-2026-002"]
    assert medicine["processing_batch_id"] is None
    links = list(db.batch_relationships.find({
        "child_batch_id": "MED-2026-099",
        "relationship_type": "PROCESSING_TO_MEDICINE",
    }))
    assert {item["parent_batch_id"] for item in links} == {"PROCESS-2026-001", "PROCESS-2026-002"}

    reverse = client.get("/api/trace/reverse/MED-2026-099", headers=headers)
    assert reverse.status_code == 200, reverse.text
    reverse_data = reverse.json()
    assert {item["processing_batch_id"] for item in reverse_data["processing_batches"]} == {
        "PROCESS-2026-001", "PROCESS-2026-002"
    }
    assert {item["raw_batch"]["raw_batch_id"] for item in reverse_data["raw_batches"]} == {
        "ASH-2026-001", "ASH-2026-002"
    }

    verified = client.get(f"/api/verify/{created['qr_id']}")
    assert verified.status_code == 200, verified.text
    assert verified.json()["traceability"]["processing_batch_ids"] == [
        "PROCESS-2026-001", "PROCESS-2026-002"
    ]



def test_lab_pdf_report_is_stored_in_gridfs_and_downloadable(client):
    db = mongo_harness.current_db()
    headers = auth_header("lab-pdf-regression", accounts.LAB, "LAB-ORG-PDF")
    db.raw_material_batches.insert_one({"raw_batch_id": "ASH-PDF-2026-001", "status": "REGISTERED"})

    payload = {
        "batch_id": "ASH-PDF-2026-001",
        "test_phase": "RAW_BATCH_TEST",
        "test_type": "RAW_MATERIAL_QUALITY",
        "test_date": "2026-11-21",
        "certificate_id": "CERT-PDF-0001",
        "test_parameters": {"moisture": "within limits"},
        "result": "PASS",
    }
    pdf_bytes = b"%PDF-1.7\nTraceVeda test PDF\n%%EOF"
    response = client.post(
        "/api/lab/tests",
        data={"payload": json.dumps(payload)},
        files={"report": ("quality-certificate.pdf", pdf_bytes, "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["report"]["filename"] == "quality-certificate.pdf"
    assert created["report"]["size_bytes"] == len(pdf_bytes)
    assert created["report"]["download_url"].endswith(
        f"/api/lab/tests/{created['lab_test_id']}/report"
    )

    saved = db.lab_tests.find_one({"lab_test_id": created["lab_test_id"]})
    assert saved["report"]["sha256"] == created["report"]["sha256"]
    assert db["lab_reports.files"].count_documents(
        {"metadata.lab_test_id": created["lab_test_id"]}
    ) == 1

    downloaded = client.get(created["report"]["download_url"], headers=headers)
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.headers["content-type"].startswith("application/pdf")
    assert downloaded.content == pdf_bytes


def test_lab_report_upload_rejects_non_pdf_content(client):
    db = mongo_harness.current_db()
    headers = auth_header("lab-invalid-pdf", accounts.LAB, "LAB-ORG-PDF")
    db.raw_material_batches.insert_one({"raw_batch_id": "ASH-PDF-2026-002", "status": "REGISTERED"})
    payload = {
        "batch_id": "ASH-PDF-2026-002",
        "test_phase": "RAW_BATCH_TEST",
        "test_type": "RAW_MATERIAL_QUALITY",
        "test_date": "2026-11-21",
        "certificate_id": "CERT-PDF-0002",
        "result": "PASS",
    }
    response = client.post(
        "/api/lab/tests",
        data={"payload": json.dumps(payload)},
        files={"report": ("not-a-pdf.pdf", b"this is not a PDF", "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 400, response.text
    assert db.lab_tests.count_documents({"batch_id": "ASH-PDF-2026-002"}) == 0
