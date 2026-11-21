from datetime import date, datetime, timezone
import base64
from io import BytesIO
import re

import qrcode
from qrcode.image.svg import SvgPathFillImage
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from pymongo.errors import ConfigurationError, DuplicateKeyError, OperationFailure

from database import db
from dependencies import require_authenticated, require_roles
from services import blockchain_service, ids
from services.accounts import MANUFACTURER

router = APIRouter(prefix="/api", tags=["Medicine"])

APPROVED_FOR_MANUFACTURING = "APPROVED_FOR_MANUFACTURING"
PROCESSING_TO_MEDICINE = "PROCESSING_TO_MEDICINE"


class MedicineBatchRequest(BaseModel):
    # New contract: one medicine lot may be formulated from several processing
    # lots. `processing_batch_id` remains accepted for older single-parent APIs.
    medicine_batch_id: str | None = Field(default=None, max_length=64)
    source_processing_batches: list[str] | None = Field(default=None, min_length=1, max_length=50)
    processing_batch_id: str | None = Field(default=None, min_length=1, max_length=64)
    manufacturer_id: str = Field(min_length=1, max_length=64)
    product_name: str = Field(min_length=1, max_length=200)
    manufacturing_date: date
    expiry_date: date

    @model_validator(mode="after")
    def _validate_batch_relationships(self):
        if self.expiry_date <= self.manufacturing_date:
            raise ValueError("expiry_date must be after manufacturing_date")

        if self.medicine_batch_id:
            medicine_id = self.medicine_batch_id.strip().upper()
            if not re.fullmatch(r"MED-\d{4}-\d{3,}", medicine_id):
                raise ValueError("medicine_batch_id must use MED-YYYY-NNN format")
            self.medicine_batch_id = medicine_id

        sources = self.source_processing_batches or []
        if self.processing_batch_id:
            legacy_source = self.processing_batch_id.strip()
            if not sources:
                sources = [legacy_source]
            elif legacy_source not in sources:
                raise ValueError("Do not mix processing_batch_id with source_processing_batches")

        cleaned = [str(value).strip() for value in sources if str(value).strip()]
        if not cleaned:
            raise ValueError("At least one source processing batch is required")
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("Source processing batches must be unique; remove duplicates")

        self.source_processing_batches = cleaned
        # Keep the singular field populated only for the one-parent legacy case.
        self.processing_batch_id = cleaned[0] if len(cleaned) == 1 else None
        return self


def _qr_code_data_url(qr_id: str) -> str:
    """Render the exact QR ID as a portable SVG data URL for print/download."""
    code = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
        image_factory=SvgPathFillImage,
    )
    code.add_data(qr_id)
    code.make(fit=True)
    image = code.make_image()
    buffer = BytesIO()
    image.save(buffer)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _persist_medicine_with_relationships(medicine_batch: dict, relationships: list[dict]):
    """Persist the medicine and all parent links as one logical operation.

    MongoDB replica sets support a true multi-document transaction. For local
    standalone MongoDB / mongomock, where sessions are unavailable, use
    compensating deletes so a failed relationship insert cannot leave an
    orphan medicine record or a half-written set of links.
    """
    try:
        with db.client.start_session() as session:
            with session.start_transaction():
                db.medicine_batches.insert_one(medicine_batch, session=session)
                db.batch_relationships.insert_many(relationships, ordered=True, session=session)
        return
    except (NotImplementedError, ConfigurationError):
        # Standalone/local Mongo deployment: use the compensating path below.
        pass
    except OperationFailure as error:
        message = str(error).lower()
        transaction_unsupported = (
            error.code == 20
            or "transaction numbers are only allowed" in message
            or "transactions are not supported" in message
        )
        if not transaction_unsupported:
            raise

    medicine_inserted = False
    try:
        db.medicine_batches.insert_one(medicine_batch)
        medicine_inserted = True
        db.batch_relationships.insert_many(relationships, ordered=True)
    except Exception:
        relationship_ids = [item["relationship_id"] for item in relationships]
        db.batch_relationships.delete_many({"relationship_id": {"$in": relationship_ids}})
        if medicine_inserted:
            db.medicine_batches.delete_one({"medicine_batch_id": medicine_batch["medicine_batch_id"]})
        raise


@router.post("/medicine", status_code=201)
def create_medicine_batch(
    data: MedicineBatchRequest,
    user: dict = Depends(require_roles(MANUFACTURER)),
):
    source_ids = data.source_processing_batches or []
    approved_sources = []

    # Validate every source before writing anything. Each parent must have
    # passed the PRE_MANUFACTURING laboratory quality gate.
    for processing_id in source_ids:
        processing_batch = db.processing_batches.find_one(
            {"processing_batch_id": processing_id},
            {"_id": 0, "status": 1},
        )
        if not processing_batch:
            raise HTTPException(status_code=404, detail=f"Processing batch not found: {processing_id}")
        if processing_batch.get("status") != APPROVED_FOR_MANUFACTURING:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Processing batch {processing_id} is not approved for manufacturing "
                    f"(status: {processing_batch.get('status') or 'unknown'}). "
                    "Record a PASS on a PRE_MANUFACTURING lab test first."
                ),
            )
        approved_sources.append(processing_id)

    medicine_batch_id = data.medicine_batch_id or ids.mint("medicine_batch")
    if db.medicine_batches.find_one({"medicine_batch_id": medicine_batch_id}, {"_id": 1}):
        raise HTTPException(status_code=409, detail=f"Medicine batch id {medicine_batch_id} is already in use")

    qr_id = medicine_batch_id.replace("MED-", "QR-", 1)
    if db.medicine_batches.find_one({"qr_id": qr_id}, {"_id": 1}):
        raise HTTPException(status_code=409, detail=f"QR id {qr_id} is already in use")

    now = datetime.now(timezone.utc)
    manufacturer_id = user.get("organisation_id") or data.manufacturer_id
    medicine_batch = {
        "medicine_batch_id": medicine_batch_id,
        "qr_id": qr_id,
        "processing_batch_ids": approved_sources,
        # Preserve old query clients only when there is exactly one parent;
        # never put a comma-joined or arbitrary first parent in this field.
        "processing_batch_id": approved_sources[0] if len(approved_sources) == 1 else None,
        "manufacturer_id": manufacturer_id,
        "product_name": data.product_name.strip(),
        "manufacturing_date": data.manufacturing_date.isoformat(),
        "expiry_date": data.expiry_date.isoformat(),
        "batch_status": "RELEASED",
        "created_by": user["username"],
        "created_at": now,
    }

    # Generate the QR payload before persistence so QR rendering failure does
    # not leave a partially registered batch.
    qr_code_data_url = _qr_code_data_url(qr_id)
    relationships = [
        {
            "relationship_id": ids.mint("relationship"),
            "parent_batch_id": processing_id,
            "child_batch_id": medicine_batch_id,
            "relationship_type": PROCESSING_TO_MEDICINE,
            "created_by": user["username"],
            "timestamp": now,
        }
        for processing_id in approved_sources
    ]

    try:
        _persist_medicine_with_relationships(medicine_batch, relationships)
    except DuplicateKeyError as error:
        raise HTTPException(status_code=409, detail="Medicine batch or relationship ID already exists; retry with a new batch ID") from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Medicine registration was rolled back: {error}") from error

    blockchain_tx = blockchain_service.safe_anchor(
        "MEDICINE_LINKED",
        "MEDICINE",
        medicine_batch_id,
        {
            "processing_batch_ids": approved_sources,
            "relationship_ids": [item["relationship_id"] for item in relationships],
            "manufacturer_id": manufacturer_id,
            "qr_id": qr_id,
            "product_name": data.product_name.strip(),
            "manufacturing_date": data.manufacturing_date.isoformat(),
            "expiry_date": data.expiry_date.isoformat(),
            "batch_status": "RELEASED",
            "recorded_by": user["username"],
        },
    )

    return {
        "medicine_batch_id": medicine_batch_id,
        "qr_id": qr_id,
        "qr_code_data_url": qr_code_data_url,
        "processing_batch_ids": approved_sources,
        "relationship_ids": [item["relationship_id"] for item in relationships],
        "status": "CREATED",
        "blockchain_tx": blockchain_tx,
    }


@router.get("/medicine/{medicine_batch_id}/qr")
def get_medicine_qr(
    medicine_batch_id: str,
    user: dict = Depends(require_roles(MANUFACTURER)),
):
    medicine = db.medicine_batches.find_one(
        {"medicine_batch_id": medicine_batch_id},
        {"_id": 0, "medicine_batch_id": 1, "qr_id": 1},
    )
    if not medicine:
        raise HTTPException(status_code=404, detail="Medicine batch not found")
    qr_id = medicine.get("qr_id")
    if not qr_id:
        raise HTTPException(status_code=409, detail="This medicine batch does not have a QR ID. Register it again or contact an administrator.")
    return {
        "exists": True,
        "medicine_batch_id": medicine_batch_id,
        "qr_id": qr_id,
        "qr_code_data_url": _qr_code_data_url(qr_id),
    }


@router.get("/medicine")
def list_medicine_batches(
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(require_authenticated),
):
    batches = list(
        db.medicine_batches.find({}, {"_id": 0})
        .sort("created_at", -1)
        .skip(offset)
        .limit(limit)
    )
    return {"batches": batches, "count": len(batches), "total": db.medicine_batches.count_documents({})}


@router.get("/medicine/{medicine_batch_id}")
def get_medicine_batch(
    medicine_batch_id: str,
    user: dict = Depends(require_authenticated),
):
    medicine = db.medicine_batches.find_one({"medicine_batch_id": medicine_batch_id}, {"_id": 0})
    if not medicine:
        raise HTTPException(status_code=404, detail="Medicine batch not found")
    return medicine


def _processing_ids_for_medicine(medicine: dict) -> list[str]:
    """Read new relationship records and legacy medicine documents."""
    medicine_id = medicine.get("medicine_batch_id")
    result = []
    for relationship in db.batch_relationships.find(
        {"child_batch_id": medicine_id, "relationship_type": PROCESSING_TO_MEDICINE},
        {"_id": 0, "parent_batch_id": 1},
    ):
        parent_id = relationship.get("parent_batch_id")
        if parent_id and parent_id not in result:
            result.append(parent_id)
    for parent_id in medicine.get("processing_batch_ids") or []:
        if parent_id and parent_id not in result:
            result.append(parent_id)
    legacy_id = medicine.get("processing_batch_id")
    if legacy_id and legacy_id not in result:
        result.append(legacy_id)
    return result


@router.get("/verify/{qr_id}")
def verify_medicine(qr_id: str):
    medicine = db.medicine_batches.find_one({"qr_id": qr_id}, {"_id": 0})
    if not medicine:
        return {"verified": False, "message": "Invalid QR"}

    processing_ids = _processing_ids_for_medicine(medicine)
    raw_batches = []
    seen_raw = set()
    plant_ids = []

    for processing_id in processing_ids:
        for relationship in db.batch_relationships.find(
            {"child_batch_id": processing_id},
            {"_id": 0, "parent_batch_id": 1, "relationship_type": 1},
        ):
            raw_id = relationship.get("parent_batch_id")
            if not raw_id or raw_id in seen_raw:
                continue
            raw = db.raw_material_batches.find_one(
                {"raw_batch_id": raw_id},
                {"_id": 0, "plant_id": 1},
            )
            if raw:
                seen_raw.add(raw_id)
                raw_batches.append(raw_id)
                if raw.get("plant_id") and raw["plant_id"] not in plant_ids:
                    plant_ids.append(raw["plant_id"])

    return {
        "verified": True,
        "medicine_batch_id": medicine.get("medicine_batch_id"),
        "product_name": medicine.get("product_name"),
        "batch_status": medicine.get("batch_status"),
        "manufacturing_date": medicine.get("manufacturing_date"),
        "expiry_date": medicine.get("expiry_date"),
        "traceability": {
            "processing_batch_id": processing_ids[0] if len(processing_ids) == 1 else None,
            "processing_batch_ids": processing_ids,
            "raw_batches": raw_batches,
            "plant_ids": plant_ids,
            "plant_id": plant_ids[0] if len(plant_ids) == 1 else None,
        },
    }
