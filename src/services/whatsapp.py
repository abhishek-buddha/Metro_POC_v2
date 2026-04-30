"""WhatsApp messaging service using Twilio API."""
import re
from typing import Optional
from twilio.rest import Client
from src.utils.config import config
from src.utils.logger import logger


def format_phone_number(phone: str) -> str:
    """
    Format Indian phone number to WhatsApp format.

    Accepts multiple formats:
    - "9876543210" (10 digits)
    - "+919876543210" (with +91)
    - "919876543210" (with 91 but no +)
    - "9876 543 210" (with spaces)
    - "+91 9876 543210" (with +91 and spaces)

    Returns:
        WhatsApp formatted phone number: "whatsapp:+919876543210"

    Args:
        phone: Phone number in various Indian formats
    """
    if phone is None or not isinstance(phone, str):
        raise ValueError("Phone number must be a non-empty string")

    # Remove all spaces
    clean_phone = re.sub(r'\s', '', phone)

    # Remove '+' if present
    clean_phone = clean_phone.lstrip('+')

    # If it starts with 91, keep it as is
    # If it doesn't start with 91, assume it's a 10-digit number and add 91 prefix
    if not clean_phone.startswith('91'):
        clean_phone = '91' + clean_phone

    # Return WhatsApp formatted number
    return f"whatsapp:+{clean_phone}"


class WhatsAppClient:
    """Client for sending WhatsApp messages via Twilio."""

    def __init__(self):
        """
        Initialize WhatsApp client with Twilio credentials from config.

        Raises:
            ValueError: If required Twilio credentials are not configured
        """
        if config is None:
            raise ValueError("Configuration not loaded")

        self.client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
        self.from_number = config.TWILIO_WHATSAPP_NUMBER

    def send_message(self, to_phone: str, message: str) -> bool:
        """
        Send a text message via WhatsApp.

        Args:
            to_phone: Recipient's phone number (Indian format or with +91)
            message: Message text to send

        Returns:
            True if message sent successfully, False otherwise
        """
        formatted_phone = None
        try:
            formatted_phone = format_phone_number(to_phone)

            self.client.messages.create(
                from_=self.from_number,
                to=formatted_phone,
                body=message
            )

            logger.info(
                "WhatsApp message sent successfully",
                extra={
                    "phone_number": to_phone,
                    "formatted_phone": formatted_phone,
                    "message_type": "text"
                }
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to send WhatsApp message",
                extra={
                    "phone_number": to_phone,
                    "formatted_phone": formatted_phone,
                    "from_number": self.from_number,
                    "message_type": "text",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "twilio_code": getattr(e, 'code', None),
                    "twilio_status": getattr(e, 'status', None),
                    "twilio_msg": getattr(e, 'msg', None),
                }
            )
            return False

    def send_document_request(self, to_phone: str, doc_type: str) -> bool:
        """
        Send a document request message.

        Template: "Please send your {doc_type} photo."

        Args:
            to_phone: Recipient's phone number
            doc_type: Type of document requested (e.g., "Aadhaar card", "bank document")

        Returns:
            True if message sent successfully, False otherwise
        """
        message = f"Please send your {doc_type} photo."
        return self.send_message(to_phone, message)

    def send_confirmation(self, to_phone: str, submission_id: str) -> bool:
        """
        Send confirmation message for successful document submission.

        Template: "✅ Your KYC documents have been received (ID: {submission_id}). We'll review and notify you."

        Args:
            to_phone: Recipient's phone number
            submission_id: Unique submission ID for the KYC documents

        Returns:
            True if message sent successfully, False otherwise
        """
        message = f"✅ Your KYC documents have been received (ID: {submission_id}). We'll review and notify you."
        return self.send_message(to_phone, message)

    def send_welcome(self, to_phone: str) -> bool:
        """
        Send welcome message.

        Template: "Welcome to Metro KYC! Please send your PAN card photo."

        Args:
            to_phone: Recipient's phone number

        Returns:
            True if message sent successfully, False otherwise
        """
        message = "Welcome to Metro KYC! Please send your PAN card photo."
        return self.send_message(to_phone, message)

    def send_error(self, to_phone: str) -> bool:
        """
        Send error message.

        Template: "❌ Error processing your document. Please try again."

        Args:
            to_phone: Recipient's phone number

        Returns:
            True if message sent successfully, False otherwise
        """
        message = "❌ Error processing your document. Please try again."
        return self.send_message(to_phone, message)
