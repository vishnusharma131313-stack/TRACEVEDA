from datetime import datetime

from fastapi import APIRouter, HTTPException

from database import db
from models.schemas import ConsumerReportRequest


router = APIRouter(
    prefix="/api/consumer",
    tags=["Consumer"]
)


# =========================
# CREATE CONSUMER REPORT
# =========================

@router.post("/reports")
def create_consumer_report(data: ConsumerReportRequest):

    # Validate medicine batch
    medicine = db.medicine_batches.find_one({
        "medicine_batch_id": data.medicine_batch_id
    })

    if not medicine:
        raise HTTPException(
            status_code=404,
            detail="Medicine batch not found"
        )

    # Validate QR
    qr = db.medicine_batches.find_one({
        "medicine_batch_id": data.medicine_batch_id,
        "qr_id": data.qr_id
    })

    if not qr:
        raise HTTPException(
            status_code=404,
            detail="QR does not belong to this medicine batch"
        )

    # Generate report ID
    count = db.consumer_reports.count_documents({}) + 1

    report_id = (
        f"RPT-{datetime.now().year}-{count:03d}"
    )

    report = {
        "report_id": report_id,
        "medicine_batch_id": data.medicine_batch_id,
        "qr_id": data.qr_id,
        "reported_at": data.reported_at.isoformat(),
        "issue_type": data.issue_type,
        "symptoms": data.symptoms,
        "description": data.description,
        "report_status": data.report_status,
        "is_synthetic": data.is_synthetic,
        "created_at": datetime.utcnow()
    }

    db.consumer_reports.insert_one(report)

    return {
        "report_id": report_id,
        "medicine_batch_id": data.medicine_batch_id,
        "qr_id": data.qr_id,
        "report_status": data.report_status,
        "status": "CREATED"
    }


# =========================
# GET REPORT
# =========================

@router.get("/reports/{report_id}")
def get_consumer_report(report_id: str):

    report = db.consumer_reports.find_one(
        {
            "report_id": report_id
        },
        {
            "_id": 0
        }
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
    medicine_batch_id: str
):

    reports = list(
        db.consumer_reports.find(
            {
                "medicine_batch_id":
                    medicine_batch_id
            },
            {
                "_id": 0
            }
        ).sort(
            "reported_at",
            -1
        )
    )

    return {
        "medicine_batch_id":
            medicine_batch_id,
        "reports": reports,
        "count": len(reports)
    }


# =========================
# UPDATE REPORT STATUS
# =========================

@router.patch("/reports/{report_id}/status")
def update_report_status(
    report_id: str,
    status: str
):

    result = db.consumer_reports.update_one(
        {
            "report_id": report_id
        },
        {
            "$set": {
                "report_status": status,
                "updated_at": datetime.utcnow()
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