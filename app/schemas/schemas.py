from typing import Optional, List, Any
from pydantic import BaseModel, Field

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
    field: str # 'total_amount', 'tax', 'quantity', 'unit_price', 'missing_item'
    item_code: Optional[str] = None
    description: Optional[str] = None
    invoice_val: Any = None
    comparison_val: Any = None # From PO or GRN
    variance_amount: float = 0.0
    message: str = ""

class LineItemComparisonResult(BaseModel):
    item_code: str
    description: str
    invoice_qty: float
    grn_qty: Optional[float]
    qty_status: str # MATCH | MISMATCH | MISSING_IN_GRN | MISSING_IN_INVOICE
    invoice_unit_price: float
    po_unit_price: Optional[float]
    price_status: str # MATCH | MISMATCH | MISSING_IN_PO
    invoice_line_total: float
    po_line_total: float
    variance_amount: float
    status: str # MATCHED | VARIANCE

class ThreeWayMatchResult(BaseModel):
    status: str # MATCHED | VARIANCE_DETECTED
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
    risk_severity: str # LOW | MEDIUM | HIGH | CRITICAL
    confidence_score: float
    summary: str
    recommended_action: str # AUTO_APPROVE | HUMAN_INVESTIGATION | ESCALATE_TO_VENDOR | REJECT_INVOICE
    dispute_email_draft: str
    findings: List[str] = Field(default_factory=list)

class ReviewRequest(BaseModel):
    action: str = Field(..., description="APPROVED | REJECTED | ESCALATED")
    notes: Optional[str] = Field(default="", description="Reviewer comments or justification")
    reviewer_name: Optional[str] = Field(default="Finance Specialist")

class ReconciliationCreateRequest(BaseModel):
    invoice_file_id: Optional[str] = None
    po_file_id: Optional[str] = None
    grn_file_id: Optional[str] = None
