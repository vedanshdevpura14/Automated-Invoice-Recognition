import os
import json
from typing import TypedDict, Optional, List, Dict, Any
from langgraph.graph import StateGraph, START, END

from models import (
    DocumentDataSchema,
    ThreeWayMatchResult,
    ArbitrationResponse,
    FraudDetectionResult
)
from extractor import extract_text_from_file, extract_document
from matcher import perform_three_way_reconciliation
from fraud import evaluate_fraud_and_duplicates
from agent import arbitrate_exceptions

# ==========================================================
# LANGGRAPH ORCHESTRATION ENGINE
# ==========================================================
# Presentation Architecture Reference:
# "3. Orchestration Engine (LangGraph): Stateful Workflow with Conditional Routing & Exception Loops"
#
# Hinglish Explanation:
# LangGraph ek stateful graph orchestration framework hai jo multi-agent finance workflow ko control karta hai:
# - Node 1: EXTRACTION AGENT (OCR + PyMuPDF + Structured Parsing)
# - Node 2: MATCHING AGENT (Deterministic 3-Way Match: Invoice vs PO vs GRN)
# - Node 3: FRAUD & DUPLICATE SHIELD (Duplicate check, Price spike, Ghost line items)
# - Conditional Router: Agar koi exception ya fraud nahi hai toh direct AUTO_APPROVE par bhejo.
#                      Agar exception ya fraud mila toh ARBITRATION AGENT aur HUMAN REVIEW par route karo.
# - Node 4: ARBITRATION AGENT (LLM / Reasoner se root-cause report aur vendor email draft karna)
# - Node 5: HUMAN REVIEW NODE (Finance specialist ke review ke liye package taiyyar karna)
# ==========================================================


class ReconciliationGraphState(TypedDict):
    """
    LangGraph Workflow State:
    Har node is state dictionary ko read karta hai aur apne output ke sath update karta hai.
    """
    session_id: str
    invoice_file_path: str
    po_file_path: str
    grn_file_path: str

    # Node 1: Extraction Outputs
    invoice_raw_text: str
    po_raw_text: str
    grn_raw_text: str
    invoice_data: Optional[Dict[str, Any]]
    po_data: Optional[Dict[str, Any]]
    grn_data: Optional[Dict[str, Any]]

    # Node 2: Matching Outputs
    match_result: Optional[Dict[str, Any]]
    has_exceptions: bool
    match_score: float

    # Node 3: Fraud Shield Outputs
    fraud_result: Optional[Dict[str, Any]]
    is_fraud_suspected: bool
    fraud_risk_level: str
    fraud_flags: List[str]

    # Node 4: Arbitration Outputs
    arbitration_result: Optional[Dict[str, Any]]

    # Telemetry & Audit
    execution_path: List[str]
    current_node: str
    workflow_status: str
    error_message: Optional[str]


# ==========================================================
# 1. Node 1: EXTRACTION AGENT
# ==========================================================
def extraction_node(state: ReconciliationGraphState) -> Dict[str, Any]:
    """
    Node 1: Documents se OCR aur selectable text nikalta hai,
    aur Gemini / Heuristic engine se structured JSON me convert karta hai.
    """
    execution_path = list(state.get("execution_path", []))
    execution_path.append("Node 1: Extraction Agent")

    try:
        inv_text = extract_text_from_file(state["invoice_file_path"])
        po_text = extract_text_from_file(state["po_file_path"])
        grn_text = extract_text_from_file(state["grn_file_path"])

        invoice_doc = extract_document(inv_text, doc_hint="invoice")
        po_doc = extract_document(po_text, doc_hint="purchase_order")
        grn_doc = extract_document(grn_text, doc_hint="grn")

        return {
            "invoice_raw_text": inv_text,
            "po_raw_text": po_text,
            "grn_raw_text": grn_text,
            "invoice_data": invoice_doc.model_dump(),
            "po_data": po_doc.model_dump(),
            "grn_data": grn_doc.model_dump(),
            "execution_path": execution_path,
            "current_node": "extraction_node",
            "workflow_status": "EXTRACTION_SUCCESS"
        }
    except Exception as e:
        raise RuntimeError(f"Document extraction node failed: {str(e)}") from e
# Comment: Node 1 PyMuPDF aur Tesseract OCR use karke raw unstructured PDF se verified JSON structure banata hai.


# ==========================================================
# 2. Node 2: MATCHING AGENT (Deterministic 3-Way Engine)
# ==========================================================
def matching_node(state: ReconciliationGraphState) -> Dict[str, Any]:
    """
    Node 2: Invoice vs Purchase Order vs Goods Receipt Note ko
    deterministic financial logic aur Pandas dataframe logic se 3-way reconcile karta hai.
    """
    execution_path = list(state.get("execution_path", []))
    execution_path.append("Node 2: 3-Way Matching Agent")

    invoice_doc = DocumentDataSchema.model_validate(state["invoice_data"])
    po_doc = DocumentDataSchema.model_validate(state["po_data"])
    grn_doc = DocumentDataSchema.model_validate(state["grn_data"])

    match_res = perform_three_way_reconciliation(invoice_doc, po_doc, grn_doc)
    has_exceptions = (match_res.status != "MATCHED")

    return {
        "match_result": match_res.model_dump(),
        "has_exceptions": has_exceptions,
        "match_score": match_res.match_score,
        "execution_path": execution_path,
        "current_node": "matching_node",
        "workflow_status": "MATCHING_EVALUATED"
    }
# Comment: Node 2 unit prices aur delivered quantities compare karta hai bina kisi LLM hallucination ke.


# ==========================================================
# 3. Node 3: FRAUD & DUPLICATE DETECTION SHIELD
# ==========================================================
def fraud_detection_node(state: ReconciliationGraphState) -> Dict[str, Any]:
    """
    Node 3: Duplicate invoice numbers, duplicate billing amounts, ghost line items,
    aur price inflation anomalies detect karta hai.
    """
    execution_path = list(state.get("execution_path", []))
    execution_path.append("Node 3: Fraud & Duplicate Shield")

    invoice_doc = DocumentDataSchema.model_validate(state["invoice_data"])
    po_doc = DocumentDataSchema.model_validate(state["po_data"])
    grn_doc = DocumentDataSchema.model_validate(state["grn_data"])
    match_res = ThreeWayMatchResult.model_validate(state["match_result"])

    fraud_res = evaluate_fraud_and_duplicates(
        invoice=invoice_doc,
        po=po_doc,
        grn=grn_doc,
        match_result=match_res
    )

    return {
        "fraud_result": fraud_res.model_dump(),
        "is_fraud_suspected": fraud_res.is_fraud_suspected,
        "fraud_risk_level": fraud_res.fraud_risk_level,
        "fraud_flags": fraud_res.flags,
        "execution_path": execution_path,
        "current_node": "fraud_detection_node",
        "workflow_status": "FRAUD_CHECK_COMPLETED"
    }
# Comment: Node 3 double billing, duplicate documents aur unauthorized charges ko screen karta hai.


# ==========================================================
# 4. Conditional Edge / Router Function (Decision Gate)
# ==========================================================
def route_after_evaluation(state: ReconciliationGraphState) -> str:
    """
    LangGraph Conditional Router:
    Decide karta hai ki invoice clean match ho gaya ya human/arbitration intervention chahiye.
    """
    has_exceptions = state.get("has_exceptions", False)
    is_fraud = state.get("is_fraud_suspected", False)

    # Agar koi exception nahi hai aur koi fraud risk nahi hai -> Clean Auto-Approval
    if not has_exceptions and not is_fraud:
        return "completion_node"

    # Agar mismatch ya fraud alert mila -> AI Arbitration aur Dispute handling
    return "arbitration_node"
# Comment: Slide me jo diamond decision block hai ("Exceptions Found?"), yeh function wahi exact routing implement karta hai.


# ==========================================================
# 5. Node 4: ARBITRATION AGENT (LLM Reasoning & Resolution)
# ==========================================================
def arbitration_node(state: ReconciliationGraphState) -> Dict[str, Any]:
    """
    Node 4: Gemini LLM ya deterministic reasoner use karke
    discrepancies aur fraud alerts ka root-cause analyze karta hai
    aur vendor dispute email draft karta hai.
    """
    execution_path = list(state.get("execution_path", []))
    execution_path.append("Node 4: AI Arbitration Agent")

    invoice_doc = DocumentDataSchema.model_validate(state["invoice_data"])
    po_doc = DocumentDataSchema.model_validate(state["po_data"])
    grn_doc = DocumentDataSchema.model_validate(state["grn_data"])
    match_res = ThreeWayMatchResult.model_validate(state["match_result"])

    arbitration_res = arbitrate_exceptions(match_res, invoice_doc, po_doc, grn_doc)

    # Agar fraud flags bhi detect huye hain toh arbitration summary me merge karo
    fraud_flags = state.get("fraud_flags", [])
    if fraud_flags:
        updated_findings = list(arbitration_res.findings)
        for flag in fraud_flags:
            if flag not in updated_findings:
                updated_findings.append(f"[FRAUD SHIELD ALERT] {flag}")
        
        # Risk severity escalate karo agar fraud alert hai
        fraud_risk = state.get("fraud_risk_level", "LOW")
        effective_risk = "CRITICAL" if fraud_risk == "CRITICAL" else ("HIGH" if fraud_risk == "HIGH" else arbitration_res.risk_severity)
        
        arbitration_res = ArbitrationResponse(
            risk_severity=effective_risk,
            confidence_score=max(arbitration_res.confidence_score, 96.0),
            summary=f"Reconciliation exceptions and security flags identified. {len(fraud_flags)} fraud/duplicate check(s) triggered. {arbitration_res.summary}",
            recommended_action="REJECT_INVOICE" if effective_risk == "CRITICAL" else "HUMAN_INVESTIGATION",
            dispute_email_draft=arbitration_res.dispute_email_draft,
            findings=updated_findings
        )

    return {
        "arbitration_result": arbitration_res.model_dump(),
        "execution_path": execution_path,
        "current_node": "arbitration_node",
        "workflow_status": "ARBITRATION_COMPLETED"
    }
# Comment: Node 4 vendor ko bhejne ke liye dispute letter draft karta hai aur audit report me exact line item quote karta hai.


# ==========================================================
# 6. Node 5: HUMAN REVIEW & RESOLUTION AGENT
# ==========================================================
def human_review_node(state: ReconciliationGraphState) -> Dict[str, Any]:
    """
    Node 5: Human-in-the-Loop review package taiyyar karta hai
    taaki finance specialist single click me approve/reject/escalate kar sake.
    """
    execution_path = list(state.get("execution_path", []))
    execution_path.append("Node 5: Human Review Package Ready")

    return {
        "execution_path": execution_path,
        "current_node": "human_review_node",
        "workflow_status": "AWAITING_HUMAN_REVIEW"
    }
# Comment: Node 5 human-in-the-loop compliance ensure karta hai taaki high-value discrepancies bina human sign-off ke pay na ho jayein.


# ==========================================================
# 7. Node 6: AUTO-COMPLETION NODE (Clean Match Path)
# ==========================================================
def completion_node(state: ReconciliationGraphState) -> Dict[str, Any]:
    """Clean 3-way match hone par direct successful completion mark karta hai."""
    execution_path = list(state.get("execution_path", []))
    execution_path.append("Node 6: Auto-Reconciliation Completed")

    # Clean match ke liye positive arbitration banate hain
    clean_arbitration = ArbitrationResponse(
        risk_severity="LOW",
        confidence_score=99.5,
        summary="Automated 3-way reconciliation matched 100%. Quantities, unit rates, tax calculations, and vendor identity verified with zero variance.",
        recommended_action="AUTO_APPROVE",
        dispute_email_draft="No dispute required. Three-way match verified for automated payment authorization.",
        findings=["Zero financial variance", "No duplicate billing detected", "Warehouse GRN fully reconciled"]
    )

    return {
        "arbitration_result": clean_arbitration.model_dump(),
        "execution_path": execution_path,
        "current_node": "completion_node",
        "workflow_status": "RECONCILIATION_COMPLETED"
    }
# Comment: Agar koi dikkat nahi hai toh yeh node fast-track approval enable kar deta hai.


# ==========================================================
# 8. StateGraph Assembly & Compilation
# ==========================================================
def build_reconciliation_graph():
    """
    LangGraph Workflow ko construct aur compile karta hai:
    START -> Node 1 (Extraction) -> Node 2 (Matching) -> Node 3 (Fraud Shield)
          -> Conditional Router:
             - [Clean] -> Node 6 (Completion) -> END
             - [Exceptions/Fraud] -> Node 4 (Arbitration) -> Node 5 (Human Review) -> END
    """
    workflow = StateGraph(ReconciliationGraphState)

    # Nodes add karo
    workflow.add_node("extraction_node", extraction_node)
    workflow.add_node("matching_node", matching_node)
    workflow.add_node("fraud_detection_node", fraud_detection_node)
    workflow.add_node("arbitration_node", arbitration_node)
    workflow.add_node("human_review_node", human_review_node)
    workflow.add_node("completion_node", completion_node)

    # Fixed Sequential Edges
    workflow.add_edge(START, "extraction_node")
    workflow.add_edge("extraction_node", "matching_node")
    workflow.add_edge("matching_node", "fraud_detection_node")

    # Conditional Routing Edge
    workflow.add_conditional_edges(
        "fraud_detection_node",
        route_after_evaluation,
        {
            "completion_node": "completion_node",
            "arbitration_node": "arbitration_node"
        }
    )

    # Terminal Edges
    workflow.add_edge("completion_node", END)
    workflow.add_edge("arbitration_node", "human_review_node")
    workflow.add_edge("human_review_node", END)

    # Graph ko compile karo
    return workflow.compile()

# Singleton compiled LangGraph instance
compiled_graph = build_reconciliation_graph()
# Comment: Graph compile hone ke baad reusable ban jata hai aur har nayi request ko fast execute karta hai.


# ==========================================================
# 9. Main Workflow Runner
# ==========================================================
def run_reconciliation_workflow(
    session_id: str,
    invoice_file_path: str,
    po_file_path: str,
    grn_file_path: str
) -> Dict[str, Any]:
    """
    Single unified entrypoint jo LangGraph multi-agent pipeline ko run karta hai:
    Input files leta hai, graph execute karta hai, aur structured result return karta hai.
    """
    initial_state: ReconciliationGraphState = {
        "session_id": session_id,
        "invoice_file_path": invoice_file_path,
        "po_file_path": po_file_path,
        "grn_file_path": grn_file_path,
        "invoice_raw_text": "",
        "po_raw_text": "",
        "grn_raw_text": "",
        "invoice_data": None,
        "po_data": None,
        "grn_data": None,
        "match_result": None,
        "has_exceptions": False,
        "match_score": 0.0,
        "fraud_result": None,
        "is_fraud_suspected": False,
        "fraud_risk_level": "LOW",
        "fraud_flags": [],
        "arbitration_result": None,
        "execution_path": ["START"],
        "current_node": "START",
        "workflow_status": "INITIALIZED",
        "error_message": None
    }

    # Execute LangGraph compiled workflow
    final_state = compiled_graph.invoke(initial_state)
    return final_state
# Comment: Yeh runner function FastAPI endpoints me call hota hai aur poore LangGraph flow ki telemetry return karta hai.
