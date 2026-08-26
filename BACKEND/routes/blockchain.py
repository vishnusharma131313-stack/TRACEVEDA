import hashlib
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import db


router = APIRouter(
    prefix="/api/blockchain",
    tags=["Blockchain"]
)


# =========================
# REQUEST MODEL
# =========================

class BlockchainEventRequest(BaseModel):
    event_type: str
    entity_type: str
    entity_id: str
    data: dict


# =========================
# CREATE BLOCKCHAIN EVENT
# =========================

@router.post("/events")
def create_blockchain_event(data: BlockchainEventRequest):

    # Get previous blockchain event
    previous = db.blockchain_events.find_one(
        {},
        sort=[("created_at", -1)]
    )

    # Safely handle old events that don't have event_hash
    if previous and previous.get("event_hash"):
        previous_hash = previous["event_hash"]
    else:
        previous_hash = "GENESIS"

    timestamp = datetime.utcnow().isoformat()

    # Deterministic payload
    payload = {
        "event_type": data.event_type,
        "entity_type": data.entity_type,
        "entity_id": data.entity_id,
        "data": data.data,
        "timestamp": timestamp,
        "previous_hash": previous_hash
    }

    payload_string = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":")
    )

    event_hash = hashlib.sha256(
        payload_string.encode("utf-8")
    ).hexdigest()

    count = db.blockchain_events.count_documents({}) + 1

    transaction_id = (
        f"TX-{datetime.now().year}-{count:06d}"
    )

    event = {
        "transaction_id": transaction_id,
        "event_type": data.event_type,
        "entity_type": data.entity_type,
        "entity_id": data.entity_id,
        "event_data": data.data,
        "timestamp": timestamp,
        "previous_hash": previous_hash,
        "event_hash": event_hash,
        "blockchain_status": "PENDING_FABRIC",
        "created_at": datetime.utcnow()
    }

    db.blockchain_events.insert_one(event)

    return {
        "transaction_id": transaction_id,
        "event_hash": event_hash,
        "previous_hash": previous_hash,
        "blockchain_status": "PENDING_FABRIC"
    }


# =========================
# GET EVENT
# =========================

@router.get("/events/{transaction_id}")
def get_blockchain_event(transaction_id: str):

    event = db.blockchain_events.find_one(
        {
            "transaction_id": transaction_id
        },
        {
            "_id": 0
        }
    )

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Blockchain event not found"
        )

    return event


# =========================
# VERIFY EVENT HASH
# =========================

@router.get("/verify/{transaction_id}")
def verify_blockchain_event(transaction_id: str):

    event = db.blockchain_events.find_one({
        "transaction_id": transaction_id
    })

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Blockchain event not found"
        )

    # Old events without hash cannot be verified
    if not event.get("event_hash"):
        return {
            "transaction_id": transaction_id,
            "valid": False,
            "message": "Event was created before hash tracking was enabled"
        }

    payload = {
        "event_type": event["event_type"],
        "entity_type": event["entity_type"],
        "entity_id": event["entity_id"],
        "data": event["event_data"],
        "timestamp": event["timestamp"],
        "previous_hash": event["previous_hash"]
    }

    payload_string = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":")
    )

    calculated_hash = hashlib.sha256(
        payload_string.encode("utf-8")
    ).hexdigest()

    valid = (
        calculated_hash == event["event_hash"]
    )

    return {
        "transaction_id": transaction_id,
        "valid": valid,
        "stored_hash": event["event_hash"],
        "calculated_hash": calculated_hash
    }