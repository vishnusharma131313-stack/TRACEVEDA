from fastapi import APIRouter, Depends, HTTPException

from database import db
from dependencies import require_authenticated

router = APIRouter(prefix="/api/trace", tags=["Traceability"])
PROCESSING_TO_MEDICINE = "PROCESSING_TO_MEDICINE"


def _parent_ids(processing_batch_id):
    """Raw batch ids feeding one processing batch, de-duplicated."""
    seen = []
    for relationship in db.batch_relationships.find(
        {"child_batch_id": processing_batch_id},
        {"_id": 0, "parent_batch_id": 1},
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
        {"_id": 0, "child_batch_id": 1},
    ):
        child_id = relationship.get("child_batch_id")
        if child_id and child_id not in seen:
            seen.append(child_id)
    return seen


def _medicine_processing_ids(medicine):
    """Return all processing parents, including legacy single-parent records."""
    medicine_id = medicine.get("medicine_batch_id")
    seen = []
    for relationship in db.batch_relationships.find(
        {"child_batch_id": medicine_id, "relationship_type": PROCESSING_TO_MEDICINE},
        {"_id": 0, "parent_batch_id": 1},
    ):
        parent_id = relationship.get("parent_batch_id")
        if parent_id and parent_id not in seen:
            seen.append(parent_id)
    for parent_id in medicine.get("processing_batch_ids") or []:
        if parent_id and parent_id not in seen:
            seen.append(parent_id)
    legacy_id = medicine.get("processing_batch_id")
    if legacy_id and legacy_id not in seen:
        seen.append(legacy_id)
    return seen


def _medicines_for_processing(processing_batch_id):
    """Find medicine children for both old single-parent and new link records."""
    medicines = list(db.medicine_batches.find(
        {"$or": [
            {"processing_batch_id": processing_batch_id},
            {"processing_batch_ids": processing_batch_id},
        ]},
        {"_id": 0},
    ))
    seen = {item.get("medicine_batch_id") for item in medicines}
    for relationship in db.batch_relationships.find(
        {"parent_batch_id": processing_batch_id, "relationship_type": PROCESSING_TO_MEDICINE},
        {"_id": 0, "child_batch_id": 1},
    ):
        medicine_id = relationship.get("child_batch_id")
        if medicine_id and medicine_id not in seen:
            medicine = db.medicine_batches.find_one(
                {"medicine_batch_id": medicine_id}, {"_id": 0}
            )
            if medicine:
                medicines.append(medicine)
                seen.add(medicine_id)
    return medicines


@router.get("/reverse/{medicine_batch_id}")
def reverse_trace(
    medicine_batch_id: str,
    user: dict = Depends(require_authenticated),
):
    medicine = db.medicine_batches.find_one({"medicine_batch_id": medicine_batch_id}, {"_id": 0})
    if not medicine:
        raise HTTPException(status_code=404, detail="Medicine batch not found")

    processing_batches = []
    raw_batches = []
    seen_raw = set()

    for processing_id in _medicine_processing_ids(medicine):
        processing = db.processing_batches.find_one(
            {"processing_batch_id": processing_id}, {"_id": 0}
        )
        if not processing:
            continue
        processing_batches.append(processing)
        for raw_id in _parent_ids(processing_id):
            if raw_id in seen_raw:
                continue
            raw = db.raw_material_batches.find_one({"raw_batch_id": raw_id}, {"_id": 0})
            if not raw:
                continue
            seen_raw.add(raw_id)
            farm = db.farms.find_one({"farm_id": raw.get("farm_id")}, {"_id": 0})
            raw_batches.append({"raw_batch": raw, "farm": farm})

    return {
        "medicine_batch": {
            "medicine_batch_id": medicine.get("medicine_batch_id"),
            "product_name": medicine.get("product_name"),
            "batch_status": medicine.get("batch_status"),
        },
        # Keep the old singular response field for clients that only know one.
        "processing_batch": processing_batches[0] if len(processing_batches) == 1 else None,
        "processing_batches": processing_batches,
        "raw_batches": raw_batches,
    }


@router.get("/forward/{raw_batch_id}")
def forward_trace(
    raw_batch_id: str,
    user: dict = Depends(require_authenticated),
):
    raw = db.raw_material_batches.find_one({"raw_batch_id": raw_batch_id}, {"_id": 0})
    if not raw:
        raise HTTPException(status_code=404, detail="Raw batch not found")

    downstream = []
    for processing_id in _child_ids(raw_batch_id):
        processing = db.processing_batches.find_one(
            {"processing_batch_id": processing_id}, {"_id": 0}
        )
        if not processing:
            continue
        downstream.append({
            "processing_batch": processing,
            "medicine_batches": _medicines_for_processing(processing_id),
        })

    return {"raw_batch": raw, "downstream": downstream}


@router.get("/impact/{raw_batch_id}")
def impact_analysis(
    raw_batch_id: str,
    user: dict = Depends(require_authenticated),
):
    """Return distinct medicine batches affected by a raw-batch recall."""
    raw = db.raw_material_batches.find_one({"raw_batch_id": raw_batch_id}, {"_id": 0})
    if not raw:
        raise HTTPException(status_code=404, detail="Raw batch not found")

    affected_medicines = []
    seen_ids = set()
    for processing_id in _child_ids(raw_batch_id):
        for medicine in _medicines_for_processing(processing_id):
            medicine_id = medicine.get("medicine_batch_id")
            if medicine_id in seen_ids:
                continue
            seen_ids.add(medicine_id)
            affected_medicines.append(medicine)

    return {
        "raw_batch_id": raw_batch_id,
        "affected_medicine_batches": affected_medicines,
        "affected_count": len(affected_medicines),
    }
