import hashlib
from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

from ..core.encryption import EncryptedString

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="user")
    license_number = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PatientRecord(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(128), unique=True, index=True)
    document_type = Column(String(32), nullable=False)
    document_number_hash = Column(String(64), nullable=False, index=True)
    document_number = Column(EncryptedString, nullable=False)
    first_name = Column(EncryptedString, nullable=False)
    last_name = Column(EncryptedString, nullable=False)
    gender = Column(EncryptedString, nullable=False)
    birth_date = Column(EncryptedString, nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ObservationRecord(Base):
    __tablename__ = "observations"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, nullable=False)
    loinc_code = Column(String(32), nullable=False)
    status = Column(String(32), default="final")
    value = Column(String(255), nullable=True)
    unit = Column(String(64), nullable=True)
    effective_datetime = Column(String(32), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String(255), nullable=False)
    action = Column(String(128), nullable=False)
    resource_type = Column(String(64), nullable=False)
    resource_id = Column(String(128), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    details = Column(EncryptedString, nullable=True)


class ProcedureLog(Base):
    __tablename__ = "procedure_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String(255), nullable=False, index=True)
    action = Column(String(128), nullable=False)
    patient_id = Column(String(128), nullable=True, index=True)
    patient_name = Column(EncryptedString, nullable=True)
    patient_identifier = Column(EncryptedString, nullable=True)
    comment = Column(EncryptedString, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
