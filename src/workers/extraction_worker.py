"""Extraction worker for background job processing."""
import json
import time
import uuid
from datetime import datetime
from typing import Dict, Tuple

from src.utils.redis_client import get_redis_client
from src.utils.logger import logger
from src.models.database import get_db, Employee, KYCSubmission, Document, AuditLog
from src.services.classification import DocumentClassifier
from src.services.ocr_extraction import OCRExtractor
from src.services.ai_extraction import AIExtractor
from src.services.whatsapp import WhatsAppClient
from src.services.encryption import encrypt_field, mask_aadhaar
from src.services.validation import calculate_name_match

# Initialize services (lazy initialization for testability)
_classifier = None
_ocr_extractor = None
_ai_extractor = None
_whatsapp_client = None


def _get_classifier():
    """Get or create classifier instance."""
    global _classifier
    if _classifier is None:
        _classifier = DocumentClassifier()
    return _classifier


def _get_ocr_extractor():
    """Get or create OCR extractor instance."""
    global _ocr_extractor
    if _ocr_extractor is None:
        _ocr_extractor = OCRExtractor()
    return _ocr_extractor


def _get_ai_extractor():
    """Get or create AI extractor instance."""
    global _ai_extractor
    if _ai_extractor is None:
        _ai_extractor = AIExtractor()
    return _ai_extractor


def _get_whatsapp_client():
    """Get or create WhatsApp client instance."""
    global _whatsapp_client
    if _whatsapp_client is None:
        _whatsapp_client = WhatsAppClient()
    return _whatsapp_client


def process_job(job: Dict) -> None:
    """
    Process a single extraction job through the pipeline.

    Pipeline steps:
    1. Classify document
    2. Extract data based on document type
    3. Validate extraction
    4. Store in database
    5. Send WhatsApp notification

    Args:
        job: Job dictionary from Redis with keys:
            - job_id: Unique job identifier
            - phone_number: User's phone number
            - file_path: Path to uploaded document
            - timestamp: Job creation timestamp
            - status: Job status
    """
    job_id = job.get("job_id")
    phone_number = job.get("phone_number")
    file_path = job.get("file_path")

    logger.info(
        "Processing job",
        extra={
            "job_id": job_id,
            "phone_number": phone_number,
            "file_path": file_path
        }
    )

    try:
        # Step 1: Classify and extract
        doc_type, classification_confidence, extracted_data = classify_and_extract(file_path)

        logger.info(
            "Classification complete",
            extra={
                "job_id": job_id,
                "doc_type": doc_type,
                "confidence": classification_confidence
            }
        )

        # Check classification confidence
        if classification_confidence < 0.7:
            logger.warning(
                "Low classification confidence",
                extra={
                    "job_id": job_id,
                    "confidence": classification_confidence
                }
            )
            _get_whatsapp_client().send_error(phone_number)
            return

        # Check if document type is unknown
        if doc_type == "UNKNOWN":
            logger.warning(
                "Unknown document type",
                extra={"job_id": job_id}
            )
            _get_whatsapp_client().send_error(phone_number)
            return

        # Step 3: Validate extraction
        is_valid, validation_confidence = validate_extraction(extracted_data, doc_type)

        logger.info(
            "Validation complete",
            extra={
                "job_id": job_id,
                "is_valid": is_valid,
                "confidence": validation_confidence
            }
        )

        if not is_valid:
            logger.warning(
                "Extraction validation failed",
                extra={"job_id": job_id}
            )
            _get_whatsapp_client().send_error(phone_number)
            return

        # Step 4: Store in database
        submission_id = store_in_database(
            job,
            extracted_data,
            doc_type,
            validation_confidence
        )

        logger.info(
            "Data stored in database",
            extra={
                "job_id": job_id,
                "submission_id": submission_id
            }
        )

        # Step 5: Send notification
        send_notifications(phone_number, submission_id)

        logger.info(
            "Job processed successfully",
            extra={
                "job_id": job_id,
                "submission_id": submission_id
            }
        )

    except Exception as e:
        logger.error(
            f"Job processing failed: {str(e)}",
            extra={
                "job_id": job_id,
                "phone_number": phone_number,
                "file_path": file_path
            }
        )
        # Send error message to user
        try:
            _get_whatsapp_client().send_error(phone_number)
        except Exception as notify_error:
            logger.error(
                f"Failed to send error notification: {str(notify_error)}",
                extra={"job_id": job_id}
            )


def classify_and_extract(file_path: str) -> Tuple[str, float, Dict]:
    """
    Classify document and extract data based on type.

    Args:
        file_path: Path to document image

    Returns:
        Tuple of (doc_type, confidence, extracted_data)
    """
    # Step 1: Classify document
    doc_type, confidence = _get_classifier().classify_document(file_path)

    logger.info(
        "Document classified",
        extra={
            "file_path": file_path,
            "doc_type": doc_type,
            "confidence": confidence
        }
    )

    # Step 2: Extract based on document type
    if doc_type == "PAN_CARD":
        extracted_data = _get_ocr_extractor().extract_pan_data(file_path)
        # If OCR extraction fails (confidence < 0.7), fall back to AI
        if extracted_data.get("confidence", 0.0) < 0.7:
            logger.info("OCR extraction failed for PAN, falling back to AI")
            extracted_data = _get_ai_extractor().extract_pan_data(file_path)
            logger.info(f"AI fallback completed with confidence {extracted_data.get('confidence', 0.0)}")
    elif doc_type == "AADHAAR_CARD":
        extracted_data = _get_ocr_extractor().extract_aadhaar_data(file_path)
        # If OCR extraction fails (confidence < 0.7), fall back to AI
        if extracted_data.get("confidence", 0.0) < 0.7:
            logger.info("OCR extraction failed for Aadhaar, falling back to AI")
            extracted_data = _get_ai_extractor().extract_aadhaar_data(file_path)
            logger.info(f"AI fallback completed with confidence {extracted_data.get('confidence', 0.0)}")
    elif doc_type == "BANK_DOCUMENT":
        extracted_data = _get_ai_extractor().extract_bank_data(file_path)
    else:
        # Unknown document type
        extracted_data = {"confidence": 0.0}

    return doc_type, confidence, extracted_data


def validate_extraction(data: Dict, doc_type: str) -> Tuple[bool, float]:
    """
    Validate extracted data.

    Args:
        data: Extracted data dictionary
        doc_type: Document type (PAN_CARD, AADHAAR_CARD, BANK_DOCUMENT)

    Returns:
        Tuple of (is_valid, confidence)
    """
    confidence = data.get("confidence", 0.0)

    # Check required fields based on document type
    if doc_type == "PAN_CARD":
        required_fields = ["pan_number", "name", "dob"]
        is_valid = all(data.get(field) for field in required_fields)
    elif doc_type == "AADHAAR_CARD":
        # Accept front (has name) OR back (has address) — both are valid Aadhaar sides
        has_front = bool(data.get("aadhaar_number") and data.get("name"))
        has_back = bool(data.get("address"))
        is_valid = has_front or has_back
    elif doc_type == "BANK_DOCUMENT":
        required_fields = ["account_number", "account_holder_name", "ifsc_code"]
        is_valid = all(data.get(field) for field in required_fields)
    else:
        is_valid = False

    return is_valid, confidence


def store_in_database(job: Dict, data: Dict, doc_type: str, confidence: float) -> str:
    """
    Store extracted data in database.

    Args:
        job: Job dictionary with phone_number and file_path
        data: Extracted data dictionary
        doc_type: Document type (PAN_CARD, AADHAAR_CARD, BANK_DOCUMENT)
        confidence: Extraction confidence score

    Returns:
        submission_id: ID of the KYC submission
    """
    phone_number = job.get("phone_number")
    file_path = job.get("file_path")

    with get_db() as db:
        # Get or create employee
        employee = db.query(Employee).filter_by(phone_number=phone_number).first()
        if not employee:
            employee = Employee(
                id=str(uuid.uuid4()),
                phone_number=phone_number
            )
            db.add(employee)
            db.flush()  # Get employee ID

            logger.info(
                "Created new employee",
                extra={
                    "employee_id": employee.id,
                    "phone_number": phone_number
                }
            )

        # Get or create KYC submission
        submission = db.query(KYCSubmission).filter_by(employee_id=employee.id).first()
        if not submission:
            submission = KYCSubmission(
                id=str(uuid.uuid4()),
                employee_id=employee.id,
                status="PENDING"
            )
            db.add(submission)
            db.flush()  # Get submission ID

            logger.info(
                "Created new KYC submission",
                extra={
                    "submission_id": submission.id,
                    "employee_id": employee.id
                }
            )

        # Update submission based on document type
        if doc_type == "PAN_CARD":
            # Encrypt PAN number
            if data.get("pan_number"):
                submission.pan_number_encrypted = encrypt_field(data["pan_number"])
            submission.pan_name = data.get("name")
            submission.pan_father_name = data.get("father_name")
            submission.pan_dob = data.get("dob")
            submission.pan_confidence = confidence

        elif doc_type == "AADHAAR_CARD":
            # Smart merge: front has name/dob/gender, back has address.
            # Never overwrite an existing field with null — always keep the best data.
            if data.get("aadhaar_number"):
                submission.aadhaar_last4 = mask_aadhaar(data["aadhaar_number"])
            if data.get("name"):
                submission.aadhaar_name = data["name"]
            if data.get("dob") and not submission.aadhaar_dob:
                # Only set DOB from front (which has real DOB); skip back-side misreads
                submission.aadhaar_dob = data["dob"]
            if data.get("gender"):
                submission.aadhaar_gender = data["gender"]
            if data.get("address"):
                submission.aadhaar_address = data["address"]
            if data.get("pincode"):
                submission.aadhaar_pincode = data["pincode"]
            # Keep the highest confidence seen across front and back
            if not submission.aadhaar_confidence or confidence > submission.aadhaar_confidence:
                submission.aadhaar_confidence = confidence

        elif doc_type == "BANK_DOCUMENT":
            # Encrypt bank account number
            if data.get("account_number"):
                submission.bank_account_encrypted = encrypt_field(data["account_number"])
            submission.bank_holder_name = data.get("account_holder_name")
            submission.bank_ifsc = data.get("ifsc_code")
            submission.bank_name = data.get("bank_name")
            submission.bank_branch = data.get("branch_name")
            submission.bank_account_type = data.get("account_type")
            submission.bank_micr = data.get("micr_code")
            submission.bank_confidence = confidence

        # Calculate cross-document name match if multiple documents present
        names = []
        if submission.pan_name:
            names.append(submission.pan_name)
        if submission.aadhaar_name:
            names.append(submission.aadhaar_name)
        if submission.bank_holder_name:
            names.append(submission.bank_holder_name)

        # Calculate name match score if we have at least 2 names
        if len(names) >= 2:
            # Calculate average match between all pairs
            total_matches = 0
            num_comparisons = 0
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    match_score = calculate_name_match(names[i], names[j])
                    total_matches += match_score
                    num_comparisons += 1

            if num_comparisons > 0:
                submission.name_match_score = total_matches / num_comparisons

        # Calculate overall confidence (average of available confidences)
        confidences = []
        if submission.pan_confidence:
            confidences.append(submission.pan_confidence)
        if submission.aadhaar_confidence:
            confidences.append(submission.aadhaar_confidence)
        if submission.bank_confidence:
            confidences.append(submission.bank_confidence)

        if confidences:
            submission.overall_confidence = sum(confidences) / len(confidences)

        # Set status based on confidence
        if submission.overall_confidence and submission.overall_confidence >= 0.7:
            submission.status = "PENDING"
        else:
            submission.status = "NEEDS_REVIEW"

        # Create document record
        document = Document(
            id=str(uuid.uuid4()),
            kyc_submission_id=submission.id,
            document_type=doc_type,
            file_path=file_path,
            extraction_method="OCR" if doc_type in ["PAN_CARD", "AADHAAR_CARD"] else "AI",
            raw_extraction_json=json.dumps(data)
        )
        db.add(document)

        # Create audit log
        audit_log = AuditLog(
            event_type="DOCUMENT_PROCESSED",
            employee_id=employee.id,
            kyc_submission_id=submission.id,
            performed_by="SYSTEM",
            details=f"Processed {doc_type} with confidence {confidence}"
        )
        db.add(audit_log)

        logger.info(
            "Document record created",
            extra={
                "document_id": document.id,
                "submission_id": submission.id,
                "doc_type": doc_type
            }
        )

        return submission.id


def send_notifications(phone: str, submission_id: str) -> None:
    """
    Send WhatsApp confirmation message.

    Args:
        phone: User's phone number
        submission_id: KYC submission ID
    """
    try:
        _get_whatsapp_client().send_confirmation(phone, submission_id)
        logger.info(
            "Confirmation sent",
            extra={
                "phone_number": phone,
                "submission_id": submission_id
            }
        )
    except Exception as e:
        logger.error(
            f"Failed to send confirmation: {str(e)}",
            extra={
                "phone_number": phone,
                "submission_id": submission_id
            }
        )


def main():
    """Main worker loop."""
    logger.info("Starting extraction worker")
    redis_client = get_redis_client()

    while True:
        try:
            # BLPOP blocks until job available (timeout 5 seconds)
            result = redis_client.blpop('kyc:jobs', timeout=5)

            if result:
                _, job_json = result
                job = json.loads(job_json)

                logger.info(
                    "Job received from queue",
                    extra={"job_id": job.get("job_id")}
                )

                process_job(job)

        except KeyboardInterrupt:
            logger.info("Worker shutdown requested")
            break
        except Exception as e:
            logger.error(f"Worker error: {str(e)}")
            time.sleep(1)  # Prevent tight loop on persistent errors


if __name__ == '__main__':
    main()
