"""
Atomic, collision-free human-readable identifiers.

WHY THIS EXISTS
---------------
Every route used to mint its id as:

    count = db.<collection>.count_documents({}) + 1
    new_id = f"RAW-{year}-{count:03d}"

That is wrong in three separate ways, and all three are reachable in a demo:

  1. RACE - two concurrent POSTs both read the same count and mint the same
     id. Two requests one second apart during a live demo is enough.
  2. DELETES - remove one document and the next insert reuses a live id.
  3. SEEDED DATA - `import_csv.py` loads 42 medicine batches numbered
     MED-2026-001..042. count+1 happens to give 043 only while nothing has
     ever been deleted; the scheme has no actual knowledge of what exists.

This module mints ids from the same atomic `$inc` counter the hash chain
already uses (see services/blockchain_service._next_sequence), bootstrapped
from the highest number already present so live ids continue past the seed
data rather than colliding with it.

The counter is the mechanism; the unique index created in `ensure_indexes`
is the guarantee. `mint` re-checks and retries, so even a counter that was
reset by hand cannot produce a duplicate.
"""

import logging
import re
from datetime import datetime, timezone

from pymongo import ReturnDocument

import database


logger = logging.getLogger(__name__)


# Counter documents are namespaced so they can never collide with the
# "blockchain_events" counter owned by blockchain_service.
COUNTER_PREFIX = "id:"

MAX_MINT_ATTEMPTS = 25

# Trailing run of digits, e.g. ASH-2026-001 -> 1, LABTEST-PRE-0007 -> 7.
_TRAILING_NUMBER = re.compile(r"(\d+)\s*$")


class IdSpec:
    """How one collection's identifiers are shaped."""

    def __init__(self, collection, field, prefix, width, dated=True):
        self.collection = collection
        self.field = field
        self.prefix = prefix
        self.width = width
        self.dated = dated

    @property
    def counter_id(self):
        return f"{COUNTER_PREFIX}{self.collection}.{self.field}"

    def format(self, number, year):

        if self.dated:
            return f"{self.prefix}-{year}-{number:0{self.width}d}"

        return f"{self.prefix}-{number:0{self.width}d}"


# Formats preserved exactly as the previous code emitted them, so nothing
# downstream (frontend, docs, seeded ids) has to change.
ID_SPECS = {
    "raw_batch": IdSpec("raw_material_batches", "raw_batch_id", "RAW", 3),
    "processing_batch": IdSpec(
        "processing_batches", "processing_batch_id", "PROCESS", 3
    ),
    "medicine_batch": IdSpec("medicine_batches", "medicine_batch_id", "MED", 3),
    "relationship": IdSpec(
        "batch_relationships", "relationship_id", "REL", 3
    ),
    "lab_test": IdSpec("lab_tests", "lab_test_id", "LABTEST", 3),
    "iot_reading": IdSpec("iot_readings", "reading_id", "READ", 4),
    "iot_alert": IdSpec("iot_alerts", "alert_id", "ALERT", 4),
    "transport_event": IdSpec(
        "transport_events", "event_id", "TRANSPORT-EVENT", 4
    ),
    "storage_event": IdSpec("storage_events", "event_id", "STORAGE-EVENT", 4),
    "consumer_report": IdSpec("consumer_reports", "report_id", "RPT", 3),
    "investigation": IdSpec(
        "investigations", "investigation_id", "INV", 3
    ),
}


def _db():
    # Resolved per call, never bound at import, so tests can swap in mongomock.
    return database.db


def _highest_existing_number(spec):
    """
    Largest trailing number already present in the collection.

    Deliberately ignores the prefix. The seeded dataset numbers raw batches
    ASH-2026-001..070 while the live route mints RAW-2026-xxx; counting only
    RAW-prefixed ids would restart at 1 and produce a confusing parallel
    numbering. Taking the maximum across every id keeps one sequence.
    """

    highest = 0

    cursor = _db()[spec.collection].find(
        {spec.field: {"$exists": True}},
        {"_id": 0, spec.field: 1}
    )

    for document in cursor:

        value = document.get(spec.field)

        if value is None:
            continue

        match = _TRAILING_NUMBER.search(str(value))

        if not match:
            continue

        try:
            number = int(match.group(1))
        except ValueError:
            continue

        if number > highest:
            highest = number

    return highest


def _next_number(spec):
    """
    One number from the atomic counter, bootstrapping it on first use.

    `find_one_and_update` with upsert is a single atomic operation, so
    concurrent callers can never receive the same number.
    """

    counter = _db().counters.find_one_and_update(
        {"_id": spec.counter_id},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )

    number = counter["seq"]

    # First ever use of this counter: it just returned 1, which may sit on
    # top of seeded ids. Jump it past whatever is already stored.
    if number == 1:

        highest = _highest_existing_number(spec)

        if highest >= 1:

            counter = _db().counters.find_one_and_update(
                {"_id": spec.counter_id, "seq": {"$lt": highest + 1}},
                {"$set": {"seq": highest + 1}},
                return_document=ReturnDocument.AFTER
            )

            # A concurrent caller may have advanced it past us already; in
            # that case keep the number we were given rather than reusing one.
            if counter is not None:
                number = counter["seq"]

    return number


def mint(kind, now=None):
    """
    A fresh, unused identifier of the given kind.

    Raises RuntimeError only if the collection is so inconsistent that
    MAX_MINT_ATTEMPTS distinct candidates were all already taken.
    """

    spec = ID_SPECS.get(kind)

    if spec is None:
        raise KeyError(f"Unknown id kind: {kind!r}")

    year = (now or datetime.now(timezone.utc)).year

    for _ in range(MAX_MINT_ATTEMPTS):

        candidate = spec.format(_next_number(spec), year)

        # The counter makes a collision almost impossible; this makes it
        # impossible, including after a hand-edited counters collection.
        if not _db()[spec.collection].find_one(
            {spec.field: candidate}, {"_id": 1}
        ):
            return candidate

        logger.warning(
            "Minted id %s already exists in %s - advancing the counter",
            candidate,
            spec.collection
        )

    raise RuntimeError(
        f"Could not mint a free {kind} id after {MAX_MINT_ATTEMPTS} attempts"
    )


def sync_counters():
    """
    Point every counter past the data currently in the database.

    Run after a bulk import: `import_csv.py` replaces whole collections, so
    counters left over from a previous dataset would otherwise mint ids that
    are already taken.
    """

    synced = {}

    for kind, spec in ID_SPECS.items():

        highest = _highest_existing_number(spec)

        _db().counters.update_one(
            {"_id": spec.counter_id},
            {"$set": {"seq": highest}},
            upsert=True
        )

        synced[kind] = highest

    return synced
