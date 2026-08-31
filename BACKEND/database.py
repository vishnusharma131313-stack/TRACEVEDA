"""
The MongoDB connection.

`db` is imported by value in a few places (`from database import db`), so it
is created once at import time and never rebound in production. The test
harness rebinds `database.db` and reloads its consumers - see
tests/mongo_harness.py.

Connection settings come from config.settings rather than os.getenv, so an
unset MONGO_URI resolves to an explicit localhost default instead of
MongoClient(None), which silently did the same thing without saying so.
"""

import logging

from pymongo import MongoClient

from config import settings


logger = logging.getLogger(__name__)


client = MongoClient(
    settings.mongo_uri,
    serverSelectionTimeoutMS=settings.mongo_timeout_ms,
    tz_aware=True
)

db = client[settings.db_name]


def ping():
    """
    True when the server answers. Never raises.

    Used by /api/health, which must return a body describing the outage
    rather than propagating a connection error.
    """

    try:
        db.command("ping")
        return True

    except Exception as error:
        logger.warning("MongoDB ping failed: %s", error)
        return False


def close():
    """Release the connection pool at shutdown."""

    try:
        client.close()
    except Exception:
        logger.exception("Error while closing the MongoDB client")
