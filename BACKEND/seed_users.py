"""
Create the demo accounts.

    python seed_users.py                 # create any that are missing
    python seed_users.py --reset         # also reset existing passwords
    python seed_users.py --password X    # use X instead of the default

One account per role, so a judge can log in as each persona and see that the
API genuinely refuses the actions that role may not perform.

The default password is a development convenience and is printed to the
console, never stored in plaintext. Pass --password (or set
TRACEVEDA_DEMO_PASSWORD) for anything that is not a local demo.
"""

import argparse
import os
import sys

import database  # noqa: F401  (loads .env and builds the client)
from services import accounts


DEFAULT_PASSWORD = os.getenv("TRACEVEDA_DEMO_PASSWORD", "traceveda2026")

DEMO_ACCOUNTS = [
    ("farmer", accounts.FARMER, "Anita Kulkarni", "FARM-001"),
    ("processor", accounts.PROCESSOR, "Ravi Menon", "PROC-001"),
    ("lab", accounts.LAB, "Dr. Sneha Rao", "LAB-001"),
    ("logistics", accounts.LOGISTICS, "Imran Shaikh", "TRN-001"),
    ("manufacturer", accounts.MANUFACTURER, "Priya Nair", "MFG-001"),
    ("regulator", accounts.REGULATOR, "Ministry of AYUSH", None),
    ("admin", accounts.ADMIN, "System Administrator", None),
]


def seed(password, reset=False):

    created = []
    updated = []
    skipped = []

    for username, role, full_name, organisation_id in DEMO_ACCOUNTS:

        if accounts.get_user(username):

            if reset:
                accounts.set_password(username, password)
                updated.append(username)
            else:
                skipped.append(username)

            continue

        accounts.create_user(
            username=username,
            password=password,
            role=role,
            full_name=full_name,
            organisation_id=organisation_id
        )

        created.append(username)

    return created, updated, skipped


def main():

    parser = argparse.ArgumentParser(description="Create TraceVeda demo accounts")

    parser.add_argument(
        "--password",
        default=DEFAULT_PASSWORD,
        help="password for every demo account (default: TRACEVEDA_DEMO_PASSWORD or traceveda2026)"
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help="reset the password of accounts that already exist"
    )

    args = parser.parse_args()

    if len(args.password) < 8:
        print("ERROR: password must be at least 8 characters")
        return 1

    try:
        created, updated, skipped = seed(args.password, reset=args.reset)

    except Exception as error:
        print(f"ERROR: {error}")
        print("Is MongoDB reachable? Check MONGO_URI in BACKEND/.env")
        return 1

    print("=" * 56)
    print("TRACEVEDA DEMO ACCOUNTS")
    print("=" * 56)

    for username, role, _, _ in DEMO_ACCOUNTS:

        if username in created:
            state = "created"
        elif username in updated:
            state = "password reset"
        else:
            state = "already existed"

        print(f"  {username:<14} {role:<14} {state}")

    print()
    print(f"Password: {args.password}")

    if skipped and not args.reset:
        print()
        print("Existing accounts were left alone. Use --reset to set their")
        print("passwords to the value above.")

    print()
    print("Log in with:  POST /api/auth/login")
    print('  {"username": "regulator", "password": "<password>"}')

    return 0


if __name__ == "__main__":
    sys.exit(main())
