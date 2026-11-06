import re
import json
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc

from models import (
    DocumentDataSchema,
    ThreeWayMatchResult,
    FraudDetectionResult,
    ReconciliationRecord,
    AMOUNT_TOLERANCE,
    PRICE_TOLERANCE
)
from matcher import are_vendors_matching, normalize_vendor_name

# ==========================================================
# FRAUD & DUPLICATE DETECTION ENGINE (CacheFlow Shield)
# ==========================================================
# Presentation Requirement:
# "Fraud Vulnerability: Lack of automated validation lets duplicate billing and phishing scams slip through."
# "Fraud Detection: Identify suspicious patterns and anomalies to prevent fraud."
#
# Hinglish Explanation:
# Yeh engine invoice ko pass hone se pehle 7 critical fraud & duplicate checks karta hai:
# 1. Exact Duplicate Invoice Check (Database me same invoice number pehle se toh nahi hai)
# 2. Fuzzy Duplicate Billing (Same vendor ne same amount ka bill alag number se dobara toh nahi bhej diya)
# 3. Ghost Invoicing / Unordered Items (Aise items bill karna jo PO me the hi nahi)
# 4. Severe Price Surge / Inflation (PO ke agreed rate se achanak 20%+ zyada price claim karna)
# 5. Phantom Delivery / False Quantity (Warehouse me saman aaya hi nahi aur bill bhej diya)
# 6. Tax / GST Rate Manipulation (Tax credit ke naam par galat tax charge karna)
# 7. Vendor Name Spoofing / Phishing (Real vendor ke naam se milta-julta fake naam use karna)
# ==========================================================


def check_duplicate_invoice_number(
    db: Optional[Session],
    invoice_number: str,
    vendor_name: str
) -> Optional[str]:
    """
    Check 1: Exact Duplicate Invoice Number Check
    Database me verify karta hai ki kya yeh invoice number pehle se process ho chuka hai.
    """
    if not db or not invoice_number:
        return None

    # Database query: check for existing non-pending record with same invoice number
    existing = db.query(ReconciliationRecord).filter(
        ReconciliationRecord.invoice_number.ilike(invoice_number.strip())
    ).order_by(desc(ReconciliationRecord.created_at)).first()

    if existing:
        return (
            f"DUPLICATE_INVOICE_NUMBER: Invoice #{invoice_number} already exists in database "
            f"(Audit Code: {existing.reconciliation_code}, Status: {existing.status}, Processed: {existing.created_at.strftime('%Y-%m-%d') if existing.created_at else 'Earlier'}). "
            f"Potential double-billing detected!"
        )
    return None
# Comment: Agar vendor ne ek hi bill do baar upload kar diya, toh yeh check use pehli hi nazar me pakad leta hai.


def check_fuzzy_duplicate_billing(
    db: Optional[Session],
    vendor_name: str,
    total_amount: float,
    current_invoice_num: str,
    po_number: Optional[str] = None
) -> Optional[str]:
    """
    Check 2: Fuzzy Duplicate Billing / Double-Submission Trap
    Check karta hai ki kya usi vendor ne same Purchase Order (PO) par exact same amount ka
    koi doosra invoice bhej kar double payment lene ki koshish toh nahi ki.
    """
    if not db or total_amount <= 0:
        return None

    # Total amount match search with tolerance
    min_amt = total_amount - AMOUNT_TOLERANCE
    max_amt = total_amount + AMOUNT_TOLERANCE

    suspicious_recs = db.query(ReconciliationRecord).filter(
        ReconciliationRecord.invoice_total >= min_amt,
        ReconciliationRecord.invoice_total <= max_amt
    ).all()

    for rec in suspicious_recs:
        # Ignore agar same record ho
        if rec.invoice_number.strip().upper() == current_invoice_num.strip().upper():
            continue
        # Vendor match check
        if are_vendors_matching(rec.vendor_name, vendor_name):
            # Same PO reference par same amount bill karna duplicate billing trap hai
            if po_number and rec.po_number and rec.po_number.strip().upper() == po_number.strip().upper():
                return (
                    f"SUSPICIOUS_DUPLICATE_BILLING: Another invoice #{rec.invoice_number} with identical "
                    f"total amount {rec.currency} {rec.invoice_total:,.2f} against PO #{po_number} was already billed by vendor '{rec.vendor_name}'. "
                    f"High risk of duplicate billing attempt under alternate invoice code!"
                )
    return None
# Comment: Agar koi vendor bill number badal kar exact same PO par dobara paise lene ki koshish karega, toh yeh check use pakad leta hai.


def check_ghost_line_items(
    invoice: DocumentDataSchema,
    po: DocumentDataSchema
) -> List[str]:
    """
    Check 3: Ghost Line Items (Unordered Items in Invoice)
    Aise line items pakadta hai jo Invoice me add kar diye gaye hain lekin Purchase Order me the hi nahi.
    """
    flags = []
    po_item_codes = {item.item_code.strip().upper() for item in po.line_items}
    po_descriptions = {item.description.strip().lower() for item in po.line_items if item.description}

    for item in invoice.line_items:
        code = item.item_code.strip().upper()
        desc = (item.description or "").strip().lower()

        code_match = code in po_item_codes
        desc_match = any(d in desc or desc in d for d in po_descriptions if len(d) > 3)

        if not code_match and not desc_match:
            flags.append(
                f"GHOST_INVOICING: Line item '{item.item_code}' ({item.description}) with value "
                f"{invoice.currency} {item.total_price:,.2f} is NOT authorized in Purchase Order {po.document_number}."
            )
    return flags
# Comment: Ghost Invoicing fraud me vendor faltu items invoice me daal deta hai jo company ne order hi nahi kiye the.


def check_price_surge_fraud(
    invoice: DocumentDataSchema,
    po: DocumentDataSchema
) -> List[str]:
    """
    Check 4: Severe Unit Price Inflation / Gouging Check
    Agar unit price approved PO price se 20% se zyada inflated hai bina change-order approval ke.
    """
    flags = []
    po_map = {item.item_code.strip().upper(): item.unit_price for item in po.line_items}

    for item in invoice.line_items:
        code = item.item_code.strip().upper()
        if code in po_map:
            po_price = po_map[code]
            if po_price > 0 and item.unit_price > po_price:
                pct_surge = round(((item.unit_price - po_price) / po_price) * 100.0, 1)
                # Agar 20% se zyada rate badha diya gaya ho toh fraud alert trigger karo
                if pct_surge >= 20.0:
                    flags.append(
                        f"PRICE_INFLATION_ANOMALY: Item '{item.item_code}' unit price is inflated by +{pct_surge}% "
                        f"({invoice.currency} {item.unit_price:,.2f} billed vs agreed PO rate {invoice.currency} {po_price:,.2f})."
                    )
    return flags
# Comment: Price surge check se ensure hota hai ki vendor secretly unit rate hike karke financial leakage na kare.


def check_phantom_delivery(
    invoice: DocumentDataSchema,
    grn: DocumentDataSchema
) -> List[str]:
    """
    Check 5: Phantom Delivery / Shortfall Exploitation
    Agar invoice me mangi gayi quantity warehouse me actually physically deliver hui quantity se kaafi zyada ho.
    """
    flags = []
    grn_map = {item.item_code.strip().upper(): item.quantity for item in grn.line_items}

    for item in invoice.line_items:
        code = item.item_code.strip().upper()
        inv_qty = item.quantity
        if code in grn_map:
            grn_qty = grn_map[code]
            if inv_qty > grn_qty:
                shortage = inv_qty - grn_qty
                pct_missing = round((shortage / inv_qty) * 100.0, 1)
                # Agar 10% se zyada delivery gayab ho
                if pct_missing >= 10.0 or grn_qty == 0:
                    flags.append(
                        f"PHANTOM_DELIVERY_FRAUD: Invoiced for {inv_qty} units of '{item.item_code}', but warehouse GRN "
                        f"confirms delivery of only {grn_qty} units ({shortage} units missing, {pct_missing}% shortfall)."
                    )
    return flags
# Comment: Phantom delivery me saman factory me kam pahunchta hai par bill poore 100% ka bhej diya jata hai.


def check_tax_manipulation(invoice: DocumentDataSchema) -> List[str]:
    """
    Check 6: Tax / GST Calculation Integrity Check
    Verify karta hai ki billed tax mathematically subtotal ke standard slabs (e.g. 5%, 12%, 18%, 28%) se match karta hai ya nahi.
    """
    flags = []
    if invoice.subtotal > 0 and invoice.tax > 0:
        calculated_effective_rate = round((invoice.tax / invoice.subtotal) * 100.0, 1)
        # Standard tax slabs
        valid_slabs = [0.0, 5.0, 12.0, 18.0, 28.0]
        # Check if rate is drastically outside standard slabs (> 35% tax claim is an anomaly)
        if calculated_effective_rate > 35.0:
            flags.append(
                f"TAX_MANIPULATION_ALERT: Billed tax of {invoice.currency} {invoice.tax:,.2f} represents an abnormal "
                f"effective rate of {calculated_effective_rate}% on subtotal {invoice.currency} {invoice.subtotal:,.2f}."
            )
        # Check if subtotal + tax != total_amount
        math_total = round(invoice.subtotal + invoice.tax, 2)
        if abs(math_total - invoice.total_amount) > AMOUNT_TOLERANCE * 2:
            flags.append(
                f"ARITHMETIC_TAMPERING: Document math does not balance. Subtotal ({invoice.subtotal:,.2f}) + "
                f"Tax ({invoice.tax:,.2f}) = {math_total:,.2f}, but Total claims {invoice.total_amount:,.2f}."
            )
    return flags
# Comment: GST ya tax calculation me koi bhi math tampering pakadne ke liye yeh calculation chalti hai.


def check_vendor_name_spoofing(
    invoice_vendor: str,
    po_vendor: str
) -> Optional[str]:
    """
    Check 7: Vendor Typosquatting / Identity Phishing Check
    Phishing emails fake supplier banakar company ko fake invoices bhejti hain.
    """
    if not invoice_vendor or not po_vendor:
        return None

    norm_inv = normalize_vendor_name(invoice_vendor)
    norm_po = normalize_vendor_name(po_vendor)

    if norm_inv == norm_po:
        return None

    # Agar vendors match hi nahi ho rahe (completely different party)
    if not are_vendors_matching(invoice_vendor, po_vendor):
        return (
            f"VENDOR_SPOOFING_ALERT: Invoice vendor '{invoice_vendor}' does not match the approved PO supplier '{po_vendor}'. "
            f"Possible vendor impersonation or unauthorized third-party billing!"
        )
    return None
# Comment: Phishing attack se bachane ke liye supplier ka identity match check kiya jata hai.


# ==========================================================
# Comprehensive Fraud Detection Pipeline Entry Point
# ==========================================================
def evaluate_fraud_and_duplicates(
    invoice: DocumentDataSchema,
    po: DocumentDataSchema,
    grn: DocumentDataSchema,
    match_result: Optional[ThreeWayMatchResult] = None,
    db: Optional[Session] = None
) -> FraudDetectionResult:
    """
    Main Fraud & Duplicate Analysis Engine:
    Run all 7 fraud checks, score cumulative risk, and generate actionable governance alerts.
    """
    flags: List[str] = []
    details: dict = {}

    # Check 1: Duplicate Invoice Number in DB
    dup_num_flag = check_duplicate_invoice_number(db, invoice.document_number, invoice.vendor_name)
    if dup_num_flag:
        flags.append(dup_num_flag)
        details["duplicate_invoice_number"] = True

    # Check 2: Fuzzy Duplicate Billing (Same vendor, same amount on same PO)
    fuzzy_dup_flag = check_fuzzy_duplicate_billing(
        db=db,
        vendor_name=invoice.vendor_name,
        total_amount=invoice.total_amount,
        current_invoice_num=invoice.document_number,
        po_number=po.document_number
    )
    if fuzzy_dup_flag:
        flags.append(fuzzy_dup_flag)
        details["fuzzy_duplicate_billing"] = True

    # Check 3: Ghost Line Items (Missing in PO)
    ghost_flags = check_ghost_line_items(invoice, po)
    flags.extend(ghost_flags)
    if ghost_flags:
        details["ghost_items_count"] = len(ghost_flags)

    # Check 4: Price Surge / Inflation (>20%)
    surge_flags = check_price_surge_fraud(invoice, po)
    flags.extend(surge_flags)
    if surge_flags:
        details["price_surge_items_count"] = len(surge_flags)

    # Check 5: Phantom Delivery (Shortfall)
    phantom_flags = check_phantom_delivery(invoice, grn)
    flags.extend(phantom_flags)
    if phantom_flags:
        details["phantom_delivery_items_count"] = len(phantom_flags)

    # Check 6: Tax Integrity & Math
    tax_flags = check_tax_manipulation(invoice)
    flags.extend(tax_flags)
    if tax_flags:
        details["tax_anomalies"] = len(tax_flags)

    # Check 7: Vendor Identity Spoofing
    spoof_flag = check_vendor_name_spoofing(invoice.vendor_name, po.vendor_name)
    if spoof_flag:
        flags.append(spoof_flag)
        details["vendor_spoofing"] = True

    # ======================================================
    # Fraud Risk Scoring Algorithm (0 - 100)
    # ======================================================
    score = 0.0

    if dup_num_flag:
        score += 50.0  # Exact duplicate is massive risk
    if fuzzy_dup_flag:
        score += 35.0  # Identical amount from same vendor
    if spoof_flag:
        score += 40.0  # Vendor mismatch / impersonation
    if surge_flags:
        score += min(40.0, len(surge_flags) * 20.0)
    if ghost_flags:
        score += min(40.0, len(ghost_flags) * 25.0)
    if phantom_flags:
        score += min(30.0, len(phantom_flags) * 15.0)
    if tax_flags:
        score += 20.0

    # Cap score at 100.0
    fraud_score = min(100.0, score)

    # Determine Severity Level & Action
    is_fraud_suspected = len(flags) > 0
    if fraud_score >= 50.0 or dup_num_flag or spoof_flag:
        risk_level = "CRITICAL"
        action = "IMMEDIATE_REJECTION"
    elif fraud_score >= 30.0:
        risk_level = "HIGH"
        action = "HOLD_PAYMENT"
    elif fraud_score > 0.0:
        risk_level = "MEDIUM"
        action = "FLAG_FOR_AUDIT"
    else:
        risk_level = "LOW"
        action = "PROCEED"

    return FraudDetectionResult(
        is_fraud_suspected=is_fraud_suspected,
        fraud_risk_level=risk_level,
        fraud_score=fraud_score,
        flags=flags,
        recommended_action=action,
        details=details
    )
# Comment: Yeh function 7 checks ko combine karke transparent 0-100 score banata hai aur batata hai ki payment rokni hai ya audit me bhejni hai.
