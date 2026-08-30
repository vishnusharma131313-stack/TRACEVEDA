from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from database import db
from dependencies import require_authenticated, require_roles
from services import blockchain_service, ids
from services.accounts import LAB

router = APIRouter(
    prefix="/api/lab",
    tags=["Laboratory"]
)


# Statuses this route may put on a processing batch.
STATUS_BLOCKED = "BLOCKED"
STATUS_APPROVED = "APPROVED_FOR_MANUFACTURING"

# The stage that gates manufacturing. Anything else is a post-manufacturing
# or in-process check and must not move the batch's status.
GATING_STAGE = "PRE_MANUFACTURING"


# =========================
# REQUEST MODEL
# =========================

class LabTestRequest(BaseModel):
    batch_id: str = Field(min_length=1, max_length=64)
    lab_id: str = Field(min_length=1, max_length=64)

    # Constrained rather than a free string: test_stage decides whether a
    # batch becomes manufacturable, so a typo used to silently produce a
    # test that gated nothing.
    test_stage: Literal[
        "PRE_MANUFACTURING",
        "IN_PROCESS",
        "POST_MANUFACTURING"
    ]

    test_type: str = Field(min_length=1, max_length=128)
    test_parameters: dict = Field(default_factory=dict)
    result: Literal["PASS", "FAIL", "pass", "fail"]


# =========================
# CREATE LAB TEST
# =========================

@router.post("/tests", status_code=201)
def create_lab_test(
    data: LabTestRequest,
    user: dict = Depends(require_roles(LAB)),
):

    batch = db.processing_batches.find_one(
        {"processing_batch_id": data.batch_id},
        {"_id": 0, "status": 1}
    )

    if not batch:
        raise HTTPException(
            status_code=404,
            detail="Processing batch not found"
        )

    result = data.result.upper()

    lab_test_id = ids.mint("lab_test")

    # Only a pre-manufacturing test moves the batch's status; every other
    # stage records its verdict without changing manufacturability.
    if data.test_stage == GATING_STAGE:
        batch_status = STATUS_BLOCKED if result == "FAIL" else STATUS_APPROVED

    else:
        batch_status = batch.get("status", "CREATED")

    lab_test = {
        "lab_test_id": lab_test_id,
        "batch_id": data.batch_id,
        "lab_id": data.lab_id,
        "test_stage": data.test_stage,
        "test_type": data.test_type,
        "test_parameters": data.test_parameters,
        "result": result,
        "status": "VERIFIED",
        "verified_by": user["username"],
        "created_at": datetime.now(timezone.utc)
    }

    db.lab_tests.insert_one(lab_test)

    if data.test_stage == GATING_STAGE:

        db.processing_batches.update_one(
            {"processing_batch_id": data.batch_id},
            {"$set": {"status": batch_status}}
        )

    # Anchored for PASS and FAIL alike - a failed quality test is exactly
    # the record a dispute turns on.
    blockchain_tx = blockchain_service.safe_anchor(
        "QUALITY_STATUS",
        "PROCESSING",
        data.batch_id,
        {
            "lab_test_id": lab_test_id,
            "lab_id": data.lab_id,
            "test_stage": data.test_stage,
            "test_type": data.test_type,
            "result": result,
            "batch_status": batch_status,
            "recorded_by": user["username"]
        }
    )

    return {
        "lab_test_id": lab_test_id,
        "batch_id": data.batch_id,
        "result": result,
        "status": "VERIFIED",
        "batch_status": batch_status,
        "blockchain_tx": blockchain_tx
    }


# =========================
# GET LAB TESTS
# =========================

@router.get("/tests/{batch_id}")
def get_lab_tests(
    batch_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    user: dict = Depends(require_authenticated),
):

    tests = list(
        db.lab_tests.find(
            {"batch_id": batch_id},
            {"_id": 0}
        ).limit(limit)
    )

    return {
        "batch_id": batch_id,
        "tests": tests
    }
