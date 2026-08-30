"""
Load the CSV dataset into MongoDB.

    python import_csv.py

Each CSV becomes a collection named after the file. Existing contents are
REPLACED, so this is a reset, not a merge.

Afterwards it does two things the old version did not, both of which the API
depends on:

  * syncs the id counters (services/ids) past the imported data, so the first
    batch created after an import cannot be given an id the seed already uses;
  * creates the indexes (services/indexes), so the 11k-row iot_readings
    collection is not scanned end to end on every request.

Run migrate_seed_blockchain_events.py next to put the seeded ledger rows onto
the canonical hash chain.
"""

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

def main():

    print("=" * 50)
    print("TraceVeda CSV -> MongoDB Import")
    print("=" * 50)

    if not database.ping():
        print("\nERROR: MongoDB is not reachable.")
        print("Check MONGO_URI in BACKEND/.env")
        return 1

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

    print(f"\nFound {len(csv_files)} CSV files.")

    successful = 0
    failed = 0

    for file_path in csv_files:

        try:
            import_csv(file_path)
            successful += 1

        except Exception as e:

            failed += 1

            print(f"\nFAILED: {file_path.name}")
            print(f"Reason: {e}")

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

    print("\n" + "=" * 50)
    print("IMPORT COMPLETED")
    print("=" * 50)

    print(f"Successful: {successful}")
    print(f"Failed:     {failed}")
    print(f"Total CSVs: {len(csv_files)}")

    print()
    print("Next:")
    print("  python migrate_seed_blockchain_events.py")
    print("  python seed_users.py")

    return 1 if failed else 0


# ==================================================
# RUN
# ==================================================

if __name__ == "__main__":
    sys.exit(main())
