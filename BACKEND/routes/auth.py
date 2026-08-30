"""
Authentication endpoints.

    POST /api/auth/login   username + password -> access token
    GET  /api/auth/me      the caller's own account
    GET  /api/auth/roles   the role vocabulary, for the login screen

These are the two endpoints docs/API_CONTRACT.md has always listed and that
main.py never mounted.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from config import settings
from dependencies import get_current_user
from services import accounts
from services.security import create_access_token


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# =========================
# MODELS
# =========================

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: int
    username: str
    role: str
    full_name: str | None = None


class UserResponse(BaseModel):
    username: str
    role: str
    full_name: str | None = None
    organisation_id: str | None = None


# =========================
# LOGIN
# =========================

@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest):

    user = accounts.authenticate(data.username, data.password)

    if user is None:

        # One message for "no such user" and "wrong password" alike, so the
        # endpoint cannot be used to discover which usernames exist.
        logger.info("Failed login attempt for %r", data.username)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token, expires_at = create_access_token(
        user["username"],
        user["role"]
    )

    return LoginResponse(
        access_token=token,
        expires_at=expires_at,
        username=user["username"],
        role=user["role"],
        full_name=user.get("full_name")
    )


# =========================
# CURRENT USER
# =========================

@router.get("/me", response_model=UserResponse)
def read_current_user(user: dict = Depends(get_current_user)):

    return UserResponse(**user)


# =========================
# ROLE VOCABULARY
# =========================

@router.get("/roles")
def list_roles():
    """
    The roles this server accepts.

    Public: the login screen renders it before anyone has a token, and it
    reveals nothing an attacker could not read in the repository.
    """

    return {
        "roles": [
            {"id": role, "label": accounts.ROLE_LABELS[role]}
            for role in accounts.ROLES
        ],
        "token_lifetime_minutes": settings.access_token_minutes,
    }
