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
    prefix="/api/storage",
    tags=["Storage"]
)


# =========================
# REQUEST MODEL
# =========================
# Storage in this prototype happens BEFORE manufacturing, so a storage event
# written by this route is associated with the RAW MATERIAL batch.
#
# The seeded storage_events.csv predates that decision and keys its rows on
# `medicine_batch_id` instead. Both are read back - see get_storage_events.
# =========================

class StorageEventRequest(BaseModel):
    raw_batch_id: str = Field(min_length=1, max_length=64)
    storage_id: str = Field(min_length=1, max_length=64)
    event_type: str = Field(min_length=1, max_length=64)
    location: Optional[str] = Field(default=None, max_length=200)
    event_timestamp: datetime
    status: str = Field(min_length=1, max_length=32)


TIMESTAMP_FIELDS = ("event_timestamp", "timestamp")


def _sort_key(event):
    """The live route writes `event_timestamp`; the seeded rows write `timestamp`."""

    for field in TIMESTAMP_FIELDS:

        value = event.get(field)

        if value is None:
            continue

        return _timestamp_key(value)

    return ""


# =========================
# CREATE STORAGE EVENT
# =========================

@router.post("/events", status_code=201)
def create_storage_event(
    data: StorageEventRequest,
    user: dict = Depends(require_roles(LOGISTICS)),
):

    raw_batch = db.raw_material_batches.find_one(
        {"raw_batch_id": data.raw_batch_id},
        {"_id": 1}
    )

    if not raw_batch:
        raise HTTPException(
            status_code=404,
            detail="Raw material batch not found"
        )

    event_id = ids.mint("storage_event")

    event = {
        "event_id": event_id,
        "raw_batch_id": data.raw_batch_id,
        "storage_id": data.storage_id,
        "event_type": data.event_type,
        "location": data.location,
        "event_timestamp": to_utc_iso(data.event_timestamp),
        "status": data.status,
        "recorded_by": user["username"],
        "created_at": datetime.now(timezone.utc)
    }

    db.storage_events.insert_one(event)

    return {
        "event_id": event_id,
        "raw_batch_id": data.raw_batch_id,
        "storage_id": data.storage_id,
        "status": "STORED"
    }


# =========================
# GET STORAGE EVENTS
# =========================

@router.get("/{batch_id}")
def get_storage_events(
    batch_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    user: dict = Depends(require_authenticated),
):
    """
    Storage events for one batch id.

    Matches BOTH keys. Documents this route writes are keyed on
    `raw_batch_id`; the 42 rows loaded from storage_events.csv are keyed on
    `medicine_batch_id`. Querying only the first returned an empty list for
    every seeded batch, so the storage timeline looked permanently empty
    during a demo on seed data.
    """

    events = list(
        db.storage_events.find(
            {
                "$or": [
                    {"raw_batch_id": batch_id},
                    {"medicine_batch_id": batch_id}
                ]
            },
            {"_id": 0}
        ).limit(limit)
    )

    events.sort(key=_sort_key)

    return {
        # Kept for backwards compatibility with the documented response.
        "raw_batch_id": batch_id,
        "batch_id": batch_id,
        "events": events,
        "count": len(events)
    }
