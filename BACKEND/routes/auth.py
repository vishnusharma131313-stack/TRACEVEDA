"""Authentication and administrator-managed account endpoints."""

import hashlib
import hmac
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from database import db
from dependencies import get_current_user, require_roles
from services import accounts
from services.security import create_access_token, hash_password

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)




class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class ActivateAccountRequest(BaseModel):
    request_id: str = Field(min_length=4, max_length=100)
    recovery_code: str = Field(min_length=24, max_length=128)
    password: str = Field(min_length=8, max_length=128)


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


@router.post("/activate")
def activate_account(data: ActivateAccountRequest, response: Response):
    """Activate an approved account using its one-time applicant recovery code."""
    response.headers["Cache-Control"] = "no-store"
    request = db.access_requests.find_one({"request_id": data.request_id})
    if not request:
        raise HTTPException(status_code=404, detail="Request ID or recovery code is incorrect.")

    supplied_hash = hashlib.sha256(f"{data.request_id}:{data.recovery_code}".encode("utf-8")).hexdigest()
    stored_hash = request.get("claim_code_hash") or ""
    if not stored_hash or not hmac.compare_digest(stored_hash, supplied_hash):
        raise HTTPException(status_code=404, detail="Request ID or recovery code is incorrect.")

    if request.get("status") != "APPROVED":
        if request.get("status") == "PENDING":
            raise HTTPException(status_code=409, detail="Your application is still awaiting administrator approval.")
        if request.get("status") == "REJECTED":
            raise HTTPException(status_code=403, detail="This application was not approved.")
        raise HTTPException(status_code=409, detail="This application is not ready for activation.")

    now = datetime.now(timezone.utc)
    if request.get("claim_code_used_at"):
        raise HTTPException(status_code=409, detail="This recovery code has already been used. Please sign in instead.")
    if request.get("claim_code_expires_at") and request["claim_code_expires_at"] <= now:
        raise HTTPException(status_code=410, detail="This recovery code has expired. Contact the administrator.")

    username = request.get("provisioned_username")
    if not username:
        raise HTTPException(status_code=409, detail="The approved account is unavailable. Contact the administrator.")

    result = db.users.update_one(
        {"username": username, "is_active": False},
        {"$set": {
            "password_hash": hash_password(data.password),
            "is_active": True,
            "must_change_password": False,
            "activated_at": now,
        }},
    )
    if result.matched_count != 1:
        raise HTTPException(status_code=409, detail="This account is already active or unavailable.")

    claim_result = db.access_requests.update_one(
        {"_id": request["_id"], "claim_code_used_at": None},
        {"$set": {"claim_code_used_at": now, "activation_status": "ACTIVATED"}},
    )
    if claim_result.matched_count != 1:
        # A concurrent activation already consumed the recovery code. Deactivate
        # this account update rather than allowing a second activation attempt.
        db.users.update_one({"username": username}, {"$set": {"is_active": False}})
        raise HTTPException(status_code=409, detail="This recovery code has already been used.")

    return {
        "status": "SUCCESS",
        "username": username,
        "message": "Account activated. You can now sign in using your TraceVeda ID and new password.",
    }


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
