"""
Upload API Router — UI-based KYC document submission.

Provides
--------
POST /api/upload/document        Upload a document file; enqueue extraction job.
GET  /api/upload/status/{job_id} Poll job processing status.
"""

import json
import mimetypes
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from src.models.database import Document, Employee, KYCSubmission, get_session
from src.utils.config import config
from src.utils.logger import logger
from src.utils.redis_client import get_redis_client

router = APIRouter(prefix="/api/upload", tags=["upload"])

# ── Constants ──────────────────────────────────────────────────────────────
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/tiff",
    "application/pdf",
}
MIME_TO_EXT: dict[str, str] = {
    "image/jpeg":      ".jpg",
    "image/png":       ".png",
    "image/webp":      ".webp",
    "image/tiff":      ".tiff",
    "application/pdf": ".pdf",
}
MAX_BYTES         = 10 * 1024 * 1024  # 10 MB
META_TTL          = 3_600             # 1 h
PROCESS_TIMEOUT   = 300               # 5 min


# ── Helpers ────────────────────────────────────────────────────────────────

def _auth(key: Optional[str]) -> None:
    if not config or key != config.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def _clean_phone(raw: str) -> str:
    digits = "".join(c for c in raw.strip() if c.isdigit())
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    return digits


def _mime(file: UploadFile) -> str:
    ct = (file.content_type or "").split(";")[0].strip().lower()
    if ct not in ALLOWED_MIME_TYPES:
        ct, _ = mimetypes.guess_type(file.filename or "")
        ct = (ct or "").lower()
    if ct not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Allowed: JPEG, PNG, WEBP, TIFF, PDF.",
        )
    return ct


def _upsert_employee_submission(phone: str) -> tuple[str, str]:
    """Return (employee_id, submission_id) — creating records if needed."""
    with get_session() as db:
        emp = db.query(Employee).filter(Employee.phone_number == phone).first()
        if not emp:
            emp = Employee(id=str(uuid.uuid4()), phone_number=phone)
            db.add(emp)
            db.flush()

        sub = (
            db.query(KYCSubmission)
            .filter(
                KYCSubmission.employee_id == emp.id,
                KYCSubmission.status.notin_(["FINALIZED"]),
            )
            .first()
        )
        if not sub:
            sub = KYCSubmission(id=str(uuid.uuid4()), employee_id=emp.id, status="PENDING")
            db.add(sub)

        db.commit()
        return emp.id, sub.id


def _rm(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/document", status_code=202, summary="Upload a KYC document")
async def upload_document(
    file: UploadFile = File(..., description="KYC document image or PDF (≤ 10 MB)"),
    phone_number: str = Form(..., description="Employee phone number"),
    x_api_key: Optional[str] = Header(None),
):
    """
    Accept a document from the HR web UI and push it into the same Redis
    extraction queue used by the WhatsApp flow.

    * Requires **X-API-Key** header.
    * Accepted types: JPEG · PNG · WEBP · TIFF · PDF (max 10 MB).
    * Returns **job_id** (for status polling) and **submission_id** (for review page).
    """
    _auth(x_api_key)

    phone = _clean_phone(phone_number)
    if len(phone) < 7 or not phone.isdigit():
        raise HTTPException(status_code=422, detail="Invalid phone number.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_BYTES // (1024*1024)} MB limit.")

    mt  = _mime(file)
    ext = MIME_TO_EXT[mt]

    # Save with UUID name → no path traversal risk
    job_id   = str(uuid.uuid4())
    dest_dir = os.path.join(config.UPLOADS_PATH, phone)
    os.makedirs(dest_dir, exist_ok=True)
    fpath = os.path.join(dest_dir, f"{job_id}{ext}")

    try:
        with open(fpath, "wb") as fh:
            fh.write(content)
    except OSError as exc:
        logger.error("file_write_failed", extra={"job_id": job_id, "err": str(exc)})
        raise HTTPException(status_code=500, detail="Could not save file.")

    try:
        _, submission_id = _upsert_employee_submission(phone)
    except Exception as exc:
        logger.error("db_error_on_upload", extra={"job_id": job_id, "err": str(exc)})
        _rm(fpath)
        raise HTTPException(status_code=500, detail="Database error. Please retry.")

    now = datetime.now(timezone.utc).isoformat()
    job = {
        "job_id":       job_id,
        "phone_number": phone,
        "file_path":    fpath,
        "timestamp":    now,
        "status":       "PENDING",
        "source":       "ui_upload",
    }
    meta = {"submission_id": submission_id, "phone_number": phone, "enqueued_at": now}

    try:
        r = get_redis_client()
        r.rpush("kyc:jobs", json.dumps(job))
        r.setex(f"upload_meta:{job_id}", META_TTL, json.dumps(meta))
    except Exception as exc:
        logger.error("redis_enqueue_failed", extra={"job_id": job_id, "err": str(exc)})
        _rm(fpath)
        raise HTTPException(status_code=503, detail="Processing service unavailable.")

    logger.info("ui_upload_queued", extra={
        "job_id": job_id, "submission_id": submission_id,
        "phone": phone, "mime": mt, "bytes": len(content),
    })
    return {"job_id": job_id, "submission_id": submission_id,
            "status": "queued", "message": "Document queued for processing."}


@router.get("/status/{job_id}", summary="Poll extraction status")
async def get_upload_status(job_id: str, x_api_key: Optional[str] = Header(None)):
    """
    | status       | meaning                                         |
    |--------------|-------------------------------------------------|
    | queued       | waiting in the Redis queue                      |
    | processing   | worker is analysing the document                |
    | completed    | done — fetch submission for extracted data      |
    | failed       | timed out or extraction error                   |
    | unknown      | job_id not found / metadata expired             |
    """
    _auth(x_api_key)

    try:
        r   = get_redis_client()
        raw = r.get(f"upload_meta:{job_id}")
    except Exception as exc:
        logger.warning("redis_status_check_failed", extra={"job_id": job_id, "err": str(exc)})
        return JSONResponse(status_code=503,
                            content={"status": "unknown", "message": "Status service unavailable."})

    if not raw:
        return JSONResponse(status_code=404,
                            content={"status": "unknown", "job_id": job_id,
                                     "message": "Job not found or expired."})

    meta          = json.loads(raw)
    submission_id = meta["submission_id"]
    enqueued_at   = datetime.fromisoformat(meta["enqueued_at"])

    try:
        with get_session() as db:
            # Query by job_id for accurate per-file status (avoids cross-contamination
            # when multiple files are uploaded for the same submission)
            doc = (
                db.query(Document)
                .filter(Document.job_id == job_id)
                .first()
            )
    except Exception as exc:
        logger.error("db_status_query_failed", extra={"job_id": job_id, "err": str(exc)})
        return JSONResponse(status_code=500, content={"status": "unknown", "message": "Error checking status."})

    if doc:
        return {
            "job_id": job_id, "status": "completed",
            "submission_id": submission_id,
            "document_type": doc.document_type,
            "message": f"{doc.document_type.replace('_', ' ').title()} processed.",
        }

    elapsed = (datetime.now(timezone.utc) - enqueued_at).total_seconds()
    if elapsed > PROCESS_TIMEOUT:
        return {"job_id": job_id, "status": "failed", "submission_id": submission_id,
                "document_type": None, "message": "Processing timed out. Please upload again."}

    return {"job_id": job_id, "status": "processing", "submission_id": submission_id,
            "document_type": None, "message": "Analysing document…"}
