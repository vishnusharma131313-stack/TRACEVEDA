"""
Load the CSV dataset into MongoDB.

    python import_csv.py              the collections the API actually reads
    python import_csv.py --all        those plus the bulk reference corpora
    python import_csv.py --only a,b   just these collections
    python import_csv.py --list       show what would be imported, and skipped

Each CSV becomes a collection named after the file. Existing contents are
REPLACED, so this is a reset, not a merge.

WHY THERE IS A DEFAULT SUBSET
-----------------------------
The folder contains 32 CSVs, but only 15 of them are ever queried by a route.
Two of the rest are enormous:

    iot_reference_normalized.csv    2,220,176 rows   (~135 MB in MongoDB)
    iot_reference_quarantine.csv       93,879 rows

Importing everything blindly pushed an Atlas M0 cluster (512 MB) to its limit
partway through the run. Because each file is truncated before it is
re-inserted, the files that failed after it were left EMPTY - including
medicine_batches and lab_tests, which the whole application depends on. A
partial import is worse than no import, and it fails silently: the API starts
fine and simply has no medicines in it.

So the bulk reference corpora are opt-in. `--all` still loads them; check your
cluster has room first.

Afterwards this also:

  * syncs the id counters (services/ids) past the imported data, so the first
    batch created after an import cannot be given an id the seed already uses;
  * creates the indexes (services/indexes), so the 11k-row iot_readings
    collection is not scanned end to end on every request;
  * verifies every imported collection is non-empty, and exits non-zero if a
    core one is not.

Run migrate_seed_blockchain_events.py next to put the seeded ledger rows onto
the canonical hash chain.
"""

import argparse
import csv
import math
import sys
from pathlib import Path

import database
from database import db
from services.ids import sync_counters
from services.indexes import ensure_indexes


# ==================================================
# CONFIG
# ==================================================

# Prefer the updated dataset when it is present locally,
# otherwise fall back to the dataset checked into the repository.
_CANDIDATE_FOLDERS = [
    Path(__file__).parent / "TraceVeda_Master_Dataset_Updated",
    Path(__file__).parent / "TraceVeda_Master_Dataset"
]

DATA_FOLDER = next(
    (folder for folder in _CANDIDATE_FOLDERS if folder.exists()),
    _CANDIDATE_FOLDERS[0]
)

BATCH_SIZE = 5000


# Collections a route reads. Keep in step with routes/ - the test
# test_import_default_covers_every_collection_the_code_reads enforces it.
CORE_COLLECTIONS = {
    "alerts",
    "batch_relationships",
    "blockchain_events",
    "consumer_reports",
    "farms",
    "investigations",
    "iot_readings",
    "lab_tests",
    "medicine_batches",
    "plants",
    "processing_batches",
    "raw_material_batches",
    "storage_events",
    "transport_events",
}

# Not queried by any route, but small and useful to have loaded for
# demonstrations and ad-hoc analysis.
SUPPORTING_COLLECTIONS = {
    "data_dictionary",
    "data_dictionary_iot_final",
    "data_quality_report",
    "foreign_key_validation",
    "handling_protocols",
    "iot_devices",
    "master_event_log",
    "master_traceability_dataset",
    "plant_source_crosswalk",
    "relationships",
    "source_ingestion_report",
    "source_to_master_mapping",
    "stakeholders",
    "traceability_validation",
}

# Millions of rows of botanical/IoT reference material that nothing reads.
# Opt in with --all.
BULK_COLLECTIONS = {
    "bsi_reference_normalized",
    "iot_reference_normalized",
    "iot_reference_quarantine",
    "nmpb_reference_normalized",
}

DEFAULT_COLLECTIONS = CORE_COLLECTIONS | SUPPORTING_COLLECTIONS


# ==================================================
# CONVERT VALUE
# ==================================================

def convert_value(value):
    """
    Best-effort typing of one CSV cell.

    NaN and the infinities are explicitly kept as text. `float("nan")` and
    `float("inf")` both parse happily, BSON stores them, and then the JSON
    encoder emits the bare tokens NaN / Infinity - which are not valid JSON,
    so any endpoint returning such a document fails in the client's parser
    rather than anywhere useful.
    """

    if value is None:
        return None

    value = value.strip()

    if value == "":
        return None

    # Boolean
    if value.lower() == "true":
        return True

    if value.lower() == "false":
        return False

    # Integer
    try:
        if "." not in value:
            return int(value)
    except ValueError:
        pass

    # Float
    try:
        number = float(value)

        if math.isnan(number) or math.isinf(number):
            return value

        return number

    except ValueError:
        pass

    # String
    return value


# ==================================================
# IMPORT ONE CSV
# ==================================================

def import_csv(file_path):

    collection_name = file_path.stem

    print("\n" + "=" * 50)
    print(f"Importing: {file_path.name}")
    print(f"Collection: {collection_name}")
    print("=" * 50)

    collection = db[collection_name]

    # Replace old dataset contents
    collection.delete_many({})

    batch = []
    total_inserted = 0

    with open(
        file_path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            # Skip completely empty rows
            if not any(
                value is not None
                and str(value).strip()
                for value in row.values()
            ):
                continue

            document = {}

            for key, value in row.items():

                if key is None:
                    continue

                key = key.strip()

                document[key] = convert_value(value)

            batch.append(document)

            # Insert in batches
            if len(batch) >= BATCH_SIZE:

                result = collection.insert_many(batch)

                total_inserted += len(result.inserted_ids)

                print(f"Inserted {total_inserted} documents...")

                batch = []

        # Insert remaining documents
        if batch:

            result = collection.insert_many(batch)

            total_inserted += len(result.inserted_ids)

    print(f"SUCCESS: {total_inserted} documents inserted")

    return total_inserted


# ==================================================
# MAIN
# ==================================================

def select_files(csv_files, include_bulk=False, only=None):
    """Split the folder's CSVs into (to import, to skip with a reason)."""

    if only:
        wanted = {name.strip() for name in only.split(",") if name.strip()}
        chosen = [f for f in csv_files if f.stem in wanted]
        skipped = [(f, "not in --only") for f in csv_files if f.stem not in wanted]

        missing = wanted - {f.stem for f in chosen}
        for name in sorted(missing):
            print(f"WARNING: --only named {name!r}, which is not in {DATA_FOLDER}")

        return chosen, skipped

    allowed = DEFAULT_COLLECTIONS | (BULK_COLLECTIONS if include_bulk else set())

    chosen = []
    skipped = []

    for file_path in csv_files:

        if file_path.stem in allowed:
            chosen.append(file_path)

        elif file_path.stem in BULK_COLLECTIONS:
            skipped.append((file_path, "bulk reference data - use --all"))

        else:
            # A CSV nobody has classified yet. Import it: an unknown file is
            # more likely to be new project data than something to ignore.
            chosen.append(file_path)

    return chosen, skipped


def verify(expected_collections):
    """
    Report any collection that ended up empty.

    A truncate-then-failed-insert leaves no error behind once the process
    exits, and the API starts perfectly happily on an empty database. This is
    the check that turns that silence into a non-zero exit code.
    """

    empty_core = []
    empty_other = []

    for name in sorted(expected_collections):

        if db[name].count_documents({}) == 0:

            if name in CORE_COLLECTIONS:
                empty_core.append(name)
            else:
                empty_other.append(name)

    return empty_core, empty_other


def main():

    parser = argparse.ArgumentParser(
        description="Load the TraceVeda CSV dataset into MongoDB"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="also import the bulk reference corpora (millions of rows, "
             "not read by any route)"
    )
    parser.add_argument(
        "--only",
        metavar="A,B",
        help="import only these collections, e.g. --only medicine_batches,lab_tests"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="show what would be imported and skipped, then exit"
    )

    args = parser.parse_args()

    print("=" * 50)
    print("TraceVeda CSV -> MongoDB Import")
    print("=" * 50)

    if not DATA_FOLDER.exists():

        print("\nERROR: Dataset folder not found!")
        print("\nExpected location:")
        print(DATA_FOLDER)

        return 1

    csv_files = sorted(DATA_FOLDER.glob("*.csv"))

    if not csv_files:

        print("\nERROR: No CSV files found!")
        print(DATA_FOLDER)

        return 1

    chosen, skipped = select_files(csv_files, args.all, args.only)

    if args.list:

        print(f"\nWould import {len(chosen)}:")
        for file_path in chosen:
            tag = "core" if file_path.stem in CORE_COLLECTIONS else "supporting"
            print(f"  {file_path.stem:<32} {tag}")

        print(f"\nWould skip {len(skipped)}:")
        for file_path, reason in skipped:
            print(f"  {file_path.stem:<32} {reason}")

        return 0

    if not database.ping():
        print("\nERROR: MongoDB is not reachable.")
        print("Check MONGO_URI in BACKEND/.env")
        return 1

    print(f"\nImporting {len(chosen)} of {len(csv_files)} CSV files.")

    if skipped and not args.only:
        print(f"Skipping {len(skipped)} (bulk reference data; use --all to include).")

    successful = 0
    failed = 0
    failed_names = []

    for file_path in chosen:

        try:
            import_csv(file_path)
            successful += 1

        except Exception as e:

            failed += 1
            failed_names.append(file_path.stem)

            print(f"\nFAILED: {file_path.name}")
            print(f"Reason: {e}")

            # The collection was truncated before the insert, so a failure
            # here leaves it EMPTY rather than stale. Say so immediately -
            # this is the exact silence that emptied medicine_batches.
            print(
                f"  !! {file_path.stem} is now EMPTY. Re-run with "
                f"--only {file_path.stem}"
            )

    # ------------------------------------------------------------------
    # POST-IMPORT. Both steps are part of the import, not optional extras:
    # without them the first live write can collide with seeded ids, and
    # every telemetry query is a full collection scan.
    # ------------------------------------------------------------------

    print("\n" + "=" * 50)
    print("SYNCING ID COUNTERS")
    print("=" * 50)

    try:
        synced = sync_counters()

        for kind, highest in sorted(synced.items()):
            print(f"  {kind:<20} next id continues after {highest}")

    except Exception as e:
        failed += 1
        print(f"FAILED to sync id counters: {e}")

    print("\n" + "=" * 50)
    print("CREATING INDEXES")
    print("=" * 50)

    try:
        created, index_failures = ensure_indexes(db)
        print(f"  {created} indexes applied, {len(index_failures)} failed")

        for collection, keys, error in index_failures:
            print(f"  ! {collection} {keys}: {error}")

    except Exception as e:
        failed += 1
        print(f"FAILED to create indexes: {e}")

    # ------------------------------------------------------------------
    # VERIFY
    # ------------------------------------------------------------------

    print("\n" + "=" * 50)
    print("VERIFYING")
    print("=" * 50)

    empty_core, empty_other = verify({f.stem for f in chosen})

    if empty_core:
        print("  CORE COLLECTIONS ARE EMPTY - the API will not work:")
        for name in empty_core:
            print(f"    {name}")
        print()
        print(f"  Fix with: python import_csv.py --only {','.join(empty_core)}")

    if empty_other:
        print("  Empty (non-critical):")
        for name in empty_other:
            print(f"    {name}")

    if not empty_core and not empty_other:
        print("  All imported collections contain data.")

    print("\n" + "=" * 50)
    print("IMPORT COMPLETED")
    print("=" * 50)

    print(f"Successful: {successful}")
    print(f"Failed:     {failed}")
    print(f"Imported:   {len(chosen)} of {len(csv_files)} CSVs")

    if failed_names:
        print(f"Failed:     {', '.join(failed_names)}")

    if not failed and not empty_core:
        print()
        print("Next:")
        print("  python migrate_seed_blockchain_events.py")
        print("  python seed_users.py")

    return 1 if (failed or empty_core) else 0


# ==================================================
# RUN
# ==================================================

if __name__ == "__main__":
    sys.exit(main())
