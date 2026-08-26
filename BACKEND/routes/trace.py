from fastapi import APIRouter, HTTPException

from database import db


router = APIRouter(
    prefix="/api/trace",
    tags=["Traceability"]
)


# =========================
# REVERSE TRACE
# Medicine → Processing → Raw → Farm
# =========================

@router.get("/reverse/{medicine_batch_id}")
def reverse_trace(medicine_batch_id: str):

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

    processing_id = medicine.get(
        "processing_batch_id"
    )

    processing = db.processing_batches.find_one(
        {
            "processing_batch_id": processing_id
        },
        {
            "_id": 0
        }
    )

    relationships = list(
        db.batch_relationships.find(
            {
                "child_batch_id": processing_id
            },
            {
                "_id": 0
            }
        )
    )

    raw_batches = []

    for relationship in relationships:

        raw_id = relationship.get(
            "parent_batch_id"
        )

        raw = db.raw_material_batches.find_one(
            {
                "raw_batch_id": raw_id
            },
            {
                "_id": 0
            }
        )

        if raw:

            farm = db.farms.find_one(
                {
                    "farm_id": raw.get("farm_id")
                },
                {
                    "_id": 0
                }
            )

            raw_batches.append(
                {
                    "raw_batch": raw,
                    "farm": farm
                }
            )

    return {
        "medicine_batch": {
            "medicine_batch_id":
                medicine.get("medicine_batch_id"),

            "product_name":
                medicine.get("product_name"),

            "batch_status":
                medicine.get("batch_status")
        },

        "processing_batch": processing,

        "raw_batches": raw_batches
    }


# =========================
# FORWARD TRACE
# Raw → Processing → Medicine
# =========================

@router.get("/forward/{raw_batch_id}")
def forward_trace(raw_batch_id: str):

    # IMPORTANT:
    # Exclude MongoDB ObjectId from response
    raw = db.raw_material_batches.find_one(
        {
            "raw_batch_id": raw_batch_id
        },
        {
            "_id": 0
        }
    )

    if not raw:
        raise HTTPException(
            status_code=404,
            detail="Raw batch not found"
        )

    relationships = list(
        db.batch_relationships.find(
            {
                "parent_batch_id": raw_batch_id
            },
            {
                "_id": 0
            }
        )
    )

    processing_batches = []

    for relationship in relationships:

        processing_id = relationship.get(
            "child_batch_id"
        )

        processing = db.processing_batches.find_one(
            {
                "processing_batch_id":
                    processing_id
            },
            {
                "_id": 0
            }
        )

        if not processing:
            continue

        medicines = list(
            db.medicine_batches.find(
                {
                    "processing_batch_id":
                        processing_id
                },
                {
                    "_id": 0
                }
            )
        )

        processing_batches.append(
            {
                "processing_batch": processing,
                "medicine_batches": medicines
            }
        )

    return {
        "raw_batch": raw,
        "downstream": processing_batches
    }


# =========================
# IMPACT ANALYSIS
# Raw → All affected medicines
# =========================

@router.get("/impact/{raw_batch_id}")
def impact_analysis(raw_batch_id: str):

    raw = db.raw_material_batches.find_one(
        {
            "raw_batch_id": raw_batch_id
        },
        {
            "_id": 0
        }
    )

    if not raw:
        raise HTTPException(
            status_code=404,
            detail="Raw batch not found"
        )

    relationships = list(
        db.batch_relationships.find(
            {
                "parent_batch_id": raw_batch_id
            },
            {
                "_id": 0
            }
        )
    )

    affected_medicines = []

    for relationship in relationships:

        processing_id = relationship.get(
            "child_batch_id"
        )

        medicines = list(
            db.medicine_batches.find(
                {
                    "processing_batch_id":
                        processing_id
                },
                {
                    "_id": 0
                }
            )
        )

        affected_medicines.extend(
            medicines
        )

    return {
        "raw_batch_id": raw_batch_id,

        "affected_medicine_batches":
            affected_medicines,

        "affected_count":
            len(affected_medicines)
    }