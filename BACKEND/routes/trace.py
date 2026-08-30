from fastapi import APIRouter, Depends, HTTPException

from database import db
from dependencies import require_authenticated


router = APIRouter(
    prefix="/api/trace",
    tags=["Traceability"]
)


def _parent_ids(processing_batch_id):
    """Raw batch ids feeding one processing batch, de-duplicated."""

    seen = []

    for relationship in db.batch_relationships.find(
        {"child_batch_id": processing_batch_id},
        {"_id": 0, "parent_batch_id": 1}
    ):

        parent_id = relationship.get("parent_batch_id")

        if parent_id and parent_id not in seen:
            seen.append(parent_id)

    return seen


def _child_ids(raw_batch_id):
    """Processing batch ids fed by one raw batch, de-duplicated."""

    seen = []

    for relationship in db.batch_relationships.find(
        {"parent_batch_id": raw_batch_id},
        {"_id": 0, "child_batch_id": 1}
    ):

        child_id = relationship.get("child_batch_id")

        if child_id and child_id not in seen:
            seen.append(child_id)

    return seen


# =========================
# REVERSE TRACE
# Medicine -> Processing -> Raw -> Farm
# =========================

@router.get("/reverse/{medicine_batch_id}")
def reverse_trace(
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

    processing_id = medicine.get("processing_batch_id")

    processing = db.processing_batches.find_one(
        {"processing_batch_id": processing_id},
        {"_id": 0}
    )

    raw_batches = []

    # De-duplicated by parent id. The shipped dataset happens to contain no
    # repeated parent/child pair, so this is not fixing observed data - it
    # keeps the trace correct for any that appear later, alongside the 409
    # guard in routes/batches.create_batch_relationship.
    for raw_id in _parent_ids(processing_id):

        raw = db.raw_material_batches.find_one(
            {"raw_batch_id": raw_id},
            {"_id": 0}
        )

        if not raw:
            continue

        farm = db.farms.find_one(
            {"farm_id": raw.get("farm_id")},
            {"_id": 0}
        )

        raw_batches.append({
            "raw_batch": raw,
            "farm": farm
        })

    return {
        "medicine_batch": {
            "medicine_batch_id": medicine.get("medicine_batch_id"),
            "product_name": medicine.get("product_name"),
            "batch_status": medicine.get("batch_status")
        },
        "processing_batch": processing,
        "raw_batches": raw_batches
    }


# =========================
# FORWARD TRACE
# Raw -> Processing -> Medicine
# =========================

@router.get("/forward/{raw_batch_id}")
def forward_trace(
    raw_batch_id: str,
    user: dict = Depends(require_authenticated),
):

    raw = db.raw_material_batches.find_one(
        {"raw_batch_id": raw_batch_id},
        {"_id": 0}
    )

    if not raw:
        raise HTTPException(
            status_code=404,
            detail="Raw batch not found"
        )

    downstream = []

    for processing_id in _child_ids(raw_batch_id):

        processing = db.processing_batches.find_one(
            {"processing_batch_id": processing_id},
            {"_id": 0}
        )

        if not processing:
            continue

        medicines = list(
            db.medicine_batches.find(
                {"processing_batch_id": processing_id},
                {"_id": 0}
            )
        )

        downstream.append({
            "processing_batch": processing,
            "medicine_batches": medicines
        })

    return {
        "raw_batch": raw,
        "downstream": downstream
    }


# =========================
# IMPACT ANALYSIS
# Raw -> All affected medicines
# =========================

@router.get("/impact/{raw_batch_id}")
def impact_analysis(
    raw_batch_id: str,
    user: dict = Depends(require_authenticated),
):
    """
    Every medicine batch a recall on this raw batch would have to cover.

    `affected_count` is the number of DISTINCT medicine batches. It was
    previously a running total across relationship rows, which would have
    double-counted a raw batch linked to the same processing batch twice.
    The shipped dataset contains no such pair, but this is the one number a
    regulator would act on, so it is counted rather than accumulated.
    """

    raw = db.raw_material_batches.find_one(
        {"raw_batch_id": raw_batch_id},
        {"_id": 0}
    )

    if not raw:
        raise HTTPException(
            status_code=404,
            detail="Raw batch not found"
        )

    affected_medicines = []
    seen_ids = set()

    for processing_id in _child_ids(raw_batch_id):

        for medicine in db.medicine_batches.find(
            {"processing_batch_id": processing_id},
            {"_id": 0}
        ):

            medicine_id = medicine.get("medicine_batch_id")

            if medicine_id in seen_ids:
                continue

            seen_ids.add(medicine_id)
            affected_medicines.append(medicine)

    return {
        "raw_batch_id": raw_batch_id,
        "affected_medicine_batches": affected_medicines,
        "affected_count": len(affected_medicines)
    }
