from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from database import db
from dependencies import require_authenticated, require_roles
from services import blockchain_service
from services.accounts import REGULATOR


router = APIRouter(
    prefix="/api/blockchain",
    tags=["Blockchain"]
)


# =========================
# REQUEST MODEL
# =========================

class BlockchainEventRequest(BaseModel):
    event_type: str = Field(min_length=1, max_length=64)
    entity_type: str = Field(min_length=1, max_length=32)
    entity_id: str = Field(min_length=1, max_length=64)
    data: dict = Field(default_factory=dict)


# =========================
# CREATE BLOCKCHAIN EVENT
# =========================
# Manual / admin anchoring. Batch, lab, medicine and critical IoT events
# anchor themselves - see services/blockchain_service.safe_anchor.
#
# Restricted to regulators and administrators. Hash-chain integrity proves
# that nobody edited history; it says nothing about who was entitled to
# append to it, so appending has to be an authorised act in its own right.
# =========================

@router.post("/events", status_code=201)
def create_blockchain_event(
    data: BlockchainEventRequest,
    user: dict = Depends(require_roles(REGULATOR)),
):

    payload = dict(data.data)
    payload["recorded_by"] = user["username"]

    try:

        event = blockchain_service.anchor_event(
            data.event_type,
            data.entity_type,
            data.entity_id,
            payload
        )

    except blockchain_service.ChainIntegrityError as error:

        raise HTTPException(
            status_code=409,
            detail=f"Chain is inconsistent, refusing to append: {error}"
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
def verify_blockchain_chain(user: dict = Depends(require_authenticated)):

    return blockchain_service.verify_chain()


# =========================
# LIST ALL BLOCKCHAIN EVENTS
# =========================

@router.get("/events")
def list_blockchain_events(
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(require_authenticated),
):

    events = list(
        db.blockchain_events.find({}, {"_id": 0})
        .sort("sequence", -1)
        .skip(offset)
        .limit(limit)
    )

    return {
        "events": events,
        "count": len(events),
        "total": db.blockchain_events.count_documents({})
    }


# =========================
# BLOCKCHAIN TRAIL FOR ONE BATCH
# =========================

@router.get("/batch/{entity_id}")
def get_blockchain_trail(
    entity_id: str,
    user: dict = Depends(require_authenticated),
):

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
def get_blockchain_event(
    transaction_id: str,
    user: dict = Depends(require_authenticated),
):

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
def verify_blockchain_event(
    transaction_id: str,
    user: dict = Depends(require_authenticated),
):

    result = blockchain_service.verify_event(transaction_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Blockchain event not found"
        )

    return result
