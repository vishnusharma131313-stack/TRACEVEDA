"""
Regulatory investigations opened against a consumer report.

Documented in docs/API_CONTRACT.md and never implemented, even though
investigations.csv ships 20 rows and import_csv.py loads them - so the data
was in the database with no way to reach it.

An investigation is the regulator's side of the consumer report loop:
a report comes in on the public endpoint, a regulator opens an investigation
against it, and closing the investigation records the root cause and the
action taken.
"""

from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from database import db
from dependencies import require_roles
from services import ids
from services.accounts import REGULATOR


router = APIRouter(prefix="/api/investigations", tags=["Investigations"])


InvestigationStatus = Literal["OPEN", "IN_PROGRESS", "CLOSED"]


class InvestigationRequest(BaseModel):
    report_id: str = Field(min_length=1, max_length=64)
    auditor_id: str = Field(min_length=1, max_length=64)
    suspected_stage: str = Field(default="UNKNOWN", max_length=64)
    evidence_summary: Optional[str] = Field(default=None, max_length=5000)


class InvestigationCloseRequest(BaseModel):
    root_cause: str = Field(min_length=1, max_length=500)
    action_taken: str = Field(min_length=1, max_length=500)
    evidence_summary: Optional[str] = Field(default=None, max_length=5000)


@router.post("", status_code=201)
def open_investigation(
    data: InvestigationRequest,
    user: dict = Depends(require_roles(REGULATOR)),
):

    report = db.consumer_reports.find_one(
        {"report_id": data.report_id}, {"_id": 1}
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Consumer report not found"
        )

    existing = db.investigations.find_one(
        {"report_id": data.report_id, "investigation_status": {"$ne": "CLOSED"}},
        {"_id": 0, "investigation_id": 1}
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Report {data.report_id} already has an open investigation "
                f"({existing['investigation_id']})"
            )
        )

    investigation_id = ids.mint("investigation")

    investigation = {
        "investigation_id": investigation_id,
        "report_id": data.report_id,
        "auditor_id": data.auditor_id,
        "opened_at": datetime.now(timezone.utc),
        "suspected_stage": data.suspected_stage,
        "evidence_summary": data.evidence_summary,
        "root_cause": None,
        "investigation_status": "OPEN",
        "action_taken": None,
        "closed_at": None,
        "opened_by": user["username"],
    }

    db.investigations.insert_one(investigation)

    # Opening an investigation moves the report out of the inbox.
    db.consumer_reports.update_one(
        {"report_id": data.report_id},
        {
            "$set": {
                "report_status": "UNDER_INVESTIGATION",
                "updated_by": user["username"],
                "updated_at": datetime.now(timezone.utc),
            }
        }
    )

    return {
        "investigation_id": investigation_id,
        "report_id": data.report_id,
        "investigation_status": "OPEN",
        "status": "CREATED",
    }


@router.get("")
def list_investigations(
    status: Optional[InvestigationStatus] = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(require_roles(REGULATOR)),
):

    query = {} if status is None else {"investigation_status": status}

    investigations = list(
        db.investigations.find(query, {"_id": 0})
        .sort("opened_at", -1)
        .skip(offset)
        .limit(limit)
    )

    return {
        "investigations": investigations,
        "count": len(investigations),
        "total": db.investigations.count_documents(query),
    }


@router.get("/{investigation_id}")
def get_investigation(
    investigation_id: str,
    user: dict = Depends(require_roles(REGULATOR)),
):

    investigation = db.investigations.find_one(
        {"investigation_id": investigation_id}, {"_id": 0}
    )

    if not investigation:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found"
        )

    # The report it was opened against, for context.
    investigation["report"] = db.consumer_reports.find_one(
        {"report_id": investigation.get("report_id")}, {"_id": 0}
    )

    return investigation


@router.patch("/{investigation_id}/close")
def close_investigation(
    investigation_id: str,
    data: InvestigationCloseRequest,
    user: dict = Depends(require_roles(REGULATOR)),
):

    investigation = db.investigations.find_one(
        {"investigation_id": investigation_id},
        {"_id": 0, "investigation_status": 1, "report_id": 1}
    )

    if not investigation:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found"
        )

    if investigation.get("investigation_status") == "CLOSED":
        raise HTTPException(
            status_code=409,
            detail="Investigation is already closed"
        )

    closed_at = datetime.now(timezone.utc)

    update = {
        "investigation_status": "CLOSED",
        "root_cause": data.root_cause,
        "action_taken": data.action_taken,
        "closed_at": closed_at,
        "closed_by": user["username"],
    }

    if data.evidence_summary is not None:
        update["evidence_summary"] = data.evidence_summary

    db.investigations.update_one(
        {"investigation_id": investigation_id},
        {"$set": update}
    )

    db.consumer_reports.update_one(
        {"report_id": investigation.get("report_id")},
        {
            "$set": {
                "report_status": "RESOLVED",
                "updated_by": user["username"],
                "updated_at": closed_at,
            }
        }
    )

    return {
        "investigation_id": investigation_id,
        "investigation_status": "CLOSED",
        "root_cause": data.root_cause,
        "action_taken": data.action_taken,
        "status": "UPDATED",
    }
