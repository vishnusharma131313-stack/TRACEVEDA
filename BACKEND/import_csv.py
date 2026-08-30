import csv
from pathlib import Path

from database import db


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
        return float(value)
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

                total_inserted += len(
                    result.inserted_ids
                )

                print(
                    f"Inserted {total_inserted} documents..."
                )

                batch = []

        # Insert remaining documents
        if batch:

            result = collection.insert_many(batch)

            total_inserted += len(
                result.inserted_ids
            )

    print(
        f"SUCCESS: {total_inserted} documents inserted"
    )


# ==================================================
# MAIN
# ==================================================

def main():

    print("=" * 50)
    print("TraceVeda CSV -> MongoDB Import")
    print("=" * 50)

    if not DATA_FOLDER.exists():

        print("\nERROR: Dataset folder not found!")

        print("\nExpected location:")
        print(DATA_FOLDER)

        return

    csv_files = sorted(
        DATA_FOLDER.glob("*.csv")
    )

    if not csv_files:

        print("\nERROR: No CSV files found!")
        print(DATA_FOLDER)

        return

    print(
        f"\nFound {len(csv_files)} CSV files."
    )

    successful = 0
    failed = 0

    for file_path in csv_files:

        try:

            import_csv(file_path)

            successful += 1

        except Exception as e:

            failed += 1

            print(
                f"\nFAILED: {file_path.name}"
            )

            print(f"Reason: {e}")

    print("\n" + "=" * 50)
    print("IMPORT COMPLETED")
    print("=" * 50)

    print(f"Successful: {successful}")
    print(f"Failed:     {failed}")
    print(f"Total CSVs: {len(csv_files)}")


# ==================================================
# RUN
# ==================================================

if __name__ == "__main__":
    main()