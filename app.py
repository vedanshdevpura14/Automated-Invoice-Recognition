import os
import uuid
import json
import csv
import io
from pathlib import Path
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc

from models import (
    init_db,
    get_db,
    get_ist_now,
    UPLOAD_DIR,
    ReconciliationRecord,
    ReconciliationLineItem,
    AuditLogEntry,
    VendorMemoryRecord,
    DocumentDataSchema,
    LineItemSchema,
    ThreeWayMatchResult,
    ArbitrationResponse,
    ReviewRequest,
    record_audit_log,
    update_vendor_memory
)
from extractor import extract_text_from_file, extract_document
from matcher import perform_three_way_reconciliation
from agent import arbitrate_exceptions
from fraud import evaluate_fraud_and_duplicates
from workflow import run_reconciliation_workflow

# Static frontend folder ka path
STATIC_DIR = Path(__file__).resolve().parent / "static"


# ==========================================================
# Application Lifespan (Startup & Shutdown Management)
# ==========================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # App start hote hi database tables ko verify ya create karta hai
    init_db()
    print("[CacheFlow AI] Database tables verified with IST timestamp support.")
    yield
    print("[CacheFlow AI] Shutting down.")
# Comment: Yeh lifespan manager ensure karta hai ki jab server boot ho, tabhi SQLite me saari tables ready ho jayein.


# ==========================================================
# FastAPI App Initialization & CORS Setup
# ==========================================================
app = FastAPI(
    title="CacheFlow AI - Automated Invoice Reconciliation",
    version="2.0.0",
    description="Agentic 3-Way Invoice Reconciliation Platform with Deterministic Financial Matching & AI Arbitration",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Starlette text/plain 500 ko intercept karke clean JSON format me return karta hai."""
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal Server Error: {str(exc)}"}
    )

# Static frontend dashboard assets mount karo
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
# Comment: CORS allow karne se local frontend aur deployment bina kisi security block ke seamlessly baat kar pate hain.


# ==========================================================
# Root Route: Web Dashboard UI Serving
# ==========================================================
@app.get("/", include_in_schema=False)
def serve_index():
    """Browser me main dashboard UI (index.html) serve karta hai."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "CacheFlow AI API is running. Open /docs for API documentation."}
# Comment: Jab user browser me http://localhost:8000 kholta hai, toh yeh route index.html render kar deta hai.


# ==========================================================
# API Endpoint 1: Health Check (/api/health)
# ==========================================================
@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    """System ki health, database connectivity, LangGraph orchestration aur Fraud Shield status check karta hai."""
    total_recs = db.query(ReconciliationRecord).count()
    has_gemini = bool(os.getenv("GEMINI_API_KEY") and len(os.getenv("GEMINI_API_KEY", "")) > 8)
    return {
        "status": "healthy",
        "version": "2.0.0",
        "database": "connected",
        "total_reconciliations_stored": total_recs,
        "gemini_api_configured": has_gemini,
        "timezone": "IST (UTC+05:30)",
        "orchestration_engine": "LangGraph Stateful Multi-Agent StateGraph",
        "ocr_engine": "PyMuPDF + Tesseract OCR Engine",
        "fraud_shield_engine": "7-Tier Duplicate & Fraud Detection Shield Active",
        "ai_extraction_mode": "Gemini 2.5 Flash" if has_gemini else "Deterministic Heuristics Engine (Offline Safe)",
        "ai_arbitration_mode": "Gemini 2.5 Pro" if has_gemini else "Deterministic Reasoner (Offline Safe)"
    }
# Comment: Monitoring aur status checking ke liye endpoint hai, bata deta hai ki DB connected hai aur Gemini enabled hai ya offline engine chal raha hai.


# ==========================================================
# API Endpoint 2: Dashboard Metrics & KPIs (/api/dashboard/stats)
# ==========================================================
@app.get("/api/dashboard/stats")
def get_dashboard_metrics(db: Session = Depends(get_db)):
    """Dashboard ke upar ke summary cards (Total Processed, Clean Matches, Variances, Amounts, Fraud Alerts) calculate karta hai."""
    total = db.query(ReconciliationRecord).count()
    matched = db.query(ReconciliationRecord).filter(ReconciliationRecord.status == "MATCHED").count()
    approved = db.query(ReconciliationRecord).filter(ReconciliationRecord.status == "APPROVED").count()
    variances = db.query(ReconciliationRecord).filter(ReconciliationRecord.status == "VARIANCE_DETECTED").count()
    escalated = db.query(ReconciliationRecord).filter(ReconciliationRecord.status == "ESCALATED").count()
    rejected = db.query(ReconciliationRecord).filter(ReconciliationRecord.status == "REJECTED").count()
    fraud_count = db.query(ReconciliationRecord).filter(ReconciliationRecord.is_fraud_suspected == True).count()

    total_variance_sum = sum(r.variance_total for r in db.query(ReconciliationRecord.variance_total).all())
    vendors = db.query(VendorMemoryRecord).order_by(desc(VendorMemoryRecord.total_reconciliations)).limit(5).all()

    return {
        "total_processed": total,
        "matched_count": matched,
        "approved_count": approved,
        "variance_count": variances,
        "escalated_count": escalated,
        "rejected_count": rejected,
        "fraud_count": fraud_count,
        "match_rate_pct": round((matched / total * 100), 1) if total > 0 else 0.0,
        "total_variance_amount": round(total_variance_sum, 2),
        "top_vendors": [v.to_dict() for v in vendors]
    }
# Comment: Frontend ke dashboard stats cards (Total runs, Clean matches, Risk amount, Fraud alerts) isi endpoint se live data uthate hain.


# ==========================================================
# API Endpoint 3: Historical Records List (/api/reconciliations)
# ==========================================================
@app.get("/api/reconciliations")
def list_reconciliations(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Purane reconciliation records ki list return karta hai with pagination and status filter."""
    query = db.query(ReconciliationRecord)
    if status and status.upper() != "ALL":
        query = query.filter(ReconciliationRecord.status == status.upper())

    total = query.count()
    records = query.order_by(desc(ReconciliationRecord.created_at)).offset(offset).limit(limit).all()
    items = [r.to_dict() for r in records]
    return {"items": items, "total": total}
# Comment: Yeh table me sare records load karta hai. Refresh karne par yahi se sara saved data wapas screen par aa jata hai.


# ==========================================================
# API Endpoint 4: Single Record Detail (/api/reconciliations/{rec_id})
# ==========================================================
@app.get("/api/reconciliations/{rec_id}")
def get_reconciliation_detail(rec_id: int, db: Session = Depends(get_db)):
    """Kisi specific reconciliation record ki poori detail (matrix + audit logs) fetch karta hai."""
    rec = db.query(ReconciliationRecord).filter(ReconciliationRecord.id == rec_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Reconciliation record not found")

    data = rec.to_dict()
    # Us record se jude audit logs bhi fetch karo
    logs = db.query(AuditLogEntry).filter(AuditLogEntry.reconciliation_id == rec_id).order_by(AuditLogEntry.timestamp).all()
    data["audit_logs"] = [l.to_dict() for l in logs]
    return data
# Comment: Jab user kisi invoice par 'Inspect Matrix' click karta hai, toh yeh endpoint side-by-side line items aur dispute email return karta hai.


# ==========================================================
# API Endpoint 5: Document Upload & Main 3-Way Reconciliation Pipeline
# ==========================================================
@app.post("/api/upload-and-reconcile")
def upload_and_reconcile(
    invoice_file: UploadFile = File(...),
    po_file: UploadFile = File(...),
    grn_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Main 3-Way Reconciliation Pipeline:
    1. Ingests 3 files (Invoice, PO, GRN)
    2. Node 1: Extraction Agent (PyMuPDF + Gemini/Heuristics)
    3. Node 2: Matching Agent (Deterministic 3-Way Check)
    4. Node 3: AI Arbitration Agent (Risk Scoring & Dispute Email)
    5. Database me IST timestamp ke sath persist karta hai
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    session_id = str(uuid.uuid4())[:8]

    try:
        # Step 1: Uploaded files ko validate aur save karo
        allowed_exts = [".pdf", ".png", ".jpg", ".jpeg", ".txt"]
        file_paths = {}
        for role, f in [("invoice", invoice_file), ("po", po_file), ("grn", grn_file)]:
            raw_filename = f.filename or f"doc_{role}.txt"
            safe_filename = Path(raw_filename).name
            ext = os.path.splitext(safe_filename)[1].lower()
            if ext not in allowed_exts:
                raise HTTPException(status_code=400, detail=f"File {safe_filename} format '{ext}' is not supported. Use PDF, TXT, or images.")

            saved_filename = f"{session_id}_{role}_{safe_filename}"
            dest_path = os.path.join(UPLOAD_DIR, saved_filename)
            content = f.file.read()
            with open(dest_path, "wb") as out:
                out.write(content)
            file_paths[role] = dest_path

        # Audit log me upload event record karo (IST time me)
        record_audit_log(
            db,
            event_type="DOCUMENT_UPLOAD",
            source="API_GATEWAY",
            description=f"Received 3 documents for batch: {invoice_file.filename}, {po_file.filename}, {grn_file.filename}"
        )

        # Step 2: LangGraph Orchestration Engine Execution
        # Presentation Slide 4: "Stateful Workflow with Conditional Routing & Exception Loops"
        graph_state = run_reconciliation_workflow(
            session_id=session_id,
            invoice_file_path=file_paths["invoice"],
            po_file_path=file_paths["po"],
            grn_file_path=file_paths["grn"]
        )

        invoice_data = DocumentDataSchema.model_validate(graph_state["invoice_data"])
        po_data = DocumentDataSchema.model_validate(graph_state["po_data"])
        grn_data = DocumentDataSchema.model_validate(graph_state["grn_data"])
        match_result = ThreeWayMatchResult.model_validate(graph_state["match_result"])
        arbitration = ArbitrationResponse.model_validate(graph_state["arbitration_result"])
        fraud_result = graph_state.get("fraud_result") or {}
        execution_path_str = " -> ".join(graph_state.get("execution_path", []))

        # Audit log me LangGraph events record karo
        record_audit_log(
            db,
            event_type="LANGGRAPH_EXECUTION_COMPLETED",
            source="LANGGRAPH_ORCHESTRATOR",
            description=f"Path traversed: {execution_path_str}. Match status: {match_result.status} (Score: {match_result.match_score}%)"
        )

        if graph_state.get("is_fraud_suspected"):
            record_audit_log(
                db,
                event_type="FRAUD_SHIELD_ALERT",
                source="FRAUD_DETECTION_NODE",
                description=f"Risk: {graph_state.get('fraud_risk_level')} ({len(graph_state.get('fraud_flags', []))} flags): {'; '.join(graph_state.get('fraud_flags', []))}",
                severity="WARNING" if graph_state.get("fraud_risk_level") != "CRITICAL" else "ERROR"
            )

        # Unique reconciliation tracking code with Indian date format (YYYYMMDD)
        now_ist = get_ist_now()
        rec_code = f"REC-{now_ist.strftime('%Y%m%d')}-{session_id.upper()}"

        # Step 3: Master record ko database me save karo
        reconciliation = ReconciliationRecord(
            reconciliation_code=rec_code,
            created_at=now_ist,
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
            status="MATCHED" if (match_result.status == "MATCHED" and not graph_state.get("is_fraud_suspected")) else "VARIANCE_DETECTED",
            has_exceptions=(match_result.status != "MATCHED" or graph_state.get("is_fraud_suspected")),
            match_score=match_result.match_score,
            is_fraud_suspected=bool(graph_state.get("is_fraud_suspected", False)),
            fraud_risk_level=graph_state.get("fraud_risk_level", "LOW"),
            fraud_score=float(fraud_result.get("fraud_score", 0.0)),
            fraud_flags_json=json.dumps(graph_state.get("fraud_flags", [])),
            langgraph_execution_path=execution_path_str,
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

        # Line items ko individual rows me save karo
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

        # Vendor memory update karo (vendor match history)
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
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        record_audit_log(db, "RECONCILIATION_ERROR", "API_GATEWAY", f"Reconciliation failed: {str(exc)}", severity="ERROR")
        raise HTTPException(status_code=500, detail=f"Reconciliation failed: {str(exc)}")
# Comment: Yeh poora 3-Node pipeline ek request me run hota hai aur result return karta hai. User screen par instant matrix dekh sakta hai.


# ==========================================================
# API Endpoint 6: Human-in-the-Loop Review (/api/reconciliations/{rec_id}/review)
# ==========================================================
@app.post("/api/reconciliations/{rec_id}/review")
def review_reconciliation(rec_id: int, review: ReviewRequest, db: Session = Depends(get_db)):
    """Finance specialist ka manual sign-off (Approve, Reject ya Escalate) record karta hai."""
    rec = db.query(ReconciliationRecord).filter(ReconciliationRecord.id == rec_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Reconciliation record not found")

    rec.reviewer_action = review.action.upper()
    rec.reviewer_notes = review.notes
    rec.reviewed_at = get_ist_now() # Exact Indian Standard Time review stamp
    rec.status = review.action.upper()

    record_audit_log(
        db,
        event_type=f"HUMAN_{review.action.upper()}",
        source=f"HUMAN_REVIEWER ({review.reviewer_name})",
        description=f"Decision: {review.action.upper()}. Notes: {review.notes or 'None'}",
        reconciliation_id=rec.id
    )

    db.commit()
    db.refresh(rec)
    return {"message": f"Reconciliation successfully updated to {rec.status}", "record": rec.to_dict()}
# Comment: Compliance ke liye audit me user ka naam, exact IST decision time aur reason notes permanently save hote hain.


# ==========================================================
# API Endpoint 7: One-Click CSV Export (/api/export/{rec_id})
# ==========================================================
@app.get("/api/export/{rec_id}")
def export_reconciliation_csv(rec_id: int, db: Session = Depends(get_db)):
    """Reconciliation line items aur discrepancy details ko download karne ke liye CSV file generate karta hai."""
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
# Comment: Finance auditors aur ERP system me upload karne ke liye structured CSV export provide karta hai.


# ==========================================================
# API Endpoint 8: Immutable Audit Logs (/api/audit-logs)
# ==========================================================
@app.get("/api/audit-logs")
def get_audit_trail(limit: int = 50, db: Session = Depends(get_db)):
    """System ke latest audit logs fetch karta hai jisme har event ka exact IST timestamp hota hai."""
    logs = db.query(AuditLogEntry).order_by(desc(AuditLogEntry.timestamp)).limit(limit).all()
    return [l.to_dict() for l in logs]
# Comment: Frontend me 'Audit Trail' tab me latest 50 events unke IST time, severity aur details ke sath dikhata hai.


# ==========================================================
# API Endpoint 9: 1-Click Demo Scenarios Loader (/api/demo/{scenario_type})
# ==========================================================
@app.post("/api/demo/{scenario_type}")
def run_demo_scenario(scenario_type: str, db: Session = Depends(get_db)):
    """
    1-Click Demo Scenarios:
    - clean_match: Sab kuch perfectly match karta hai (100 laptops @ Rs 50,000)
    - price_mismatch: Vendor ne PO se zyada rate lagaya hai (Rs 550 vs Rs 500)
    - quantity_shortage: Billed 100 lekin delivered sirf 90 pieces
    - vendor_alias: Pvt Ltd vs Private Limited alias matching
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
    elif scenario_type == "duplicate_fraud":
        # Scenario 5: Duplicate Billing, Ghost Line Item & Price Inflation Fraud
        invoice = DocumentDataSchema(
            document_type="invoice",
            vendor_name="CyberShield Security Solutions",
            document_number=f"INV-FRAUD-{session_id}",
            document_date="2026-11-04",
            currency="INR",
            subtotal=650000.0,
            tax=117000.0,
            total_amount=767000.0,
            line_items=[
                LineItemSchema(item_code="FW-APPLIANCE", description="Next-Gen Enterprise Firewall Appliance", quantity=2.0, unit_price=200000.0, total_price=400000.0), # Invoiced at 200,000 vs PO 125,000 (+60% surge!)
                LineItemSchema(item_code="PHANTOM-CONSULT", description="Unauthorized Cyber Assessment Surcharge", quantity=1.0, unit_price=250000.0, total_price=250000.0) # Ghost item, not in PO!
            ]
        )
        po = DocumentDataSchema(
            document_type="purchase_order",
            vendor_name="CyberShield Security Solutions",
            document_number=f"PO-SEC-{session_id}",
            document_date="2026-10-15",
            currency="INR",
            subtotal=250000.0,
            tax=45000.0,
            total_amount=295000.0,
            line_items=[
                LineItemSchema(item_code="FW-APPLIANCE", description="Next-Gen Enterprise Firewall Appliance", quantity=2.0, unit_price=125000.0, total_price=250000.0)
            ]
        )
        grn = DocumentDataSchema(
            document_type="grn",
            vendor_name="CyberShield Security Solutions",
            document_number=f"GRN-SEC-{session_id}",
            document_date="2026-10-30",
            currency="INR",
            subtotal=0.0,
            tax=0.0,
            total_amount=0.0,
            line_items=[
                LineItemSchema(item_code="FW-APPLIANCE", description="Next-Gen Enterprise Firewall Appliance", quantity=2.0, unit_price=0.0, total_price=0.0)
            ]
        )
    else:
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

    # 3-Way match, Fraud Detection aur AI Arbitration run karo
    match_result = perform_three_way_reconciliation(invoice, po, grn)
    fraud_result = evaluate_fraud_and_duplicates(invoice, po, grn, match_result, db=db)
    arbitration = arbitrate_exceptions(match_result, invoice, po, grn)

    # Agar fraud alerts hain toh arbitration summary aur risk severity me add karo
    if fraud_result.is_fraud_suspected:
        for flag in fraud_result.flags:
            if flag not in arbitration.findings:
                arbitration.findings.append(f"[FRAUD SHIELD ALERT] {flag}")
        if fraud_result.fraud_risk_level in ["HIGH", "CRITICAL"]:
            arbitration.risk_severity = fraud_result.fraud_risk_level
            arbitration.recommended_action = "REJECT_INVOICE" if fraud_result.fraud_risk_level == "CRITICAL" else "HOLD_PAYMENT"

    # LangGraph simulated execution path for demo scenario
    if match_result.status == "MATCHED" and not fraud_result.is_fraud_suspected:
        langgraph_path = "START -> Node 1: Extraction Agent -> Node 2: 3-Way Matching Agent -> Node 3: Fraud & Duplicate Shield -> Node 6: Auto-Reconciliation Completed -> END"
    else:
        langgraph_path = "START -> Node 1: Extraction Agent -> Node 2: 3-Way Matching Agent -> Node 3: Fraud & Duplicate Shield -> Node 4: AI Arbitration Agent -> Node 5: Human Review Package Ready -> END"

    now_ist = get_ist_now()
    rec_code = f"REC-DEMO-{session_id.upper()}"
    reconciliation = ReconciliationRecord(
        reconciliation_code=rec_code,
        created_at=now_ist,
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
        status="MATCHED" if (match_result.status == "MATCHED" and not fraud_result.is_fraud_suspected) else "VARIANCE_DETECTED",
        has_exceptions=(match_result.status != "MATCHED" or fraud_result.is_fraud_suspected),
        match_score=match_result.match_score,
        is_fraud_suspected=fraud_result.is_fraud_suspected,
        fraud_risk_level=fraud_result.fraud_risk_level,
        fraud_score=fraud_result.fraud_score,
        fraud_flags_json=json.dumps(fraud_result.flags),
        langgraph_execution_path=langgraph_path,
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
        description=f"Loaded test scenario '{scenario_type}' ({rec_code})",
        reconciliation_id=reconciliation.id
    )

    db.commit()
    db.refresh(reconciliation)
    return reconciliation.to_dict()
# Comment: Interview ya demo ke dauran bina manual file upload kare 1-click me exact test scenario load kar deta hai.


# ==========================================================
# Server Runner (Local aur Render Deployment ke liye)
# ==========================================================
if __name__ == "__main__":
    import uvicorn
    # Render cloud platform se PORT environment variable uthata hai, default 8000
    port = int(os.environ.get("PORT", 8000))
    print(f"[CacheFlow AI] Server starting on port {port} (IST Timezone Active)...")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
# Comment: Yeh file directly 'python app.py' se bhi run ho sakti hai aur Render cloud pe 'uvicorn app:app --port $PORT' se bhi chalti hai.
