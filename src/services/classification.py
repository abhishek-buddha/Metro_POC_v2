"""Document classification service using keyword detection and AI fallback."""
import base64
import mimetypes
import sys
from typing import Tuple
from unittest.mock import MagicMock

from openai import OpenAI

from src.utils.config import config
from src.utils.logger import logger

# Handle easyocr import for compatibility with mocking
try:
    import easyocr
except ImportError:
    # Create a mock module for easyocr if not installed (for testing)
    easyocr = MagicMock()


class DocumentClassifier:
    """
    Two-stage document classifier for KYC documents.

    Stage 1: Keyword detection (fast, free)
    - Extracts text using EasyOCR
    - Searches for document-specific keywords
    - Returns HIGH confidence (0.95) if keywords found

    Stage 2: AI fallback (accurate, costs tokens)
    - Uses Claude Vision API for unclear documents
    - Returns confidence of 0.85 for successful classification
    """

    # Keywords for each document type
    PAN_KEYWORDS = {"INCOME TAX", "PERMANENT ACCOUNT NUMBER", "PAN"}
    AADHAAR_KEYWORDS = {"AADHAAR", "आधार", "UIDAI", "GOVERNMENT OF INDIA"}
    BANK_KEYWORDS = {"BANK", "IFSC", "ACCOUNT", "BRANCH"}

    def __init__(self):
        """Initialize OpenAI client. EasyOCR bypassed for memory efficiency."""
        logger.info("Initializing DocumentClassifier (AI-only mode)")
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        logger.info("DocumentClassifier initialized successfully")

    def classify_document(self, file_path: str) -> Tuple[str, float]:
        """
        Classify a document using two-stage pipeline.

        Stage 1: Try keyword detection on OCR text
        Stage 2: Fallback to AI classification if Stage 1 fails

        Args:
            file_path: Path to document image file

        Returns:
            Tuple of (doc_type, confidence) where:
            - doc_type: One of "PAN_CARD", "AADHAAR_CARD", "BANK_DOCUMENT", "UNKNOWN"
            - confidence: Float between 0.0 and 1.0

        Raises:
            Exception: If file cannot be read or processed
        """
        logger.info(
            f"Classifying document",
            extra={"file_path": file_path}
        )

        # AI-only classification — EasyOCR/PyTorch bypassed to reduce memory usage
        logger.info("Classifying with AI (AI-only mode)", extra={"file_path": file_path})
        doc_type, confidence = self._classify_with_ai(file_path)
        logger.info(
            "Document classified with AI",
            extra={"file_path": file_path, "doc_type": doc_type, "confidence": confidence}
        )
        return doc_type, confidence

    def _classify_with_keywords(self, text: str) -> Tuple[str, float]:
        """
        Classify document using keyword detection (Stage 1).

        Performs case-insensitive keyword search on extracted text.

        Args:
            text: Text extracted from document

        Returns:
            Tuple of (doc_type, confidence) where confidence is 0.95 if keywords found,
            0.0 if no keywords found
        """
        # Convert text to uppercase for case-insensitive matching
        text_upper = text.upper()

        # Check PAN keywords
        if any(keyword in text_upper for keyword in self.PAN_KEYWORDS):
            logger.info("PAN card detected via keyword matching")
            return "PAN_CARD", 0.95

        # Check Aadhaar keywords
        if any(keyword in text_upper for keyword in self.AADHAAR_KEYWORDS):
            logger.info("Aadhaar card detected via keyword matching")
            return "AADHAAR_CARD", 0.95

        # Check Bank keywords
        if any(keyword in text_upper for keyword in self.BANK_KEYWORDS):
            logger.info("Bank document detected via keyword matching")
            return "BANK_DOCUMENT", 0.95

        # No keywords matched
        logger.info("No keywords matched for document classification")
        return "UNKNOWN", 0.0

    def _classify_with_ai(self, file_path: str) -> Tuple[str, float]:
        """
        Classify document using OpenAI GPT-4 Vision API (Stage 2).

        Sends image to GPT-4o-mini for classification with vision capability.

        Args:
            file_path: Path to document image file

        Returns:
            Tuple of (doc_type, confidence) where:
            - confidence is 0.85 for A/B/C responses, 0.5 for D (unclear)
        """
        # Read image file and convert to base64
        try:
            with open(file_path, 'rb') as f:
                image_data = f.read()
            image_base64 = base64.standard_b64encode(image_data).decode('utf-8')
            logger.info(f"Image read and encoded to base64: {file_path}")
        except Exception as e:
            logger.error(f"Failed to read image file: {str(e)}")
            return "UNKNOWN", 0.0

        # Detect media type
        media_type, _ = mimetypes.guess_type(file_path)
        if not media_type:
            # Default to JPEG if type cannot be determined
            media_type = "image/jpeg"
        logger.info(f"Detected media type: {media_type}")

        # Call OpenAI GPT-4o Vision API
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                max_tokens=5,
                temperature=0,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "You are classifying Indian KYC documents. "
                                    "Look at the image and pick ONE letter:\n\n"
                                    "A) PAN Card — issued by India Income Tax Dept. "
                                    "Has text 'INCOME TAX DEPARTMENT' or 'Permanent Account Number', "
                                    "a 10-character PAN number like ABCDE1234F, person's photo, DOB, father's name.\n\n"
                                    "B) Aadhaar Card — India national ID issued by UIDAI. "
                                    "Has 'AADHAAR' or 'आधार' text, 12-digit Aadhaar number, "
                                    "person's photo and DOB (front side) OR full address with pincode (back side). "
                                    "May have a QR code.\n\n"
                                    "C) Bank Document — cancelled cheque, bank passbook page, or bank statement. "
                                    "Shows bank name/logo, account number, IFSC code, branch, account holder name.\n\n"
                                    "D) Other — anything else.\n\n"
                                    "Reply with ONLY the single letter A, B, C, or D."
                                )
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{image_base64}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ]
            )
            logger.info("OpenAI Vision API response received")
        except Exception as e:
            logger.error(f"OpenAI Vision API call failed: {str(e)}")
            return "UNKNOWN", 0.0

        # Parse response — take first alphabetic character to handle "A.", "A)" etc.
        raw = response.choices[0].message.content.strip().upper()
        logger.info(f"AI classification response: {raw}")
        response_text = next((c for c in raw if c in "ABCD"), "")

        # Map response to document type
        if response_text == "A":
            return "PAN_CARD", 0.85
        elif response_text == "B":
            return "AADHAAR_CARD", 0.85
        elif response_text == "C":
            return "BANK_DOCUMENT", 0.85
        elif response_text == "D":
            return "UNKNOWN", 0.5
        else:
            logger.warning(f"Unexpected AI response: {raw}")
            return "UNKNOWN", 0.0
