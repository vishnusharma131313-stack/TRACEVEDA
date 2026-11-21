from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from database import db
from dependencies import require_authenticated, require_roles
from services import blockchain_service, ids
from services.accounts import LAB

router = APIRouter(prefix="/api/lab", tags=["Laboratory"])

STATUS_BLOCKED = "BLOCKED"
STATUS_APPROVED = "APPROVED_FOR_MANUFACTURING"
GATING_STAGE = "PRE_MANUFACTURING"


class LabTestRequest(BaseModel):
    """Unified lab submission contract.

    `test_phase` is used by the current UI for raw-material and finished-
    medicine tests. `test_stage` remains supported for existing integrations
    that test a processing batch and use the manufacturing quality gate.
    """

    batch_id: str = Field(min_length=1, max_length=64)
    test_type: str = Field(default="QUALITY_TEST", min_length=1, max_length=128)
    result: Literal["PASS", "FAIL", "pass", "fail"]
    test_parameters: dict = Field(default_factory=dict)
    test_date: date | None = None
    certificate_id: str | None = Field(default=None, max_length=128)
    test_phase: Literal["RAW_BATCH_TEST", "FINAL_PRODUCT_QUALITY_TEST"] | None = None
    test_stage: Literal[
        "PRE_MANUFACTURING",
        "IN_PROCESS",
        "POST_MANUFACTURING",
    ] | None = None

    # Accepted for older API clients only. The authenticated organisation is
    # authoritative whenever present; certificate_id is never treated as lab_id.
    lab_id: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def _require_target_phase(self):
        if not self.test_phase and not self.test_stage:
            raise ValueError("test_phase is required for raw/medicine tests; test_stage is required for processing-batch tests")
        if self.test_phase and self.test_stage:
            raise ValueError("Send test_phase or test_stage, not both")
        if self.certificate_id is not None:
            self.certificate_id = self.certificate_id.strip() or None
        return self


def _resolve_lab_target(data: LabTestRequest):
    """Return collection, identifier field and ledger entity type."""
    if data.test_phase == "RAW_BATCH_TEST":
        return db.raw_material_batches, "raw_batch_id", "RAW", "RAW_BATCH_TEST"
    if data.test_phase == "FINAL_PRODUCT_QUALITY_TEST":
        return db.medicine_batches, "medicine_batch_id", "MEDICINE", "FINAL_PRODUCT_QUALITY_TEST"
    return db.processing_batches, "processing_batch_id", "PROCESSING", data.test_stage


@router.post("/tests", status_code=201)
def create_lab_test(
    data: LabTestRequest,
    user: dict = Depends(require_roles(LAB)),
):
    collection, id_field, entity_type, phase = _resolve_lab_target(data)
    batch = collection.find_one({id_field: data.batch_id}, {"_id": 0})
    if not batch:
        label = {
            "RAW": "Raw material batch",
            "MEDICINE": "Medicine batch",
            "PROCESSING": "Processing batch",
        }[entity_type]
        raise HTTPException(status_code=404, detail=f"{label} not found")

    result = data.result.upper()
    lab_test_id = ids.mint("lab_test")
    # Prefer the organisation attached to the authenticated lab account.
    # A legacy client-supplied ID is only a fallback for old seeded accounts.
    lab_id = user.get("organisation_id") or data.lab_id or user.get("username") or "UNKNOWN_LAB"
    verified_at = datetime.now(timezone.utc)

    batch_status = batch.get("status") or batch.get("batch_status") or ""
    if entity_type == "PROCESSING" and phase == GATING_STAGE:
        batch_status = STATUS_BLOCKED if result == "FAIL" else STATUS_APPROVED
        collection.update_one(
            {id_field: data.batch_id},
            {"$set": {"status": batch_status}},
        )

    lab_test = {
        "lab_test_id": lab_test_id,
        "batch_id": data.batch_id,
        "batch_type": entity_type,
        "lab_id": lab_id,
        "test_phase": phase,
        "test_stage": data.test_stage,
        "test_type": data.test_type,
        "test_parameters": data.test_parameters,
        "test_date": data.test_date.isoformat() if data.test_date else None,
        "certificate_id": data.certificate_id,
        "result": result,
        "status": "VERIFIED",
        "verified_by": user.get("username"),
        "verification_timestamp": verified_at,
        "created_at": verified_at,
    }
    db.lab_tests.insert_one(lab_test)

    blockchain_tx = blockchain_service.safe_anchor(
        "QUALITY_STATUS",
        entity_type,
        data.batch_id,
        {
            "lab_test_id": lab_test_id,
            "lab_id": lab_id,
            "test_phase": phase,
            "test_stage": data.test_stage,
            "test_type": data.test_type,
            "certificate_id": data.certificate_id,
            "test_date": data.test_date.isoformat() if data.test_date else None,
            "result": result,
            "batch_status": batch_status,
            "recorded_by": user.get("username"),
        },
    )

    return {
        "success": True,
        "lab_test_id": lab_test_id,
        "batch_id": data.batch_id,
        "batch_type": entity_type,
        "lab_id": lab_id,
        "test_phase": phase,
        "test_stage": data.test_stage,
        "test_type": data.test_type,
        "test_date": data.test_date.isoformat() if data.test_date else None,
        "certificate_id": data.certificate_id,
        "result": result,
        "status": "VERIFIED",
        "batch_status": batch_status,
        "blockchain_tx": blockchain_tx,
    }


@router.get("/tests/{batch_id}")
def get_lab_tests(
    batch_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    user: dict = Depends(require_authenticated),
):
    tests = list(
        db.lab_tests.find({"batch_id": batch_id}, {"_id": 0})
        .sort("created_at", -1)
        .limit(limit)
    )
    return {"batch_id": batch_id, "tests": tests}
