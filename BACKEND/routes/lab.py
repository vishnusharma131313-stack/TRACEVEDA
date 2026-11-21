import hashlib
import json
import logging
import re
from datetime import date, datetime, timezone
from typing import Literal
from urllib.parse import quote

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from gridfs import GridFS
from gridfs.errors import NoFile
from pydantic import BaseModel, Field, ValidationError, model_validator

from config import settings
from database import db
from dependencies import require_authenticated, require_roles
from services import blockchain_service, ids
from services.accounts import LAB

router = APIRouter(prefix="/api/lab", tags=["Laboratory"])

logger = logging.getLogger(__name__)

STATUS_BLOCKED = "BLOCKED"
STATUS_APPROVED = "APPROVED_FOR_MANUFACTURING"
GATING_STAGE = "PRE_MANUFACTURING"
LAB_REPORT_BUCKET = "lab_reports"
GRIDFS_CHUNK_SIZE = 255 * 1024


class LabTestRequest(BaseModel):
    """Unified lab submission contract.

    `test_phase` is used by the current UI for raw-material and finished-
    medicine tests. `test_stage` remains supported for existing integrations
    that test a processing batch and use the manufacturing quality gate.
    """

    batch_id: str = Field(min_length=1, max_length=64)
    test_type: str = Field(default="QUALITY_TEST", min_length=1, max_length=128)
    result: Literal["PASS", "FAIL", "pass", "fail"]
    test_parameters: dict = Field(default_factory=dict)
    test_date: date | None = None
    certificate_id: str | None = Field(default=None, max_length=128)
    test_phase: Literal["RAW_BATCH_TEST", "FINAL_PRODUCT_QUALITY_TEST"] | None = None
    test_stage: Literal[
        "PRE_MANUFACTURING",
        "IN_PROCESS",
        "POST_MANUFACTURING",
    ] | None = None

    # Accepted for older API clients only. The authenticated organisation is
    # authoritative whenever present; certificate_id is never treated as lab_id.
    lab_id: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def _require_target_phase(self):
        if not self.test_phase and not self.test_stage:
            raise ValueError(
                "test_phase is required for raw/medicine tests; "
                "test_stage is required for processing-batch tests"
            )
        if self.test_phase and self.test_stage:
            raise ValueError("Send test_phase or test_stage, not both")
        if self.certificate_id is not None:
            self.certificate_id = self.certificate_id.strip() or None
        return self


def _resolve_lab_target(data: LabTestRequest):
    """Return collection, identifier field and ledger entity type."""
    if data.test_phase == "RAW_BATCH_TEST":
        return db.raw_material_batches, "raw_batch_id", "RAW", "RAW_BATCH_TEST"
    if data.test_phase == "FINAL_PRODUCT_QUALITY_TEST":
        return db.medicine_batches, "medicine_batch_id", "MEDICINE", "FINAL_PRODUCT_QUALITY_TEST"
    return db.processing_batches, "processing_batch_id", "PROCESSING", data.test_stage


async def _parse_submission(request: Request):
    """Accept the legacy JSON body and multipart JSON+PDF submissions."""
    content_type = request.headers.get("content-type", "").lower()
    report = None

    if "multipart/form-data" in content_type:
        try:
            form = await request.form()
        except Exception as error:
            raise HTTPException(
                status_code=400,
                detail="Could not read the multipart lab submission",
            ) from error

        payload = form.get("payload")
        if not isinstance(payload, str) or not payload.strip():
            raise HTTPException(
                status_code=422,
                detail="Multipart submissions must include a JSON 'payload' field",
            )
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as error:
            raise HTTPException(
                status_code=422,
                detail="The lab submission payload must contain valid JSON",
            ) from error

        candidate = form.get("report")
        if candidate is not None:
            if not hasattr(candidate, "filename") or not hasattr(candidate, "read"):
                raise HTTPException(status_code=422, detail="The 'report' field must be a PDF file")
            report = candidate
    else:
        try:
            payload = await request.json()
        except Exception as error:
            raise HTTPException(
                status_code=400,
                detail="Request body must be valid JSON or multipart form data",
            ) from error

    try:
        data = LabTestRequest.model_validate(payload)
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error.errors()) from error

    return data, report


async def _read_pdf_report(upload):
    """Read and validate a bounded PDF upload before it reaches GridFS."""
    if upload is None:
        return None

    filename = str(upload.filename or "").replace("\\", "/").split("/")[-1].strip()
    if not filename or not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Lab report must have a .pdf filename")

    max_bytes = max(1, int(settings.max_lab_report_bytes))
    content = await upload.read(max_bytes + 1)
    if not content:
        raise HTTPException(status_code=400, detail="The selected PDF is empty")
    if len(content) > max_bytes:
        max_mb = max_bytes / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"PDF report exceeds the {max_mb:g} MB upload limit",
        )
    if not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="The selected file is not a valid PDF document")

    return {
        "filename": filename,
        "content": content,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def _save_report(lab_test_id: str, report: dict, user: dict, uploaded_at: datetime):
    """Persist a PDF in MongoDB GridFS and return safe document metadata."""
    bucket = GridFS(db, collection=LAB_REPORT_BUCKET)
    metadata = {
        "lab_test_id": lab_test_id,
        "uploaded_by": user.get("username"),
        "sha256": report["sha256"],
    }
    file_id = bucket.put(
        report["content"],
        filename=report["filename"],
        contentType="application/pdf",
        chunk_size=GRIDFS_CHUNK_SIZE,
        metadata=metadata,
    )
    return {
        "file_id": str(file_id),
        "filename": report["filename"],
        "content_type": "application/pdf",
        "size_bytes": report["size_bytes"],
        "sha256": report["sha256"],
        "uploaded_at": uploaded_at,
        "uploaded_by": user.get("username"),
        "download_url": f"/api/lab/tests/{lab_test_id}/report",
    }


@router.post("/tests", status_code=201)
async def create_lab_test(
    request: Request,
    user: dict = Depends(require_roles(LAB)),
):
    data, report_upload = await _parse_submission(request)
    report = await _read_pdf_report(report_upload)

    collection, id_field, entity_type, phase = _resolve_lab_target(data)
    batch = collection.find_one({id_field: data.batch_id}, {"_id": 0})
    if not batch:
        label = {
            "RAW": "Raw material batch",
            "MEDICINE": "Medicine batch",
            "PROCESSING": "Processing batch",
        }[entity_type]
        raise HTTPException(status_code=404, detail=f"{label} not found")

    result = data.result.upper()
    lab_test_id = ids.mint("lab_test")
    # Prefer the organisation attached to the authenticated lab account.
    # A legacy client-supplied ID is only a fallback for old seeded accounts.
    lab_id = user.get("organisation_id") or data.lab_id or user.get("username") or "UNKNOWN_LAB"
    verified_at = datetime.now(timezone.utc)

    batch_status = batch.get("status") or batch.get("batch_status") or ""
    if entity_type == "PROCESSING" and phase == GATING_STAGE:
        batch_status = STATUS_BLOCKED if result == "FAIL" else STATUS_APPROVED
        collection.update_one(
            {id_field: data.batch_id},
            {"$set": {"status": batch_status}},
        )

    report_metadata = None
    saved_report_file_id = None
    try:
        if report is not None:
            report_metadata = _save_report(lab_test_id, report, user, verified_at)
            saved_report_file_id = ObjectId(report_metadata["file_id"])

        lab_test = {
            "lab_test_id": lab_test_id,
            "batch_id": data.batch_id,
            "batch_type": entity_type,
            "lab_id": lab_id,
            "test_phase": phase,
            "test_stage": data.test_stage,
            "test_type": data.test_type,
            "test_parameters": data.test_parameters,
            "test_date": data.test_date.isoformat() if data.test_date else None,
            "certificate_id": data.certificate_id,
            "result": result,
            "status": "VERIFIED",
            "verified_by": user.get("username"),
            "verification_timestamp": verified_at,
            "created_at": verified_at,
        }
        if report_metadata is not None:
            lab_test["report"] = report_metadata
        db.lab_tests.insert_one(lab_test)
    except Exception as error:
        if saved_report_file_id is not None:
            try:
                GridFS(db, collection=LAB_REPORT_BUCKET).delete(saved_report_file_id)
            except Exception:
                logger.exception("Could not remove orphaned lab report for %s", lab_test_id)
        logger.exception("Could not persist laboratory test %s", lab_test_id)
        raise HTTPException(
            status_code=500,
            detail="Could not save the laboratory test and report. Please retry.",
        ) from error

    blockchain_tx = blockchain_service.safe_anchor(
        "QUALITY_STATUS",
        entity_type,
        data.batch_id,
        {
            "lab_test_id": lab_test_id,
            "lab_id": lab_id,
            "test_phase": phase,
            "test_stage": data.test_stage,
            "test_type": data.test_type,
            "certificate_id": data.certificate_id,
            "test_date": data.test_date.isoformat() if data.test_date else None,
            "result": result,
            "batch_status": batch_status,
            "report_sha256": report_metadata.get("sha256") if report_metadata else None,
            "recorded_by": user.get("username"),
        },
    )

    return {
        "success": True,
        "lab_test_id": lab_test_id,
        "batch_id": data.batch_id,
        "batch_type": entity_type,
        "lab_id": lab_id,
        "test_phase": phase,
        "test_stage": data.test_stage,
        "test_type": data.test_type,
        "test_date": data.test_date.isoformat() if data.test_date else None,
        "certificate_id": data.certificate_id,
        "result": result,
        "status": "VERIFIED",
        "batch_status": batch_status,
        "report": report_metadata,
        "blockchain_tx": blockchain_tx,
    }


@router.get("/tests")
def list_lab_tests(
    limit: int = Query(default=200, ge=1, le=1000),
    user: dict = Depends(require_authenticated),
):
    """List recent laboratory certifications for the authenticated workspace."""
    tests = list(
        db.lab_tests.find({}, {"_id": 0})
        .sort("created_at", -1)
        .limit(limit)
    )
    return {"tests": tests, "count": len(tests)}


@router.get("/tests/{lab_test_id}/report")
def download_lab_report(
    lab_test_id: str,
    user: dict = Depends(require_authenticated),
):
    """Stream a stored PDF only to an authenticated TraceVeda account."""
    lab_test = db.lab_tests.find_one(
        {"lab_test_id": lab_test_id},
        {"_id": 0, "report": 1},
    )
    report = (lab_test or {}).get("report")
    if not report or not report.get("file_id"):
        raise HTTPException(status_code=404, detail="No PDF report is attached to this laboratory test")

    try:
        file_id = ObjectId(report["file_id"])
        report_file = GridFS(db, collection=LAB_REPORT_BUCKET).get(file_id)
    except (ValueError, NoFile, TypeError):
        raise HTTPException(status_code=404, detail="Stored laboratory PDF could not be found")
    except Exception as error:
        logger.exception("Could not open lab report %s", lab_test_id)
        raise HTTPException(status_code=500, detail="Could not retrieve the laboratory PDF") from error

    filename = str(report.get("filename") or "lab-report.pdf")
    filename = filename.replace("\\", "_").replace('"', "_").replace("\r", "_").replace("\n", "_")
    fallback_name = re.sub(r"[^A-Za-z0-9._-]", "_", filename) or "lab-report.pdf"

    def content_stream():
        try:
            while True:
                chunk = report_file.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            report_file.close()

    return StreamingResponse(
        content_stream(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"{fallback_name}\"; filename*=UTF-8''{quote(filename)}",
            "Content-Length": str(report.get("size_bytes") or report_file.length),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/tests/{batch_id}")
def get_lab_tests(
    batch_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    user: dict = Depends(require_authenticated),
):
    tests = list(
        db.lab_tests.find({"batch_id": batch_id}, {"_id": 0})
        .sort("created_at", -1)
        .limit(limit)
    )
    return {"batch_id": batch_id, "tests": tests}
