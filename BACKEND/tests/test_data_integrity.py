"""
Identifier generation and seeded-data compatibility.

These cover the defects that only show up once the shipped CSV dataset is
loaded, or once more than one request happens at a time - which is to say,
exactly the conditions of a live demo and none of a quick manual test.

Run with:
    python -m pytest tests/test_data_integrity.py -v
"""

import mongo_harness  # noqa: F401  (must be imported before routes/services)

mongo_harness.install()

import threading  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from services import accounts, ids  # noqa: E402
from services.security import create_access_token  # noqa: E402


PASSWORD = "demo-password-123"


@pytest.fixture(autouse=True)
def fresh_database():
    mongo_harness.install()


@pytest.fixture
def client():
    return TestClient(mongo_harness.make_app())


def auth_header(username, role):
    accounts.create_user(username=username, password=PASSWORD, role=role)
    token, _ = create_access_token(username, role)
    return {"Authorization": f"Bearer {token}"}


# ============================================================
# IDENTIFIERS
# ============================================================

def test_ids_do_not_collide_with_the_seeded_dataset():
    """
    medicine_batches.csv ships MED-2026-001..042.

    The old count_documents()+1 scheme produced MED-2026-043 here purely by
    coincidence - it counted documents rather than reading ids.
    """

    db = mongo_harness.current_db()

    for number in range(1, 43):
        db.medicine_batches.insert_one({
            "medicine_batch_id": f"MED-2026-{number:03d}"
        })

    assert ids.mint("medicine_batch") == "MED-2026-043"


def test_ids_are_not_reused_after_a_delete():
    """
    The coincidence above breaks the moment anything is removed.

    count_documents()+1 on 42 documents with one deleted gives 042, which is
    still in use. The counter is monotonic and does not care.
    """

    db = mongo_harness.current_db()

    for number in range(1, 43):
        db.medicine_batches.insert_one({
            "medicine_batch_id": f"MED-2026-{number:03d}"
        })

    first = ids.mint("medicine_batch")

    db.medicine_batches.delete_one({"medicine_batch_id": "MED-2026-007"})

    second = ids.mint("medicine_batch")

    assert second != first
    assert second == "MED-2026-044"


def test_ids_continue_past_a_differently_prefixed_seed():
    """Raw batches are seeded as ASH-2026-001..070, minted as RAW-2026-xxx."""

    db = mongo_harness.current_db()

    for number in range(1, 71):
        db.raw_material_batches.insert_one({
            "raw_batch_id": f"ASH-2026-{number:03d}"
        })

    assert ids.mint("raw_batch") == "RAW-2026-071"


def test_concurrent_minting_never_produces_a_duplicate():
    """The race the old scheme lost: two writes close enough together."""

    minted = []
    errors = []
    lock = threading.Lock()

    def worker():
        try:
            value = ids.mint("iot_reading")
            with lock:
                minted.append(value)
        except Exception as error:  # pragma: no cover - failure path
            with lock:
                errors.append(error)

    threads = [threading.Thread(target=worker) for _ in range(50)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert not errors, errors
    assert len(minted) == 50
    assert len(set(minted)) == 50, "duplicate ids were minted concurrently"


def test_sync_counters_moves_every_counter_past_existing_data():

    db = mongo_harness.current_db()

    db.medicine_batches.insert_one({"medicine_batch_id": "MED-2026-042"})
    db.raw_material_batches.insert_one({"raw_batch_id": "ASH-2026-070"})

    synced = ids.sync_counters()

    assert synced["medicine_batch"] == 42
    assert synced["raw_batch"] == 70

    assert ids.mint("medicine_batch") == "MED-2026-043"
    assert ids.mint("raw_batch") == "RAW-2026-071"


def test_a_hand_reset_counter_still_cannot_produce_a_duplicate():
    """The unique-index guarantee, exercised through mint's retry loop."""

    db = mongo_harness.current_db()

    for number in range(1, 6):
        db.medicine_batches.insert_one({
            "medicine_batch_id": f"MED-2026-{number:03d}"
        })

    # Someone edits the counters collection by hand, or restores an old dump.
    db.counters.update_one(
        {"_id": ids.ID_SPECS["medicine_batch"].counter_id},
        {"$set": {"seq": 0}},
        upsert=True,
    )

    assert ids.mint("medicine_batch") == "MED-2026-006"


# ============================================================
# SEEDED DATA COMPATIBILITY
# ============================================================

def test_storage_events_are_found_under_the_seeded_key(client):
    """
    storage_events.csv keys its 42 rows on `medicine_batch_id`; the live
    route writes `raw_batch_id`. Querying only the second returned an empty
    list for every seeded batch, so the storage timeline looked permanently
    empty during a demo on seed data.
    """

    db = mongo_harness.current_db()

    db.storage_events.insert_one({
        "storage_event_id": "STR-0001",
        "medicine_batch_id": "MED-2026-001",
        "facility_id": "MFG-001-STORAGE",
        "timestamp": "2026-06-05T16:38:43",
        "temperature_c": 27.92,
    })

    db.storage_events.insert_one({
        "event_id": "STORAGE-EVENT-2026-0001",
        "raw_batch_id": "RAW-2026-001",
        "storage_id": "STR-0002",
        "event_timestamp": "2026-06-06T10:00:00",
    })

    headers = auth_header("regulator", accounts.REGULATOR)

    seeded = client.get("/api/storage/MED-2026-001", headers=headers)

    assert seeded.status_code == 200
    assert seeded.json()["count"] == 1
    assert seeded.json()["events"][0]["storage_event_id"] == "STR-0001"

    live = client.get("/api/storage/RAW-2026-001", headers=headers)

    assert live.json()["count"] == 1


def test_alerts_are_read_from_both_collections(client):
    """
    import_csv.py loads alerts.csv into `alerts`; the IoT route writes
    `iot_alerts`. Reading one collection hid the other entirely.
    """

    db = mongo_harness.current_db()

    db.alerts.insert_one({
        "alert_id": "ALERT-00001",
        "batch_id": "MED-2026-001",
        "alert_type": "TEMPERATURE_EXCURSION",
        "severity": "WARNING",
        "timestamp": "2026-06-05T18:08:43",
        "observed_value": 35.8,
    })

    db.iot_alerts.insert_one({
        "alert_id": "ALERT-2026-0001",
        "batch_id": "MED-2026-001",
        "parameter": "temperature_c",
        "severity": "CRITICAL",
        "message": "Temperature outside allowed range",
        "created_at": datetime(2026, 6, 6, 9, 0, tzinfo=timezone.utc),
    })

    response = client.get(
        "/api/iot/alerts/MED-2026-001",
        headers=auth_header("regulator", accounts.REGULATOR),
    )

    assert response.status_code == 200

    alerts = response.json()["alerts"]

    assert len(alerts) == 2

    sources = {alert["source"] for alert in alerts}
    assert sources == {"live", "seed"}

    # Newest first, across the two different timestamp fields.
    assert alerts[0]["alert_id"] == "ALERT-2026-0001"


def test_transport_events_sort_on_whichever_timestamp_exists(client):
    """
    transport_events.csv has departure_time/arrival_time and no
    event_timestamp, so sorting on event_timestamp alone ordered the seeded
    rows arbitrarily.
    """

    db = mongo_harness.current_db()

    db.transport_events.insert_many([
        {
            "transport_id": "TRN-RAW-0002",
            "batch_id": "ASH-2026-001",
            "transport_stage": "RAW_TO_PROCESSOR",
            "departure_time": "2026-06-03T13:56:31",
        },
        {
            "transport_id": "TRN-RAW-0001",
            "batch_id": "ASH-2026-001",
            "transport_stage": "RAW_TO_PROCESSOR",
            "departure_time": "2026-06-01T13:56:31",
        },
        {
            "event_id": "TRANSPORT-EVENT-2026-0001",
            "batch_id": "ASH-2026-001",
            "event_type": "DISPATCH",
            "event_timestamp": "2026-06-02T09:00:00",
        },
    ])

    response = client.get(
        "/api/transport/ASH-2026-001",
        headers=auth_header("regulator", accounts.REGULATOR),
    )

    assert response.status_code == 200

    events = response.json()["events"]

    assert [
        event.get("transport_id") or event.get("event_id") for event in events
    ] == [
        "TRN-RAW-0001",
        "TRANSPORT-EVENT-2026-0001",
        "TRN-RAW-0002",
    ]


def test_telemetry_is_capped_and_keeps_the_newest_readings(client):
    """
    11k+ seeded readings live in one collection. An uncapped find() was the
    slowest thing the API could be asked to do, and truncating from the wrong
    end would leave the gauges showing stale telemetry.
    """

    db = mongo_harness.current_db()

    db.raw_material_batches.insert_one({"raw_batch_id": "RAW-2026-001"})

    db.iot_readings.insert_many([
        {
            "reading_id": f"READ-{number:06d}",
            "batch_id": "RAW-2026-001",
            "timestamp": f"2026-06-05T{number // 60:02d}:{number % 60:02d}:00",
        }
        for number in range(300)
    ])

    response = client.get(
        "/api/iot/readings/RAW-2026-001?limit=50",
        headers=auth_header("regulator", accounts.REGULATOR),
    )

    body = response.json()

    assert body["count"] == 50
    assert body["total"] == 300
    assert body["truncated"] is True

    # Oldest-first within the window, and the window is the newest 50.
    timestamps = [reading["timestamp"] for reading in body["readings"]]
    assert timestamps == sorted(timestamps)
    assert body["readings"][-1]["reading_id"] == "READ-000299"


# ============================================================
# BUSINESS RULES
# ============================================================

def test_a_raw_batch_cannot_over_contribute(client):

    db = mongo_harness.current_db()

    db.farms.insert_one({"farm_id": "FARM-001"})
    db.plants.insert_one({"plant_id": "PLANT-001"})
    db.raw_material_batches.insert_one({
        "raw_batch_id": "RAW-2026-001", "quantity": 100.0, "unit": "kg"
    })
    db.processing_batches.insert_one({
        "processing_batch_id": "PROCESS-2026-001", "status": "CREATED"
    })
    db.processing_batches.insert_one({
        "processing_batch_id": "PROCESS-2026-002", "status": "CREATED"
    })

    headers = auth_header("processor", accounts.PROCESSOR)

    def link(child, quantity):
        return client.post("/api/batches/relationships", json={
            "parent_batch_id": "RAW-2026-001",
            "child_batch_id": child,
            "relationship_type": "RAW_TO_PROCESSING",
            "quantity_contributed": quantity,
            "unit": "kg",
        }, headers=headers)

    assert link("PROCESS-2026-001", 60.0).status_code == 201

    over = link("PROCESS-2026-002", 60.0)

    assert over.status_code == 400
    assert "remaining" in over.json()["detail"]

    assert link("PROCESS-2026-002", 40.0).status_code == 201


def test_the_same_link_cannot_be_created_twice(client):

    db = mongo_harness.current_db()

    db.raw_material_batches.insert_one({
        "raw_batch_id": "RAW-2026-001", "quantity": 100.0
    })
    db.processing_batches.insert_one({
        "processing_batch_id": "PROCESS-2026-001"
    })

    headers = auth_header("processor", accounts.PROCESSOR)

    body = {
        "parent_batch_id": "RAW-2026-001",
        "child_batch_id": "PROCESS-2026-001",
        "relationship_type": "RAW_TO_PROCESSING",
        "quantity_contributed": 10.0,
        "unit": "kg",
    }

    assert client.post(
        "/api/batches/relationships", json=body, headers=headers
    ).status_code == 201

    assert client.post(
        "/api/batches/relationships", json=body, headers=headers
    ).status_code == 409


def test_only_a_pre_manufacturing_test_moves_the_batch_status(client):
    """
    test_stage used to be a free string. Anything that was not exactly
    "PRE_MANUFACTURING" silently left the batch unapproved, and a typo in
    that constant was indistinguishable from a genuine post-market test.
    """

    db = mongo_harness.current_db()

    db.processing_batches.insert_one({
        "processing_batch_id": "PROCESS-2026-001", "status": "CREATED"
    })

    headers = auth_header("lab", accounts.LAB)

    post_market = client.post("/api/lab/tests", json={
        "batch_id": "PROCESS-2026-001",
        "lab_id": "LAB-001",
        "test_stage": "POST_MANUFACTURING",
        "test_type": "STABILITY",
        "test_parameters": {},
        "result": "PASS",
    }, headers=headers)

    assert post_market.status_code == 201
    assert post_market.json()["batch_status"] == "CREATED"

    gating = client.post("/api/lab/tests", json={
        "batch_id": "PROCESS-2026-001",
        "lab_id": "LAB-001",
        "test_stage": "PRE_MANUFACTURING",
        "test_type": "PURITY",
        "test_parameters": {},
        "result": "PASS",
    }, headers=headers)

    assert gating.json()["batch_status"] == "APPROVED_FOR_MANUFACTURING"

    typo = client.post("/api/lab/tests", json={
        "batch_id": "PROCESS-2026-001",
        "lab_id": "LAB-001",
        "test_stage": "PRE-MANUFACTURING",
        "test_type": "PURITY",
        "test_parameters": {},
        "result": "PASS",
    }, headers=headers)

    assert typo.status_code == 422


def test_medicine_expiry_must_follow_manufacture(client):

    db = mongo_harness.current_db()

    db.processing_batches.insert_one({
        "processing_batch_id": "PROCESS-2026-001",
        "status": "APPROVED_FOR_MANUFACTURING",
    })

    headers = auth_header("manufacturer", accounts.MANUFACTURER)

    response = client.post("/api/medicine", json={
        "processing_batch_id": "PROCESS-2026-001",
        "manufacturer_id": "MFG-001",
        "product_name": "Ashwagandha Tablets",
        "manufacturing_date": "2026-08-26",
        "expiry_date": "2025-08-26",
    }, headers=headers)

    assert response.status_code == 422


def test_medicine_requires_an_approved_processing_batch(client):

    db = mongo_harness.current_db()

    db.processing_batches.insert_one({
        "processing_batch_id": "PROCESS-2026-001", "status": "COMPLETED"
    })

    headers = auth_header("manufacturer", accounts.MANUFACTURER)

    response = client.post("/api/medicine", json={
        "processing_batch_id": "PROCESS-2026-001",
        "manufacturer_id": "MFG-001",
        "product_name": "Ashwagandha Tablets",
        "manufacturing_date": "2026-08-26",
        "expiry_date": "2028-08-26",
    }, headers=headers)

    assert response.status_code == 400
    assert "COMPLETED" in response.json()["detail"]


def test_the_qr_id_always_matches_its_medicine_id(client):

    db = mongo_harness.current_db()

    db.processing_batches.insert_one({
        "processing_batch_id": "PROCESS-2026-001",
        "status": "APPROVED_FOR_MANUFACTURING",
    })

    response = client.post("/api/medicine", json={
        "processing_batch_id": "PROCESS-2026-001",
        "manufacturer_id": "MFG-001",
        "product_name": "Ashwagandha Tablets",
        "manufacturing_date": "2026-08-26",
        "expiry_date": "2028-08-26",
    }, headers=auth_header("manufacturer", accounts.MANUFACTURER)).json()

    assert response["medicine_batch_id"].replace("MED-", "QR-") == response["qr_id"]


def test_negative_quantities_are_refused(client):

    db = mongo_harness.current_db()
    db.farms.insert_one({"farm_id": "FARM-001"})
    db.plants.insert_one({"plant_id": "PLANT-001"})

    response = client.post("/api/batches/raw", json={
        "farm_id": "FARM-001",
        "plant_id": "PLANT-001",
        "collection_date": "2026-08-26",
        "quantity": -5.0,
        "unit": "kg",
    }, headers=auth_header("farmer", accounts.FARMER))

    assert response.status_code == 422


def test_impact_analysis_counts_distinct_medicine_batches(client):

    db = mongo_harness.current_db()

    db.raw_material_batches.insert_one({"raw_batch_id": "RAW-2026-001"})

    db.batch_relationships.insert_many([
        {"parent_batch_id": "RAW-2026-001", "child_batch_id": "PROCESS-2026-001"},
        {"parent_batch_id": "RAW-2026-001", "child_batch_id": "PROCESS-2026-001"},
    ])

    db.medicine_batches.insert_one({
        "medicine_batch_id": "MED-2026-001",
        "processing_batch_id": "PROCESS-2026-001",
    })

    response = client.get(
        "/api/trace/impact/RAW-2026-001",
        headers=auth_header("regulator", accounts.REGULATOR),
    )

    assert response.json()["affected_count"] == 1


# ============================================================
# CSV TYPING
# ============================================================

def test_nan_and_infinity_stay_as_text():
    """
    float("nan") parses, BSON stores it, and the JSON encoder then emits the
    bare token NaN - which is not valid JSON, so the failure surfaces in the
    browser's parser rather than anywhere useful.
    """

    from import_csv import convert_value

    assert convert_value("NaN") == "NaN"
    assert convert_value("Infinity") == "Infinity"
    assert convert_value("-inf") == "-inf"

    # Ordinary values are unaffected.
    assert convert_value("22.5") == 22.5
    assert convert_value("42") == 42
    assert convert_value("true") is True
    assert convert_value("") is None
    assert convert_value("RAW-2026-001") == "RAW-2026-001"


# ============================================================
# TIMESTAMP NORMALISATION
# ============================================================

def test_timestamps_are_stored_in_one_comparable_format(client):
    """
    Stored timestamps are ISO strings and MongoDB sorts strings
    lexicographically, which only equals chronological order when every
    string carries the same offset. `datetime.isoformat()` preserved whatever
    the caller sent, so these three instants sorted wrongly against each
    other. services/timeutils normalises them on write.
    """

    db = mongo_harness.current_db()
    db.raw_material_batches.insert_one({"raw_batch_id": "RAW-2026-001"})

    headers = auth_header("logistics", accounts.LOGISTICS)

    # Same instant, three notations, submitted out of order.
    for offset_form in (
        "2026-08-29T15:30:00+05:30",   # 10:00 UTC
        "2026-08-29T09:00:00Z",        # 09:00 UTC
        "2026-08-29T11:00:00",         # naive, treated as UTC
    ):
        response = client.post("/api/iot/readings", json={
            "batch_id": "RAW-2026-001",
            "sensor_id": "IOT-TZ-001",
            "timestamp": offset_form,
            "temperature_c": 22.0,
        }, headers=headers)

        assert response.status_code == 201, response.text

    stored = [
        reading["timestamp"]
        for reading in db.iot_readings.find({}, {"_id": 0, "timestamp": 1})
    ]

    # Every stored value is UTC, so all three share one suffix.
    assert all(value.endswith("+00:00") for value in stored), stored

    body = client.get(
        "/api/iot/readings/RAW-2026-001",
        headers=auth_header("regulator", accounts.REGULATOR),
    ).json()

    returned = [reading["timestamp"] for reading in body["readings"]]

    # Chronological, which is what the gauges and timeline depend on.
    assert returned == [
        "2026-08-29T09:00:00+00:00",
        "2026-08-29T10:00:00+00:00",
        "2026-08-29T11:00:00+00:00",
    ], returned


def test_the_time_helpers_handle_every_input_shape():

    from datetime import datetime, timedelta, timezone as tz

    from services.timeutils import now_utc, sort_key, to_utc, to_utc_iso

    naive = datetime(2026, 8, 29, 11, 0, 0)
    aware = datetime(2026, 8, 29, 15, 30, 0, tzinfo=tz(timedelta(hours=5, minutes=30)))

    assert to_utc(naive).tzinfo is tz.utc
    assert to_utc_iso(naive) == "2026-08-29T11:00:00+00:00"
    assert to_utc_iso(aware) == "2026-08-29T10:00:00+00:00"

    # Non-datetimes pass through untouched rather than raising.
    assert to_utc_iso(None) is None
    assert to_utc_iso("already-a-string") == "already-a-string"

    # sort_key never raises and never returns a non-string.
    assert sort_key(None) == ""
    assert sort_key(naive) == "2026-08-29T11:00:00+00:00"
    assert sort_key("2026-06-05T16:38:43") == "2026-06-05T16:38:43"

    assert now_utc().tzinfo is tz.utc


# ============================================================
# IMPORT SELECTION
# ============================================================
# A partial import is worse than none: import_csv truncates each collection
# before re-inserting it, so a run that dies partway leaves the remaining
# collections EMPTY. The API then starts perfectly happily with no medicines
# in it. These pin the guard rails that make that loud instead of silent.

def _collections_referenced_in_code(*directories):
    """
    Collection names reached through `db.<name>` or `db["<name>"]`.

    Parses the AST rather than grepping the text. A regex over the source
    also matches inside strings and comments - the diagnosis message in
    services/indexes.py names `db.iot_reference_normalized.drop()` as advice,
    which a text scan reads as a query the app makes.
    """

    import ast

    found = set()

    for directory in directories:

        for path in sorted(directory.glob("*.py")):

            tree = ast.parse(path.read_text(encoding="utf-8"), str(path))

            for node in ast.walk(tree):

                # db.<name>
                if (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == "db"
                ):
                    found.add(node.attr)

                # db["<name>"]
                if (
                    isinstance(node, ast.Subscript)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == "db"
                    and isinstance(node.slice, ast.Constant)
                    and isinstance(node.slice.value, str)
                ):
                    found.add(node.slice.value)

    return found


def test_import_default_covers_every_collection_the_code_reads():
    """
    CORE_COLLECTIONS must not drift behind the routes.

    If a new route starts reading a collection that the default import skips,
    a fresh database will be missing it and the failure shows up as an empty
    screen rather than an error.
    """

    from pathlib import Path

    import import_csv

    backend = Path(__file__).resolve().parents[1]

    read = _collections_referenced_in_code(
        backend / "routes",
        backend / "services",
    )

    # Written by the app at runtime, not loaded from a CSV.
    runtime_only = {"users", "counters", "iot_alerts", "investigations"}

    # Not collections - attributes and methods on the database object.
    not_collections = {
        "command", "list_collection_names", "client", "name",
        "drop_collection",
    }

    read -= runtime_only | not_collections

    missing = read - import_csv.CORE_COLLECTIONS

    assert not missing, (
        f"routes read {sorted(missing)}, which the default import does not "
        f"load. Add them to CORE_COLLECTIONS in import_csv.py."
    )


def test_the_collection_scanner_ignores_strings_and_comments():
    """The false positive that motivated parsing the AST."""

    import ast
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:

        directory = Path(tmp)

        (directory / "sample.py").write_text(
            'MESSAGE = "run db.some_reference_corpus.drop() in mongosh"\n'
            "# db.another_mentioned_in_a_comment.find()\n"
            "def go(db):\n"
            "    return db.medicine_batches.find_one({})\n",
            encoding="utf-8",
        )

        found = _collections_referenced_in_code(directory)

    assert "medicine_batches" in found
    assert "some_reference_corpus" not in found
    assert "another_mentioned_in_a_comment" not in found


def test_the_bulk_corpora_are_excluded_by_default():
    """
    iot_reference_normalized alone is 2.2M rows / ~135 MB and no route
    touches it. Importing it by default filled an Atlas M0 cluster partway
    through a run and left every later collection empty.
    """

    import import_csv

    files = [
        type("F", (), {"stem": name})()
        for name in [
            "medicine_batches",
            "lab_tests",
            "iot_reference_normalized",
            "iot_reference_quarantine",
            "bsi_reference_normalized",
            "nmpb_reference_normalized",
        ]
    ]

    chosen, skipped = import_csv.select_files(files)

    chosen_names = {f.stem for f in chosen}
    skipped_names = {f.stem for f, _ in skipped}

    assert "medicine_batches" in chosen_names
    assert "lab_tests" in chosen_names
    assert import_csv.BULK_COLLECTIONS <= skipped_names

    # --all opts back in.
    chosen_all, skipped_all = import_csv.select_files(files, include_bulk=True)

    assert not skipped_all
    assert "iot_reference_normalized" in {f.stem for f in chosen_all}


def test_only_selects_exactly_what_was_named():
    """The recovery path: re-import one emptied collection, touch nothing else."""

    import import_csv

    files = [
        type("F", (), {"stem": name})()
        for name in ["medicine_batches", "lab_tests", "iot_readings", "plants"]
    ]

    chosen, skipped = import_csv.select_files(
        files, only="medicine_batches,lab_tests"
    )

    assert {f.stem for f in chosen} == {"medicine_batches", "lab_tests"}
    assert {f.stem for f, _ in skipped} == {"iot_readings", "plants"}


def test_an_unknown_csv_is_imported_rather_than_silently_dropped():
    """New project data should land in the database, not be quietly ignored."""

    import import_csv

    files = [type("F", (), {"stem": "brand_new_dataset"})()]

    chosen, skipped = import_csv.select_files(files)

    assert [f.stem for f in chosen] == ["brand_new_dataset"]
    assert not skipped


def test_verify_reports_an_empty_core_collection(client):
    """
    The check that turns a silent partial import into a non-zero exit code.
    """

    import import_csv

    db = mongo_harness.current_db()

    db.medicine_batches.delete_many({})
    db.lab_tests.insert_one({"lab_test_id": "LABTEST-2026-001"})

    empty_core, empty_other = import_csv.verify({"medicine_batches", "lab_tests"})

    assert empty_core == ["medicine_batches"]
    assert empty_other == []


# ============================================================
# INDEX FAILURE REPORTING
# ============================================================

def test_index_failures_are_diagnosed_not_just_repeated():
    """
    A full Atlas M0 made every one of the 32 index builds fail with the same
    700-character quota error. All 32 were logged in full, and the summary
    then blamed "duplicate business ids" - so the startup log was unreadable
    AND it named the wrong cause.
    """

    from services import indexes

    class FullCluster:
        """Every create_index fails the way an out-of-space Atlas does."""

        def __getitem__(self, name):
            return self

        def create_index(self, keys, unique=False):
            raise RuntimeError(
                "you are over your space quota, using 512 MB of 512 MB. "
                "Writes are blocked on your cluster."
            )

    succeeded, failed = indexes.ensure_indexes(FullCluster())

    assert succeeded == 0
    assert len(failed) == len(indexes.INDEXES)

    # The summary names the real cause and what to do about it.
    diagnosis = indexes._diagnose([error for _, _, error in failed])

    assert "OUT OF STORAGE" in diagnosis
    assert "iot_reference_normalized" in diagnosis
    assert "duplicate" not in diagnosis.lower()


def test_a_duplicate_key_failure_is_diagnosed_differently():

    from services import indexes

    diagnosis = indexes._diagnose([
        "E11000 duplicate key error collection: traceveda.medicine_batches"
    ])

    assert "Duplicate business ids" in diagnosis
    assert "STORAGE" not in diagnosis


def test_a_permissions_failure_is_diagnosed_differently():

    from services import indexes

    diagnosis = indexes._diagnose(["not authorized on traceveda to execute command"])

    assert "not permitted to create indexes" in diagnosis


def test_indexes_still_succeed_on_a_healthy_database():

    from services import indexes

    succeeded, failed = indexes.ensure_indexes(mongo_harness.current_db())

    assert failed == []
    assert succeeded == len(indexes.INDEXES)
