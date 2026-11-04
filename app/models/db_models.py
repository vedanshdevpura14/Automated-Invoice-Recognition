import json
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class ReconciliationRecord(Base):
    __tablename__ = "reconciliations"

    id = Column(Integer, primary_key=True, index=True)
    reconciliation_code = Column(String(50), unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Parties & Document references
    vendor_name = Column(String(200), index=True)
    invoice_number = Column(String(100), index=True)
    po_number = Column(String(100), index=True)
    grn_number = Column(String(100), nullable=True)
    currency = Column(String(10), default="INR")

    # Financial Totals
    invoice_total = Column(Float, default=0.0)
    po_total = Column(Float, default=0.0)
    invoice_tax = Column(Float, default=0.0)
    po_tax = Column(Float, default=0.0)
    variance_total = Column(Float, default=0.0)

    # Reconciliation Status: MATCHED | VARIANCE_DETECTED | APPROVED | REJECTED | ESCALATED
    status = Column(String(50), default="PENDING", index=True)
    has_exceptions = Column(Boolean, default=False)
    match_score = Column(Float, default=100.0)

    # AI Arbitration Outputs
    risk_severity = Column(String(20), default="LOW") # LOW | MEDIUM | HIGH | CRITICAL
    confidence_score = Column(Float, default=0.0)
    arbitration_summary = Column(Text, nullable=True)
    dispute_email_draft = Column(Text, nullable=True)

    # Human-in-the-Loop review
    reviewer_action = Column(String(50), nullable=True) # APPROVED | REJECTED | ESCALATED | OVERRIDDEN
    reviewer_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    # Raw extracted JSON payloads
    invoice_json_str = Column(Text, nullable=True)
    po_json_str = Column(Text, nullable=True)
    grn_json_str = Column(Text, nullable=True)

    # File paths
    invoice_file = Column(String(255), nullable=True)
    po_file = Column(String(255), nullable=True)
    grn_file = Column(String(255), nullable=True)

    # Relationships
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

    # Quantities (Invoice vs GRN)
    invoice_qty = Column(Float, default=0.0)
    grn_qty = Column(Float, nullable=True)
    qty_status = Column(String(50), default="MATCH") # MATCH | MISMATCH | MISSING_IN_GRN

    # Unit Prices (Invoice vs PO)
    invoice_unit_price = Column(Float, default=0.0)
    po_unit_price = Column(Float, nullable=True)
    price_status = Column(String(50), default="MATCH") # MATCH | MISMATCH | MISSING_IN_PO

    # Total & Line Status
    invoice_line_total = Column(Float, default=0.0)
    po_line_total = Column(Float, default=0.0)
    variance_amount = Column(Float, default=0.0)
    status = Column(String(50), default="MATCHED") # MATCHED | VARIANCE

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
    event_type = Column(String(50), index=True) # UPLOAD, EXTRACTION, 3WAY_MATCH, ARBITRATION, REVIEW, OVERRIDE
    source = Column(String(100)) # EXTRACTION_AGENT, MATCHING_AGENT, ARBITRATION_AGENT, HUMAN_REVIEWER
    description = Column(Text)
    severity = Column(String(20), default="INFO") # INFO, WARNING, ERROR

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
    aliases_json = Column(Text, default="[]") # JSON list of string aliases
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
