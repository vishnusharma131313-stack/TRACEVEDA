"""
Migration of the seeded blockchain_events.csv onto the canonical schema.

Runs against the real CSV shipped in the repository, through the real
import_csv loader, so it exercises the exact path a teammate follows:

    python import_csv.py
    python migrate_seed_blockchain_events.py
    GET /api/blockchain/verify-chain

Run with:
    python -m pytest tests/test_seed_migration.py -v
or:
    python tests/test_seed_migration.py
"""

import mongo_harness  # noqa: F401  (must be imported before routes/services)

mongo_harness.install()

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

import import_csv  # noqa: E402
import migrate_seed_blockchain_events as migration  # noqa: E402

from services import blockchain_service  # noqa: E402


SEED_CSV = (
    Path(__file__).resolve().parents[1]
    / "TraceVeda_Master_Dataset"
    / "blockchain_events.csv"
)


@pytest.fixture(autouse=True)
def fresh_database():
    """A clean chain per test - see mongo_harness for why this is per-test."""

    mongo_harness.install()


def import_seed_csv():
    """Load the seed CSV exactly as import_csv.py does."""

    assert SEED_CSV.exists(), f"seed CSV missing: {SEED_CSV}"

    import_csv.import_csv(SEED_CSV)

    return mongo_harness.current_db().blockchain_events.count_documents({})


def test_import_leaves_documents_in_the_legacy_schema():
    """Establishes the problem the migration exists to solve."""

    seeded = import_seed_csv()

    db = mongo_harness.current_db()

    assert seeded > 0

    legacy = db.blockchain_events.count_documents(
        {"data_hash": {"$exists": True}}
    )

    assert legacy == seeded, "import inserts CSV columns verbatim"

    # None of the fields the live chain reads are present.
    assert db.blockchain_events.count_documents(
        {"entity_id": {"$exists": True}}
    ) == 0
    assert db.blockchain_events.count_documents(
        {"sequence": {"$exists": True}}
    ) == 0

    # And verify-chain says so, with an actionable reason.
    before = blockchain_service.verify_chain()

    assert before["valid"] is False
    assert "migrate_seed_blockchain_events" in before["reason"]

    print(f"OK  {seeded} seed rows imported in the legacy schema")


def test_seed_migration_produces_a_valid_chain():

    seeded = import_seed_csv()

    db = mongo_harness.current_db()

    assert migration.migrate() == 0

    # ---------------------------------------------
    # Canonical schema everywhere, no legacy leftovers
    # ---------------------------------------------

    assert db.blockchain_events.count_documents(
        {"data_hash": {"$exists": True}}
    ) == 0, "replace_one should have dropped the legacy fields"

    assert db.blockchain_events.count_documents(
        {"batch_id": {"$exists": True}}
    ) == 0

    for document in db.blockchain_events.find({}):
        assert isinstance(document["sequence"], int)
        assert document["blockchain_status"] == "ANCHORED"
        assert document["entity_type"] in {"RAW", "PROCESSING", "MEDICINE"}
        assert document["entity_id"]
        assert document["transaction_id"].startswith("TX-")
        # CSV provenance is preserved, not discarded.
        assert document["event_data"]["blockchain_event_id"]
        assert document["event_data"]["legacy_data_hash"]

    # ---------------------------------------------
    # The whole seeded history verifies
    # ---------------------------------------------

    result = blockchain_service.verify_chain()

    assert result["valid"] is True, result
    assert result["checked"] == seeded, result

    assert db.blockchain_events.count_documents(
        {"previous_hash": "GENESIS"}
    ) == 1

    print(f"OK  {seeded} seed events migrated, chain valid")


def test_live_events_continue_the_migrated_chain():
    """The counter must not restart at 1 after migration."""

    seeded = import_seed_csv()

    assert migration.migrate() == 0

    counter = mongo_harness.current_db().counters.find_one(
        {"_id": "blockchain_events"}
    )

    assert counter["seq"] == seeded

    live = blockchain_service.anchor_event(
        "BATCH_CREATED",
        "RAW",
        "RAW-2026-999",
        {"quantity": 10.0}
    )

    assert live["sequence"] == seeded + 1
    assert live["previous_hash"] != "GENESIS"

    after = blockchain_service.verify_chain()

    assert after["valid"] is True, after
    assert after["checked"] == seeded + 1

    print(
        f"OK  live event continued at sequence {live['sequence']} "
        f"after {seeded} seed events"
    )


def test_migration_is_safe_to_rerun():
    """Re-running touches nothing: only legacy documents are considered."""

    import_seed_csv()

    assert migration.migrate() == 0

    before = blockchain_service.verify_chain()

    assert migration.migrate() == 0

    after = blockchain_service.verify_chain()

    assert after == before, "re-running the migration changed the chain"
    assert after["valid"] is True

    print("OK  migration is idempotent")


def test_migration_refuses_a_mixed_collection():
    """Re-sequencing from 1 on top of live events would collide."""

    import_seed_csv()

    # A live event anchored before anyone remembered to migrate.
    blockchain_service.anchor_event(
        "BATCH_CREATED",
        "RAW",
        "RAW-2026-500",
        {"quantity": 1.0}
    )

    assert migration.migrate() == 1, "mixed collection should abort"

    # Nothing was rewritten.
    assert mongo_harness.current_db().blockchain_events.count_documents(
        {"data_hash": {"$exists": True}}
    ) > 0

    print("OK  mixed collection aborted instead of corrupting history")


def test_migration_on_an_empty_collection_is_a_noop():

    assert migration.migrate() == 0

    print("OK  empty collection is a clean no-op")


def test_seed_event_types_are_preserved():
    """Seeded event types are historical fact, not values to remap."""

    import_seed_csv()

    assert migration.migrate() == 0

    event_types = mongo_harness.current_db().blockchain_events.distinct(
        "event_type"
    )

    # These are outside the canonical live vocabulary but must survive.
    assert "SHIPMENT_MILESTONE" in event_types
    assert "MEDICINE_LINKAGE" in event_types
    assert "ENVIRONMENTAL_ALERT" in event_types

    print(f"OK  preserved seed event types: {sorted(event_types)}")


def test_duplicate_timestamps_get_a_deterministic_order():
    """
    Seven timestamps appear on more than one seed row. Ordering has to be
    stable, or the rebuilt chain differs run to run.
    """

    import_seed_csv()

    assert migration.migrate() == 0

    first_run = [
        (document["sequence"], document["event_hash"])
        for document in
        mongo_harness.current_db().blockchain_events.find({}).sort(
            "sequence", 1
        )
    ]

    # Re-import and re-migrate from scratch.
    mongo_harness.install()
    import_seed_csv()
    assert migration.migrate() == 0

    second_run = [
        (document["sequence"], document["event_hash"])
        for document in
        mongo_harness.current_db().blockchain_events.find({}).sort(
            "sequence", 1
        )
    ]

    assert first_run == second_run, (
        "migration is not deterministic across runs"
    )

    print(f"OK  {len(first_run)} events hashed identically on both runs")


if __name__ == "__main__":

    mongo_harness.run_standalone(
        test_import_leaves_documents_in_the_legacy_schema,
        test_seed_migration_produces_a_valid_chain,
        test_live_events_continue_the_migrated_chain,
        test_migration_is_safe_to_rerun,
        test_migration_refuses_a_mixed_collection,
        test_migration_on_an_empty_collection_is_a_noop,
        test_seed_event_types_are_preserved,
        test_duplicate_timestamps_get_a_deterministic_order
    )
