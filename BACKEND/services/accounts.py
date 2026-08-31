"""
User accounts and the role vocabulary.

The roles mirror the seven the frontend already shows on its login screen
(Frontend/src/lib/roles.js). `consumer` is deliberately NOT an account role:
the consumer journey is the public QR page, which needs no login and must
keep working for someone scanning a box in a shop.

Accounts live in the `users` collection:

    { username, password_hash, role, full_name, organisation_id,
      is_active, created_at }

`password_hash` is the only representation of a password anywhere in this
codebase - nothing stores or logs the plaintext.
"""

import logging
from datetime import datetime, timezone

import database
from services.security import hash_password, verify_password


logger = logging.getLogger(__name__)

COLLECTION = "users"


# =========================
# ROLES
# =========================

FARMER = "farmer"
PROCESSOR = "processor"
LAB = "lab"
LOGISTICS = "logistics"
MANUFACTURER = "manufacturer"
REGULATOR = "regulator"
ADMIN = "admin"

ROLES = (
    FARMER,
    PROCESSOR,
    LAB,
    LOGISTICS,
    MANUFACTURER,
    REGULATOR,
    ADMIN,
)

ROLE_LABELS = {
    FARMER: "Farmer",
    PROCESSOR: "Processor",
    LAB: "Laboratory",
    LOGISTICS: "Logistics / IoT",
    MANUFACTURER: "Manufacturer",
    REGULATOR: "Regulator / Auditor",
    ADMIN: "Administrator",
}

# Everyone who can read the internal screens. The public QR/report routes
# are not gated at all - see routes/medicine.py and routes/consumer.py.
ALL_ROLES = ROLES


def _db():
    return database.db


# =========================
# LOOKUP
# =========================

def get_user(username):
    """One account by username, or None. Never returns the password hash."""

    if not username:
        return None

    return _db()[COLLECTION].find_one(
        {"username": str(username).lower()},
        {"_id": 0, "password_hash": 0}
    )


def authenticate(username, password):
    """
    Verify a username/password pair.

    Returns the user document (without its hash) on success, or None. A
    missing user and a wrong password are indistinguishable to the caller so
    the endpoint cannot be used to enumerate valid usernames.
    """

    if not username or not password:
        return None

    user = _db()[COLLECTION].find_one({"username": str(username).lower()})

    if not user:
        # Spend roughly the same time as a real verification so a timing
        # difference does not reveal whether the username exists.
        verify_password(password, hash_password("dummy-comparison-value"))
        return None

    if not verify_password(password, user.get("password_hash", "")):
        return None

    if not user.get("is_active", True):
        return None

    user.pop("_id", None)
    user.pop("password_hash", None)

    return user


# =========================
# CREATE
# =========================

def create_user(
    username,
    password,
    role,
    full_name=None,
    organisation_id=None
):
    """Create one account. Raises ValueError on a bad role or duplicate name."""

    username = str(username or "").strip().lower()

    if not username:
        raise ValueError("username is required")

    if role not in ROLES:
        raise ValueError(
            f"Unknown role {role!r}. Valid roles: {', '.join(ROLES)}"
        )

    if not password or len(password) < 8:
        raise ValueError("password must be at least 8 characters")

    if _db()[COLLECTION].find_one({"username": username}, {"_id": 1}):
        raise ValueError(f"User {username!r} already exists")

    document = {
        "username": username,
        "password_hash": hash_password(password),
        "role": role,
        "full_name": full_name or username.title(),
        "organisation_id": organisation_id,
        "is_active": True,
        "created_at": datetime.now(timezone.utc)
    }

    _db()[COLLECTION].insert_one(document)

    document.pop("_id", None)
    document.pop("password_hash", None)

    return document


def set_password(username, password):
    """Replace one account's password. Returns True when a user was updated."""

    result = _db()[COLLECTION].update_one(
        {"username": str(username or "").strip().lower()},
        {"$set": {"password_hash": hash_password(password)}}
    )

    return result.matched_count == 1


def count_users():
    return _db()[COLLECTION].count_documents({})
