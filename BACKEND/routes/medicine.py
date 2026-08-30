from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import date, datetime

from database import db
from services import blockchain_service

router = APIRouter(
    prefix="/api",
    tags=["Medicine"]
)


# =========================
# REQUEST MODEL
# =========================

class MedicineBatchRequest(BaseModel):
    processing_batch_id: str
    manufacturer_id: str
    product_name: str
    manufacturing_date: date
    expiry_date: date


# =========================
# CREATE MEDICINE BATCH
# =========================

@router.post("/medicine")
def create_medicine_batch(data: MedicineBatchRequest):

    processing_batch = db.processing_batches.find_one({
        "processing_batch_id": data.processing_batch_id
    })

    if not processing_batch:
        raise HTTPException(
            status_code=404,
            detail="Processing batch not found"
        )

    # Medicine can only be created after successful
    # pre-manufacturing laboratory verification.
    if processing_batch.get("status") != "APPROVED_FOR_MANUFACTURING":
        raise HTTPException(
            status_code=400,
            detail="Processing batch is not approved for manufacturing"
        )

    count = db.medicine_batches.count_documents({}) + 1

    medicine_batch_id = (
        f"MED-{datetime.now().year}-{count:03d}"
    )

    qr_id = (
        f"QR-{datetime.now().year}-{count:03d}"
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
        "created_at": datetime.utcnow()
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
            "batch_status": "RELEASED"
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
def list_medicine_batches():
    batches = list(
        db.medicine_batches.find(
            {},
            {"_id": 0}
        ).sort("created_at", -1)
    )
    return {"batches": batches, "count": len(batches)}


# =========================
# GET MEDICINE BATCH
# =========================

@router.get("/medicine/{medicine_batch_id}")
def get_medicine_batch(medicine_batch_id: str):

    medicine = db.medicine_batches.find_one(
        {
            "medicine_batch_id": medicine_batch_id
        },
        {
            "_id": 0
        }
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

@router.get("/verify/{qr_id}")
def verify_medicine(qr_id: str):

    medicine = db.medicine_batches.find_one({
        "qr_id": qr_id
    })

    if not medicine:
        return {
            "verified": False,
            "message": "Invalid QR"
        }

    processing_batch = db.processing_batches.find_one({
        "processing_batch_id":
            medicine["processing_batch_id"]
    })

    raw_relationships = list(
        db.batch_relationships.find(
            {
                "child_batch_id":
                    medicine["processing_batch_id"]
            },
            {
                "_id": 0,
                "parent_batch_id": 1
            }
        )
    )

    raw_batches = [
        relationship["parent_batch_id"]
        for relationship in raw_relationships
    ]

    plant_id = None

    if raw_batches:
        raw_batch = db.raw_material_batches.find_one({
            "raw_batch_id": raw_batches[0]
        })

        if raw_batch:
            plant_id = raw_batch.get("plant_id")

    return {
        "verified": True,
        "medicine_batch_id":
            medicine["medicine_batch_id"],
        "product_name":
            medicine["product_name"],
        "batch_status":
            medicine["batch_status"],
        "traceability": {
            "processing_batch_id":
                medicine["processing_batch_id"],
            "raw_batches":
                raw_batches,
            "plant_id":
                plant_id
        }
    }