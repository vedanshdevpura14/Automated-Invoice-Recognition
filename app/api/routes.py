import os
import uuid
import json
import csv
import io
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.config import settings
from app.core.database import get_db
from app.models.db_models import (
    ReconciliationRecord,
    ReconciliationLineItem,
    AuditLogEntry,
    VendorMemoryRecord
)
from app.schemas.schemas import (
    DocumentDataSchema,
    LineItemSchema,
    ThreeWayMatchResult,
    ReviewRequest,
    ArbitrationResponse
)
from app.services.ocr_service import extract_text_from_file
from app.services.extraction_service import extract_document
from app.services.matching_engine import perform_three_way_reconciliation
from app.services.arbitration_agent import arbitrate_exceptions
from app.services.audit_service import record_audit_log, update_vendor_memory

router = APIRouter()

@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """System health check endpoint."""
    total_recs = db.query(ReconciliationRecord).count()
    has_gemini = bool(settings.GEMINI_API_KEY and len(settings.GEMINI_API_KEY) > 8)
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "database": "connected",
        "total_reconciliations_stored": total_recs,
        "gemini_api_configured": has_gemini,
        "ai_extraction_mode": "Gemini 1.5 Flash" if has_gemini else "Deterministic Heuristics Engine (Offline Safe)",
        "ai_arbitration_mode": "Gemini 1.5 Pro" if has_gemini else "Deterministic Reasoner (Offline Safe)"
    }


@router.post("/upload-and-reconcile")
async def upload_and_reconcile(
    invoice_file: UploadFile = File(...),
    po_file: UploadFile = File(...),
    grn_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Main 3-Way Reconciliation Pipeline:
    1. Ingests Invoice, PO, and GRN documents
    2. Node 1: Extraction Agent (OCR + Gemini / Heuristic Parser)
    3. Node 2: Matching Agent (Deterministic 3-Way Match with tolerances)
    4. Node 3: Arbitration Agent (AI Reasoner, Risk Scoring, Vendor Dispute Drafter)
    5. Persistence in SQLite & Audit Log registration
    """
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    session_id = str(uuid.uuid4())[:8]

    # Save uploaded files
    file_paths = {}
    for role, f in [("invoice", invoice_file), ("po", po_file), ("grn", grn_file)]:
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"File {f.filename} format '{ext}' is not supported. Use PDF, TXT, or images.")
        
        saved_filename = f"{session_id}_{role}_{f.filename}"
        dest_path = os.path.join(settings.UPLOAD_DIR, saved_filename)
        content = await f.read()
        with open(dest_path, "wb") as out:
            out.write(content)
        file_paths[role] = dest_path

    # Audit file upload
    record_audit_log(
        db,
        event_type="DOCUMENT_UPLOAD",
        source="API_GATEWAY",
        description=f"Received 3 documents for reconciliation batch: {invoice_file.filename}, {po_file.filename}, {grn_file.filename}"
    )

    # Node 1: Extraction Agent
    try:
        inv_text = extract_text_from_file(file_paths["invoice"])
        po_text = extract_text_from_file(file_paths["po"])
        grn_text = extract_text_from_file(file_paths["grn"])

        invoice_data = extract_document(inv_text, doc_hint="invoice")
        po_data = extract_document(po_text, doc_hint="purchase_order")
        grn_data = extract_document(grn_text, doc_hint="grn")
    except Exception as e:
        record_audit_log(db, "EXTRACTION_FAILURE", "EXTRACTION_AGENT", f"Extraction error: {str(e)}", severity="ERROR")
        raise HTTPException(status_code=500, detail=f"Document extraction failed: {str(e)}")

    record_audit_log(
        db,
        event_type="EXTRACTION_COMPLETED",
        source="EXTRACTION_AGENT",
        description=f"Extracted data for Invoice #{invoice_data.document_number}, PO #{po_data.document_number}, GRN #{grn_data.document_number}"
    )

    # Node 2: Deterministic 3-Way Matching Engine
    match_result = perform_three_way_reconciliation(invoice_data, po_data, grn_data)

    record_audit_log(
        db,
        event_type="MATCH_EVALUATION",
        source="MATCHING_AGENT",
        description=f"Deterministic matching status: {match_result.status} (Score: {match_result.match_score}%, Variances: {len(match_result.variances)})",
        severity="WARNING" if match_result.status != "MATCHED" else "INFO"
    )

    # Node 3: AI Arbitration Agent
    arbitration = arbitrate_exceptions(match_result, invoice_data, po_data, grn_data)

    # Create Database Record
    rec_code = f"REC-{datetime.utcnow().strftime('%Y%m%d')}-{session_id.upper()}"
    reconciliation = ReconciliationRecord(
        reconciliation_code=rec_code,
        vendor_name=invoice_data.vendor_name,
        invoice_number=invoice_data.document_number,
        po_number=po_data.document_number,
        grn_number=grn_data.document_number,
        currency=invoice_data.currency,
        invoice_total=invoice_data.total_amount,
        po_total=po_data.total_amount,
        invoice_tax=invoice_data.tax,
        po_tax=po_data.tax,
        variance_total=match_result.variance_total,
        status="MATCHED" if match_result.status == "MATCHED" else "VARIANCE_DETECTED",
        has_exceptions=(match_result.status != "MATCHED"),
        match_score=match_result.match_score,
        risk_severity=arbitration.risk_severity,
        confidence_score=arbitration.confidence_score,
        arbitration_summary=arbitration.summary,
        dispute_email_draft=arbitration.dispute_email_draft,
        invoice_json_str=json.dumps(invoice_data.model_dump()),
        po_json_str=json.dumps(po_data.model_dump()),
        grn_json_str=json.dumps(grn_data.model_dump()),
        invoice_file=file_paths["invoice"],
        po_file=file_paths["po"],
        grn_file=file_paths["grn"]
    )
    db.add(reconciliation)
    db.commit()
    db.refresh(reconciliation)

    # Save Line Item Records
    for item in match_result.line_comparisons:
        line_item = ReconciliationLineItem(
            reconciliation_id=reconciliation.id,
            item_code=item.item_code,
            description=item.description,
            invoice_qty=item.invoice_qty,
            grn_qty=item.grn_qty,
            qty_status=item.qty_status,
            invoice_unit_price=item.invoice_unit_price,
            po_unit_price=item.po_unit_price,
            price_status=item.price_status,
            invoice_line_total=item.invoice_line_total,
            po_line_total=item.po_line_total,
            variance_amount=item.variance_amount,
            status=item.status
        )
        db.add(line_item)

    # Update Vendor Memory
    update_vendor_memory(db, invoice_data.vendor_name, was_matched=(match_result.status == "MATCHED"))

    record_audit_log(
        db,
        event_type="RECONCILIATION_SAVED",
        source="SYSTEM",
        description=f"Reconciliation {rec_code} saved with status {reconciliation.status}",
        reconciliation_id=reconciliation.id
    )

    db.commit()
    db.refresh(reconciliation)

    return reconciliation.to_dict()


@router.get("/reconciliations")
def list_reconciliations(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Lists past reconciliation records with optional filtering."""
    query = db.query(ReconciliationRecord).order_by(desc(ReconciliationRecord.created_at))
    if status and status.upper() != "ALL":
        query = query.filter(ReconciliationRecord.status == status.upper())
    
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return {
        "total": total,
        "items": [item.to_dict() for item in items]
    }


@router.get("/reconciliations/{rec_id}")
def get_reconciliation_detail(rec_id: int, db: Session = Depends(get_db)):
    """Retrieves full 3-way reconciliation audit details for a specific record."""
    rec = db.query(ReconciliationRecord).filter(ReconciliationRecord.id == rec_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Reconciliation record not found")
    
    data = rec.to_dict()
    # Add audit logs for this record
    logs = db.query(AuditLogEntry).filter(AuditLogEntry.reconciliation_id == rec_id).order_by(AuditLogEntry.timestamp).all()
    data["audit_logs"] = [l.to_dict() for l in logs]
    return data


@router.post("/reconciliations/{rec_id}/review")
def review_reconciliation(
    rec_id: int,
    review: ReviewRequest,
    db: Session = Depends(get_db)
):
    """Human-in-the-Loop review: Approve, Reject, or Escalate with justification notes."""
    rec = db.query(ReconciliationRecord).filter(ReconciliationRecord.id == rec_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Reconciliation record not found")

    rec.reviewer_action = review.action.upper()
    rec.reviewer_notes = review.notes
    rec.reviewed_at = datetime.utcnow()
    rec.status = review.action.upper()

    record_audit_log(
        db,
        event_type=f"HUMAN_{review.action.upper()}",
        source=f"HUMAN_REVIEWER ({review.reviewer_name})",
        description=f"Decision: {review.action.upper()}. Notes: {review.notes or 'None provided'}",
        reconciliation_id=rec.id
    )

    db.commit()
    db.refresh(rec)
    return {"message": f"Reconciliation successfully updated to {rec.status}", "record": rec.to_dict()}


@router.get("/dashboard/stats")
def get_dashboard_metrics(db: Session = Depends(get_db)):
    """Returns analytics KPIs and variance breakdowns for the dashboard."""
    total = db.query(ReconciliationRecord).count()
    matched = db.query(ReconciliationRecord).filter(ReconciliationRecord.status == "MATCHED").count()
    approved = db.query(ReconciliationRecord).filter(ReconciliationRecord.status == "APPROVED").count()
    variances = db.query(ReconciliationRecord).filter(ReconciliationRecord.status == "VARIANCE_DETECTED").count()
    escalated = db.query(ReconciliationRecord).filter(ReconciliationRecord.status == "ESCALATED").count()
    rejected = db.query(ReconciliationRecord).filter(ReconciliationRecord.status == "REJECTED").count()

    total_variance_sum = sum(r.variance_total for r in db.query(ReconciliationRecord.variance_total).all())

    # Vendor Health summary
    vendors = db.query(VendorMemoryRecord).order_by(desc(VendorMemoryRecord.total_reconciliations)).limit(5).all()

    return {
        "total_processed": total,
        "matched_count": matched,
        "approved_count": approved,
        "variance_count": variances,
        "escalated_count": escalated,
        "rejected_count": rejected,
        "match_rate_pct": round((matched / total * 100), 1) if total > 0 else 0.0,
        "total_variance_amount": round(total_variance_sum, 2),
        "top_vendors": [v.to_dict() for v in vendors]
    }


@router.get("/audit-logs")
def get_audit_trail(
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Retrieves immutable audit logs."""
    logs = db.query(AuditLogEntry).order_by(desc(AuditLogEntry.timestamp)).limit(limit).all()
    return [l.to_dict() for l in logs]


@router.get("/export/{rec_id}")
def export_reconciliation_csv(rec_id: int, db: Session = Depends(get_db)):
    """Exports reconciliation line items and variances as a CSV report."""
    rec = db.query(ReconciliationRecord).filter(ReconciliationRecord.id == rec_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Reconciliation record not found")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Reconciliation Code", rec.reconciliation_code])
    writer.writerow(["Vendor Name", rec.vendor_name])
    writer.writerow(["Invoice Number", rec.invoice_number])
    writer.writerow(["PO Number", rec.po_number])
    writer.writerow(["GRN Number", rec.grn_number])
    writer.writerow(["Status", rec.status])
    writer.writerow(["Match Score", f"{rec.match_score}%"])
    writer.writerow(["Risk Severity", rec.risk_severity])
    writer.writerow(["Variance Total", f"{rec.currency} {rec.variance_total:,.2f}"])
    writer.writerow([])
    writer.writerow(["Item Code", "Description", "Invoice Qty", "GRN Qty", "Qty Status", "Invoice Unit Price", "PO Unit Price", "Price Status", "Variance Amount", "Line Status"])

    for item in rec.line_items:
        writer.writerow([
            item.item_code,
            item.description,
            item.invoice_qty,
            item.grn_qty,
            item.qty_status,
            item.invoice_unit_price,
            item.po_unit_price,
            item.price_status,
            item.variance_amount,
            item.status
        ])

    output.seek(0)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={rec.reconciliation_code}.csv"}
    )


@router.post("/demo/{scenario_type}")
def run_demo_scenario(scenario_type: str, db: Session = Depends(get_db)):
    """
    1-Click Demo Loader: Runs real 3-way matching on realistic business cases.
    Scenarios:
    - clean_match: Perfect 3-way match (100 laptops @ Rs 50,000)
    - price_mismatch: Invoiced Rs 550 vs PO Rs 500 (from Page 4/15 in PDF)
    - quantity_shortage: Invoiced 100 vs GRN 90 delivered (from Page 4/15 in PDF)
    - vendor_alias: ABC Technologies Private Limited vs ABC Technologies Pvt. Ltd.
    """
    session_id = str(uuid.uuid4())[:8]

    if scenario_type == "clean_match":
        invoice = DocumentDataSchema(
            document_type="invoice",
            vendor_name="ABC Technologies Private Limited",
            document_number=f"INV-{session_id}",
            document_date="2026-11-04",
            currency="INR",
            subtotal=5000000.0,
            tax=900000.0,
            total_amount=5900000.0,
            line_items=[
                LineItemSchema(item_code="LAP-DELL-5420", description="Dell Latitude 5420 Laptops", quantity=100.0, unit_price=50000.0, total_price=5000000.0)
            ]
        )
        po = DocumentDataSchema(
            document_type="purchase_order",
            vendor_name="ABC Technologies Private Limited",
            document_number=f"PO-{session_id}",
            document_date="2026-10-25",
            currency="INR",
            subtotal=5000000.0,
            tax=900000.0,
            total_amount=5900000.0,
            line_items=[
                LineItemSchema(item_code="LAP-DELL-5420", description="Dell Latitude 5420 Laptops", quantity=100.0, unit_price=50000.0, total_price=5000000.0)
            ]
        )
        grn = DocumentDataSchema(
            document_type="grn",
            vendor_name="ABC Technologies",
            document_number=f"GRN-{session_id}",
            document_date="2026-11-02",
            currency="INR",
            subtotal=0.0,
            tax=0.0,
            total_amount=0.0,
            line_items=[
                LineItemSchema(item_code="LAP-DELL-5420", description="Dell Latitude 5420 Laptops", quantity=100.0, unit_price=0.0, total_price=0.0)
            ]
        )

    elif scenario_type == "price_mismatch":
        # Exactly Scenario 1 from the PDF guide!
        invoice = DocumentDataSchema(
            document_type="invoice",
            vendor_name="TechMatrix Solutions Ltd",
            document_number=f"INV-{session_id}",
            document_date="2026-11-04",
            currency="INR",
            subtotal=55000.0,
            tax=9900.0,
            total_amount=64900.0,
            line_items=[
                LineItemSchema(item_code="MON-24-IPS", description="24-inch IPS UltraSharp Monitors", quantity=100.0, unit_price=550.0, total_price=55000.0)
            ]
        )
        po = DocumentDataSchema(
            document_type="purchase_order",
            vendor_name="TechMatrix Solutions Ltd",
            document_number=f"PO-{session_id}",
            document_date="2026-10-28",
            currency="INR",
            subtotal=50000.0,
            tax=9000.0,
            total_amount=59000.0,
            line_items=[
                LineItemSchema(item_code="MON-24-IPS", description="24-inch IPS UltraSharp Monitors", quantity=100.0, unit_price=500.0, total_price=50000.0)
            ]
        )
        grn = DocumentDataSchema(
            document_type="grn",
            vendor_name="TechMatrix Solutions",
            document_number=f"GRN-{session_id}",
            document_date="2026-11-03",
            currency="INR",
            subtotal=0.0,
            tax=0.0,
            total_amount=0.0,
            line_items=[
                LineItemSchema(item_code="MON-24-IPS", description="24-inch IPS UltraSharp Monitors", quantity=100.0, unit_price=0.0, total_price=0.0)
            ]
        )

    elif scenario_type == "quantity_shortage":
        # Exactly Scenario 4/Example from the PDF: Invoiced 100, delivered 90!
        invoice = DocumentDataSchema(
            document_type="invoice",
            vendor_name="Apex Global Hardware",
            document_number=f"INV-{session_id}",
            document_date="2026-11-04",
            currency="INR",
            subtotal=200000.0,
            tax=36000.0,
            total_amount=236000.0,
            line_items=[
                LineItemSchema(item_code="RAM-16GB-DDR4", description="16GB DDR4 Server Memory Modules", quantity=100.0, unit_price=2000.0, total_price=200000.0)
            ]
        )
        po = DocumentDataSchema(
            document_type="purchase_order",
            vendor_name="Apex Global Hardware",
            document_number=f"PO-{session_id}",
            document_date="2026-10-20",
            currency="INR",
            subtotal=200000.0,
            tax=36000.0,
            total_amount=236000.0,
            line_items=[
                LineItemSchema(item_code="RAM-16GB-DDR4", description="16GB DDR4 Server Memory Modules", quantity=100.0, unit_price=2000.0, total_price=200000.0)
            ]
        )
        grn = DocumentDataSchema(
            document_type="grn",
            vendor_name="Apex Global Hardware",
            document_number=f"GRN-{session_id}",
            document_date="2026-11-01",
            currency="INR",
            subtotal=0.0,
            tax=0.0,
            total_amount=0.0,
            line_items=[
                LineItemSchema(item_code="RAM-16GB-DDR4", description="16GB DDR4 Server Memory Modules", quantity=90.0, unit_price=0.0, total_price=0.0)
            ]
        )

    else:
        # Vendor alias scenario
        invoice = DocumentDataSchema(
            document_type="invoice",
            vendor_name="CloudNet Infra Pvt. Ltd.",
            document_number=f"INV-{session_id}",
            document_date="2026-11-04",
            currency="INR",
            subtotal=150000.0,
            tax=27000.0,
            total_amount=177000.0,
            line_items=[
                LineItemSchema(item_code="SFP-10G-SR", description="10G SFP+ Optical Transceivers", quantity=50.0, unit_price=3000.0, total_price=150000.0)
            ]
        )
        po = DocumentDataSchema(
            document_type="purchase_order",
            vendor_name="CloudNet Infra Private Limited",
            document_number=f"PO-{session_id}",
            document_date="2026-10-22",
            currency="INR",
            subtotal=150000.0,
            tax=27000.0,
            total_amount=177000.0,
            line_items=[
                LineItemSchema(item_code="SFP-10G-SR", description="10G SFP+ Optical Transceivers", quantity=50.0, unit_price=3000.0, total_price=150000.0)
            ]
        )
        grn = DocumentDataSchema(
            document_type="grn",
            vendor_name="CloudNet Infra",
            document_number=f"GRN-{session_id}",
            document_date="2026-11-02",
            currency="INR",
            subtotal=0.0,
            tax=0.0,
            total_amount=0.0,
            line_items=[
                LineItemSchema(item_code="SFP-10G-SR", description="10G SFP+ Optical Transceivers", quantity=50.0, unit_price=0.0, total_price=0.0)
            ]
        )

    match_result = perform_three_way_reconciliation(invoice, po, grn)
    arbitration = arbitrate_exceptions(match_result, invoice, po, grn)

    rec_code = f"REC-DEMO-{session_id.upper()}"
    reconciliation = ReconciliationRecord(
        reconciliation_code=rec_code,
        vendor_name=invoice.vendor_name,
        invoice_number=invoice.document_number,
        po_number=po.document_number,
        grn_number=grn.document_number,
        currency=invoice.currency,
        invoice_total=invoice.total_amount,
        po_total=po.total_amount,
        invoice_tax=invoice.tax,
        po_tax=po.tax,
        variance_total=match_result.variance_total,
        status="MATCHED" if match_result.status == "MATCHED" else "VARIANCE_DETECTED",
        has_exceptions=(match_result.status != "MATCHED"),
        match_score=match_result.match_score,
        risk_severity=arbitration.risk_severity,
        confidence_score=arbitration.confidence_score,
        arbitration_summary=arbitration.summary,
        dispute_email_draft=arbitration.dispute_email_draft,
        invoice_json_str=json.dumps(invoice.model_dump()),
        po_json_str=json.dumps(po.model_dump()),
        grn_json_str=json.dumps(grn.model_dump())
    )
    db.add(reconciliation)
    db.commit()
    db.refresh(reconciliation)

    for item in match_result.line_comparisons:
        line_item = ReconciliationLineItem(
            reconciliation_id=reconciliation.id,
            item_code=item.item_code,
            description=item.description,
            invoice_qty=item.invoice_qty,
            grn_qty=item.grn_qty,
            qty_status=item.qty_status,
            invoice_unit_price=item.invoice_unit_price,
            po_unit_price=item.po_unit_price,
            price_status=item.price_status,
            invoice_line_total=item.invoice_line_total,
            po_line_total=item.po_line_total,
            variance_amount=item.variance_amount,
            status=item.status
        )
        db.add(line_item)

    update_vendor_memory(db, invoice.vendor_name, was_matched=(match_result.status == "MATCHED"))

    record_audit_log(
        db,
        event_type="DEMO_SCENARIO_LOADED",
        source="SYSTEM_DEMO_LOADER",
        description=f"Loaded sample scenario '{scenario_type}' for testing ({rec_code})",
        reconciliation_id=reconciliation.id
    )

    db.commit()
    db.refresh(reconciliation)

    return reconciliation.to_dict()
