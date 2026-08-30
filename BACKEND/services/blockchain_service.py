"""
Blockchain anchoring service.

Single source of truth for writing to and verifying the TraceVeda hash chain.

This is a SHA-256 hash chain standing in for a permissioned ledger
(Hyperledger Fabric). That substitution is deliberate and documented in the
project research dossier - only dispute-relevant, state-changing events are
anchored here. High-frequency telemetry stays in MongoDB only.

ORDERING CONTRACT
-----------------
The chain is ordered by the integer `sequence` field and NOTHING else.

`created_at` / `timestamp` are informational. MongoDB datetimes only carry
millisecond precision, so two events written in the same millisecond have no
defined tiebreak - ordering by time forks the chain. `sequence` comes from an
atomic `$inc` on a counter document, so it is strictly increasing and
race-free.
"""

import hashlib
import json
import logging
import threading
import time
from datetime import date, datetime, timezone

from pymongo import ReturnDocument

import database


logger = logging.getLogger(__name__)


# =========================
# CONSTANTS
# =========================

COLLECTION = "blockchain_events"
COUNTER_ID = "blockchain_events"

GENESIS = "GENESIS"
ANCHORED = "ANCHORED"

# How long a writer waits for the holder of sequence-1 to insert its event.
# Only ever reached when a second process (e.g. another uvicorn worker) holds
# the preceding sequence number - in-process writers are serialised by the
# lock below and never wait.
PREDECESSOR_WAIT_SECONDS = 5.0
PREDECESSOR_POLL_SECONDS = 0.01


# Serialises "take a sequence -> read the predecessor -> insert" so the chain
# cannot fork within this process. See the module docstring.
_ANCHOR_LOCK = threading.Lock()


class ChainIntegrityError(RuntimeError):
    """Raised when an event cannot be linked to its predecessor."""


# =========================
# INTERNAL HELPERS
# =========================

def _db():
    # Resolved on every call, not bound at import time, so tests can swap
    # `database.db` for a mongomock database.
    return database.db


def _normalize(value):
    """
    Convert a payload into plain JSON-safe types.

    This is required, not cosmetic: pymongo cannot store a bare
    `datetime.date` (and several request models use one). Normalising once,
    before both hashing and storing, guarantees the stored payload rehashes
    to the same digest after a MongoDB round-trip.
    """

    if isinstance(value, dict):
        return {
            str(key): _normalize(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]

    # datetime is a subclass of date, so it must be checked first.
    if isinstance(value, (datetime, date)):
        return value.isoformat()

    return value


def compute_event_hash(
    event_type,
    entity_type,
    entity_id,
    data,
    timestamp,
    previous_hash
):
    """
    SHA-256 over the canonical payload.

    Exported so the seed-data migration hashes identically to the live path -
    there is exactly one hashing implementation in the codebase.
    """

    payload = {
        "event_type": event_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "data": data,
        "timestamp": timestamp,
        "previous_hash": previous_hash
    }

    payload_string = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str
    )

    return hashlib.sha256(
        payload_string.encode("utf-8")
    ).hexdigest()


def _next_sequence():
    """Atomic, strictly increasing counter. Never count_documents() + 1."""

    counter = _db().counters.find_one_and_update(
        {"_id": COUNTER_ID},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )

    return counter["seq"]


def _previous_hash_for(sequence):
    """
    Hash of the event holding `sequence - 1`.

    The atomic counter guarantees exactly one writer per sequence number, so
    waiting for the predecessor always terminates.
    """

    if sequence <= 1:
        return GENESIS

    deadline = time.monotonic() + PREDECESSOR_WAIT_SECONDS

    while True:

        previous = _db()[COLLECTION].find_one(
            {"sequence": sequence - 1},
            {"_id": 0, "event_hash": 1}
        )

        if previous and previous.get("event_hash"):
            return previous["event_hash"]

        # Stale counter against a wiped collection: there is genuinely
        # nothing to chain to, so start a fresh chain rather than spinning
        # until the deadline.
        if _db()[COLLECTION].count_documents({}) == 0:
            return GENESIS

        if time.monotonic() >= deadline:
            raise ChainIntegrityError(
                f"Event with sequence {sequence - 1} never appeared; "
                f"cannot link sequence {sequence} to the chain"
            )

        time.sleep(PREDECESSOR_POLL_SECONDS)


# =========================
# ANCHOR
# =========================

def anchor_event(event_type, entity_type, entity_id, data):
    """
    Write one event to the chain and return the stored document.

    Raises on failure. Routes should call `safe_anchor` instead.
    """

    event_data = _normalize(data or {})

    with _ANCHOR_LOCK:

        sequence = _next_sequence()
        previous_hash = _previous_hash_for(sequence)

        now = datetime.now(timezone.utc)
        timestamp = now.isoformat()

        event_hash = compute_event_hash(
            event_type,
            entity_type,
            entity_id,
            event_data,
            timestamp,
            previous_hash
        )

        document = {
            "transaction_id": f"TX-{now.year}-{sequence:06d}",
            "sequence": sequence,
            "event_type": event_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "event_data": event_data,
            "timestamp": timestamp,
            "previous_hash": previous_hash,
            "event_hash": event_hash,
            "blockchain_status": ANCHORED,
            "created_at": now
        }

        _db()[COLLECTION].insert_one(document)

    document.pop("_id", None)

    return document


def safe_anchor(event_type, entity_type, entity_id, data):
    """
    Anchor an event without ever failing the caller's request.

    The supply-chain record has already been written by the time a route
    calls this, so a ledger outage must not turn a successful write into a
    500. Returns the transaction id, or None if anchoring failed.
    """

    try:

        event = anchor_event(
            event_type,
            entity_type,
            entity_id,
            data
        )

        return event["transaction_id"]

    except Exception:

        logger.exception(
            "Failed to anchor %s for %s (%s)",
            event_type,
            entity_id,
            entity_type
        )

        return None


# =========================
# READ
# =========================

def get_event(transaction_id):
    """One anchored event, or None."""

    return _db()[COLLECTION].find_one(
        {"transaction_id": transaction_id},
        {"_id": 0}
    )


def get_events_for_entity(entity_id):
    """
    Full anchored history for one batch / medicine id, in chain order.

    Backs both the "blockchain trail for this batch" view and the
    reverse-trace flow.
    """

    return list(
        _db()[COLLECTION].find(
            {"entity_id": entity_id},
            {"_id": 0}
        ).sort("sequence", 1)
    )


# =========================
# VERIFY
# =========================

def verify_event(transaction_id):
    """Recompute a single event's hash."""

    event = get_event(transaction_id)

    if not event:
        return None

    if not event.get("event_hash"):
        return {
            "transaction_id": transaction_id,
            "valid": False,
            "message": (
                "Event has no event_hash - legacy seed document. "
                "Run migrate_seed_blockchain_events.py"
            )
        }

    calculated_hash = compute_event_hash(
        event.get("event_type"),
        event.get("entity_type"),
        event.get("entity_id"),
        event.get("event_data"),
        event.get("timestamp"),
        event.get("previous_hash")
    )

    return {
        "transaction_id": transaction_id,
        "valid": calculated_hash == event["event_hash"],
        "stored_hash": event["event_hash"],
        "calculated_hash": calculated_hash
    }


def _broken(checked, transaction_id, reason):
    return {
        "valid": False,
        "checked": checked,
        "broken_at": transaction_id,
        "reason": reason
    }


def verify_chain():
    """
    Walk every event in `sequence` order and prove the whole chain.

    Catches what single-event verification cannot:
      - a tampered payload      -> the event's own hash stops recomputing
      - a deleted event         -> a gap in the sequence
      - a re-hashed forgery     -> the next event's previous_hash stops matching
      - unmigrated seed data    -> no integer `sequence` field

    Returns {"valid", "checked", "broken_at", "reason"}.
    """

    events = _db()[COLLECTION].find({}, {"_id": 0}).sort("sequence", 1)

    checked = 0
    expected_previous_hash = GENESIS
    previous_sequence = 0

    for event in events:

        transaction_id = event.get("transaction_id")

        sequence = event.get("sequence")

        # bool is a subclass of int, so exclude it explicitly.
        if not isinstance(sequence, int) or isinstance(sequence, bool):
            return _broken(
                checked,
                transaction_id,
                "Event has no integer 'sequence' field - legacy seed "
                "document. Run migrate_seed_blockchain_events.py"
            )

        if sequence != previous_sequence + 1:
            return _broken(
                checked,
                transaction_id,
                f"Sequence gap: expected {previous_sequence + 1}, "
                f"found {sequence} (an event was deleted or never inserted)"
            )

        calculated_hash = compute_event_hash(
            event.get("event_type"),
            event.get("entity_type"),
            event.get("entity_id"),
            event.get("event_data"),
            event.get("timestamp"),
            event.get("previous_hash")
        )

        if calculated_hash != event.get("event_hash"):
            return _broken(
                checked,
                transaction_id,
                "Event hash does not match its contents - "
                "the event was modified after anchoring"
            )

        if event.get("previous_hash") != expected_previous_hash:
            return _broken(
                checked,
                transaction_id,
                f"Broken link: previous_hash is "
                f"{event.get('previous_hash')!r} but the preceding event "
                f"hashes to {expected_previous_hash!r}"
            )

        expected_previous_hash = event["event_hash"]
        previous_sequence = sequence
        checked += 1

    return {
        "valid": True,
        "checked": checked,
        "broken_at": None,
        "reason": None
    }
