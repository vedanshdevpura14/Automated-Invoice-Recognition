import pytest
from app.schemas.schemas import DocumentDataSchema, LineItemSchema
from app.services.matching_engine import (
    perform_three_way_reconciliation,
    are_vendors_matching,
    normalize_vendor_name
)

def test_vendor_name_normalization():
    v1 = "ABC Technologies Private Limited"
    v2 = "ABC Technologies Pvt. Ltd."
    assert are_vendors_matching(v1, v2) is True

    v3 = "Global Software Corp."
    v4 = "Global Software Corporation"
    assert are_vendors_matching(v3, v4) is True

    v5 = "Apex Hardware LLC"
    v6 = "Completely Different Vendor Inc"
    assert are_vendors_matching(v5, v6) is False


def test_clean_3way_match():
    invoice = DocumentDataSchema(
        document_type="invoice",
        vendor_name="ABC Technologies Private Limited",
        document_number="INV-101",
        currency="INR",
        subtotal=50000.0,
        tax=9000.0,
        total_amount=59000.0,
        line_items=[
            LineItemSchema(item_code="ITEM-01", description="Dell Laptops", quantity=100.0, unit_price=500.0, total_price=50000.0)
        ]
    )
    po = DocumentDataSchema(
        document_type="purchase_order",
        vendor_name="ABC Technologies Pvt. Ltd.",
        document_number="PO-101",
        currency="INR",
        subtotal=50000.0,
        tax=9000.0,
        total_amount=59000.0,
        line_items=[
            LineItemSchema(item_code="ITEM-01", description="Dell Laptops", quantity=100.0, unit_price=500.0, total_price=50000.0)
        ]
    )
    grn = DocumentDataSchema(
        document_type="grn",
        vendor_name="ABC Technologies",
        document_number="GRN-101",
        currency="INR",
        subtotal=0.0,
        tax=0.0,
        total_amount=0.0,
        line_items=[
            LineItemSchema(item_code="ITEM-01", description="Dell Laptops", quantity=100.0, unit_price=0.0, total_price=0.0)
        ]
    )

    result = perform_three_way_reconciliation(invoice, po, grn)
    assert result.status == "MATCHED"
    assert result.match_score == 100.0
    assert len(result.variances) == 0
    assert result.vendor_matched is True


def test_price_mismatch_scenario():
    # Scenario 1 from Interview Guide:
    # PO: 100 units @ 500 = 50,000
    # Invoice: 100 units @ 550 = 55,000 (Difference: Rs 5,000)
    invoice = DocumentDataSchema(
        document_type="invoice",
        vendor_name="TechMatrix Ltd",
        document_number="INV-202",
        currency="INR",
        subtotal=55000.0,
        tax=9900.0,
        total_amount=64900.0,
        line_items=[
            LineItemSchema(item_code="MON-01", description="Monitors", quantity=100.0, unit_price=550.0, total_price=55000.0)
        ]
    )
    po = DocumentDataSchema(
        document_type="purchase_order",
        vendor_name="TechMatrix Ltd",
        document_number="PO-202",
        currency="INR",
        subtotal=50000.0,
        tax=9000.0,
        total_amount=59000.0,
        line_items=[
            LineItemSchema(item_code="MON-01", description="Monitors", quantity=100.0, unit_price=500.0, total_price=50000.0)
        ]
    )
    grn = DocumentDataSchema(
        document_type="grn",
        vendor_name="TechMatrix Ltd",
        document_number="GRN-202",
        currency="INR",
        line_items=[
            LineItemSchema(item_code="MON-01", description="Monitors", quantity=100.0, unit_price=0.0, total_price=0.0)
        ]
    )

    result = perform_three_way_reconciliation(invoice, po, grn)
    assert result.status == "VARIANCE_DETECTED"
    assert any(v.field == "unit_price" for v in result.variances)
    assert any(v.field == "total_amount" for v in result.variances)
    assert result.variance_total == 5900.0 or result.variance_total == 5000.0 or result.variance_total >= 5000.0


def test_quantity_shortage_scenario():
    # Scenario 4 from Interview Guide:
    # Invoiced 100, PO ordered 100, but warehouse received only 90!
    invoice = DocumentDataSchema(
        document_type="invoice",
        vendor_name="Apex Hardware",
        document_number="INV-303",
        currency="INR",
        subtotal=200000.0,
        tax=36000.0,
        total_amount=236000.0,
        line_items=[
            LineItemSchema(item_code="RAM-01", description="Server RAM", quantity=100.0, unit_price=2000.0, total_price=200000.0)
        ]
    )
    po = DocumentDataSchema(
        document_type="purchase_order",
        vendor_name="Apex Hardware",
        document_number="PO-303",
        currency="INR",
        subtotal=200000.0,
        tax=36000.0,
        total_amount=236000.0,
        line_items=[
            LineItemSchema(item_code="RAM-01", description="Server RAM", quantity=100.0, unit_price=2000.0, total_price=200000.0)
        ]
    )
    grn = DocumentDataSchema(
        document_type="grn",
        vendor_name="Apex Hardware",
        document_number="GRN-303",
        currency="INR",
        line_items=[
            LineItemSchema(item_code="RAM-01", description="Server RAM", quantity=90.0, unit_price=0.0, total_price=0.0)
        ]
    )

    result = perform_three_way_reconciliation(invoice, po, grn)
    assert result.status == "VARIANCE_DETECTED"
    qty_var = next((v for v in result.variances if v.field == "quantity"), None)
    assert qty_var is not None
    assert qty_var.invoice_val == 100.0
    assert qty_var.comparison_val == 90.0
