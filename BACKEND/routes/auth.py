"""Authentication and administrator-managed account endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from dependencies import get_current_user, require_roles
from services import accounts
from services.security import create_access_token

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)




class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class AdminCreateUserRequest(BaseModel):
    """A user can only be created by an authenticated administrator."""
    password: str = Field(min_length=8)
    role: str
    full_name: str | None = None
    organisation_id: str | None = None
    username: str | None = None


@router.post("/login")
def login(data: LoginRequest):
    user = accounts.authenticate(data.username, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    access_token, expires_at = create_access_token(
        username=user.get("username"),
        role=user.get("role"),
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_at": expires_at,
        "username": user.get("username"),
        "role": user.get("role"),
        "full_name": user.get("full_name"),
        "organisation_id": user.get("organisation_id"),
        "status": "SUCCESS",
        "user": user,
    }




@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    user: dict = Depends(get_current_user),
):
    """Allow stakeholders to change their own password; admin is excluded."""
    if user.get("role") == accounts.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Password changes are disabled for administrator accounts.",
        )

    authenticated = accounts.authenticate(user.get("username"), data.current_password)
    if not authenticated:
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    if data.current_password == data.new_password:
        raise HTTPException(
            status_code=400,
            detail="New password must be different from the current password.",
        )

    if not accounts.set_password(user.get("username"), data.new_password):
        raise HTTPException(status_code=404, detail="Account not found.")

    return {"status": "SUCCESS", "message": "Password changed successfully."}


@router.get("/me")
def get_current_user_profile(user: dict = Depends(get_current_user)):
    """Return the authenticated user's current database-backed profile."""
    return user


@router.get("/roles")
def get_roles():
    """Return supported role identifiers for the administrator UI."""
    return {
        "roles": [
            {"id": role, "label": accounts.ROLE_LABELS[role]}
            for role in accounts.ROLES
        ]
    }


@router.get("/users")
def list_users(_admin: dict = Depends(require_roles(accounts.ADMIN))):
    """List accounts for the administrator UI; never expose credentials."""
    users = accounts.list_users()
    return {"users": users, "count": len(users)}


@router.post("/users", status_code=201)
def admin_create_user(
    data: AdminCreateUserRequest,
    _admin: dict = Depends(require_roles(accounts.ADMIN)),
):
    """Create an account. Public self-registration is intentionally disabled."""
    try:
        user = accounts.create_user(
            password=data.password,
            role=data.role,
            full_name=data.full_name,
            organisation_id=data.organisation_id,
            username=data.username,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {"status": "SUCCESS", "message": "Account created successfully", "user": user}
