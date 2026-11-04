import re
import json
from typing import Optional
from app.core.config import settings
from app.schemas.schemas import (
    ThreeWayMatchResult,
    DocumentDataSchema,
    ArbitrationResponse
)

ARBITRATION_PROMPT = """
You are the Accounts Payable AI Arbitration Agent for CacheFlow.
Your task is to analyze discrepancies identified during 3-way reconciliation (Invoice vs PO vs GRN), assess financial risk, formulate an objective root-cause explanation grounded strictly in the source documents, and draft a formal resolution letter/email to the vendor.

Rules:
1. Do NOT hallucinate or assume unverified price changes or verbal approvals.
2. Ground all statements in the actual numbers and document IDs provided.
3. Determine risk severity: "LOW", "MEDIUM", "HIGH", or "CRITICAL".
4. Provide a confidence score between 0.0 and 100.0.
5. Recommend an action: "AUTO_APPROVE", "HUMAN_INVESTIGATION", "ESCALATE_TO_VENDOR", or "REJECT_INVOICE".
6. Draft a clear, polite, and actionable vendor dispute email citing exact line items, PO numbers, and amounts.
7. Return strictly valid JSON with this schema:
{
    "risk_severity": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
    "confidence_score": 95.0,
    "summary": "Clear executive summary of findings",
    "recommended_action": "ESCALATE_TO_VENDOR",
    "dispute_email_draft": "Formal email text with Subject and Body",
    "findings": [
        "Finding 1 citing exact fields",
        "Finding 2"
    ]
}
"""

def arbitrate_with_gemini(
    match_result: ThreeWayMatchResult,
    invoice: DocumentDataSchema,
    po: DocumentDataSchema,
    grn: DocumentDataSchema
) -> Optional[ArbitrationResponse]:
    """Uses Google Gemini Pro/Flash to generate explainable arbitration rationale."""
    if not settings.GEMINI_API_KEY or len(settings.GEMINI_API_KEY.strip()) < 8:
        return None

    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_MODEL_ARBITRATION)

        context_data = {
            "invoice": invoice.model_dump(),
            "po": po.model_dump(),
            "grn": grn.model_dump(),
            "match_result": match_result.model_dump()
        }

        user_content = f"{ARBITRATION_PROMPT}\n\nRECONCILIATION AUDIT DATA:\n{json.dumps(context_data, indent=2)}"
        response = model.generate_content(user_content)
        text = response.text.strip()

        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        parsed = json.loads(text.strip())
        return ArbitrationResponse.model_validate(parsed)
    except Exception as e:
        print(f"[Arbitration Notice] Falling back to deterministic agent: {e}")
        return None


def arbitrate_deterministic(
    match_result: ThreeWayMatchResult,
    invoice: DocumentDataSchema,
    po: DocumentDataSchema,
    grn: DocumentDataSchema
) -> ArbitrationResponse:
    """
    Deterministic Financial Reasoner:
    Grounded, zero-hallucination analysis and vendor email drafting.
    """
    if match_result.status == "MATCHED":
        return ArbitrationResponse(
            risk_severity="LOW",
            confidence_score=99.0,
            summary=f"Three-way reconciliation succeeded. All quantities, unit rates, and totals on Invoice #{invoice.document_number} match PO #{po.document_number} and Goods Receipt #{grn.document_number}.",
            recommended_action="AUTO_APPROVE",
            dispute_email_draft="No dispute required. Invoice verified for payment authorization.",
            findings=["Invoice line items match PO unit prices.", "Warehouse GRN confirms full receipt of invoiced goods.", "Tax calculation and totals align within tolerance."]
        )

    # Discrepancies present
    findings = []
    risk = "MEDIUM"
    action = "ESCALATE_TO_VENDOR"
    
    if match_result.variance_total > 50000:
        risk = "CRITICAL"
        action = "REJECT_INVOICE"
    elif match_result.variance_total > 10000:
        risk = "HIGH"
        action = "HUMAN_INVESTIGATION"

    for var in match_result.variances:
        findings.append(var.message)

    # Generate professional vendor communication citing exact documents
    variance_bullet_points = "\n".join([f"  - {f}" for f in findings])
    email_draft = f"""Subject: Discrepancy Notification for Invoice #{invoice.document_number} (Ref: PO #{po.document_number})

Dear {invoice.vendor_name} Accounts Receivable Team,

We have completed the three-way reconciliation for your Invoice #{invoice.document_number} dated {invoice.document_date or 'recently'} against our Purchase Order #{po.document_number} and Goods Receipt Note #{grn.document_number}.

During automated verification, our audit system identified the following variance(s):
{variance_bullet_points}

Net Discrepancy Impact: {invoice.currency} {match_result.variance_total:,.2f}

Action Requested:
1. Please review your billed amounts and delivery logs against the confirmed receipt records.
2. If this was a clerical error, kindly provide a revised credit note or updated invoice reflecting the received quantities and agreed purchase order pricing.
3. If an authorized change order exists, please furnish the approved documentation referencing PO #{po.document_number}.

To prevent payment holds, kindly reply to this reconciliation notice within 3 business days.

Sincerely,
Accounts Payable Department
CacheFlow Financial Systems"""

    return ArbitrationResponse(
        risk_severity=risk,
        confidence_score=94.5,
        summary=f"Found {len(match_result.variances)} reconciliation variance(s) totaling {invoice.currency} {match_result.variance_total:,.2f}. Discrepancies primarily stem from {', '.join([v.field for v in match_result.variances])}.",
        recommended_action=action,
        dispute_email_draft=email_draft,
        findings=findings
    )


def arbitrate_exceptions(
    match_result: ThreeWayMatchResult,
    invoice: DocumentDataSchema,
    po: DocumentDataSchema,
    grn: DocumentDataSchema
) -> ArbitrationResponse:
    """Unified Arbitration Agent entry point with graceful fallback."""
    ai_result = arbitrate_with_gemini(match_result, invoice, po, grn)
    if ai_result is not None:
        return ai_result
    return arbitrate_deterministic(match_result, invoice, po, grn)
