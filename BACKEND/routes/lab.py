from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime

from database import db

router = APIRouter(
    prefix="/api/lab",
    tags=["Laboratory"]
)


# =========================
# REQUEST MODEL
# =========================

class LabTestRequest(BaseModel):
    batch_id: str
    lab_id: str
    test_stage: str
    test_type: str
    test_parameters: dict
    result: str


# =========================
# CREATE LAB TEST
# =========================

@router.post("/tests")
def create_lab_test(data: LabTestRequest):

    # Check that batch exists
    batch = db.processing_batches.find_one({
        "processing_batch_id": data.batch_id
    })

    if not batch:
        raise HTTPException(
            status_code=404,
            detail="Processing batch not found"
        )

    # Validate result
    result = data.result.upper()

    if result not in ["PASS", "FAIL"]:
        raise HTTPException(
            status_code=400,
            detail="Result must be PASS or FAIL"
        )

    # Generate test ID
    count = db.lab_tests.count_documents({}) + 1

    lab_test_id = f"LABTEST-{datetime.now().year}-{count:03d}"

    # Determine batch status
    if data.test_stage == "PRE_MANUFACTURING":

        if result == "FAIL":
            batch_status = "BLOCKED"

        else:
            batch_status = "APPROVED_FOR_MANUFACTURING"

    else:
        batch_status = batch.get("status", "CREATED")

    # Store lab test
    lab_test = {
        "lab_test_id": lab_test_id,
        "batch_id": data.batch_id,
        "lab_id": data.lab_id,
        "test_stage": data.test_stage,
        "test_type": data.test_type,
        "test_parameters": data.test_parameters,
        "result": result,
        "status": "VERIFIED",
        "created_at": datetime.utcnow()
    }

    db.lab_tests.insert_one(lab_test)

    # Update processing batch status
    db.processing_batches.update_one(
        {
            "processing_batch_id": data.batch_id
        },
        {
            "$set": {
                "status": batch_status
            }
        }
    )

    return {
        "lab_test_id": lab_test_id,
        "batch_id": data.batch_id,
        "result": result,
        "status": "VERIFIED",
        "batch_status": batch_status
    }


# =========================
# GET LAB TESTS
# =========================

@router.get("/tests/{batch_id}")
def get_lab_tests(batch_id: str):

    tests = list(
        db.lab_tests.find(
            {"batch_id": batch_id},
            {"_id": 0}
        )
    )

    return {
        "batch_id": batch_id,
        "tests": tests
    }