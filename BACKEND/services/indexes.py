"""
Index definitions, applied at startup and after a bulk import.

Two jobs:

  1. SPEED. `iot_readings` holds 11k+ seeded documents and every request for
     one batch's telemetry scanned all of them. Every lookup this API makes
     is by a business id, and none of those fields were indexed.

  2. CORRECTNESS. The unique indexes are the hard guarantee behind
     services/ids.mint - a duplicate business id becomes impossible at the
     storage layer rather than merely unlikely in application code.

Creating an index is idempotent, so this is safe to run on every boot.
Failures are logged and never raised: a pre-existing index with different
options, or a mongomock database in the test suite, must not stop the API
from starting.
"""

import logging


logger = logging.getLogger(__name__)


# (collection, keys, unique)
# keys is a list of (field, direction) pairs; 1 ascending, -1 descending.
INDEXES = [
    # ---- accounts ----
    ("users", [("username", 1)], True),

    # ---- supply chain ----
    ("raw_material_batches", [("raw_batch_id", 1)], True),
    ("raw_material_batches", [("farm_id", 1)], False),
    ("raw_material_batches", [("created_at", -1)], False),

    ("processing_batches", [("processing_batch_id", 1)], True),
    ("processing_batches", [("created_at", -1)], False),

    ("medicine_batches", [("medicine_batch_id", 1)], True),
    ("medicine_batches", [("qr_id", 1)], True),
    ("medicine_batches", [("processing_batch_id", 1)], False),
    ("medicine_batches", [("created_at", -1)], False),

    ("batch_relationships", [("relationship_id", 1)], True),
    ("batch_relationships", [("parent_batch_id", 1)], False),
    ("batch_relationships", [("child_batch_id", 1)], False),

    # ---- quality ----
    ("lab_tests", [("lab_test_id", 1)], True),
    ("lab_tests", [("batch_id", 1)], False),

    # ---- telemetry (the big ones) ----
    ("iot_readings", [("reading_id", 1)], True),
    ("iot_readings", [("batch_id", 1), ("timestamp", 1)], False),

    ("iot_alerts", [("alert_id", 1)], True),
    ("iot_alerts", [("batch_id", 1), ("created_at", -1)], False),

    # Seeded alert collection, read alongside iot_alerts by routes/iot.py.
    ("alerts", [("batch_id", 1)], False),

    # ---- custody ----
    ("transport_events", [("batch_id", 1)], False),
    ("storage_events", [("raw_batch_id", 1)], False),
    ("storage_events", [("medicine_batch_id", 1)], False),

    # ---- consumer ----
    ("consumer_reports", [("report_id", 1)], True),
    ("consumer_reports", [("medicine_batch_id", 1)], False),

    ("investigations", [("investigation_id", 1)], True),
    ("investigations", [("report_id", 1)], False),

    # ---- ledger ----
    # sequence is unique because the chain's ordering contract depends on
    # exactly one event holding each number.
    ("blockchain_events", [("sequence", 1)], True),
    ("blockchain_events", [("transaction_id", 1)], True),
    ("blockchain_events", [("entity_id", 1), ("sequence", 1)], False),

    # ---- reference data ----
    ("farms", [("farm_id", 1)], True),
    ("plants", [("plant_id", 1)], True),
]


def ensure_indexes(db):
    """
    Create every index. Returns (created_or_existing, failed).

    A failure here is reported, not fatal - see the module docstring.
    """

    succeeded = 0
    failed = []

    for collection, keys, unique in INDEXES:

        try:
            db[collection].create_index(keys, unique=unique)
            succeeded += 1

        except Exception as error:

            failed.append((collection, keys, str(error)))

            logger.warning(
                "Could not create %s index on %s%s: %s",
                "unique" if unique else "",
                collection,
                keys,
                error
            )

    if failed:
        logger.warning(
            "%s of %s indexes could not be created. Duplicate business ids "
            "in the data are the usual cause; the API still runs.",
            len(failed),
            len(INDEXES)
        )

    return succeeded, failed
