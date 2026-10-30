"""
User accounts and role management.
"""

from datetime import datetime, timezone

import database
from services.security import hash_password, verify_password


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


ALL_ROLES = ROLES

# Older frontend builds and manually provisioned accounts may store the UI
# label rather than the backend's canonical role key. Keep one canonical key
# throughout authentication and authorization.
ROLE_ALIASES = {
    "transporter": LOGISTICS,
    "logistics": LOGISTICS,
    "auditor": REGULATOR,
    "regulator": REGULATOR,
}


def normalize_role(role):
    """Return the canonical backend role for a role name or UI alias."""
    value = str(role or "").strip().lower()
    return ROLE_ALIASES.get(value, value)


def _db():
    return database.db


# =========================
# GENERATE USERNAME / ID
# =========================

def generate_username(role):

    prefixes = {
        "farmer": "far",
        "processor": "pro",
        "lab": "lab",
        "logistics": "log",
        "manufacturer": "man",
        "regulator": "aud",
        "admin": "adm"
    }

    prefix = prefixes.get(role)

    if not prefix:
        raise ValueError("Invalid role")


    # Get all users with this prefix
    users = list(
        _db()[COLLECTION].find(
            {
                "username": {
                    "$regex": f"^{prefix}-\\d+$"
                }
            },
            {
                "username": 1
            }
        )
    )


    highest_number = 0


    for user in users:

        try:

            username = user.get("username", "")

            number = int(
                username.split("-")[1]
            )

            if number > highest_number:

                highest_number = number

        except Exception:

            continue


    next_number = highest_number + 1


    return f"{prefix}-{next_number:03d}"


# =========================
# LOOKUP
# =========================

def get_user(username):

    if not username:
        return None


    user = _db()[COLLECTION].find_one(
        {
            "username": str(username).strip().lower()
        },
        {
            "_id": 0,
            "password_hash": 0
        }
    )
    if user:
        user["role"] = normalize_role(user.get("role"))
    return user


# =========================
# AUTHENTICATE
# =========================

def authenticate(username, password):

    if not username or not password:
        return None


    username = str(username).strip().lower()


    user = _db()[COLLECTION].find_one(
        {
            "username": username
        }
    )


    if not user:

        # Dummy hash comparison
        verify_password(
            password,
            hash_password(
                "dummy-comparison-value"
            )
        )

        return None


    if not verify_password(
        password,
        user.get("password_hash", "")
    ):

        return None


    if not user.get("is_active", True):

        return None


    user.pop("_id", None)
    user.pop("password_hash", None)
    user["role"] = normalize_role(user.get("role"))

    return user


# =========================
# CREATE USER
# =========================

def create_user(

    password,
    role,

    full_name=None,

    organisation_id=None,

    username=None

):


    role = normalize_role(role)

    if role not in ROLES:

        raise ValueError(

            f"Unknown role {role!r}. "
            f"Valid roles: {', '.join(ROLES)}"

        )


    # Generate ID automatically
    if not username or not str(username).strip():

        username = generate_username(role)

    else:

        username = (
            str(username)
            .strip()
            .lower()
        )


    # Password validation
    if not password or len(password) < 8:

        raise ValueError(
            "password must be at least 8 characters"
        )


    # Check duplicate username
    existing_user = _db()[COLLECTION].find_one(
        {
            "username": username
        }
    )


    if existing_user:

        raise ValueError(
            f"User {username!r} already exists"
        )


    # Create document
    document = {

        "username": username,

        "password_hash": hash_password(password),

        "role": role,

        "full_name":
            full_name or username.upper(),

        "organisation_id":
            organisation_id,

        "is_active": True,

        "created_at":
            datetime.now(timezone.utc)

    }


    _db()[COLLECTION].insert_one(
        document
    )


    document.pop("_id", None)

    document.pop(
        "password_hash",
        None
    )


    return document


# =========================
# SET PASSWORD
# =========================

def set_password(username, password):

    result = _db()[COLLECTION].update_one(

        {
            "username":
                str(username or "")
                .strip()
                .lower()
        },

        {
            "$set": {

                "password_hash":
                    hash_password(password)

            }
        }

    )


    return result.matched_count == 1


# =========================
# LIST USERS
# =========================

def list_users():
    """Return account records without credentials and with canonical roles."""
    users = list(
        _db()[COLLECTION].find(
            {},
            {"_id": 0, "password": 0, "password_hash": 0},
        ).sort("username", 1)
    )
    for user in users:
        user["role"] = normalize_role(user.get("role"))
    return users


# =========================
# LOCAL DEMO ADMINISTRATOR
# =========================

DEFAULT_ADMIN_USERNAME = "admin-001"
DEFAULT_ADMIN_PASSWORD = "12345678"


def ensure_default_admin():
    """Ensure the requested demo administrator exists with known credentials.

    The password is never stored in plaintext. If this named demo account
    already exists, its role/status and default password are corrected so a
    pre-existing database can use the documented login immediately.
    """
    username = DEFAULT_ADMIN_USERNAME
    existing = _db()[COLLECTION].find_one({"username": username})
    expected_hash_is_valid = bool(
        existing
        and existing.get("role") == ADMIN
        and existing.get("is_active", True)
        and verify_password(DEFAULT_ADMIN_PASSWORD, existing.get("password_hash", ""))
    )

    if expected_hash_is_valid:
        return {"username": username, "created": False, "updated": False}

    password_hash = hash_password(DEFAULT_ADMIN_PASSWORD)
    _db()[COLLECTION].update_one(
        {"username": username},
        {
            "$set": {
                "username": username,
                "password_hash": password_hash,
                "role": ADMIN,
                "full_name": "TraceVeda Administrator",
                "organisation_id": "TRACEVEDA-HQ",
                "is_active": True,
                "updated_at": datetime.now(timezone.utc),
            },
            "$setOnInsert": {"created_at": datetime.now(timezone.utc)},
        },
        upsert=True,
    )
    return {"username": username, "created": existing is None, "updated": existing is not None}


# =========================
# COUNT USERS
# =========================

def count_users():

    return _db()[COLLECTION].count_documents({})