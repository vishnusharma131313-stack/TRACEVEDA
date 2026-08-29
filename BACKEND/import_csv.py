import csv
from pathlib import Path

from database import db


# ==================================================
# CONFIG
# ==================================================

# Prefer the updated dataset when it is present locally, otherwise fall back
# to the dataset checked into the repository.
_CANDIDATE_FOLDERS = [
    Path(__file__).parent / "TraceVeda_Master_Dataset_Updated",
    Path(__file__).parent / "TraceVeda_Master_Dataset"
]

DATA_FOLDER = next(
    (folder for folder in _CANDIDATE_FOLDERS if folder.exists()),
    _CANDIDATE_FOLDERS[0]
)


# ==================================================
# IMPORT ONE CSV
# ==================================================

def import_csv(file_path):

    collection_name = file_path.stem

    print(f"\nImporting: {file_path.name}")
    print(f"Collection: {collection_name}")

    collection = db[collection_name]

    documents = []

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

                if value is None:
                    document[key] = None
                    continue

                value = value.strip()

                # Empty value
                if value == "":
                    document[key] = None

                # Boolean
                elif value.lower() == "true":
                    document[key] = True

                elif value.lower() == "false":
                    document[key] = False

                # Integer
                elif value.isdigit():
                    document[key] = int(value)

                # Float
                else:
                    try:
                        document[key] = float(value)
                    except ValueError:
                        document[key] = value

            documents.append(document)

    # Replace existing contents
    collection.delete_many({})

    # Insert documents
    if documents:

        result = collection.insert_many(documents)

        print(
            f"SUCCESS: "
            f"{len(result.inserted_ids)} documents inserted"
        )

    else:
        print("WARNING: CSV contains no data")


# ==================================================
# MAIN
# ==================================================

def main():

    print("=" * 50)
    print("TraceVeda CSV → MongoDB Import")
    print("=" * 50)

    if not DATA_FOLDER.exists():

        print("\nERROR: Dataset folder not found!")
        print(f"Expected location:")
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