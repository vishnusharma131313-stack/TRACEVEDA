from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.accounts import (
    authenticate,
    create_user
)


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

            detail=
                "Invalid username or password"

        )


    return {

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

            "message":
                "Account created successfully",

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

        "message":
            "Authentication endpoint available"

    }