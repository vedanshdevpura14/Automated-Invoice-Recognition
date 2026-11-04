import re
from difflib import SequenceMatcher

from models import (
    AMOUNT_TOLERANCE,
    TAX_TOLERANCE,
    PRICE_TOLERANCE,
    DocumentDataSchema,
    ThreeWayMatchResult,
    VarianceItem,
    LineItemComparisonResult
)


def normalize_vendor_name(name: str) -> str:
    """Removes corporate legal suffixes and cleans whitespace for reliable alias matching."""
    if not name:
        return ""
    cleaned = name.lower()
    suffixes = [
        "private limited", "pvt. ltd.", "pvt ltd", "ltd.", "ltd",
        "corporation", "corp.", "corp", "incorporated", "inc.", "inc",
        "llc", "llp", "gmbh", "co.", "co"
    ]
    for s in suffixes:
        cleaned = re.sub(rf"\b{re.escape(s)}\b", "", cleaned)
    cleaned = re.sub(r"[^\w\s]", "", cleaned)
    return " ".join(cleaned.split())


def are_vendors_matching(v1: str, v2: str) -> bool:
    """Checks vendor equivalence using normalization and fuzzy string similarity."""
    n1 = normalize_vendor_name(v1)
    n2 = normalize_vendor_name(v2)
    if not n1 or not n2:
        return True
    if n1 == n2:
        return True
    similarity = SequenceMatcher(None, n1, n2).ratio()
    return similarity >= 0.85


def perform_three_way_reconciliation(
    invoice: DocumentDataSchema,
    po: DocumentDataSchema,
    grn: DocumentDataSchema
) -> ThreeWayMatchResult:
    """
    Node 2: Deterministic 3-Way Matching Engine:
    Compares Invoice vs Purchase Order (PO) vs Goods Receipt Note (GRN).
    Enforces financial rules strictly with configured tolerances.
    """
    variances: list[VarianceItem] = []
    line_comparisons: list[LineItemComparisonResult] = []

    # 1. Vendor Match Check
    vendor_matched = are_vendors_matching(invoice.vendor_name, po.vendor_name)
    if not vendor_matched:
        variances.append(VarianceItem(
            field="vendor_name",
            invoice_val=invoice.vendor_name,
            comparison_val=po.vendor_name,
            variance_amount=0.0,
            message=f"Vendor mismatch: Invoice shows '{invoice.vendor_name}' while PO states '{po.vendor_name}'"
        ))

    # 2. Grand Total Match Check
    total_diff = round(invoice.total_amount - po.total_amount, 2)
    if abs(total_diff) > AMOUNT_TOLERANCE:
        variances.append(VarianceItem(
            field="total_amount",
            invoice_val=invoice.total_amount,
            comparison_val=po.total_amount,
            variance_amount=abs(total_diff),
            message=f"Total amount variance: Invoice is {invoice.currency} {invoice.total_amount:,.2f} vs PO agreed {invoice.currency} {po.total_amount:,.2f} (Diff: {total_diff:+,.2f})"
        ))

    # 3. Tax Match Check
    tax_diff = round(invoice.tax - po.tax, 2)
    if abs(tax_diff) > TAX_TOLERANCE:
        variances.append(VarianceItem(
            field="tax",
            invoice_val=invoice.tax,
            comparison_val=po.tax,
            variance_amount=abs(tax_diff),
            message=f"Tax variance: Invoice tax is {invoice.currency} {invoice.tax:,.2f} vs PO tax {invoice.currency} {po.tax:,.2f} (Diff: {tax_diff:+,.2f})"
        ))

    # 4. Line Items Alignment
    po_items_map = {item.item_code.upper(): item for item in po.line_items}
    grn_items_map = {item.item_code.upper(): item for item in grn.line_items}

    def find_matching_item(code: str, desc: str, items_map: dict):
        code_upper = code.upper()
        if code_upper in items_map:
            return items_map[code_upper]
        for k, v in items_map.items():
            if desc and v.description and SequenceMatcher(None, desc.lower(), v.description.lower()).ratio() > 0.8:
                return v
        return None

    all_invoice_codes = set()
    total_line_variance = 0.0

    for inv_item in invoice.line_items:
        code = inv_item.item_code
        all_invoice_codes.add(code.upper())
        desc = inv_item.description or code
        inv_qty = inv_item.quantity
        inv_price = inv_item.unit_price
        inv_line_tot = inv_item.total_price or (inv_qty * inv_price)

        # Match with PO
        po_match = find_matching_item(code, desc, po_items_map)
        po_price = po_match.unit_price if po_match else None
        po_line_tot = (inv_qty * po_price) if po_price is not None else 0.0

        # Match with GRN
        grn_match = find_matching_item(code, desc, grn_items_map)
        grn_qty = grn_match.quantity if grn_match else None

        # Price Check
        price_status = "MATCH"
        if po_match is None:
            price_status = "MISSING_IN_PO"
            variances.append(VarianceItem(
                field="missing_in_po",
                item_code=code,
                description=desc,
                invoice_val=inv_price,
                comparison_val=None,
                variance_amount=inv_line_tot,
                message=f"Item {code} ({desc}) was invoiced but does not exist in Purchase Order {po.document_number}"
            ))
        elif abs(inv_price - po_price) > PRICE_TOLERANCE:
            price_status = "MISMATCH"
            p_diff = round(inv_price - po_price, 2)
            variances.append(VarianceItem(
                field="unit_price",
                item_code=code,
                description=desc,
                invoice_val=inv_price,
                comparison_val=po_price,
                variance_amount=abs(p_diff * inv_qty),
                message=f"Unit price mismatch for {code} ({desc}): Billed {invoice.currency} {inv_price:,.2f}/unit vs PO price {invoice.currency} {po_price:,.2f}/unit (Overbilled: {p_diff:+,.2f}/unit)"
            ))

        # Quantity Check (Invoice vs GRN)
        qty_status = "MATCH"
        if grn_match is None:
            qty_status = "MISSING_IN_GRN"
            variances.append(VarianceItem(
                field="quantity",
                item_code=code,
                description=desc,
                invoice_val=inv_qty,
                comparison_val=0,
                variance_amount=inv_line_tot,
                message=f"Quantity discrepancy for {code}: Invoiced {inv_qty} units, but item not found in Goods Receipt Note"
            ))
        elif inv_qty != grn_qty:
            qty_status = "MISMATCH"
            q_diff = inv_qty - grn_qty
            if q_diff > 0:
                variances.append(VarianceItem(
                    field="quantity",
                    item_code=code,
                    description=desc,
                    invoice_val=inv_qty,
                    comparison_val=grn_qty,
                    variance_amount=round(q_diff * (po_price or inv_price), 2),
                    message=f"Quantity discrepancy for {code} ({desc}): Invoiced for {inv_qty} units, but warehouse GRN verified delivery of only {grn_qty} units (Shortfall: {q_diff} units)"
                ))

        expected_line_cost = (grn_qty if grn_qty is not None else 0.0) * (po_price if po_price is not None else inv_price)
        line_variance = max(0.0, round(inv_line_tot - expected_line_cost, 2)) if (price_status != "MATCH" or qty_status != "MATCH") else 0.0
        total_line_variance += line_variance

        line_status = "MATCHED" if (price_status == "MATCH" and qty_status == "MATCH") else "VARIANCE"

        line_comparisons.append(LineItemComparisonResult(
            item_code=code,
            description=desc,
            invoice_qty=inv_qty,
            grn_qty=grn_qty,
            qty_status=qty_status,
            invoice_unit_price=inv_price,
            po_unit_price=po_price,
            price_status=price_status,
            invoice_line_total=inv_line_tot,
            po_line_total=po_line_tot,
            variance_amount=line_variance,
            status=line_status
        ))

    # Calculate match score 0 - 100%
    passed_checks = 0
    if vendor_matched: passed_checks += 1
    if abs(total_diff) <= AMOUNT_TOLERANCE: passed_checks += 1
    if abs(tax_diff) <= TAX_TOLERANCE: passed_checks += 1

    qty_matches = sum(1 for l in line_comparisons if l.qty_status == "MATCH")
    price_matches = sum(1 for l in line_comparisons if l.price_status == "MATCH")
    total_lines = max(1, len(line_comparisons))

    match_score = round(
        ((passed_checks / 3.0) * 50.0) +
        ((qty_matches / total_lines) * 25.0) +
        ((price_matches / total_lines) * 25.0),
        1
    )

    status = "MATCHED" if len(variances) == 0 else "VARIANCE_DETECTED"

    return ThreeWayMatchResult(
        status=status,
        vendor_matched=vendor_matched,
        invoice_vendor=invoice.vendor_name,
        po_vendor=po.vendor_name,
        invoice_total=invoice.total_amount,
        po_total=po.total_amount,
        invoice_tax=invoice.tax,
        po_tax=po.tax,
        variance_total=round(max(abs(total_diff), total_line_variance), 2),
        match_score=match_score,
        variances=variances,
        line_comparisons=line_comparisons
    )
