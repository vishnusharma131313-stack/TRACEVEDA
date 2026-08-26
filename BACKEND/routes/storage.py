from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from database import db

router = APIRouter(
    prefix="/api/storage",
    tags=["Storage"]
)


class StorageEventRequest(BaseModel):
    medicine_batch_id: str
    storage_id: str
    event_type: str
    location: Optional[str] = None
    event_timestamp: datetime
    status: str


@router.post("/events")
def create_storage_event(data: StorageEventRequest):

    medicine = db.medicine_batches.find_one({
        "medicine_batch_id": data.medicine_batch_id
    })

    if not medicine:
        raise HTTPException(
            status_code=404,
            detail="Medicine batch not found"
        )

    count = db.storage_events.count_documents({}) + 1

    event_id = (
        f"STORAGE-EVENT-{datetime.now().year}-{count:04d}"
    )

    event = {
        "event_id": event_id,
        "medicine_batch_id": data.medicine_batch_id,
        "storage_id": data.storage_id,
        "event_type": data.event_type,
        "location": data.location,
        "event_timestamp": data.event_timestamp.isoformat(),
        "status": data.status,
        "created_at": datetime.utcnow()
    }

    db.storage_events.insert_one(event)

    return {
        "event_id": event_id,
        "storage_id": data.storage_id,
        "status": "STORED"
    }


@router.get("/{medicine_batch_id}")
def get_storage_events(medicine_batch_id: str):

    events = list(
        db.storage_events.find(
            {"medicine_batch_id": medicine_batch_id},
            {"_id": 0}
        ).sort("event_timestamp", 1)
    )

    return {
        "medicine_batch_id": medicine_batch_id,
        "events": events
    }