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


    return _db()[COLLECTION].find_one(
        {
            "username": str(username).lower()
        },
        {
            "_id": 0,
            "password_hash": 0
        }
    )


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
# COUNT USERS
# =========================

def count_users():

    return _db()[COLLECTION].count_documents({})