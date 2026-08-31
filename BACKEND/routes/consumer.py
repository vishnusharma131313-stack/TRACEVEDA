from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from database import db
from dependencies import get_optional_user, require_authenticated, require_roles
from models.schemas import ConsumerReportRequest
from services import ids
from services.accounts import REGULATOR
from services.timeutils import to_utc_iso


router = APIRouter(
    prefix="/api/consumer",
    tags=["Consumer"]
)


# The workflow a report can be in. Any string at all used to be accepted and
# written straight onto the document, so a typo silently created a status no
# screen knows how to render.
ReportStatus = Literal[
    "OPEN",
    "UNDER_INVESTIGATION",
    "RESOLVED",
    "DISMISSED",
    "CLOSED",
]


# =========================
# CREATE CONSUMER REPORT
# =========================
# PUBLIC. Someone who has just taken a suspect medicine has no account and
# must not need one to report it. The QR/batch pair is verified instead, so a
# report can only be filed against a real product.
# =========================

@router.post("/reports", status_code=201)
def create_consumer_report(
    data: ConsumerReportRequest,
    reporter: Optional[dict] = Depends(get_optional_user),
):

    # One query, not two: the previous pair of lookups reported "batch not
    # found" and "QR does not belong to this batch" separately, which let an
    # anonymous caller confirm which batch ids exist.
    medicine = db.medicine_batches.find_one(
        {
            "medicine_batch_id": data.medicine_batch_id,
            "qr_id": data.qr_id
        },
        {"_id": 1}
    )

    if not medicine:
        raise HTTPException(
            status_code=404,
            detail="No medicine batch matches that batch id and QR code"
        )

    report_id = ids.mint("consumer_report")

    report = {
        "report_id": report_id,
        "medicine_batch_id": data.medicine_batch_id,
        "qr_id": data.qr_id,
        "reported_at": to_utc_iso(data.reported_at),
        "issue_type": data.issue_type,
        "symptoms": data.symptoms,
        "description": data.description,
        # A consumer cannot open a report in any state but OPEN; letting the
        # request body choose meant a report could arrive pre-dismissed.
        "report_status": "OPEN",
        "is_synthetic": data.is_synthetic,
        "reported_by": reporter.get("username") if reporter else None,
        "created_at": datetime.now(timezone.utc)
    }

    db.consumer_reports.insert_one(report)

    return {
        "report_id": report_id,
        "medicine_batch_id": data.medicine_batch_id,
        "qr_id": data.qr_id,
        "report_status": "OPEN",
        "status": "CREATED"
    }


# =========================
# GET REPORT
# =========================

@router.get("/reports/{report_id}")
def get_consumer_report(
    report_id: str,
    user: dict = Depends(require_authenticated),
):

    report = db.consumer_reports.find_one(
        {"report_id": report_id},
        {"_id": 0}
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Consumer report not found"
        )

    return report


# =========================
# GET REPORTS FOR MEDICINE
# =========================

@router.get("/reports/batch/{medicine_batch_id}")
def get_batch_consumer_reports(
    medicine_batch_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    user: dict = Depends(require_authenticated),
):

    reports = list(
        db.consumer_reports.find(
            {"medicine_batch_id": medicine_batch_id},
            {"_id": 0}
        ).sort("reported_at", -1).limit(limit)
    )

    return {
        "medicine_batch_id": medicine_batch_id,
        "reports": reports,
        "count": len(reports)
    }


# =========================
# UPDATE REPORT STATUS
# =========================
# Closing an adverse-event report is a regulatory act. It was previously an
# unauthenticated PATCH taking an arbitrary string as a query parameter.
# =========================

@router.patch("/reports/{report_id}/status")
def update_report_status(
    report_id: str,
    status: ReportStatus = Body(embed=True),
    user: dict = Depends(require_roles(REGULATOR)),
):

    result = db.consumer_reports.update_one(
        {"report_id": report_id},
        {
            "$set": {
                "report_status": status,
                "updated_by": user["username"],
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=404,
            detail="Consumer report not found"
        )

    return {
        "report_id": report_id,
        "report_status": status,
        "status": "UPDATED"
    }
