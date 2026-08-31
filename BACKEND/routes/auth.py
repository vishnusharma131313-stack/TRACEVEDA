from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.accounts import authenticate


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)


# =========================
# REQUEST MODEL
# =========================

class LoginRequest(BaseModel):
    username: str
    password: str


# =========================
# LOGIN
# =========================

@router.post("/login")
def login(data: LoginRequest):

    user = authenticate(
        data.username,
        data.password
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    return {
        "status": "SUCCESS",
        "user": {
            "username": user.get("username"),
            "role": user.get("role"),
            "user_id": user.get("user_id")
        }
    }


@router.get("/me")
def get_current_user():

    return {
        "message": "Authentication endpoint available"
    }