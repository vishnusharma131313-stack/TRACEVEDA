from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.accounts import (
    authenticate,
    create_user
)

from services.security import create_access_token


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)


# =========================
# LOGIN REQUEST
# =========================

class LoginRequest(BaseModel):
    username: str
    password: str


# =========================
# SIGNUP REQUEST
# =========================

class SignupRequest(BaseModel):
    password: str
    role: str
    full_name: str | None = None


# =========================
# LOGIN
# =========================

@router.post("/login")
def login(data: LoginRequest):

    user = authenticate(
        username=data.username,
        password=data.password
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    username = user.get("username")
    role = user.get("role")

    # Create JWT access token
    access_token, expires_at = create_access_token(
        username=username,
        role=role
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_at": expires_at,

        "username": username,
        "role": role,
        "full_name": user.get("full_name"),
        "organisation_id": user.get("organisation_id"),

        # Keep this for compatibility with your existing UI
        "status": "SUCCESS",
        "user": user
    }


# =========================
# SIGNUP
# =========================

@router.post("/signup")
def signup(data: SignupRequest):

    try:

        user = create_user(
            password=data.password,
            role=data.role,
            full_name=data.full_name
        )

        return {
            "status": "SUCCESS",
            "message": "Account created successfully",
            "user": user
        }

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )


# =========================
# CURRENT USER
# =========================

@router.get("/me")
def get_current_user():

    return {
        "message": "Authentication endpoint available"
    }