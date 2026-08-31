"""
Password hashing and access tokens.

PASSWORD HASHING
----------------
PBKDF2-HMAC-SHA256 from the standard library, at the OWASP-recommended
iteration count. Deliberately not bcrypt/argon2: those pull in a compiled
dependency whose version skew is a common way for a working checkout to stop
importing on someone else's machine, and PBKDF2 at 600k iterations is an
accepted choice. Hashes are self-describing -

    pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>

- so the iteration count can be raised later without invalidating old hashes.

TOKENS
------
Short-lived HS256 JWTs carrying the user's role. Stateless: there is no
server-side session to fall out of sync, and `verify_token` is the only place
that decides whether a request is authenticated.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from config import settings


PBKDF2_ITERATIONS = 600_000
PBKDF2_ALGORITHM = "pbkdf2_sha256"
SALT_BYTES = 16


class TokenError(Exception):
    """Raised when a token is missing, malformed, expired or not ours."""


# =========================
# PASSWORDS
# =========================

def hash_password(password):
    """Hash a plaintext password into a self-describing PBKDF2 string."""

    if not isinstance(password, str) or not password:
        raise ValueError("password must be a non-empty string")

    salt = secrets.token_bytes(SALT_BYTES)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS
    )

    return (
        f"{PBKDF2_ALGORITHM}${PBKDF2_ITERATIONS}"
        f"${salt.hex()}${digest.hex()}"
    )


def verify_password(password, stored):
    """
    Constant-time check of a plaintext password against a stored hash.

    Returns False rather than raising for any malformed stored value: a
    corrupt user document must fail the login, not 500 the endpoint.
    """

    if not password or not isinstance(stored, str):
        return False

    parts = stored.split("$")

    if len(parts) != 4 or parts[0] != PBKDF2_ALGORITHM:
        return False

    _, iterations, salt_hex, expected_hex = parts

    try:
        iterations = int(iterations)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hex)
    except ValueError:
        return False

    if iterations < 1 or not salt or not expected:
        return False

    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations
    )

    return hmac.compare_digest(candidate, expected)


# =========================
# TOKENS
# =========================

def create_access_token(username, role, expires_minutes=None):
    """Sign a short-lived access token for one user."""

    if expires_minutes is None:
        expires_minutes = settings.access_token_minutes

    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(minutes=expires_minutes)

    payload = {
        "sub": username,
        "role": role,
        "iss": settings.jwt_issuer,
        "iat": issued_at,
        "exp": expires_at
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm
    )

    # PyJWT < 2 returned bytes. Normalising here keeps the response model
    # honest whichever version is installed.
    if isinstance(token, bytes):
        token = token.decode("utf-8")

    return token, int(expires_at.timestamp())


def verify_token(token):
    """
    Decode and validate a token, returning its claims.

    The algorithm is pinned to a single value: accepting a list that includes
    "none", or letting the token name its own algorithm, is the classic JWT
    forgery route.
    """

    if not token:
        raise TokenError("Missing token")

    try:

        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "sub", "iss"]}
        )

    except jwt.ExpiredSignatureError:
        raise TokenError("Token has expired")

    except jwt.InvalidTokenError as error:
        raise TokenError(f"Invalid token: {error}")

    if not claims.get("sub") or not claims.get("role"):
        raise TokenError("Token is missing required claims")

    return claims


# =========================
# DEVICE KEY
# =========================

def verify_device_key(presented):
    """Constant-time comparison of an IoT node's X-Device-Key header."""

    if not presented:
        return False

    return hmac.compare_digest(
        str(presented),
        settings.device_api_key
    )
