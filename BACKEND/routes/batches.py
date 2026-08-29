from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import date, datetime

from database import db
from services import blockchain_service

router = APIRouter(prefix="/api/batches", tags=["Batches"])


# =========================
# REQUEST MODELS
# =========================

class RawBatchRequest(BaseModel):
    farm_id: str
    plant_id: str
    collection_date: date
    quantity: float
    unit: str


class ProcessingBatchRequest(BaseModel):
    processor_id: str
    processing_date: date
    output_quantity: float
    unit: str
    processing_type: str


class BatchRelationshipRequest(BaseModel):
    parent_batch_id: str
    child_batch_id: str
    relationship_type: str
    quantity_contributed: float
    unit: str


# =========================
# RAW MATERIAL BATCH
# =========================

@router.post("/raw")
def create_raw_batch(data: RawBatchRequest):

    farm = db.farms.find_one({
        "farm_id": data.farm_id
    })

    if not farm:
        raise HTTPException(
            status_code=404,
            detail="Farm not found"
        )

    plant = db.plants.find_one({
        "plant_id": data.plant_id
    })

    if not plant:
        raise HTTPException(
            status_code=404,
            detail="Plant not found"
        )

    count = db.raw_material_batches.count_documents({}) + 1

    raw_batch_id = f"RAW-{datetime.now().year}-{count:03d}"

    batch = {
        "raw_batch_id": raw_batch_id,
        "plant_id": data.plant_id,
        "farm_id": data.farm_id,
        "collection_date": data.collection_date.isoformat(),
        "quantity": data.quantity,
        "unit": data.unit,
        "batch_status": "CREATED",
        "created_at": datetime.utcnow()
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
            "batch_status": "CREATED"
        }
    )

    return {
        "raw_batch_id": raw_batch_id,
        "status": "CREATED",
        "blockchain_tx": blockchain_tx
    }


# =========================
# GET RAW BATCH
# =========================

@router.get("/raw/{raw_batch_id}")
def get_raw_batch(raw_batch_id: str):

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

@router.post("/processing")
def create_processing_batch(data: ProcessingBatchRequest):

    count = db.processing_batches.count_documents({}) + 1

    processing_batch_id = (
        f"PROCESS-{datetime.now().year}-{count:03d}"
    )

    batch = {
        "processing_batch_id": processing_batch_id,
        "processor_id": data.processor_id,
        "processing_date": data.processing_date.isoformat(),
        "output_quantity": data.output_quantity,
        "unit": data.unit,
        "processing_type": data.processing_type,
        "status": "CREATED",
        "created_at": datetime.utcnow()
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
            "batch_status": "CREATED"
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
def get_processing_batch(processing_batch_id: str):

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

@router.post("/relationships")
def create_batch_relationship(
    data: BatchRelationshipRequest
):

    parent = db.raw_material_batches.find_one({
        "raw_batch_id": data.parent_batch_id
    })

    if not parent:
        raise HTTPException(
            status_code=404,
            detail="Parent batch not found"
        )

    child = db.processing_batches.find_one({
        "processing_batch_id": data.child_batch_id
    })

    if not child:
        raise HTTPException(
            status_code=404,
            detail="Child batch not found"
        )

    count = db.batch_relationships.count_documents({}) + 1

    relationship_id = (
        f"REL-{datetime.now().year}-{count:03d}"
    )

    relationship = {
        "relationship_id": relationship_id,
        "parent_batch_id": data.parent_batch_id,
        "child_batch_id": data.child_batch_id,
        "relationship_type": data.relationship_type,
        "quantity_contributed": data.quantity_contributed,
        "unit": data.unit,
        "timestamp": datetime.utcnow()
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
            "unit": data.unit
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
def get_batch_relationships(batch_id: str):

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