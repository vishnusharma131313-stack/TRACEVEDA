import csv
from pathlib import Path

from database import db


# ==================================================
# CONFIG
# ==================================================

DATA_FOLDER = (
    Path(__file__).parent
    / "TraceVeda_Master_Dataset"
)

BATCH_SIZE = 100000


# ==================================================
# CONVERT VALUE
# ==================================================

def convert_value(value):

    if value is None:
        return None

    value = value.strip()

    if value == "":
        return None

    if value.lower() == "true":
        return True

    if value.lower() == "false":
        return False

    try:
        if "." not in value:
            return int(value)
    except ValueError:
        pass

    try:
        return float(value)
    except ValueError:
        pass

    return value


# ==================================================
# IMPORT FILE
# ==================================================

def import_csv(filename):

    file_path = DATA_FOLDER / filename

    collection_name = file_path.stem

    print("\n" + "=" * 50)
    print(f"Importing: {filename}")
    print(f"Collection: {collection_name}")
    print("=" * 50)

    if not file_path.exists():
        print(f"ERROR: File not found: {file_path}")
        return

    collection = db[collection_name]

    # Clear old/incomplete data from previous attempt
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

                document[key.strip()] = convert_value(value)

            batch.append(document)

            # Smaller batches reduce Atlas connection/load issues
            if len(batch) >= BATCH_SIZE:

                collection.insert_many(batch)

                total_inserted += len(batch)

                print(
                    f"Inserted {total_inserted} documents..."
                )

                batch = []

        # Insert remaining documents
        if batch:

            collection.insert_many(batch)

            total_inserted += len(batch)

    print("\nSUCCESS!")
    print(f"Total inserted: {total_inserted}")


# ==================================================
# RUN
# ==================================================

if __name__ == "__main__":

    files = [
        "iot_reference_normalized.csv",
        "iot_reference_quarantine.csv"
    ]

    for filename in files:

        try:
            import_csv(filename)

        except Exception as e:

            print("\nFAILED!")
            print(f"File: {filename}")
            print(f"Reason: {e}")

    print("\nIMPORT RETRY COMPLETED")