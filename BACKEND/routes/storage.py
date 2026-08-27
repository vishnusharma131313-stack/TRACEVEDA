from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from database import db


router = APIRouter(
    prefix="/api/storage",
    tags=["Storage"]
)


# =========================
# REQUEST MODEL
# =========================
# CHANGED:
# medicine_batch_id -> raw_batch_id
#
# Storage in our prototype happens
# BEFORE manufacturing, so storage
# is associated with the raw-material batch.
# =========================

class StorageEventRequest(BaseModel):
    raw_batch_id: str
    storage_id: str
    event_type: str
    location: Optional[str] = None
    event_timestamp: datetime
    status: str


# =========================
# CREATE STORAGE EVENT
# =========================

@router.post("/events")
def create_storage_event(data: StorageEventRequest):

    # =========================
    # CHANGED:
    # Validate RAW MATERIAL batch
    # instead of medicine batch
    # =========================

    raw_batch = db.raw_material_batches.find_one({
        "raw_batch_id": data.raw_batch_id
    })

    if not raw_batch:
        raise HTTPException(
            status_code=404,
            detail="Raw material batch not found"
        )


    # =========================
    # CREATE EVENT ID
    # =========================

    count = db.storage_events.count_documents({}) + 1

    event_id = (
        f"STORAGE-EVENT-{datetime.now().year}-{count:04d}"
    )


    # =========================
    # STORAGE EVENT
    # =========================
    # CHANGED:
    # medicine_batch_id -> raw_batch_id
    # =========================

    event = {
        "event_id": event_id,
        "raw_batch_id": data.raw_batch_id,
        "storage_id": data.storage_id,
        "event_type": data.event_type,
        "location": data.location,
        "event_timestamp": data.event_timestamp.isoformat(),
        "status": data.status,
        "created_at": datetime.utcnow()
    }


    # =========================
    # SAVE EVENT
    # =========================

    db.storage_events.insert_one(event)


    # =========================
    # RESPONSE
    # =========================

    return {
        "event_id": event_id,
        "raw_batch_id": data.raw_batch_id,
        "storage_id": data.storage_id,
        "status": "STORED"
    }


# =========================
# GET STORAGE EVENTS
# =========================

@router.get("/{raw_batch_id}")
def get_storage_events(raw_batch_id: str):

    # =========================
    # CHANGED:
    # Search using raw_batch_id
    # =========================

    events = list(
        db.storage_events.find(
            {
                "raw_batch_id": raw_batch_id
            },
            {
                "_id": 0
            }
        ).sort(
            "event_timestamp",
            1
        )
    )


    return {
        "raw_batch_id": raw_batch_id,
        "events": events
    }