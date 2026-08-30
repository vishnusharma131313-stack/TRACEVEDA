"""
One-time migration of seeded blockchain events onto the canonical schema.

`blockchain_events.csv` ships these columns:

    blockchain_event_id, event_id, batch_id, batch_type, event_type,
    transaction_id, blockchain_timestamp, data_hash, is_synthetic

`import_csv.py` inserts them verbatim, so seeded documents do not match the
schema the live chain reads and writes. They fail verification and break the
"find the previous event" lookup as soon as live events are appended.

This script rewrites each legacy document into the canonical schema, assigns
sequence numbers, rebuilds a real previous_hash chain across them, and moves
the atomic counter to the final sequence so the next live anchor_event
continues the chain instead of restarting at 1.

Safe to re-run: only documents that still carry the legacy `data_hash` field
are touched.

    python migrate_seed_blockchain_events.py
"""

import sys
from datetime import datetime, timezone

from database import db
from services.blockchain_service import (
    ANCHORED,
    COLLECTION,
    COUNTER_ID,
    GENESIS,
    compute_event_hash
)


LEGACY_FILTER = {"data_hash": {"$exists": True}}


def _event_year(timestamp):
    """Year of the seeded event, falling back to today."""

    if isinstance(timestamp, datetime):
        return timestamp.year

    if isinstance(timestamp, str) and len(timestamp) >= 4:

        try:
            return int(timestamp[:4])
        except ValueError:
            pass

    return datetime.now(timezone.utc).year


def _sort_key(document):
    """
    Chronological order, with a deterministic tiebreak.

    The secondary key is required, not defensive: the shipped CSV contains
    seven timestamps that appear on more than one row.
    """

    return (
        str(document.get("blockchain_timestamp") or ""),
        str(document.get("blockchain_event_id") or "")
    )


def migrate():

    legacy_documents = list(
        db[COLLECTION].find(LEGACY_FILTER)
    )

    if not legacy_documents:

        print("Nothing to migrate: no legacy documents found.")
        print(
            "(Legacy documents are the ones that still carry a "
            "'data_hash' field.)"
        )
        return 0

    already_canonical = db[COLLECTION].count_documents(
        {"sequence": {"$exists": True}}
    )

    if already_canonical:

        print("ABORTED: the collection is mixed.")
        print(
            f"Found {len(legacy_documents)} legacy document(s) alongside "
            f"{already_canonical} already-canonical event(s)."
        )
        print()
        print(
            "Re-sequencing the seed data from 1 would collide with events "
            "that are already anchored."
        )
        print(
            "Re-import the seed data first "
            "(python import_csv.py), then run this script again."
        )
        return 1

    legacy_documents.sort(key=_sort_key)

    previous_hash = GENESIS
    sequence = 0
    migrated = 0

    for document in legacy_documents:

        sequence += 1

        entity_id = document.get("batch_id")
        entity_type = document.get("batch_type")
        event_type = document.get("event_type")
        timestamp = document.get("blockchain_timestamp")

        if isinstance(timestamp, datetime):
            timestamp = timestamp.isoformat()
        else:
            timestamp = str(timestamp) if timestamp is not None else ""

        # The seed CSV carries no payload, so event_data preserves the
        # provenance of the row instead. Nothing from the CSV is lost.
        event_data = {
            "blockchain_event_id": document.get("blockchain_event_id"),
            "event_id": document.get("event_id"),
            "is_synthetic": document.get("is_synthetic"),
            "legacy_transaction_id": document.get("transaction_id"),
            "legacy_data_hash": document.get("data_hash"),
            "migrated_from": "blockchain_events.csv"
        }

        event_hash = compute_event_hash(
            event_type,
            entity_type,
            entity_id,
            event_data,
            timestamp,
            previous_hash
        )

        canonical = {
            "transaction_id": (
                f"TX-{_event_year(document.get('blockchain_timestamp'))}"
                f"-{sequence:06d}"
            ),
            "sequence": sequence,
            "event_type": event_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "event_data": event_data,
            "timestamp": timestamp,
            "previous_hash": previous_hash,
            "event_hash": event_hash,
            "blockchain_status": ANCHORED,
            "created_at": datetime.now(timezone.utc)
        }

        # replace_one, not update_one: the legacy fields must disappear
        # rather than sit alongside the canonical ones.
        db[COLLECTION].replace_one(
            {"_id": document["_id"]},
            canonical
        )

        previous_hash = event_hash
        migrated += 1

    # Move the atomic counter so live anchoring continues the chain.
    db.counters.replace_one(
        {"_id": COUNTER_ID},
        {"_id": COUNTER_ID, "seq": sequence},
        upsert=True
    )

    print("=" * 50)
    print("SEED BLOCKCHAIN EVENT MIGRATION COMPLETE")
    print("=" * 50)
    print(f"Documents migrated: {migrated}")
    print(f"Final sequence:     {sequence}")
    print(f"Counter '{COUNTER_ID}' set to {sequence}")
    print()
    print(
        "The next anchored event will be "
        f"sequence {sequence + 1}."
    )
    print("Verify with: GET /api/blockchain/verify-chain")

    return 0


if __name__ == "__main__":
    sys.exit(migrate())
