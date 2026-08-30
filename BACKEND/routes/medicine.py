from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from database import db
from dependencies import require_authenticated, require_roles
from services import blockchain_service, ids
from services.accounts import MANUFACTURER

router = APIRouter(
    prefix="/api",
    tags=["Medicine"]
)


APPROVED_FOR_MANUFACTURING = "APPROVED_FOR_MANUFACTURING"


# =========================
# REQUEST MODEL
# =========================

class MedicineBatchRequest(BaseModel):
    processing_batch_id: str = Field(min_length=1, max_length=64)
    manufacturer_id: str = Field(min_length=1, max_length=64)
    product_name: str = Field(min_length=1, max_length=200)
    manufacturing_date: date
    expiry_date: date

    @model_validator(mode="after")
    def _expiry_after_manufacture(self):

        if self.expiry_date <= self.manufacturing_date:
            raise ValueError("expiry_date must be after manufacturing_date")

        return self


# =========================
# CREATE MEDICINE BATCH
# =========================

@router.post("/medicine", status_code=201)
def create_medicine_batch(
    data: MedicineBatchRequest,
    user: dict = Depends(require_roles(MANUFACTURER)),
):

    processing_batch = db.processing_batches.find_one(
        {"processing_batch_id": data.processing_batch_id},
        {"_id": 0, "status": 1}
    )

    if not processing_batch:
        raise HTTPException(
            status_code=404,
            detail="Processing batch not found"
        )

    # Medicine can only be created after successful
    # pre-manufacturing laboratory verification.
    if processing_batch.get("status") != APPROVED_FOR_MANUFACTURING:
        raise HTTPException(
            status_code=400,
            detail=(
                "Processing batch is not approved for manufacturing "
                f"(status: {processing_batch.get('status') or 'unknown'}). "
                "Record a PASS on a PRE_MANUFACTURING lab test first."
            )
        )

    medicine_batch_id = ids.mint("medicine_batch")

    # The QR id tracks the medicine id so a scanned code is traceable back to
    # its batch by inspection. Both are unique-indexed.
    qr_id = medicine_batch_id.replace("MED-", "QR-", 1)

    if db.medicine_batches.find_one({"qr_id": qr_id}, {"_id": 1}):
        raise HTTPException(
            status_code=409,
            detail=f"QR id {qr_id} is already in use"
        )

    medicine_batch = {
        "medicine_batch_id": medicine_batch_id,
        "qr_id": qr_id,
        "processing_batch_id": data.processing_batch_id,
        "manufacturer_id": data.manufacturer_id,
        "product_name": data.product_name,
        "manufacturing_date": data.manufacturing_date.isoformat(),
        "expiry_date": data.expiry_date.isoformat(),
        "batch_status": "RELEASED",
        "created_by": user["username"],
        "created_at": datetime.now(timezone.utc)
    }

    db.medicine_batches.insert_one(medicine_batch)

    blockchain_tx = blockchain_service.safe_anchor(
        "MEDICINE_LINKED",
        "MEDICINE",
        medicine_batch_id,
        {
            "processing_batch_id": data.processing_batch_id,
            "manufacturer_id": data.manufacturer_id,
            "qr_id": qr_id,
            "product_name": data.product_name,
            "manufacturing_date": data.manufacturing_date,
            "expiry_date": data.expiry_date,
            "batch_status": "RELEASED",
            "recorded_by": user["username"]
        }
    )

    return {
        "medicine_batch_id": medicine_batch_id,
        "qr_id": qr_id,
        "status": "CREATED",
        "blockchain_tx": blockchain_tx
    }


# =========================
# LIST ALL MEDICINE BATCHES
# =========================

@router.get("/medicine")
def list_medicine_batches(
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(require_authenticated),
):

    batches = list(
        db.medicine_batches.find({}, {"_id": 0})
        .sort("created_at", -1)
        .skip(offset)
        .limit(limit)
    )

    return {
        "batches": batches,
        "count": len(batches),
        "total": db.medicine_batches.count_documents({})
    }


# =========================
# GET MEDICINE BATCH
# =========================

@router.get("/medicine/{medicine_batch_id}")
def get_medicine_batch(
    medicine_batch_id: str,
    user: dict = Depends(require_authenticated),
):

    medicine = db.medicine_batches.find_one(
        {"medicine_batch_id": medicine_batch_id},
        {"_id": 0}
    )

    if not medicine:
        raise HTTPException(
            status_code=404,
            detail="Medicine batch not found"
        )

    return medicine


# =========================
# QR VERIFICATION
# =========================
# PUBLIC. This is the endpoint a consumer's phone hits after scanning a pack,
# so it deliberately requires no credentials. It returns provenance only -
# no manufacturer internals, no commercial quantities, no operator names.
# =========================

@router.get("/verify/{qr_id}")
def verify_medicine(qr_id: str):

    medicine = db.medicine_batches.find_one({"qr_id": qr_id}, {"_id": 0})

    if not medicine:
        return {
            "verified": False,
            "message": "Invalid QR"
        }

    raw_relationships = list(
        db.batch_relationships.find(
            {"child_batch_id": medicine.get("processing_batch_id")},
            {"_id": 0, "parent_batch_id": 1}
        )
    )

    raw_batches = [
        relationship["parent_batch_id"]
        for relationship in raw_relationships
        if relationship.get("parent_batch_id")
    ]

    plant_id = None

    if raw_batches:

        raw_batch = db.raw_material_batches.find_one(
            {"raw_batch_id": raw_batches[0]},
            {"_id": 0, "plant_id": 1}
        )

        if raw_batch:
            plant_id = raw_batch.get("plant_id")

    # .get() throughout: seeded documents come from a CSV whose columns do
    # not perfectly match what this route writes, and a missing column must
    # not turn a consumer's scan into a 500.
    return {
        "verified": True,
        "medicine_batch_id": medicine.get("medicine_batch_id"),
        "product_name": medicine.get("product_name"),
        "batch_status": medicine.get("batch_status"),
        "manufacturing_date": medicine.get("manufacturing_date"),
        "expiry_date": medicine.get("expiry_date"),
        "traceability": {
            "processing_batch_id": medicine.get("processing_batch_id"),
            "raw_batches": raw_batches,
            "plant_id": plant_id
        }
    }
