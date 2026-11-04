import os
from models import (
    SessionLocal,
    DocumentDataSchema,
    LineItemSchema,
    ReconciliationRecord
)
from matcher import perform_three_way_reconciliation, are_vendors_matching
from extractor import extract_document
from agent import arbitrate_deterministic
from app import health_check, run_demo_scenario, get_dashboard_metrics, export_reconciliation_csv


def test_vendor_alias_matching():
    """Verifies corporate suffix normalization and fuzzy matching."""
    assert are_vendors_matching("ABC Technologies Private Limited", "ABC Technologies Pvt. Ltd.")
    assert are_vendors_matching("Global Supplies Corp.", "Global Supplies Corporation")
    assert are_vendors_matching("Delta Logistics LLC", "Delta Logistics Ltd")


def test_three_way_matching_clean():
    """Verifies that identical invoice, PO, and GRN yield a clean MATCHED status."""
    invoice = DocumentDataSchema(
        document_type="invoice",
        vendor_name="Acme Corp",
        document_number="INV-001",
        currency="INR",
        subtotal=10000.0,
        tax=1800.0,
        total_amount=11800.0,
        line_items=[
            LineItemSchema(item_code="ITEM-A", description="Item A", quantity=10.0, unit_price=1000.0, total_price=10000.0)
        ]
    )
    po = DocumentDataSchema(
        document_type="purchase_order",
        vendor_name="Acme Corp",
        document_number="PO-001",
        currency="INR",
        subtotal=10000.0,
        tax=1800.0,
        total_amount=11800.0,
        line_items=[
            LineItemSchema(item_code="ITEM-A", description="Item A", quantity=10.0, unit_price=1000.0, total_price=10000.0)
        ]
    )
    grn = DocumentDataSchema(
        document_type="grn",
        vendor_name="Acme Corp",
        document_number="GRN-001",
        currency="INR",
        subtotal=0.0,
        tax=0.0,
        total_amount=0.0,
        line_items=[
            LineItemSchema(item_code="ITEM-A", description="Item A", quantity=10.0, unit_price=0.0, total_price=0.0)
        ]
    )

    result = perform_three_way_reconciliation(invoice, po, grn)
    assert result.status == "MATCHED"
    assert result.match_score == 100.0
    assert len(result.variances) == 0

    arbitration = arbitrate_deterministic(result, invoice, po, grn)
    assert arbitration.risk_severity == "LOW"
    assert arbitration.recommended_action == "AUTO_APPROVE"


def test_three_way_matching_price_mismatch():
    """Verifies that unit price over-billing is flagged."""
    invoice = DocumentDataSchema(
        document_type="invoice",
        vendor_name="Acme Corp",
        document_number="INV-002",
        currency="INR",
        subtotal=55000.0,
        tax=9900.0,
        total_amount=64900.0,
        line_items=[
            LineItemSchema(item_code="ITEM-B", description="Item B", quantity=100.0, unit_price=550.0, total_price=55000.0)
        ]
    )
    po = DocumentDataSchema(
        document_type="purchase_order",
        vendor_name="Acme Corp",
        document_number="PO-002",
        currency="INR",
        subtotal=50000.0,
        tax=9000.0,
        total_amount=59000.0,
        line_items=[
            LineItemSchema(item_code="ITEM-B", description="Item B", quantity=100.0, unit_price=500.0, total_price=50000.0)
        ]
    )
    grn = DocumentDataSchema(
        document_type="grn",
        vendor_name="Acme Corp",
        document_number="GRN-002",
        currency="INR",
        subtotal=0.0,
        tax=0.0,
        total_amount=0.0,
        line_items=[
            LineItemSchema(item_code="ITEM-B", description="Item B", quantity=100.0, unit_price=0.0, total_price=0.0)
        ]
    )

    result = perform_three_way_reconciliation(invoice, po, grn)
    assert result.status == "VARIANCE_DETECTED"
    assert any(v.field == "unit_price" for v in result.variances)

    arbitration = arbitrate_deterministic(result, invoice, po, grn)
    assert arbitration.recommended_action in ["HUMAN_INVESTIGATION", "ESCALATE_TO_VENDOR", "REJECT_INVOICE"]
    assert "Discrepancy Notification" in arbitration.dispute_email_draft


def test_extractor_heuristics():
    """Verifies that raw text gets extracted accurately into DocumentDataSchema."""
    sample_text = """
    INVOICE
    Vendor: TechMatrix Solutions Pvt Ltd
    Invoice No: INV-9876
    Date: 2026-11-04
    Subtotal: 50,000.00
    Tax: 9,000.00
    Total Amount: 59,000.00

    ITEM-101 Laptop Computer 5 10000 50000
    """
    doc = extract_document(sample_text, doc_hint="invoice")
    assert doc.document_type == "invoice"
    assert "TechMatrix" in doc.vendor_name
    assert doc.document_number == "INV-9876"
    assert doc.total_amount == 59000.0


def test_api_pipeline():
    """Verifies FastAPI health check, demo scenario execution, dashboard metrics, and CSV export."""
    db = SessionLocal()
    try:
        # 1. Health check
        health = health_check(db)
        assert health["status"] == "healthy"
        assert health["database"] == "connected"

        # 2. Run clean match scenario
        demo_rec = run_demo_scenario("clean_match", db)
        assert demo_rec["status"] == "MATCHED"
        assert demo_rec["match_score"] == 100.0
        rec_id = demo_rec["id"]

        # 3. Dashboard KPIs
        stats = get_dashboard_metrics(db)
        assert stats["total_processed"] >= 1

        # 4. CSV export
        csv_resp = export_reconciliation_csv(rec_id, db)
        assert csv_resp.status_code == 200
        assert "INV-" in str(csv_resp.body)
    finally:
        db.close()


if __name__ == "__main__":
    import pytest
    pytest.main(["-v", __file__])
