"""Public access requests and administrator review workflow."""

import secrets
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from database import db
from dependencies import require_roles
from services import accounts, ids


router = APIRouter(prefix="/api/access-requests", tags=["Access Requests"])

REQUESTABLE_ROLES = {
    "farmer": accounts.FARMER,
    "processor": accounts.PROCESSOR,
    "lab": accounts.LAB,
    "manufacturer": accounts.MANUFACTURER,
    "transporter": accounts.LOGISTICS,
    "logistics": accounts.LOGISTICS,
    "auditor": accounts.REGULATOR,
    "regulator": accounts.REGULATOR,
}


class AccessRequestCreate(BaseModel):
    role: str = Field(min_length=1, max_length=32)
    organisation_name: str = Field(min_length=2, max_length=160)
    location: str = Field(min_length=2, max_length=160)
    contact_details: str = Field(min_length=5, max_length=200)

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        role = value.strip().lower()
        if role not in REQUESTABLE_ROLES:
            raise ValueError("This role cannot be requested. Administrator access is assigned internally.")
        return REQUESTABLE_ROLES[role]

    @field_validator("organisation_name", "location", "contact_details")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank")
        return value


class AccessRequestDecision(BaseModel):
    decision: Literal["APPROVE", "REJECT"]
    admin_notes: Optional[str] = Field(default=None, max_length=1000)


@router.post("", status_code=201)
def submit_access_request(data: AccessRequestCreate):
    """Public form submission. No account is created before approval."""
    duplicate = db.access_requests.find_one(
        {
            "role": data.role,
            "contact_details": data.contact_details,
            "status": "PENDING",
        },
        {"_id": 0, "request_id": 1},
    )
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=f"A pending request already exists ({duplicate['request_id']}).",
        )

    request_id = ids.mint("access_request")
    request = {
        "request_id": request_id,
        "role": data.role,
        "organisation_name": data.organisation_name,
        "location": data.location,
        "contact_details": data.contact_details,
        "status": "PENDING",
        "submitted_at": datetime.now(timezone.utc),
        "reviewed_at": None,
        "reviewed_by": None,
        "admin_notes": None,
        "provisioned_username": None,
    }
    db.access_requests.insert_one(request)
    return {
        "request_id": request_id,
        "status": "PENDING",
        "message": "Your access request has been submitted for review.",
    }


@router.get("")
def list_access_requests(
    status: Optional[Literal["PENDING", "APPROVED", "REJECTED"]] = None,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _admin: dict = Depends(require_roles(accounts.ADMIN)),
):
    query = {"status": status} if status else {}
    requests = list(
        db.access_requests.find(query, {"_id": 0})
        .sort("submitted_at", -1)
        .skip(offset)
        .limit(limit)
    )
    return {
        "requests": requests,
        "count": len(requests),
        "total": db.access_requests.count_documents(query),
    }


@router.patch("/{request_id}/decision")
def decide_access_request(
    request_id: str,
    data: AccessRequestDecision,
    admin: dict = Depends(require_roles(accounts.ADMIN)),
):
    request = db.access_requests.find_one({"request_id": request_id}, {"_id": 0})
    if not request:
        raise HTTPException(status_code=404, detail="Access request not found")
    if request.get("status") != "PENDING":
        raise HTTPException(status_code=409, detail="This request has already been reviewed")

    now = datetime.now(timezone.utc)
    update = {
        "status": "APPROVED" if data.decision == "APPROVE" else "REJECTED",
        "reviewed_at": now,
        "reviewed_by": admin["username"],
        "admin_notes": (data.admin_notes or "").strip() or None,
    }
    response = {"request_id": request_id, "status": update["status"]}

    if data.decision == "APPROVE":
        # Generate a one-time password. Only its hash is stored in MongoDB;
        # the plaintext is returned once to the administrator for hand-off.
        temporary_password = secrets.token_urlsafe(9)
        try:
            user = accounts.create_user(
                password=temporary_password,
                role=request["role"],
                full_name=request["organisation_name"],
                organisation_id=request["organisation_name"],
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        update["provisioned_username"] = user["username"]
        response.update({
            "username": user["username"],
            "temporary_password": temporary_password,
            "role": user["role"],
            "message": "Request approved and stakeholder account created. Share these credentials securely; the password is shown only once.",
        })
    else:
        response["message"] = "Access request rejected."

    db.access_requests.update_one({"request_id": request_id}, {"$set": update})
    return response
