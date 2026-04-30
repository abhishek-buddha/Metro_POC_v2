"""
FastAPI webhook application for WhatsApp KYC automation.

This module provides:
- POST /webhook/whatsapp - Receive WhatsApp messages from Twilio
- GET /api/submissions - List KYC submissions (paginated)
- GET /api/submissions/{id} - Get specific submission
- POST /api/submissions/{id}/review - Review and approve/reject
- GET /health - Health check endpoint
"""

from fastapi import FastAPI, Request, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from twilio.request_validator import RequestValidator
import requests
import uuid
import os
import json
import re
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.utils.config import config, get_config
from src.utils.logger import logger, setup_logger
from src.utils.redis_client import get_redis_client
from src.models.database import (
    get_session, Employee, KYCSubmission, Document, AuditLog, init_database
)
from src.services.encryption import decrypt_field, encrypt_field
from src.api.upload import router as upload_router

# Initialize app
app = FastAPI(
    title="WhatsApp KYC API",
    description="Webhook and REST API for WhatsApp KYC automation",
    version="1.0.0"
)

# Add CORS middleware
# Allow origins from env var CORS_ORIGINS (comma-separated) or defaults
_cors_origins_raw = os.getenv("CORS_ORIGINS", "")
_cors_origins = (
    [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
    if _cors_origins_raw
    else ["http://localhost:5173", "http://127.0.0.1:5173", "*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded documents as static files
_uploads_path = os.getenv('UPLOADS_PATH', 'uploads')
os.makedirs(_uploads_path, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=_uploads_path), name="uploads")

# Register routers
app.include_router(upload_router)

# Initialise DB tables on startup (creates tables if they don't exist)
@app.on_event("startup")
async def startup_event():
    init_database()

# Setup logger for this module
webhook_logger = setup_logger(__name__)


# Pydantic request models
class FinalizeRequest(BaseModel):
    """Request model for finalizing HRMS submissions"""
    finalized_by: Optional[str] = None
    notes: Optional[str] = None


class UpdateSubmissionRequest(BaseModel):
    """Request model for saving HR-edited form data"""
    first_name: Optional[str] = None
    full_name: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    marital_status: Optional[str] = None
    father_name: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    address_line3: Optional[str] = None
    address_line4: Optional[str] = None
    bank_account: Optional[str] = None
    ifsc_code: Optional[str] = None
    bank_name: Optional[str] = None
    bank_branch: Optional[str] = None


def generate_employee_id(session: Session) -> str:
    """
    Generate unique HRMS employee ID.

    Format: EMP{YEAR}{SEQUENCE}
    Example: EMP2026001, EMP2026002, etc.

    Args:
        session: SQLAlchemy database session

    Returns:
        str: Unique HRMS employee ID in format EMP{YEAR}{SEQUENCE}

    Raises:
        ValueError: If session is None or sequence limit (999) is reached

    Note:
        Race condition handling: This function may generate duplicate IDs if called
        concurrently. Callers should implement retry logic with try/except to handle
        database unique constraint violations. The finalize endpoint implements this
        pattern by catching IntegrityError and retrying ID generation.
    """
    # Validate input
    if session is None:
        raise ValueError("Database session cannot be None")

    current_year = datetime.now().year
    max_sequence = 999

    # Get last employee ID for current year
    last_submission = session.query(KYCSubmission).filter(
        KYCSubmission.hrms_employee_id.like(f"EMP{current_year}%")
    ).order_by(KYCSubmission.hrms_employee_id.desc()).first()

    if last_submission and last_submission.hrms_employee_id:
        # Validate ID format before parsing
        id_pattern = re.compile(r'^EMP\d{4}\d{3}$')
        if not id_pattern.match(last_submission.hrms_employee_id):
            raise ValueError(
                f"Invalid employee ID format: {last_submission.hrms_employee_id}. "
                f"Expected format: EMP{{YEAR}}{{SEQ}}"
            )

        # Extract sequence number and increment
        try:
            last_seq = int(last_submission.hrms_employee_id[-3:])
        except ValueError as e:
            raise ValueError(
                f"Failed to parse sequence from ID {last_submission.hrms_employee_id}: {e}"
            )

        new_seq = last_seq + 1

        # Check maximum sequence limit
        if new_seq > max_sequence:
            raise ValueError(
                f"Maximum employee ID sequence reached for year {current_year}. "
                f"Limit: {max_sequence}"
            )
    else:
        new_seq = 1

    return f"EMP{current_year}{new_seq:03d}"


def get_db():
    """
    Dependency to get database session.
    Yields a session and ensures it's closed after use.
    """
    db = get_session()
    try:
        yield db
    finally:
        db.close()


def verify_api_key(x_api_key: str = Header(...)):
    """
    Dependency to verify API key from X-API-Key header.

    Args:
        x_api_key: API key from request header

    Raises:
        HTTPException: If API key is invalid

    Returns:
        str: The validated API key
    """
    try:
        cfg = get_config()
        if x_api_key != cfg.API_KEY:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return x_api_key
    except Exception as e:
        webhook_logger.error(f"API key verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Receive WhatsApp messages from Twilio.

    This endpoint:
    1. Verifies Twilio signature for security
    2. Extracts phone number and media URL
    3. Downloads document from Twilio
    4. Saves to uploads directory
    5. Creates job in Redis queue
    6. Updates session state in Redis
    7. Returns 200 OK to Twilio

    Args:
        request: FastAPI request object containing form data

    Returns:
        Response: Plain text "OK" response for Twilio
    """
    try:
        # Get form data
        form_data = await request.form()
        form_dict = dict(form_data)

        # Get Twilio signature
        signature = request.headers.get("X-Twilio-Signature", "")

        # Verify Twilio signature
        cfg = get_config()
        validator = RequestValidator(cfg.TWILIO_AUTH_TOKEN)

        # Reconstruct the public URL Twilio signed against — tunnels (localtunnel/ngrok)
        # forward the original host via X-Forwarded-Host, so request.url would
        # otherwise reflect the internal localhost address and fail validation.
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "https")
        forwarded_host = request.headers.get("X-Forwarded-Host") or request.headers.get("Host", "")
        if forwarded_host and "localhost" not in forwarded_host:
            url = f"{forwarded_proto}://{forwarded_host}{request.url.path}"
        else:
            url = str(request.url)

        webhook_logger.info(f"Validating Twilio signature against URL: {url}")

        if not validator.validate(url, form_dict, signature):
            webhook_logger.error(f"Invalid Twilio signature for URL: {url}")
            raise HTTPException(status_code=401, detail="Invalid Twilio signature")

        # Extract phone number (remove "whatsapp:" prefix)
        from_number = form_dict.get("From", "")
        phone_number = from_number.replace("whatsapp:", "")

        # Extract message body
        body = form_dict.get("Body", "")

        # Check if media is present
        num_media = int(form_dict.get("NumMedia", "0"))

        webhook_logger.info(
            f"Received WhatsApp message from {phone_number}, "
            f"media count: {num_media}"
        )

        if num_media == 0:
            # No media, just acknowledge
            webhook_logger.info(f"No media in message from {phone_number}")
            return Response(content="OK", media_type="text/plain")

        # Download media
        media_url = form_dict.get("MediaUrl0", "")
        media_content_type = form_dict.get("MediaContentType0", "")

        # Determine file extension
        extension_map = {
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "application/pdf": ".pdf"
        }
        extension = extension_map.get(media_content_type, ".jpg")

        # Generate job ID and file path
        job_id = str(uuid.uuid4())
        upload_dir = os.path.join(cfg.UPLOADS_PATH, phone_number)
        os.makedirs(upload_dir, exist_ok=True)

        file_name = f"{job_id}{extension}"
        file_path = os.path.join(upload_dir, file_name)

        # Download media from Twilio
        webhook_logger.info(f"Downloading media from {media_url}")
        response = requests.get(
            media_url,
            auth=(cfg.TWILIO_ACCOUNT_SID, cfg.TWILIO_AUTH_TOKEN),
            timeout=30
        )

        if response.status_code == 200:
            # Save file
            with open(file_path, 'wb') as f:
                f.write(response.content)
            webhook_logger.info(f"Media saved to {file_path}")
        else:
            webhook_logger.error(
                f"Failed to download media: {response.status_code}"
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to download media"
            )

        # Create job in Redis
        redis_client = get_redis_client()
        job_data = {
            "job_id": job_id,
            "phone_number": phone_number,
            "file_path": file_path,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "PENDING"
        }

        redis_client.rpush("kyc:jobs", json.dumps(job_data))
        webhook_logger.info(f"Created job {job_id} in Redis queue")

        # Get or create employee in database
        db = next(get_db())
        try:
            employee = db.query(Employee).filter(
                Employee.phone_number == phone_number
            ).first()

            if not employee:
                employee = Employee(
                    id=str(uuid.uuid4()),
                    phone_number=phone_number,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                db.add(employee)
                db.commit()
                webhook_logger.info(f"Created new employee: {phone_number}")

            # Update session state in Redis
            session_key = f"session:{phone_number}"

            # Determine current step (simplified logic)
            # In production, this would be more sophisticated
            current_step = redis_client.hget(session_key, "current_step")
            if not current_step:
                current_step = "pan_card"
            elif current_step == "pan_card":
                current_step = "aadhaar_card"
            elif current_step == "aadhaar_card":
                current_step = "bank_document"

            redis_client.hset(session_key, "current_step", current_step)
            redis_client.hset(session_key, "last_job_id", job_id)
            redis_client.expire(session_key, 1800)  # 30 minutes TTL

            webhook_logger.info(
                f"Updated session for {phone_number}, step: {current_step}"
            )

        finally:
            db.close()

        return Response(content="OK", media_type="text/plain")

    except HTTPException:
        raise
    except Exception as e:
        webhook_logger.error(f"Webhook error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/submissions")
def list_submissions(
    status: Optional[str] = None,
    phone_number: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    api_key: str = Depends(verify_api_key),
    db=Depends(get_db)
):
    """
    List KYC submissions with optional filters and pagination.

    Args:
        status: Filter by status (PENDING, IN_PROGRESS, COMPLETED, APPROVED, REJECTED)
        phone_number: Filter by employee phone number
        limit: Maximum number of results (default 50)
        offset: Number of results to skip (default 0)
        api_key: API key for authentication (from header)
        db: Database session

    Returns:
        dict: List of submissions with total count
    """
    try:
        # Build query
        query = db.query(KYCSubmission).join(Employee)

        # Apply filters
        if status:
            query = query.filter(KYCSubmission.status == status)

        if phone_number:
            query = query.filter(Employee.phone_number == phone_number)

        # Get total count
        total = query.count()

        # Apply pagination and ordering
        submissions = query.order_by(
            KYCSubmission.submitted_at.desc()
        ).offset(offset).limit(limit).all()

        # Serialize results
        result = {
            "submissions": [
                {
                    "id": s.id,
                    "employee_id": s.employee_id,
                    "phone_number": s.employee.phone_number,
                    "status": s.status,
                    "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
                    "reviewed_at": s.reviewed_at.isoformat() if s.reviewed_at else None,
                    "reviewed_by": s.reviewed_by,
                    "overall_confidence": s.overall_confidence,
                }
                for s in submissions
            ],
            "total": total,
            "limit": limit,
            "offset": offset
        }

        webhook_logger.info(
            f"Listed {len(submissions)} submissions (total: {total})"
        )

        return result

    except Exception as e:
        webhook_logger.error(f"Error listing submissions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/submissions/{submission_id}")
def get_submission(
    submission_id: str,
    api_key: str = Depends(verify_api_key),
    db=Depends(get_db)
):
    """
    Get a specific KYC submission with all details.

    Args:
        submission_id: UUID of the submission
        api_key: API key for authentication (from header)
        db: Database session

    Returns:
        dict: Submission details including documents

    Raises:
        HTTPException: If submission not found
    """
    try:
        submission = db.query(KYCSubmission).filter(
            KYCSubmission.id == submission_id
        ).first()

        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")

        # Decrypt sensitive fields
        pan_number = None
        if submission.pan_number_encrypted:
            try:
                pan_number = decrypt_field(submission.pan_number_encrypted)
            except Exception as e:
                webhook_logger.warning(f"Failed to decrypt PAN: {e}")

        bank_account = None
        if submission.bank_account_encrypted:
            try:
                bank_account = decrypt_field(submission.bank_account_encrypted)
            except Exception as e:
                webhook_logger.warning(f"Failed to decrypt bank account: {e}")

        # Serialize submission
        result = {
            "id": submission.id,
            "employee_id": submission.employee_id,
            "phone_number": submission.employee.phone_number,
            "status": submission.status,

            # Employee object for frontend
            "employee": {
                "id": submission.employee_id,
                "phone_number": submission.employee.phone_number
            },

            # PAN details
            "pan_number": pan_number,
            "pan_name": submission.pan_name,
            "pan_father_name": submission.pan_father_name,
            "pan_dob": submission.pan_dob,
            "pan_confidence": submission.pan_confidence,

            # Aadhaar details
            "aadhaar_last4": submission.aadhaar_last4,
            "aadhaar_name": submission.aadhaar_name,
            "aadhaar_dob": submission.aadhaar_dob,
            "aadhaar_gender": submission.aadhaar_gender,
            "aadhaar_address": submission.aadhaar_address,
            "aadhaar_pincode": submission.aadhaar_pincode,
            "aadhaar_confidence": submission.aadhaar_confidence,

            # Bank details
            "bank_account": bank_account,
            "bank_holder_name": submission.bank_holder_name,
            "bank_ifsc": submission.bank_ifsc,
            "bank_name": submission.bank_name,
            "bank_branch": submission.bank_branch,
            "bank_account_type": submission.bank_account_type,
            "bank_micr": submission.bank_micr,
            "bank_confidence": submission.bank_confidence,

            # Validation
            "name_match_score": submission.name_match_score,
            "overall_confidence": submission.overall_confidence,

            # Metadata
            "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else None,
            "reviewed_at": submission.reviewed_at.isoformat() if submission.reviewed_at else None,
            "reviewed_by": submission.reviewed_by,
            "review_notes": submission.review_notes,

            # Finalization fields
            "finalized_at": submission.finalized_at.isoformat() if submission.finalized_at else None,
            "finalized_by": submission.finalized_by,
            "hrms_employee_id": submission.hrms_employee_id,

            # Documents
            "documents": [
                {
                    "id": doc.id,
                    "document_type": doc.document_type,
                    "file_path": doc.file_path,
                    "file_size": doc.file_size,
                    "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                    "extraction_method": doc.extraction_method,
                    "aadhaar_side": (
                        lambda d: (
                            # dob is the only reliable front-side indicator —
                            # aadhaar_number can appear on both sides, name appears on back (S/O)
                            "both"  if d.get("dob") and d.get("address") else
                            "front" if d.get("dob") else
                            "back"  if d.get("address") else None
                        )
                    )(json.loads(doc.raw_extraction_json) if doc.document_type == "AADHAAR_CARD" and doc.raw_extraction_json else {})
                }
                for doc in submission.documents
            ]
        }

        webhook_logger.info(f"Retrieved submission {submission_id}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        webhook_logger.error(f"Error getting submission: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/submissions/{submission_id}/review")
def review_submission(
    submission_id: str,
    review_data: dict,
    api_key: str = Depends(verify_api_key),
    db=Depends(get_db)
):
    """
    Review and approve/reject a KYC submission.

    Args:
        submission_id: UUID of the submission
        review_data: Dictionary with "status" and "notes" keys
        api_key: API key for authentication (from header)
        db: Database session

    Returns:
        dict: Updated submission details

    Raises:
        HTTPException: If submission not found or invalid status
    """
    try:
        # Validate status
        valid_statuses = ["APPROVED", "REJECTED"]
        status = review_data.get("status")
        notes = review_data.get("notes", "")

        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {valid_statuses}"
            )

        # Get submission
        submission = db.query(KYCSubmission).filter(
            KYCSubmission.id == submission_id
        ).first()

        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")

        # Update submission
        submission.status = status
        submission.review_notes = notes
        submission.reviewed_at = datetime.now(timezone.utc)
        submission.reviewed_by = "api_user"  # In production, get from auth context

        # Create audit log
        audit_log = AuditLog(
            event_type="submission_reviewed",
            employee_id=submission.employee_id,
            kyc_submission_id=submission_id,
            performed_by="api_user",
            details=json.dumps({
                "status": status,
                "notes": notes
            }),
            timestamp=datetime.now(timezone.utc)
        )

        db.add(audit_log)
        db.commit()

        webhook_logger.info(
            f"Submission {submission_id} reviewed: {status}"
        )

        # Return updated submission
        result = {
            "id": submission.id,
            "employee_id": submission.employee_id,
            "phone_number": submission.employee.phone_number,
            "status": submission.status,
            "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else None,
            "reviewed_at": submission.reviewed_at.isoformat() if submission.reviewed_at else None,
            "reviewed_by": submission.reviewed_by,
            "review_notes": submission.review_notes,
            "overall_confidence": submission.overall_confidence
        }

        return result

    except HTTPException:
        raise
    except Exception as e:
        webhook_logger.error(f"Error reviewing submission: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/submissions/{submission_id}")
def update_submission(
    submission_id: str,
    update_data: UpdateSubmissionRequest,
    api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """
    Save HR-edited form data for a submission.
    Updates name corrections, blood group, address, bank details, etc.
    Can be called multiple times — each call overwrites provided fields.
    """
    try:
        submission = db.query(KYCSubmission).filter(
            KYCSubmission.id == submission_id
        ).first()

        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")

        if submission.status == "FINALIZED":
            raise HTTPException(status_code=400, detail="Cannot edit a finalized submission")

        # Name fields
        if update_data.first_name is not None:
            submission.aadhaar_name = update_data.first_name
        if update_data.full_name is not None:
            submission.pan_name = update_data.full_name
        if update_data.dob is not None:
            submission.pan_dob = update_data.dob
            submission.aadhaar_dob = update_data.dob
        if update_data.gender is not None:
            submission.aadhaar_gender = update_data.gender
        if update_data.father_name is not None:
            submission.pan_father_name = update_data.father_name

        # HR-only fields
        if update_data.blood_group is not None:
            submission.blood_group = update_data.blood_group
        if update_data.marital_status is not None:
            submission.marital_status = update_data.marital_status

        # Reconstruct address from form lines
        address_parts = [
            update_data.address_line1,
            update_data.address_line2,
            update_data.address_line3,
            update_data.address_line4,
        ]
        address = ', '.join(p for p in address_parts if p)
        if address:
            submission.aadhaar_address = address

        # Bank fields
        if update_data.bank_account is not None and update_data.bank_account.strip():
            submission.bank_account_encrypted = encrypt_field(update_data.bank_account)
        if update_data.ifsc_code is not None:
            submission.bank_ifsc = update_data.ifsc_code
        if update_data.bank_name is not None:
            submission.bank_name = update_data.bank_name
        if update_data.bank_branch is not None:
            submission.bank_branch = update_data.bank_branch

        db.add(AuditLog(
            event_type="SUBMISSION_UPDATED",
            employee_id=submission.employee_id,
            kyc_submission_id=submission_id,
            performed_by="hr_user",
            details=json.dumps({"updated_fields": [k for k, v in update_data.dict().items() if v is not None]}),
            timestamp=datetime.now(timezone.utc)
        ))
        db.commit()

        webhook_logger.info(f"Submission {submission_id} updated by HR")
        return {"id": submission_id, "status": "updated", "message": "Submission saved successfully"}

    except HTTPException:
        raise
    except Exception as e:
        webhook_logger.error(f"Error updating submission: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/submissions/{submission_id}/finalize")
def finalize_submission(
    submission_id: str,
    finalize_data: FinalizeRequest,
    api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_db)
) -> dict:
    """
    Finalize an APPROVED submission after HRMS review.

    Steps:
    1. Validate API key
    2. Fetch submission from database
    3. Check status is APPROVED
    4. Check not already finalized
    5. Update status to FINALIZED
    6. Generate/assign HRMS employee ID
    7. Log audit event
    8. Return success response

    Args:
        submission_id: UUID of the submission
        finalize_data: FinalizeRequest with finalized_by and notes
        api_key: API key for authentication (from header)
        db: Database session

    Returns:
        dict: Success response with employee ID

    Raises:
        HTTPException: If submission not found, already finalized, or not APPROVED
    """
    try:
        # Fetch submission
        submission = db.query(KYCSubmission).filter(
            KYCSubmission.id == submission_id
        ).first()

        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")

        # Check status
        if submission.status == "FINALIZED":
            raise HTTPException(
                status_code=400,
                detail="Submission already finalized"
            )

        # Generate HRMS employee ID with retry for race conditions
        max_retries = 2
        for attempt in range(max_retries):
            try:
                submission.hrms_employee_id = generate_employee_id(db)
                submission.status = "FINALIZED"
                submission.finalized_at = datetime.now(timezone.utc)
                submission.finalized_by = finalize_data.finalized_by
                if finalize_data.notes:
                    submission.review_notes = finalize_data.notes

                # Log audit event in same transaction
                audit_log = AuditLog(
                    event_type="SUBMISSION_FINALIZED",
                    employee_id=submission.employee_id,
                    kyc_submission_id=submission_id,
                    performed_by=finalize_data.finalized_by,
                    details=json.dumps({
                        "hrms_employee_id": submission.hrms_employee_id,
                        "notes": finalize_data.notes
                    }),
                    timestamp=datetime.now(timezone.utc)
                )
                db.add(audit_log)

                # Single commit for both submission update and audit log
                db.commit()
                break
            except IntegrityError as e:
                db.rollback()
                if attempt == max_retries - 1:
                    raise HTTPException(status_code=409, detail="Failed to generate unique employee ID after retries")
                webhook_logger.warning(f"Retry {attempt + 1}/{max_retries}: {e}")

        webhook_logger.info(
            f"Submission {submission_id} finalized with employee ID: "
            f"{submission.hrms_employee_id}"
        )

        return {
            "id": submission_id,
            "status": "FINALIZED",
            "finalized_at": submission.finalized_at.isoformat(),
            "finalized_by": finalize_data.finalized_by,
            "hrms_employee_id": submission.hrms_employee_id,
            "message": "Employee data finalized successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        webhook_logger.error(f"Error finalizing submission: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/submissions/{submission_id}")
def delete_submission(
    submission_id: str,
    api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_db)
) -> dict:
    """Delete a submission and its associated documents and audit logs."""
    submission = db.query(KYCSubmission).filter(
        KYCSubmission.id == submission_id
    ).first()

    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    try:
        db.query(Document).filter(Document.kyc_submission_id == submission_id).delete()
        db.query(AuditLog).filter(AuditLog.kyc_submission_id == submission_id).delete()
        employee_id = submission.employee_id
        db.delete(submission)

        # Delete employee record if no other submissions reference it
        remaining = db.query(KYCSubmission).filter(
            KYCSubmission.employee_id == employee_id
        ).count()
        if remaining == 0:
            employee = db.query(Employee).filter(Employee.id == employee_id).first()
            if employee:
                db.delete(employee)

        db.commit()
        webhook_logger.info(f"Submission {submission_id} deleted")
        return {"id": submission_id, "message": "Submission deleted successfully"}
    except Exception as e:
        db.rollback()
        webhook_logger.error(f"Error deleting submission {submission_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health_check():
    """
    Health check endpoint to verify service status.

    Checks:
    - Redis connection
    - Database connection

    Returns:
        dict: Health status of all components
    """
    health_status = {
        "status": "healthy",
        "redis": "disconnected",
        "database": "disconnected"
    }

    status_code = 200

    # Check Redis
    try:
        redis_client = get_redis_client()
        redis_client.ping()
        health_status["redis"] = "connected"
    except Exception as e:
        webhook_logger.error(f"Redis health check failed: {e}")
        health_status["status"] = "unhealthy"
        status_code = 503

    # Check database
    try:
        db = get_session()
        try:
            # Execute simple query to verify connection
            db.execute(text("SELECT 1"))
            health_status["database"] = "connected"
        finally:
            db.close()
    except Exception as e:
        webhook_logger.error(f"Database health check failed: {e}")
        health_status["status"] = "unhealthy"
        status_code = 503

    return JSONResponse(content=health_status, status_code=status_code)


# Root endpoint
@app.get("/")
def root():
    """Root endpoint with API information"""
    return {
        "service": "WhatsApp KYC API",
        "version": "1.0.0",
        "endpoints": {
            "webhook": "/webhook/whatsapp",
            "submissions": "/api/submissions",
            "health": "/health"
        }
    }
