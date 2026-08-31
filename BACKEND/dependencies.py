"""
Authentication and authorisation dependencies.

One place decides who a request is (`get_current_user`) and one place decides
whether they may proceed (`require_roles`). Routes declare their requirement
and never inspect a token themselves.

    @router.post("/raw")
    def create_raw_batch(
        data: RawBatchRequest,
        user: dict = Depends(require_roles(FARMER, ADMIN)),
    ):

Failure modes are kept distinct on purpose:

    401  no credentials, or credentials that are not valid
    403  valid credentials belonging to a role that may not do this

Collapsing them into one status makes a misconfigured demo account
indistinguishable from an expired token, which is a miserable thing to debug
ten minutes before a presentation.
"""

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services import accounts
from services.security import TokenError, verify_device_key, verify_token


# auto_error=False so a missing header reaches our own handler and produces
# a message that says what to do, instead of Starlette's bare "Not authenticated".
bearer_scheme = HTTPBearer(auto_error=False, description="JWT from /api/auth/login")


UNAUTHENTICATED_HEADERS = {"WWW-Authenticate": "Bearer"}


def _unauthenticated(detail):

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers=UNAUTHENTICATED_HEADERS
    )


# =========================
# IDENTITY
# =========================

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
):
    """
    The authenticated user behind this request.

    The account is re-read on every request rather than trusted from the
    token, so deactivating a user takes effect immediately instead of when
    their token happens to expire.
    """

    if credentials is None:
        raise _unauthenticated(
            "Not authenticated. Send 'Authorization: Bearer <token>' from "
            "POST /api/auth/login."
        )

    try:
        claims = verify_token(credentials.credentials)

    except TokenError as error:
        raise _unauthenticated(str(error))

    username = claims.get("sub")

    user = accounts.get_user(username)

    if user is None:
        raise _unauthenticated("Account no longer exists")

    if not user.get("is_active", True):
        raise _unauthenticated("Account is disabled")

    # The stored role wins over the token's copy: a role change must not wait
    # for the old token to expire.
    return {
        "username": user.get("username"),
        "role": user.get("role"),
        "full_name": user.get("full_name"),
        "organisation_id": user.get("organisation_id"),
    }


def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
):
    """
    The user, if any, without ever rejecting the request.

    For public routes that record who acted when a token happens to be
    present - the consumer report endpoint, which must stay open to
    unauthenticated consumers.
    """

    if credentials is None:
        return None

    try:
        claims = verify_token(credentials.credentials)
    except TokenError:
        return None

    return accounts.get_user(claims.get("sub"))


# =========================
# AUTHORISATION
# =========================

def require_roles(*allowed_roles):
    """
    Dependency admitting only the listed roles.

    ADMIN is always admitted: an administrator locked out of an endpoint
    cannot fix the account that is locked out of it.
    """

    permitted = set(allowed_roles) | {accounts.ADMIN}

    def dependency(user: dict = Depends(get_current_user)):

        if user.get("role") not in permitted:

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{user.get('role')}' may not perform this action. "
                    f"Required: {', '.join(sorted(permitted))}."
                )
            )

        return user

    return dependency


def require_authenticated(user: dict = Depends(get_current_user)):
    """Any active account. Used for the read-only internal screens."""

    return user


# =========================
# DEVICE INGEST
# =========================

def require_device_or_roles(*allowed_roles):
    """
    Admits either an IoT node presenting X-Device-Key, or a listed role.

    The ESP32 nodes cannot hold a rotating JWT, so they authenticate with a
    shared device key. Operators posting a reading from the dashboard
    authenticate normally.
    """

    permitted = set(allowed_roles) | {accounts.ADMIN}

    def dependency(
        x_device_key: str = Header(
            default=None,
            alias="X-Device-Key",
            description="Shared key flashed to the IoT nodes"
        ),
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
    ):

        if x_device_key is not None:

            if not verify_device_key(x_device_key):
                raise _unauthenticated("Invalid device key")

            return {"username": "device", "role": "device", "is_device": True}

        if credentials is None:
            raise _unauthenticated(
                "Not authenticated. Send 'X-Device-Key: <key>' from an IoT "
                "node, or 'Authorization: Bearer <token>' from an operator "
                "account."
            )

        try:
            claims = verify_token(credentials.credentials)
        except TokenError as error:
            raise _unauthenticated(str(error))

        user = accounts.get_user(claims.get("sub"))

        if user is None or not user.get("is_active", True):
            raise _unauthenticated("Account no longer exists or is disabled")

        if user.get("role") not in permitted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{user.get('role')}' may not submit readings. "
                    f"Required: {', '.join(sorted(permitted))}, or a valid "
                    "X-Device-Key."
                )
            )

        return {
            "username": user.get("username"),
            "role": user.get("role"),
            "is_device": False,
        }

    return dependency
