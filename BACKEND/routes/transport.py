from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from database import db

router = APIRouter(
    prefix="/api/transport",
    tags=["Transport"]
)


class TransportEventRequest(BaseModel):
    batch_id: str
    transport_id: str
    event_type: str
    location: Optional[str] = None
    event_timestamp: datetime
    status: str


@router.post("/events")
def create_transport_event(data: TransportEventRequest):

    # Check that the batch exists
    batch = (
        db.raw_material_batches.find_one(
            {"raw_batch_id": data.batch_id}
        )
        or db.processing_batches.find_one(
            {"processing_batch_id": data.batch_id}
        )
        or db.medicine_batches.find_one(
            {"medicine_batch_id": data.batch_id}
        )
    )

    if not batch:
        raise HTTPException(
            status_code=404,
            detail="Batch not found"
        )

    count = db.transport_events.count_documents({}) + 1

    event_id = (
        f"TRANSPORT-EVENT-{datetime.now().year}-{count:04d}"
    )

    event = {
        "event_id": event_id,
        "batch_id": data.batch_id,
        "transport_id": data.transport_id,
        "event_type": data.event_type,
        "location": data.location,
        "event_timestamp": data.event_timestamp.isoformat(),
        "status": data.status,
        "created_at": datetime.utcnow()
    }

    db.transport_events.insert_one(event)

    return {
        "event_id": event_id,
        "transport_id": data.transport_id,
        "status": "STORED"
    }


@router.get("/{batch_id}")
def get_transport_events(batch_id: str):

    events = list(
        db.transport_events.find(
            {"batch_id": batch_id},
            {"_id": 0}
        ).sort("event_timestamp", 1)
    )

    return {
        "batch_id": batch_id,
        "events": events
    }