from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services import blockchain_service


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
# Manual / admin anchoring. Batch, lab, medicine and critical IoT events
# anchor themselves - see services/blockchain_service.safe_anchor.
# =========================

@router.post("/events")
def create_blockchain_event(data: BlockchainEventRequest):

    try:

        event = blockchain_service.anchor_event(
            data.event_type,
            data.entity_type,
            data.entity_id,
            data.data
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to anchor event: {error}"
        )

    return {
        "transaction_id": event["transaction_id"],
        "event_hash": event["event_hash"],
        "previous_hash": event["previous_hash"],
        "blockchain_status": event["blockchain_status"]
    }


# =========================
# VERIFY WHOLE CHAIN
# =========================

@router.get("/verify-chain")
def verify_blockchain_chain():

    return blockchain_service.verify_chain()


# =========================
# BLOCKCHAIN TRAIL FOR ONE BATCH
# =========================

@router.get("/batch/{entity_id}")
def get_blockchain_trail(entity_id: str):

    events = blockchain_service.get_events_for_entity(entity_id)

    return {
        "entity_id": entity_id,
        "event_count": len(events),
        "events": events
    }


# =========================
# GET EVENT
# =========================

@router.get("/events/{transaction_id}")
def get_blockchain_event(transaction_id: str):

    event = blockchain_service.get_event(transaction_id)

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

    result = blockchain_service.verify_event(transaction_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Blockchain event not found"
        )

    return result
