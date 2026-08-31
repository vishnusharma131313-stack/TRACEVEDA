"""
Re-import only the two IoT reference CSVs.

    python retry_iot_import.py

These two files are the ones most likely to fail partway through against a
remote Atlas cluster, and re-running the whole of import_csv.py to recover
them wipes and reloads every other collection too.

This was previously a near-verbatim copy of import_csv.py, including its own
slightly different copy of convert_value. It now reuses that module, so the
two paths cannot drift into typing the same CSV cell differently.
"""

import sys

import database
from import_csv import DATA_FOLDER, import_csv


FILES = [
    "iot_reference_normalized.csv",
    "iot_reference_quarantine.csv",
]


def main():

    if not database.ping():
        print("ERROR: MongoDB is not reachable.")
        print("Check MONGO_URI in BACKEND/.env")
        return 1

    failed = 0

    for filename in FILES:

        file_path = DATA_FOLDER / filename

        if not file_path.exists():
            print(f"\nSKIPPED: {filename} is not in {DATA_FOLDER}")
            continue

        try:
            import_csv(file_path)

        except Exception as error:
            failed += 1
            print("\nFAILED!")
            print(f"File: {filename}")
            print(f"Reason: {error}")

    print("\nIMPORT RETRY COMPLETED")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
