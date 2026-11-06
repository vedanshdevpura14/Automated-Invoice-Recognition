import os
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Any
from pathlib import Path

from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session

# ==========================================================
# 0. Directory & Database Paths (Folder aur Database Path Setup)
# ==========================================================
# Yeh project ki base directory nikalta hai aur database/upload paths set karta hai.
BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'cacheflow.db'}")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)
# Comment: Yahan humne SQLite database ka path set kiya hai aur uploaded files ke liye 'uploads' folder banaya hai.

# ==========================================================
# IST (Indian Standard Time) Timezone Setup (UTC + 5:30)
# ==========================================================
# Audit logs aur timestamps ko exact Indian time me rakhne ke liye UTC + 5:30 offset define kiya hai.
IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now() -> datetime:
    """Current Indian Standard Time (IST) return karta hai."""
    # Yeh function current datetime ko Indian Standard Time (+05:30) me calculate karke deta hai.
    return datetime.now(IST)
# Comment: Is function se hume hamesha IST me time milega, chahe server America (Render) me ho ya local machine par.

# ==========================================================
# Reconciliation Tolerances (Paisa Rounding Tolerances)
# ==========================================================
# Financial calculations me 50 paise ya 1 rupee ka difference aana aam baat hoti hai rounding ki wajah se.
# False alarm na baje, isliye hum tolerance limit set karte hain.
AMOUNT_TOLERANCE = float(os.getenv("AMOUNT_TOLERANCE", "1.0"))   # ₹1.00 tak ka total rounding difference allowed hai
TAX_TOLERANCE = float(os.getenv("TAX_TOLERANCE", "1.0"))         # ₹1.00 tak ka tax calculation difference allowed hai
PRICE_TOLERANCE = float(os.getenv("PRICE_TOLERANCE", "0.01"))    # Unit price me 1 paise ka difference allowed hai
# Comment: Agar koi ₹100 ki cheez ₹100.005 bill kar de toh system reject nahi karega, tolerance ke andar pass kar dega.

# ==========================================================
# Database Engine & Session Setup (SQLAlchemy Engine)
# ==========================================================
# SQLite database ke sath connect karne ke liye engine aur sessionmaker banaya hai.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """FastAPI endpoints ke liye database session provide karta hai aur close karta hai."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
# Comment: Yeh dependency injection helper hai jo har request pe DB session kholta hai aur request khatam hone par safely band karta hai.

def init_db():
    """Database tables create karta hai agar pehle se nahi bani ho."""
    Base.metadata.create_all(bind=engine)
# Comment: Jab app start hota hai toh yeh function sari tables (reconciliations, line_items, audit_logs) create kar deta hai.


# ==========================================================
# 1. Pydantic Schemas (API Data Contracts / Validation)
# ==========================================================

class LineItemSchema(BaseModel):
    # Ek specific product item ki details validate karta hai (Item Code, Description, Qty, Rate, Total)
    item_code: str = Field(default="", description="Product SKU ya code")
    description: Optional[str] = Field(default="", description="Product ka naam ya details")
    quantity: float = Field(default=0.0, ge=0, description="Kitni quantity mangwai ya receive hui")
    unit_price: float = Field(default=0.0, ge=0, description="Ek piece ka price")
    total_price: float = Field(default=0.0, ge=0, description="Line item ka total amount")
# Comment: Yeh schema verify karta hai ki koi negative quantity ya price na daale aur data structured format me rahe.


class DocumentDataSchema(BaseModel):
    # Pure extracted document (Invoice, PO ya GRN) ka structured JSON format
    document_type: str = Field(..., description="'invoice', 'purchase_order', ya 'grn'")
    vendor_name: str = Field(default="Unknown Vendor", description="Supplier ya seller company ka naam")
    document_number: str = Field(default="", description="Invoice number ya PO/GRN number")
    document_date: Optional[str] = Field(default="", description="Document generate hone ki date")
    currency: str = Field(default="INR", description="Currency (INR, USD, etc.)")
    subtotal: float = Field(default=0.0, description="Tax se pehle ka amount")
    tax: float = Field(default=0.0, description="GST / Tax amount")
    total_amount: float = Field(default=0.0, description="Grand Total amount")
    line_items: List[LineItemSchema] = Field(default_factory=list, description="Document ke andar ke line items ki list")
# Comment: PyMuPDF aur Gemini se jo data extract hota hai, usko is Pydantic model me daal kar clean format me convert karte hain.


class VarianceItem(BaseModel):
    # Jab 3-way match me koi gadbad (difference) milti hai, toh yeh object banta hai
    field: str                  # Kis field me mismatch hai: 'unit_price', 'quantity', 'tax', 'total_amount', etc.
    item_code: Optional[str] = None
    description: Optional[str] = None
    invoice_val: Any = None     # Invoice me kya likha tha
    comparison_val: Any = None  # PO ya GRN me kya likha tha
    variance_amount: float = 0.0 # Kitne rupaye ka nuksaan ya farak hai
    message: str = ""           # Human-readable message ki exact kya problem hai
# Comment: Agar vendor ne ₹500 ki jagah ₹550 bill kiya hai, toh yeh object store karega ki ₹50 overbilling hui hai.


class LineItemComparisonResult(BaseModel):
    # Har line item ka 3-way side-by-side verification result
    item_code: str
    description: str
    invoice_qty: float
    grn_qty: Optional[float]
    qty_status: str             # MATCH | MISMATCH | MISSING_IN_GRN
    invoice_unit_price: float
    po_unit_price: Optional[float]
    price_status: str           # MATCH | MISMATCH | MISSING_IN_PO
    invoice_line_total: float
    po_line_total: float
    variance_amount: float
    status: str                 # MATCHED | VARIANCE
# Comment: Dashboard ke side-by-side matrix me yahi data show hota hai ki Invoice vs PO rate aur Invoice vs GRN quantity match hui ya nahi.


class ThreeWayMatchResult(BaseModel):
    # Pure 3-Way reconciliation ka final mathematical outcome
    status: str                 # MATCHED | VARIANCE_DETECTED
    vendor_matched: bool        # Vendor name match hua ya nahi (alias aware)
    invoice_vendor: str
    po_vendor: str
    invoice_total: float
    po_total: float
    invoice_tax: float
    po_tax: float
    variance_total: float       # Total kitna extra paisa manga gaya hai
    match_score: float          # 0% se 100% tak reliability score
    variances: List[VarianceItem] = Field(default_factory=list)
    line_comparisons: List[LineItemComparisonResult] = Field(default_factory=list)
# Comment: Node 2 (matcher.py) calculate karke yahi complete result Node 3 aur database ko bhejta hai.


class ArbitrationResponse(BaseModel):
    # Node 3 (AI Arbitration Agent) ka output
    risk_severity: str          # LOW | MEDIUM | HIGH | CRITICAL
    confidence_score: float     # AI ka confidence level (e.g. 95.0%)
    summary: str                # Executive summary ki root-cause kya hai
    recommended_action: str     # AUTO_APPROVE | HUMAN_INVESTIGATION | ESCALATE_TO_VENDOR | REJECT_INVOICE
    dispute_email_draft: str    # Vendor ko bhejne ke liye ready-made formal email draft
    findings: List[str] = Field(default_factory=list)
# Comment: Agar shortage ya price hike hai toh AI turant vendor ke liye email draft taiyyar karta hai jisme document numbers aur difference clearly mentioned hota hai.


class ReviewRequest(BaseModel):
    # Human-in-the-Loop approval/rejection request payload
    action: str = Field(..., description="APPROVED | REJECTED | ESCALATED")
    notes: Optional[str] = Field(default="", description="Finance specialist ke comments")
    reviewer_name: Optional[str] = Field(default="Finance Specialist")
# Comment: Final decision lene ke liye human reviewer ka action aur unke notes capture karta hai.


# ==========================================================
# 2. SQLAlchemy Database Tables (Persistent Storage)
# ==========================================================

class ReconciliationRecord(Base):
    # Main table jisme har 3-way reconciliation audit ka master record save hota hai
    __tablename__ = "reconciliations"

    id = Column(Integer, primary_key=True, index=True)
    reconciliation_code = Column(String(50), unique=True, index=True) # Unique tracking code (e.g. REC-20261106-ABCD)
    created_at = Column(DateTime, default=get_ist_now)                 # Indian Standard Time (IST) record timestamp

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

    # Status: MATCHED | VARIANCE_DETECTED | APPROVED | REJECTED | ESCALATED
    status = Column(String(50), default="PENDING", index=True)
    has_exceptions = Column(Boolean, default=False)
    match_score = Column(Float, default=100.0)

    # AI Arbitration Outputs
    risk_severity = Column(String(20), default="LOW")
    confidence_score = Column(Float, default=0.0)
    arbitration_summary = Column(Text, nullable=True)
    dispute_email_draft = Column(Text, nullable=True)

    # Human-in-the-Loop review audit
    reviewer_action = Column(String(50), nullable=True)
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
        # Database object ko clean Python dictionary me badalta hai taaki JSON response ban sake
        created_ist = self.created_at.strftime("%Y-%m-%d %I:%M:%S %p IST") if self.created_at else None
        reviewed_ist = self.reviewed_at.strftime("%Y-%m-%d %I:%M:%S %p IST") if self.reviewed_at else None

        return {
            "id": self.id,
            "reconciliation_code": self.reconciliation_code,
            "created_at": created_ist,
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
            "reviewed_at": reviewed_ist,
            "invoice_data": json.loads(self.invoice_json_str) if self.invoice_json_str else None,
            "po_data": json.loads(self.po_json_str) if self.po_json_str else None,
            "grn_data": json.loads(self.grn_json_str) if self.grn_json_str else None,
            "line_items": [item.to_dict() for item in self.line_items]
        }
# Comment: Is table me poori audit history permanently store rehti hai, page refresh hone ke baad bhi data kabhi delete nahi hota.


class ReconciliationLineItem(Base):
    # Har document ke specific line item ka reconciliation data
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
# Comment: Ek invoice me 10 alag-alag laptop ya monitor ho sakte hain, yeh table un sabhi 10 items ka alag-alag record rakhti hai.


class AuditLogEntry(Base):
    # Compliance ke liye immutable audit trail table
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    # Default time ab Indian Standard Time (IST) function se calculate hoga
    timestamp = Column(DateTime, default=get_ist_now, index=True)
    reconciliation_id = Column(Integer, ForeignKey("reconciliations.id"), nullable=True, index=True)
    event_type = Column(String(50), index=True)   # DOCUMENT_UPLOAD, EXTRACTION_COMPLETED, MATCH_EVALUATION, etc.
    source = Column(String(100))                  # EXTRACTION_AGENT, MATCHING_AGENT, HUMAN_REVIEWER
    description = Column(Text)                    # Event ka clear explanation
    severity = Column(String(20), default="INFO") # INFO, WARNING, ERROR

    reconciliation = relationship("ReconciliationRecord", back_populates="audit_logs")

    def to_dict(self):
        # Timestamp ko formatted IST string me convert karte hain (e.g. 2026-11-06 02:45:10 PM IST)
        formatted_ist = self.timestamp.strftime("%Y-%m-%d %I:%M:%S %p IST") if self.timestamp else None
        return {
            "id": self.id,
            "timestamp": formatted_ist,
            "reconciliation_id": self.reconciliation_id,
            "event_type": self.event_type,
            "source": self.source,
            "description": self.description,
            "severity": self.severity
        }
# Comment: Financial compliance me zaroori hota hai ki kis agent ne kab aur kya action liya, yeh table vahi audit trail banati hai.


class VendorMemoryRecord(Base):
    # Vendor ke alias aur track record ko yaad rakhne wali memory table
    __tablename__ = "vendor_memory"

    id = Column(Integer, primary_key=True, index=True)
    canonical_name = Column(String(200), unique=True, index=True)
    aliases_json = Column(Text, default="[]") # JSON list of known name variations
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
# Comment: Yeh table vendor ke alternate naamo ko track karti hai (jaise Pvt Ltd vs Private Limited) taaki agli baar bina galti match ho sake.


# ==========================================================
# 3. Audit & Memory Helpers (Helper Functions)
# ==========================================================

def record_audit_log(
    db: Session,
    event_type: str,
    source: str,
    description: str,
    severity: str = "INFO",
    reconciliation_id: Optional[int] = None
) -> AuditLogEntry:
    """Audit log table me ek naya event IST time ke sath log karta hai."""
    # Yahan current IST time nikal kar audit log entry banayi jaati hai
    log_entry = AuditLogEntry(
        reconciliation_id=reconciliation_id,
        event_type=event_type,
        source=source,
        description=description,
        severity=severity,
        timestamp=get_ist_now() # Exact Indian Standard Time
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry
# Comment: Jab bhi koi file upload hoti hai, extraction hoti hai ya matching hoti hai, yeh function IST time stamp ke sath log kar deta hai.


def update_vendor_memory(db: Session, vendor_name: str, was_matched: bool):
    """Vendor ke historical performance stats aur alias ko update karta hai."""
    if not vendor_name:
        return

    record = db.query(VendorMemoryRecord).filter(
        VendorMemoryRecord.canonical_name.ilike(vendor_name.strip())
    ).first()

    if not record:
        # Naye vendor ko register karo
        record = VendorMemoryRecord(
            canonical_name=vendor_name.strip(),
            aliases_json=json.dumps([vendor_name.strip()]),
            total_reconciliations=1,
            successful_matches=1 if was_matched else 0,
            notes="Auto-registered by CacheFlow agent"
        )
        db.add(record)
    else:
        # Existing vendor ka count badhao
        record.total_reconciliations += 1
        if was_matched:
            record.successful_matches += 1

    db.commit()
# Comment: Agar koi vendor lagatar sahi invoice bhejta hai toh uska match score high rehta hai, fraud vendors easily identify ho jate hain.
