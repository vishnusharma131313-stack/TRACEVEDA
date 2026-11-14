"""Public anonymous access applications and administrator review workflow.

Applicants supply contact details but no email/SMS verification is performed.
A random recovery code is shown once to the applicant and only its SHA-256
hash is stored. The code lets the applicant check status and, after admin
approval, set a password exactly once.
"""

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator

from database import db
from dependencies import require_roles
from services import accounts, ids
from services.security import hash_password

router = APIRouter(prefix="/api/access-requests", tags=["Access Requests"])

REQUESTABLE_ROLES = {
    "farmer": accounts.FARMER,
    "processor": accounts.PROCESSOR,
    "lab": accounts.LAB,
    "laboratory": accounts.LAB,
    "manufacturer": accounts.MANUFACTURER,
    "transporter": accounts.LOGISTICS,
    "logistics": accounts.LOGISTICS,
    "auditor": accounts.REGULATOR,
    "regulator": accounts.REGULATOR,
}
CLAIM_CODE_LIFETIME_DAYS = 30


class AccessRequestCreate(BaseModel):
    role: str = Field(min_length=1, max_length=32)
    full_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=6, max_length=254)
    phone: str = Field(min_length=7, max_length=24)
    organisation_name: str = Field(min_length=2, max_length=160)
    location: str = Field(min_length=2, max_length=160)
    designation: str = Field(min_length=2, max_length=120)
    role_details: str = Field(min_length=2, max_length=1000)
    reason: str = Field(min_length=5, max_length=1000)

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        role = value.strip().lower()
        if role not in REQUESTABLE_ROLES:
            raise ValueError("This role cannot be requested. Administrator access is assigned internally.")
        return REQUESTABLE_ROLES[role]

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address.")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        value = value.strip()
        digits = re.sub(r"\D", "", value)
        if not 7 <= len(digits) <= 15:
            raise ValueError("Enter a valid phone number.")
        return value

    @field_validator("full_name", "organisation_name", "location", "designation", "role_details", "reason")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value


class AccessRequestStatusCheck(BaseModel):
    request_id: str = Field(min_length=4, max_length=100)
    recovery_code: str = Field(min_length=24, max_length=128)


class AccessRequestDecision(BaseModel):
    decision: Literal["APPROVE", "REJECT"]
    admin_notes: Optional[str] = Field(default=None, max_length=1000)


def _claim_code_digest(request_id: str, recovery_code: str) -> str:
    # The code is generated from 192 bits of randomness. Hashing it means the
    # database never stores the applicant's bearer secret in plaintext.
    material = f"{request_id}:{recovery_code}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _verify_claim_code(request: dict, recovery_code: str) -> bool:
    stored = request.get("claim_code_hash") or ""
    supplied = _claim_code_digest(request.get("request_id", ""), recovery_code)
    return bool(stored) and hmac.compare_digest(stored, supplied)



def _load_request_for_claim(data: AccessRequestStatusCheck) -> dict:
    request = db.access_requests.find_one({"request_id": data.request_id})
    if not request:
        raise HTTPException(status_code=404, detail="Request ID or recovery code is incorrect.")
    if not _verify_claim_code(request, data.recovery_code):
        raise HTTPException(status_code=404, detail="Request ID or recovery code is incorrect.")
    return request


@router.post("", status_code=201)
def submit_access_request(data: AccessRequestCreate, response: Response):
    """Submit a public application; no account or contact verification is created."""
    response.headers["Cache-Control"] = "no-store"
    now = datetime.now(timezone.utc)
    email = data.email
    phone = data.phone

    existing_user = db.users.find_one({"$or": [{"email": email}, {"phone": phone}]}, {"_id": 1})
    if existing_user:
        raise HTTPException(status_code=409, detail="An account already uses this email address or phone number. Please sign in or contact the administrator.")

    duplicate = db.access_requests.find_one({
        "status": "PENDING",
        "$or": [{"email": email}, {"phone": phone}],
    }, {"_id": 0, "request_id": 1})
    if duplicate:
        raise HTTPException(status_code=409, detail=f"A pending application already exists for these contact details ({duplicate['request_id']}).")

    recent = db.access_requests.count_documents({
        "$or": [{"email": email}, {"phone": phone}],
        "submitted_at": {"$gte": now - timedelta(hours=24)},
    })
    if recent >= 3:
        raise HTTPException(status_code=429, detail="Too many applications were submitted using these contact details. Try again later or contact the administrator.")

    request_id = ids.mint("access_request")
    recovery_code = secrets.token_urlsafe(24)
    request = {
        "request_id": request_id,
        **data.model_dump(),
        "email_verified": False,
        "phone_verified": False,
        "status": "PENDING",
        "submitted_at": now,
        "reviewed_at": None,
        "reviewed_by": None,
        "admin_notes": None,
        "provisioned_username": None,
        "claim_code_hash": _claim_code_digest(request_id, recovery_code),
        "claim_code_expires_at": now + timedelta(days=CLAIM_CODE_LIFETIME_DAYS),
        "claim_code_used_at": None,
        "activation_status": "NOT_AVAILABLE",
    }
    db.access_requests.insert_one(request)

    # The plaintext recovery code is returned exactly once. It is never stored
    # in the chat history, admin queue, or MongoDB.
    return {
        "request_id": request_id,
        "recovery_code": recovery_code,
        "recovery_code_expires_at": request["claim_code_expires_at"],
        "status": "PENDING",
        "role": data.role,
        "message": "Application submitted. Save the recovery code; it will not be shown again. An administrator must approve the request.",
    }


@router.post("/status")
def check_access_request_status(data: AccessRequestStatusCheck, response: Response):
    """Return limited status details to the applicant who holds the recovery code."""
    response.headers["Cache-Control"] = "no-store"
    request = _load_request_for_claim(data)
    now = datetime.now(timezone.utc)
    activated = bool(request.get("claim_code_used_at")) or request.get("activation_status") == "ACTIVATED"
    if (not activated and request.get("status") == "APPROVED"
            and request.get("claim_code_expires_at")
            and request["claim_code_expires_at"] <= now):
        raise HTTPException(status_code=410, detail="The recovery code has expired. Contact the administrator.")

    status = "ACTIVATED" if activated else request.get("status", "PENDING")
    result = {
        "request_id": request["request_id"],
        "status": status,
        "role": request.get("role"),
        "message": "Your account is active." if activated else "Your application is awaiting administrator review." if status == "PENDING" else "Your application was approved. You can now create your password." if status == "APPROVED" else "Your application was not approved.",
    }
    if status in {"APPROVED", "ACTIVATED"}:
        result["username"] = request.get("provisioned_username")
    if status == "REJECTED" and request.get("admin_notes"):
        result["admin_notes"] = request["admin_notes"]
    return result


@router.get("")
def list_access_requests(
    status: Optional[Literal["PENDING", "APPROVED", "REJECTED"]] = None,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _admin: dict = Depends(require_roles(accounts.ADMIN)),
):
    """Only administrators can inspect the full application records."""
    query = {"status": status} if status else {}
    requests = list(
        db.access_requests.find(query, {"_id": 0, "claim_code_attempts": 0})
        .sort("submitted_at", -1)
        .skip(offset)
        .limit(limit)
    )
    for request in requests:
        request["activation_ready"] = bool(
            request.get("claim_code_hash")
            and request.get("email")
            and request.get("phone")
            and request.get("full_name")
            and request.get("organisation_name")
        )
        # The admin UI receives readiness only, never the bearer-code hash.
        request.pop("claim_code_hash", None)
    return {"requests": requests, "count": len(requests), "total": db.access_requests.count_documents(query)}


@router.patch("/{request_id}/decision")
def decide_access_request(
    request_id: str,
    data: AccessRequestDecision,
    admin: dict = Depends(require_roles(accounts.ADMIN)),
):
    request = db.access_requests.find_one({"request_id": request_id})
    if not request:
        raise HTTPException(status_code=404, detail="Access request not found")
    if request.get("status") != "PENDING":
        raise HTTPException(status_code=409, detail="This request has already been reviewed")

    now = datetime.now(timezone.utc)
    admin_notes = (data.admin_notes or "").strip() or None
    if data.decision == "REJECT":
        update = {
            "status": "REJECTED",
            "reviewed_at": now,
            "reviewed_by": admin["username"],
            "admin_notes": admin_notes,
        }
        db.access_requests.update_one({"_id": request["_id"], "status": "PENDING"}, {"$set": update})
        return {"request_id": request_id, "status": "REJECTED", "message": "Access request rejected. No account was created."}

    if not request.get("claim_code_hash") or not request.get("email") or not request.get("phone"):
        raise HTTPException(status_code=400, detail="This is a legacy application without a recovery code. Ask the applicant to submit a new request through TraceVeda Assistant.")
    if request.get("role") not in set(REQUESTABLE_ROLES.values()):
        raise HTTPException(status_code=403, detail="This role cannot be provisioned through public access requests. Administrator accounts must be created internally.")
    if db.users.find_one({"$or": [{"email": request["email"]}, {"phone": request["phone"]}]}, {"_id": 1}):
        raise HTTPException(status_code=409, detail="An account already uses this applicant email address or phone number.")

    # The random bootstrap password is never returned and the account is
    # disabled immediately. Only the applicant's recovery code can activate it.
    bootstrap_password = secrets.token_urlsafe(36)
    try:
        user = accounts.create_user(
            password=bootstrap_password,
            role=request["role"],
            full_name=request.get("full_name") or request["organisation_name"],
            organisation_id=request["organisation_name"],
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    db.users.update_one(
        {"username": user["username"]},
        {"$set": {
            "is_active": False,
            "email": request["email"],
            "phone": request["phone"],
            "designation": request.get("designation"),
            "must_change_password": True,
            "email_verified": False,
            "phone_verified": False,
            "access_request_id": request_id,
        }},
    )

    update = {
        "status": "APPROVED",
        "reviewed_at": now,
        "reviewed_by": admin["username"],
        "admin_notes": admin_notes,
        "provisioned_username": user["username"],
        "activation_status": "READY",
        # Start the activation window from approval, not submission.
        "claim_code_expires_at": now + timedelta(days=CLAIM_CODE_LIFETIME_DAYS),
    }
    result = db.access_requests.update_one(
        {"_id": request["_id"], "status": "PENDING"},
        {"$set": update},
    )
    if result.matched_count != 1:
        db.users.delete_one({"username": user["username"], "is_active": False})
        raise HTTPException(status_code=409, detail="This request was reviewed by another administrator. Refresh the request list.")

    return {
        "request_id": request_id,
        "status": "APPROVED",
        "username": user["username"],
        "activation_expires_at": update["claim_code_expires_at"],
        "message": "Account approved. The applicant must use the recovery code they saved at submission to create a password. No email or SMS was sent.",
    }
