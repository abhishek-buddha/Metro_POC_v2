"""
SQLAlchemy database models for KYC automation system.

Models:
- Employee: User records with phone numbers
- KYCSubmission: Complete KYC submission with extracted data
- Document: Uploaded documents (PAN, Aadhaar, bank statement)
- AuditLog: Audit trail for all system events
"""

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    Index,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from src.utils.config import get_config
from src.utils.logger import setup_logger

Base = declarative_base()
logger = setup_logger(__name__)


class Employee(Base):
    """Employee model with phone number as primary identifier"""

    __tablename__ = "employees"

    id = Column(String(255), primary_key=True)
    phone_number = Column(String(20), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    kyc_submissions = relationship(
        "KYCSubmission", back_populates="employee", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Employee(id={self.id}, phone_number={self.phone_number})>"


class KYCSubmission(Base):
    """KYC submission with all extracted data from documents"""

    __tablename__ = "kyc_submissions"

    id = Column(String(255), primary_key=True)
    employee_id = Column(
        String(255), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    status = Column(String(50), nullable=False, index=True, default='PENDING')

    # PAN fields
    pan_number_encrypted = Column(String(500), nullable=True)
    pan_name = Column(String(255), nullable=True)
    pan_father_name = Column(String(255), nullable=True)
    pan_dob = Column(String(50), nullable=True)
    pan_confidence = Column(Float, nullable=True)

    # Aadhaar fields
    aadhaar_last4 = Column(String(4), nullable=True)
    aadhaar_name = Column(String(255), nullable=True)
    aadhaar_dob = Column(String(50), nullable=True)
    aadhaar_gender = Column(String(20), nullable=True)
    aadhaar_address = Column(Text, nullable=True)
    aadhaar_pincode = Column(String(10), nullable=True)
    aadhaar_confidence = Column(Float, nullable=True)

    # Bank fields
    bank_account_encrypted = Column(String(500), nullable=True)
    bank_holder_name = Column(String(255), nullable=True)
    bank_ifsc = Column(String(20), nullable=True)
    bank_name = Column(String(255), nullable=True)
    bank_branch = Column(String(255), nullable=True)
    bank_account_type = Column(String(50), nullable=True)
    bank_micr = Column(String(20), nullable=True)
    bank_confidence = Column(Float, nullable=True)

    # HR-edited fields (saved when form is submitted)
    blood_group = Column(String(10), nullable=True)
    marital_status = Column(String(50), nullable=True)

    # Previous employment (HR-entered during onboarding)
    previously_worked = Column(String(10), nullable=True)   # 'yes' or 'no'
    previous_employee_id = Column(String(100), nullable=True)

    # Cross-validation fields
    name_match_score = Column(Float, nullable=True)
    overall_confidence = Column(Float, nullable=True)

    # Metadata
    submitted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String(255), nullable=True)
    review_notes = Column(Text, nullable=True)

    # Finalization fields
    finalized_at = Column(DateTime, nullable=True)
    finalized_by = Column(String(255), nullable=True)
    hrms_employee_id = Column(String(50), unique=True, nullable=True, index=True)

    # Relationships
    employee = relationship("Employee", back_populates="kyc_submissions")
    documents = relationship(
        "Document", back_populates="kyc_submission", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<KYCSubmission(id={self.id}, employee_id={self.employee_id}, status={self.status})>"


class Document(Base):
    """Document model for uploaded files (PAN, Aadhaar, bank statement)"""

    __tablename__ = "documents"

    id = Column(String(255), primary_key=True)
    kyc_submission_id = Column(
        String(255),
        ForeignKey("kyc_submissions.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id = Column(String(255), nullable=True, index=True)
    document_type = Column(String(50), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=True)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    extraction_method = Column(String(100), nullable=True)
    raw_extraction_json = Column(Text, nullable=True)

    # Relationships
    kyc_submission = relationship("KYCSubmission", back_populates="documents")

    def __repr__(self):
        return f"<Document(id={self.id}, type={self.document_type}, kyc_submission_id={self.kyc_submission_id})>"


class AuditLog(Base):
    """Audit log for tracking all system events"""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(100), nullable=False)
    employee_id = Column(String(255), nullable=True, index=True)
    kyc_submission_id = Column(String(255), nullable=True)
    performed_by = Column(String(255), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    def __repr__(self):
        return f"<AuditLog(id={self.id}, event_type={self.event_type}, timestamp={self.timestamp})>"


def init_database() -> None:
    """
    Initialize the database by creating all tables and necessary directories.

    This function:
    1. Creates the data directory if it doesn't exist
    2. Creates the database engine
    3. Creates all tables defined in the models
    4. Logs success
    """
    try:
        config = get_config()

        # Create data directory if it doesn't exist
        db_path = config.DATABASE_PATH
        data_dir = os.path.dirname(db_path)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
            logger.info(f"Created data directory: {data_dir}")

        # Create database engine
        database_url = f"sqlite:///{db_path}"
        engine = create_engine(database_url, echo=False)

        # Create all tables
        Base.metadata.create_all(engine)

        logger.info(f"Database initialized successfully at {db_path}")
        logger.info(f"Created tables: {', '.join(Base.metadata.tables.keys())}")

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def get_session():
    """
    Create and return a new database session.

    Returns:
        Session: SQLAlchemy session instance
    """
    try:
        config = get_config()
        database_url = f"sqlite:///{config.DATABASE_PATH}"
        engine = create_engine(database_url, echo=False)
        Session = sessionmaker(bind=engine)
        return Session()
    except Exception as e:
        logger.error(f"Failed to create database session: {e}")
        raise


@contextmanager
def get_db():
    """
    Context manager for database sessions.

    Yields:
        Session: SQLAlchemy session instance

    Example:
        with get_db() as db:
            employee = db.query(Employee).first()
    """
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
