from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from database import db
from dependencies import require_authenticated, require_roles
from services import ids
from services.accounts import LOGISTICS
from services.timeutils import sort_key as _timestamp_key, to_utc_iso

router = APIRouter(
    prefix="/api/transport",
    tags=["Transport"]
)


# Timestamp fields, in preference order. The live route writes
# `event_timestamp`; the seeded transport_events.csv ships `departure_time`
# and `arrival_time` and no event_timestamp at all. Sorting on a single field
# put every seeded row in an arbitrary order, because the field was absent.
TIMESTAMP_FIELDS = ("event_timestamp", "departure_time", "arrival_time")


def _sort_key(event):
    """Best available instant for one event, as a comparable string."""

    for field in TIMESTAMP_FIELDS:

        value = event.get(field)

        if value is None:
            continue

        return _timestamp_key(value)

    return ""


class TransportEventRequest(BaseModel):
    batch_id: str = Field(min_length=1, max_length=64)
    transport_id: str = Field(min_length=1, max_length=64)
    event_type: str = Field(min_length=1, max_length=64)
    location: Optional[str] = Field(default=None, max_length=200)
    event_timestamp: datetime
    status: str = Field(min_length=1, max_length=32)


@router.post("/events", status_code=201)
def create_transport_event(
    data: TransportEventRequest,
    user: dict = Depends(require_roles(LOGISTICS)),
):

    # Check that the batch exists in any of the three stages.
    exists = (
        db.raw_material_batches.find_one(
            {"raw_batch_id": data.batch_id}, {"_id": 1}
        )
        or db.processing_batches.find_one(
            {"processing_batch_id": data.batch_id}, {"_id": 1}
        )
        or db.medicine_batches.find_one(
            {"medicine_batch_id": data.batch_id}, {"_id": 1}
        )
    )

    if not exists:
        raise HTTPException(
            status_code=404,
            detail="Batch not found"
        )

    event_id = ids.mint("transport_event")

    event = {
        "event_id": event_id,
        "batch_id": data.batch_id,
        "transport_id": data.transport_id,
        "event_type": data.event_type,
        "location": data.location,
        "event_timestamp": to_utc_iso(data.event_timestamp),
        "status": data.status,
        "recorded_by": user["username"],
        "created_at": datetime.now(timezone.utc)
    }

    db.transport_events.insert_one(event)

    # Transport milestones are operational telemetry and are deliberately not
    # anchored - see services/blockchain_service for the on/off-chain split.
    return {
        "event_id": event_id,
        "transport_id": data.transport_id,
        "status": "STORED"
    }


@router.get("/{batch_id}")
def get_transport_events(
    batch_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    user: dict = Depends(require_authenticated),
):

    events = list(
        db.transport_events.find(
            {"batch_id": batch_id},
            {"_id": 0}
        ).limit(limit)
    )

    # Sorted in Python rather than by MongoDB: the two document shapes carry
    # their instant under different field names, so no single sort key works.
    events.sort(key=_sort_key)

    return {
        "batch_id": batch_id,
        "events": events,
        "count": len(events)
    }
