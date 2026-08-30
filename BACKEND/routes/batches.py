from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from database import db
from dependencies import require_authenticated, require_roles
from services import blockchain_service, ids
from services.accounts import FARMER, PROCESSOR

router = APIRouter(prefix="/api/batches", tags=["Batches"])


# =========================
# REQUEST MODELS
# =========================

class RawBatchRequest(BaseModel):
    farm_id: str = Field(min_length=1, max_length=64)
    plant_id: str = Field(min_length=1, max_length=64)
    collection_date: date
    quantity: float = Field(gt=0, description="Harvested quantity, must be positive")
    unit: str = Field(min_length=1, max_length=16)


class ProcessingBatchRequest(BaseModel):
    processor_id: str = Field(min_length=1, max_length=64)
    processing_date: date
    output_quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=16)
    processing_type: str = Field(min_length=1, max_length=64)


class BatchRelationshipRequest(BaseModel):
    parent_batch_id: str = Field(min_length=1, max_length=64)
    child_batch_id: str = Field(min_length=1, max_length=64)
    relationship_type: str = Field(min_length=1, max_length=64)
    quantity_contributed: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=16)

    @field_validator("parent_batch_id", "child_batch_id")
    @classmethod
    def _strip(cls, value):
        return value.strip()


# =========================
# RAW MATERIAL BATCH
# =========================

@router.post("/raw", status_code=201)
def create_raw_batch(
    data: RawBatchRequest,
    user: dict = Depends(require_roles(FARMER)),
):

    farm = db.farms.find_one({"farm_id": data.farm_id}, {"_id": 1})

    if not farm:
        raise HTTPException(
            status_code=404,
            detail="Farm not found"
        )

    plant = db.plants.find_one({"plant_id": data.plant_id}, {"_id": 1})

    if not plant:
        raise HTTPException(
            status_code=404,
            detail="Plant not found"
        )

    # Atomic and collision-free; see services/ids for why count+1 was not.
    raw_batch_id = ids.mint("raw_batch")

    batch = {
        "raw_batch_id": raw_batch_id,
        "plant_id": data.plant_id,
        "farm_id": data.farm_id,
        "collection_date": data.collection_date.isoformat(),
        "quantity": data.quantity,
        "unit": data.unit,
        "batch_status": "CREATED",
        "created_by": user["username"],
        "created_at": datetime.now(timezone.utc)
    }

    db.raw_material_batches.insert_one(batch)

    blockchain_tx = blockchain_service.safe_anchor(
        "BATCH_CREATED",
        "RAW",
        raw_batch_id,
        {
            "farm_id": data.farm_id,
            "plant_id": data.plant_id,
            "collection_date": data.collection_date,
            "quantity": data.quantity,
            "unit": data.unit,
            "batch_status": "CREATED",
            "recorded_by": user["username"]
        }
    )

    return {
        "raw_batch_id": raw_batch_id,
        "status": "CREATED",
        "blockchain_tx": blockchain_tx
    }


# =========================
# LIST ALL RAW BATCHES
# =========================

@router.get("/raw")
def list_raw_batches(
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(require_authenticated),
):

    batches = list(
        db.raw_material_batches.find({}, {"_id": 0})
        .sort("created_at", -1)
        .skip(offset)
        .limit(limit)
    )

    return {
        "batches": batches,
        "count": len(batches),
        "total": db.raw_material_batches.count_documents({})
    }


# =========================
# LIST ALL PROCESSING BATCHES
# =========================

@router.get("/processing")
def list_processing_batches(
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(require_authenticated),
):

    batches = list(
        db.processing_batches.find({}, {"_id": 0})
        .sort("created_at", -1)
        .skip(offset)
        .limit(limit)
    )

    return {
        "batches": batches,
        "count": len(batches),
        "total": db.processing_batches.count_documents({})
    }


# =========================
# GET RAW BATCH
# =========================

@router.get("/raw/{raw_batch_id}")
def get_raw_batch(
    raw_batch_id: str,
    user: dict = Depends(require_authenticated),
):

    batch = db.raw_material_batches.find_one(
        {"raw_batch_id": raw_batch_id},
        {"_id": 0}
    )

    if not batch:
        raise HTTPException(
            status_code=404,
            detail="Raw batch not found"
        )

    return batch


# =========================
# PROCESSING BATCH
# =========================

@router.post("/processing", status_code=201)
def create_processing_batch(
    data: ProcessingBatchRequest,
    user: dict = Depends(require_roles(PROCESSOR)),
):

    processing_batch_id = ids.mint("processing_batch")

    batch = {
        "processing_batch_id": processing_batch_id,
        "processor_id": data.processor_id,
        "processing_date": data.processing_date.isoformat(),
        "output_quantity": data.output_quantity,
        "unit": data.unit,
        "processing_type": data.processing_type,
        "status": "CREATED",
        "created_by": user["username"],
        "created_at": datetime.now(timezone.utc)
    }

    db.processing_batches.insert_one(batch)

    blockchain_tx = blockchain_service.safe_anchor(
        "BATCH_CREATED",
        "PROCESSING",
        processing_batch_id,
        {
            "processor_id": data.processor_id,
            "processing_date": data.processing_date,
            "output_quantity": data.output_quantity,
            "unit": data.unit,
            "processing_type": data.processing_type,
            "batch_status": "CREATED",
            "recorded_by": user["username"]
        }
    )

    return {
        "processing_batch_id": processing_batch_id,
        "status": "CREATED",
        "blockchain_tx": blockchain_tx
    }


# =========================
# GET PROCESSING BATCH
# =========================

@router.get("/processing/{processing_batch_id}")
def get_processing_batch(
    processing_batch_id: str,
    user: dict = Depends(require_authenticated),
):

    batch = db.processing_batches.find_one(
        {"processing_batch_id": processing_batch_id},
        {"_id": 0}
    )

    if not batch:
        raise HTTPException(
            status_code=404,
            detail="Processing batch not found"
        )

    return batch


# =========================
# BATCH RELATIONSHIP
# =========================

@router.post("/relationships", status_code=201)
def create_batch_relationship(
    data: BatchRelationshipRequest,
    user: dict = Depends(require_roles(PROCESSOR)),
):

    parent = db.raw_material_batches.find_one(
        {"raw_batch_id": data.parent_batch_id},
        {"_id": 0, "quantity": 1, "unit": 1}
    )

    if not parent:
        raise HTTPException(
            status_code=404,
            detail="Parent batch not found"
        )

    child = db.processing_batches.find_one(
        {"processing_batch_id": data.child_batch_id},
        {"_id": 1}
    )

    if not child:
        raise HTTPException(
            status_code=404,
            detail="Child batch not found"
        )

    if db.batch_relationships.find_one(
        {
            "parent_batch_id": data.parent_batch_id,
            "child_batch_id": data.child_batch_id
        },
        {"_id": 1}
    ):
        raise HTTPException(
            status_code=409,
            detail="This parent/child link already exists"
        )

    # A raw batch cannot contribute more mass than it holds. Without this,
    # the forward-trace and recall-impact quantities are arithmetic on
    # nothing. Skipped when the parent carries no numeric quantity, which is
    # true of some seeded rows.
    available = parent.get("quantity")

    if isinstance(available, (int, float)) and not isinstance(available, bool):

        already_contributed = sum(
            relationship.get("quantity_contributed") or 0
            for relationship in db.batch_relationships.find(
                {"parent_batch_id": data.parent_batch_id},
                {"_id": 0, "quantity_contributed": 1}
            )
        )

        remaining = available - already_contributed

        # Tolerance absorbs float representation error on values that are
        # exactly equal, e.g. 100.0 contributed out of 100.0 available.
        if data.quantity_contributed > remaining + 1e-9:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Parent batch {data.parent_batch_id} has "
                    f"{remaining:g} {parent.get('unit') or ''} remaining; "
                    f"cannot contribute {data.quantity_contributed:g}"
                )
            )

    relationship_id = ids.mint("relationship")

    relationship = {
        "relationship_id": relationship_id,
        "parent_batch_id": data.parent_batch_id,
        "child_batch_id": data.child_batch_id,
        "relationship_type": data.relationship_type,
        "quantity_contributed": data.quantity_contributed,
        "unit": data.unit,
        "created_by": user["username"],
        "timestamp": datetime.now(timezone.utc)
    }

    db.batch_relationships.insert_one(relationship)

    # Manufacturing linkage: the raw -> processing edge the data model is
    # built around. Anchored deliberately, not opportunistically.
    blockchain_tx = blockchain_service.safe_anchor(
        "BATCH_LINKED",
        "PROCESSING",
        data.child_batch_id,
        {
            "relationship_id": relationship_id,
            "parent_batch_id": data.parent_batch_id,
            "child_batch_id": data.child_batch_id,
            "relationship_type": data.relationship_type,
            "quantity_contributed": data.quantity_contributed,
            "unit": data.unit,
            "recorded_by": user["username"]
        }
    )

    return {
        "relationship_id": relationship_id,
        "status": "CREATED",
        "blockchain_tx": blockchain_tx
    }


# =========================
# GET BATCH RELATIONSHIPS
# =========================

@router.get("/{batch_id}/relationships")
def get_batch_relationships(
    batch_id: str,
    user: dict = Depends(require_authenticated),
):

    relationships = list(
        db.batch_relationships.find(
            {
                "$or": [
                    {"parent_batch_id": batch_id},
                    {"child_batch_id": batch_id}
                ]
            },
            {"_id": 0}
        )
    )

    return {
        "batch_id": batch_id,
        "relationships": relationships
    }
