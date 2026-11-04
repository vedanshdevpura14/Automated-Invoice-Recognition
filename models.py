import os
import json
from datetime import datetime
from typing import Optional, List, Any
from pathlib import Path

from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session

BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'cacheflow.db'}")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Reconciliation Tolerances
AMOUNT_TOLERANCE = float(os.getenv("AMOUNT_TOLERANCE", "1.0"))   # Rounding difference tolerance
TAX_TOLERANCE = float(os.getenv("TAX_TOLERANCE", "1.0"))         # Tax rounding tolerance
PRICE_TOLERANCE = float(os.getenv("PRICE_TOLERANCE", "0.01"))    # Unit price variance tolerance

# Database Engine & Session
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)


# ==========================================================
# 1. Pydantic Schemas (API Data Contracts)
# ==========================================================

class LineItemSchema(BaseModel):
    item_code: str = Field(default="", description="Product SKU or identifier")
    description: Optional[str] = Field(default="", description="Item description")
    quantity: float = Field(default=0.0, ge=0)
    unit_price: float = Field(default=0.0, ge=0)
    total_price: float = Field(default=0.0, ge=0)


class DocumentDataSchema(BaseModel):
    document_type: str = Field(..., description="'invoice', 'purchase_order', or 'grn'")
    vendor_name: str = Field(default="Unknown Vendor")
    document_number: str = Field(default="")
    document_date: Optional[str] = Field(default="")
    currency: str = Field(default="INR")
    subtotal: float = Field(default=0.0)
    tax: float = Field(default=0.0)
    total_amount: float = Field(default=0.0)
    line_items: List[LineItemSchema] = Field(default_factory=list)


class VarianceItem(BaseModel):
    field: str
    item_code: Optional[str] = None
    description: Optional[str] = None
    invoice_val: Any = None
    comparison_val: Any = None
    variance_amount: float = 0.0
    message: str = ""


class LineItemComparisonResult(BaseModel):
    item_code: str
    description: str
    invoice_qty: float
    grn_qty: Optional[float]
    qty_status: str
    invoice_unit_price: float
    po_unit_price: Optional[float]
    price_status: str
    invoice_line_total: float
    po_line_total: float
    variance_amount: float
    status: str


class ThreeWayMatchResult(BaseModel):
    status: str
    vendor_matched: bool
    invoice_vendor: str
    po_vendor: str
    invoice_total: float
    po_total: float
    invoice_tax: float
    po_tax: float
    variance_total: float
    match_score: float
    variances: List[VarianceItem] = Field(default_factory=list)
    line_comparisons: List[LineItemComparisonResult] = Field(default_factory=list)


class ArbitrationResponse(BaseModel):
    risk_severity: str
    confidence_score: float
    summary: str
    recommended_action: str
    dispute_email_draft: str
    findings: List[str] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    action: str = Field(..., description="APPROVED | REJECTED | ESCALATED")
    notes: Optional[str] = Field(default="", description="Reviewer notes")
    reviewer_name: Optional[str] = Field(default="Finance Specialist")


# ==========================================================
# 2. SQLAlchemy Database Tables
# ==========================================================

class ReconciliationRecord(Base):
    __tablename__ = "reconciliations"

    id = Column(Integer, primary_key=True, index=True)
    reconciliation_code = Column(String(50), unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    vendor_name = Column(String(200), index=True)
    invoice_number = Column(String(100), index=True)
    po_number = Column(String(100), index=True)
    grn_number = Column(String(100), nullable=True)
    currency = Column(String(10), default="INR")

    invoice_total = Column(Float, default=0.0)
    po_total = Column(Float, default=0.0)
    invoice_tax = Column(Float, default=0.0)
    po_tax = Column(Float, default=0.0)
    variance_total = Column(Float, default=0.0)

    status = Column(String(50), default="PENDING", index=True)
    has_exceptions = Column(Boolean, default=False)
    match_score = Column(Float, default=100.0)

    risk_severity = Column(String(20), default="LOW")
    confidence_score = Column(Float, default=0.0)
    arbitration_summary = Column(Text, nullable=True)
    dispute_email_draft = Column(Text, nullable=True)

    reviewer_action = Column(String(50), nullable=True)
    reviewer_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    invoice_json_str = Column(Text, nullable=True)
    po_json_str = Column(Text, nullable=True)
    grn_json_str = Column(Text, nullable=True)

    invoice_file = Column(String(255), nullable=True)
    po_file = Column(String(255), nullable=True)
    grn_file = Column(String(255), nullable=True)

    line_items = relationship("ReconciliationLineItem", back_populates="reconciliation", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLogEntry", back_populates="reconciliation", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "reconciliation_code": self.reconciliation_code,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "vendor_name": self.vendor_name,
            "invoice_number": self.invoice_number,
            "po_number": self.po_number,
            "grn_number": self.grn_number,
            "currency": self.currency,
            "invoice_total": self.invoice_total,
            "po_total": self.po_total,
            "invoice_tax": self.invoice_tax,
            "po_tax": self.po_tax,
            "variance_total": self.variance_total,
            "status": self.status,
            "has_exceptions": self.has_exceptions,
            "match_score": self.match_score,
            "risk_severity": self.risk_severity,
            "confidence_score": self.confidence_score,
            "arbitration_summary": self.arbitration_summary,
            "dispute_email_draft": self.dispute_email_draft,
            "reviewer_action": self.reviewer_action,
            "reviewer_notes": self.reviewer_notes,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "invoice_data": json.loads(self.invoice_json_str) if self.invoice_json_str else None,
            "po_data": json.loads(self.po_json_str) if self.po_json_str else None,
            "grn_data": json.loads(self.grn_json_str) if self.grn_json_str else None,
            "line_items": [item.to_dict() for item in self.line_items]
        }


class ReconciliationLineItem(Base):
    __tablename__ = "reconciliation_line_items"

    id = Column(Integer, primary_key=True, index=True)
    reconciliation_id = Column(Integer, ForeignKey("reconciliations.id"), index=True)

    item_code = Column(String(100), index=True)
    description = Column(String(255), nullable=True)

    invoice_qty = Column(Float, default=0.0)
    grn_qty = Column(Float, nullable=True)
    qty_status = Column(String(50), default="MATCH")

    invoice_unit_price = Column(Float, default=0.0)
    po_unit_price = Column(Float, nullable=True)
    price_status = Column(String(50), default="MATCH")

    invoice_line_total = Column(Float, default=0.0)
    po_line_total = Column(Float, default=0.0)
    variance_amount = Column(Float, default=0.0)
    status = Column(String(50), default="MATCHED")

    reconciliation = relationship("ReconciliationRecord", back_populates="line_items")

    def to_dict(self):
        return {
            "id": self.id,
            "item_code": self.item_code,
            "description": self.description,
            "invoice_qty": self.invoice_qty,
            "grn_qty": self.grn_qty,
            "qty_status": self.qty_status,
            "invoice_unit_price": self.invoice_unit_price,
            "po_unit_price": self.po_unit_price,
            "price_status": self.price_status,
            "invoice_line_total": self.invoice_line_total,
            "po_line_total": self.po_line_total,
            "variance_amount": self.variance_amount,
            "status": self.status
        }


class AuditLogEntry(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    reconciliation_id = Column(Integer, ForeignKey("reconciliations.id"), nullable=True, index=True)
    event_type = Column(String(50), index=True)
    source = Column(String(100))
    description = Column(Text)
    severity = Column(String(20), default="INFO")

    reconciliation = relationship("ReconciliationRecord", back_populates="audit_logs")

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "reconciliation_id": self.reconciliation_id,
            "event_type": self.event_type,
            "source": self.source,
            "description": self.description,
            "severity": self.severity
        }


class VendorMemoryRecord(Base):
    __tablename__ = "vendor_memory"

    id = Column(Integer, primary_key=True, index=True)
    canonical_name = Column(String(200), unique=True, index=True)
    aliases_json = Column(Text, default="[]")
    total_reconciliations = Column(Integer, default=0)
    successful_matches = Column(Integer, default=0)
    notes = Column(Text, nullable=True)

    def get_aliases(self) -> list[str]:
        try:
            return json.loads(self.aliases_json)
        except Exception:
            return []

    def to_dict(self):
        return {
            "id": self.id,
            "canonical_name": self.canonical_name,
            "aliases": self.get_aliases(),
            "total_reconciliations": self.total_reconciliations,
            "successful_matches": self.successful_matches,
            "notes": self.notes
        }


# ==========================================================
# 3. Audit & Memory Helpers
# ==========================================================

def record_audit_log(
    db: Session,
    event_type: str,
    source: str,
    description: str,
    severity: str = "INFO",
    reconciliation_id: Optional[int] = None
) -> AuditLogEntry:
    log_entry = AuditLogEntry(
        reconciliation_id=reconciliation_id,
        event_type=event_type,
        source=source,
        description=description,
        severity=severity,
        timestamp=datetime.utcnow()
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry


def update_vendor_memory(db: Session, vendor_name: str, was_matched: bool):
    if not vendor_name:
        return

    record = db.query(VendorMemoryRecord).filter(
        VendorMemoryRecord.canonical_name.ilike(vendor_name.strip())
    ).first()

    if not record:
        record = VendorMemoryRecord(
            canonical_name=vendor_name.strip(),
            aliases_json=json.dumps([vendor_name.strip()]),
            total_reconciliations=1,
            successful_matches=1 if was_matched else 0,
            notes="Auto-registered by CacheFlow agent"
        )
        db.add(record)
    else:
        record.total_reconciliations += 1
        if was_matched:
            record.successful_matches += 1

    db.commit()
