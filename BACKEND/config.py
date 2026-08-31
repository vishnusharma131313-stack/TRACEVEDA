"""
Central configuration, read from the environment exactly once.

Every tunable that used to be a literal in the middle of a route lives here,
so deploying to a new machine is an .env change rather than a code change.

DEVELOPMENT FALLBACKS
---------------------
The app must start on a fresh clone with no .env at all - a demo that dies on
a missing variable is worse than one that starts loudly degraded. So the two
secrets fall back to generated/dev values AND log a warning that names the
variable to set. `settings.is_hardened` reports whether both were supplied,
and `GET /api/health` surfaces it.
"""

import logging
import os
import secrets

from dotenv import load_dotenv


load_dotenv()

logger = logging.getLogger(__name__)


def _env(name, default=None):
    """Read a variable, treating an empty/whitespace value as absent."""

    value = os.getenv(name)

    if value is None or not value.strip():
        return default

    return value.strip()


def _env_int(name, default):

    raw = _env(name)

    if raw is None:
        return default

    try:
        return int(raw)
    except ValueError:
        logger.warning(
            "%s=%r is not an integer; falling back to %s", name, raw, default
        )
        return default


def _env_list(name, default):
    """Comma-separated list, e.g. TRACEVEDA_CORS_ORIGINS=http://a,http://b"""

    raw = _env(name)

    if raw is None:
        return list(default)

    return [item.strip() for item in raw.split(",") if item.strip()]


class Settings:

    def __init__(self):

        # ---------- database ----------
        self.mongo_uri = _env("MONGO_URI", "mongodb://localhost:27017")
        self.db_name = _env("DB_NAME", "traceveda")
        self.mongo_timeout_ms = _env_int("MONGO_TIMEOUT_MS", 5000)

        # ---------- auth ----------
        self.jwt_secret = _env("TRACEVEDA_JWT_SECRET")
        self.jwt_secret_supplied = self.jwt_secret is not None

        if not self.jwt_secret_supplied:
            # Ephemeral on purpose: a hardcoded fallback secret in a public
            # repo is worse than sessions that end at restart.
            self.jwt_secret = secrets.token_urlsafe(48)

        self.jwt_algorithm = "HS256"
        self.jwt_issuer = "traceveda"
        self.access_token_minutes = _env_int("TRACEVEDA_TOKEN_MINUTES", 12 * 60)

        # ---------- device ingest ----------
        self.device_api_key = _env("TRACEVEDA_DEVICE_API_KEY")
        self.device_key_supplied = self.device_api_key is not None

        if not self.device_key_supplied:
            self.device_api_key = "traceveda-dev-device-key"

        # ---------- http ----------
        self.cors_origins = _env_list(
            "TRACEVEDA_CORS_ORIGINS",
            [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:4173",
                "http://127.0.0.1:4173",
            ],
        )

        # ---------- query limits ----------
        # 11k+ seeded IoT readings live in one collection; an unbounded
        # find() on it is the slowest thing this API can be asked to do.
        self.default_page_size = _env_int("TRACEVEDA_PAGE_SIZE", 200)
        self.max_page_size = _env_int("TRACEVEDA_MAX_PAGE_SIZE", 2000)

    @property
    def is_hardened(self):
        """True when no secret is running on a generated development value."""

        return self.jwt_secret_supplied and self.device_key_supplied

    def warn_about_fallbacks(self):
        """Called once at startup so the operator sees exactly what is unset."""

        if not self.jwt_secret_supplied:
            logger.warning(
                "TRACEVEDA_JWT_SECRET is not set - using a random secret for "
                "this process only. Every issued token becomes invalid when "
                "the server restarts. Set it in BACKEND/.env before a demo."
            )

        if not self.device_key_supplied:
            logger.warning(
                "TRACEVEDA_DEVICE_API_KEY is not set - IoT ingest accepts the "
                "development key %r. Set it in BACKEND/.env and flash the "
                "same value to the ESP32 nodes.",
                self.device_api_key,
            )

        if "*" in self.cors_origins:
            logger.warning(
                "TRACEVEDA_CORS_ORIGINS=* allows any website to call this API "
                "with a user's token. Set an explicit origin list."
            )


settings = Settings()
