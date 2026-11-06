# CacheFlow AI – Automated 3-Way Invoice Reconciliation Platform
### Problem Statement No. 49 | Agentic AI • Deterministic Matching • LangGraph • Fraud Shield

[![Python 3.11](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-StateGraph-FF6F00?style=for-the-badge&logo=langchain&logoColor=white)](https://langchain.com)
[![OCR](https://img.shields.io/badge/OCR-PyMuPDF%20%2B%20Tesseract-blue?style=for-the-badge)](https://pymupdf.readthedocs.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

---

## 📌 Project Overview & Presentation Context

**CacheFlow AI** is an intelligent, agentic financial reconciliation platform built specifically for enterprise Accounts Payable (AP) departments. As presented in **Problem Statement No. 49**, it automates the traditional, error-prone manual document verification across:

1. **Vendor Invoice**: The billing document submitted by the seller.
2. **Purchase Order (PO)**: The legally agreed items, quantities, and contracted rates.
3. **Goods Receipt Note (GRN)**: The warehouse delivery receipt confirming physical goods received.

### 🎯 Key Presentation Features Implemented
- ✅ **OCR & Document Extraction**: PyMuPDF for fast digital PDF parsing + Tesseract OCR for scanned images/invoices.
- ✅ **LangGraph Stateful Orchestration**: Multi-agent StateGraph with conditional routing and exception loops (`workflow.py`).
- ✅ **Deterministic 3-Way Matching**: Zero-hallucination mathematical verification of quantities, prices, taxes, and totals (`matcher.py`).
- ✅ **Duplicate & Fraud Detection Shield**: 7-tier security checking duplicate invoice numbers, double billing traps, ghost line items, price surges, and phantom deliveries (`fraud.py`).
- ✅ **AI Arbitration & Dispute Drafting**: Gemini 2.5 Flash / Pro generating explainable root-cause narratives and vendor-ready dispute emails (`agent.py`).
- ✅ **Executive Web Dashboard**: Dark-mode dashboard with side-by-side matching matrix, audit trail, vendor memory, and 1-click demo scenarios (`static/`).
- ✅ **Bilingual / Hinglish Comments**: Clean, well-documented code with intuitive Hinglish comments for easy learning, explanation, and interview presentation.

---

## 🏛️ System Architecture (LangGraph Multi-Agent Workflow)

```text
                               ┌─────────────────────────────────┐
                               │           INPUT DATA            │
                               │  - Supplier Invoice (PDF/Image) │
                               │  - Purchase Order (PDF/Image)   │
                               │  - Goods Receipt Note (GRN)     │
                               └────────────────┬────────────────┘
                                                │
                                                ▼
     ┌────────────────────────────────────────────────────────────────────────────────────────┐
     │                     NODE 1: EXTRACTION AGENT (PyMuPDF + Tesseract OCR)                 │
     │  - Fast selectable text parsing via PyMuPDF (fitz)                                     │
     │  - Scanned image and photo OCR via Tesseract Engine                                    │
     │  - Gemini 2.5 Flash structured parsing with 100% offline heuristic regex fallback     │
     └──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                                │
                                                ▼
     ┌────────────────────────────────────────────────────────────────────────────────────────┐
     │                     NODE 2: 3-WAY MATCHING AGENT (Deterministic Math)                  │
     │  - Vendor Legal Suffix Normalization ("Pvt Ltd" vs "Private Limited")                  │
     │  - Line Item Alignment: Invoiced Qty vs GRN Received Qty                              │
     │  - Unit Rate Comparison: Invoiced Price vs Agreed PO Price                            │
     │  - Subtotal, Tax (GST), and Total Amount Tolerance Check                               │
     └──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                                │
                                                ▼
     ┌────────────────────────────────────────────────────────────────────────────────────────┐
     │                     NODE 3: FRAUD & DUPLICATE DETECTION SHIELD                         │
     │  - Check 1: Duplicate Invoice Number in Database                                       │
     │  - Check 2: Fuzzy Duplicate Billing (Same Vendor, Same Amount on Same PO)              │
     │  - Check 3: Ghost Invoicing (Line items billed that were never in PO)                  │
     │  - Check 4: Price Inflation Gouging (>20% sudden rate surge)                           │
     │  - Check 5: Phantom Delivery (Shortfalls & unverified physical items)                  │
     │  - Check 6: Tax / GST Rate Manipulation & Math Integrity                               │
     │  - Check 7: Vendor Name Spoofing & Phishing Alert                                      │
     └──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                                │
                           [ Conditional Router: Exceptions or Fraud? ]
                                            /       \
                        NO EXCEPTIONS      /         \    EXCEPTIONS OR FRAUD
                        & ZERO FRAUD      /           \   DETECTED
                                         ▼             ▼
                 ┌──────────────────────────┐   ┌─────────────────────────────────────────────┐
                 │  NODE 6: AUTO-COMPLETION │   │    NODE 4: AI ARBITRATION AGENT             │
                 │  - 100% Verified Match   │   │  - Google Gemini 2.5 Pro Reasoning          │
                 │  - Score: 100%, Low Risk │   │  - Discrepancy & Fraud Impact Analysis      │
                 │  - Fast-Track Payment    │   │  - Auto-Drafts Professional Dispute Email   │
                 └──────────────┬───────────┘   └──────────────────────┬──────────────────────┘
                                │                                      │
                                │                                      ▼
                                │               ┌─────────────────────────────────────────────┐
                                │               │    NODE 5: HUMAN REVIEW & RESOLUTION        │
                                │               │  - Finance Specialist Review Package        │
                                │               │  - Approve, Reject, or Escalate with Notes  │
                                └───────┬───────┴──────────────────────┬──────────────────────┘
                                        │                              │
                                        ▼                              ▼
                               ┌────────────────────────────────────────────────┐
                               │           OUTPUT & GOVERNANCE LAYER            │
                               │  - SQLite Audit Trail (`cacheflow.db`)         │
                               │  - Indian Standard Time (IST) Timestamps       │
                               │  - Interactive Side-by-Side Matrix UI          │
                               │  - One-Click Structured CSV Export             │
                               └────────────────────────────────────────────────┘
```

---

## 📂 Project Structure

```text
Automated Invoice Recognition/
│
├── workflow.py            # LangGraph StateGraph pipeline (Extraction -> Matching -> Fraud -> Arbitration)
├── fraud.py               # 7-tier Duplicate & Fraud Detection Engine (Scoring 0-100 & Risk classification)
├── extractor.py           # Node 1: Document OCR (PyMuPDF + Tesseract) & Structured JSON extraction
├── matcher.py             # Node 2: Deterministic 3-Way Matching engine (Zero-hallucination math)
├── agent.py               # Node 4: AI Arbitration Agent (Gemini Reasoning & Dispute email generator)
├── models.py              # Pydantic Schemas + SQLAlchemy SQLite tables (IST timestamps & audit trails)
├── app.py                 # FastAPI Application Gateway & REST endpoints
│
├── static/                # Interactive Frontend Web Dashboard
│   ├── index.html         # Main dashboard layout with KPI cards, Fraud Shield & LangGraph visualizer
│   ├── app.js             # Client controller, tab switching, and LangGraph animation runner
│   └── styles.css         # Dark theme aesthetic styles
│
├── sample_data/           # Sample Invoices, POs, and GRNs for all 5 presentation scenarios
│   ├── create_sample_docs.py # Generator for clean match, price mismatch, shortage, and fraud files
│   └── *.txt / *.pdf      # Ready-to-use sample test documents
│
├── test_flow.py           # Pytest automated test suite (7 comprehensive test cases)
├── requirements.txt       # Production dependencies
└── README.md
```

---

## ⚡ Key Highlights for Viva / Presentation (Hinglish Guide)

If you are explaining this project in an interview or project evaluation, here is the structured flow:

### 1. Presentation Problem Statement
> *"Current AP (Accounts Payable) workflows manually cross-check bills, leading to slow cycles, compliance risk, and duplicate/fraud vulnerability."*

### 2. Node 1: OCR & Extraction (`extractor.py`)
> **Hinglish:** *"PyMuPDF use karke digital PDFs se text instantly extract hota hai. Agar document scanned photo ya physical paper ki image ho, toh Tesseract OCR run hota hai. Text structuring ke liye Gemini 2.5 Flash use hota hai, aur agar internet na ho toh regex-based deterministic heuristic engine 100% offline kaam karta hai."*

### 3. Node 2: Deterministic 3-Way Matching (`matcher.py`)
> **Hinglish:** *"Mathematical calculations ke liye hum LLM use nahi karte taaki hallucination na ho. Quantity verify hoti hai Invoice vs GRN, price verify hoti hai Invoice vs PO, aur vendor alias normalizer 'Pvt Ltd' aur 'Private Limited' ko smoothly match kar leta hai."*

### 4. Node 3: Fraud & Duplicate Shield (`fraud.py`)
> **Hinglish:** *"Slide 1 aur Slide 5 me mention duplicate billing aur fraud vulnerability ko solve karne ke liye humne 7-Tier Fraud Shield banaya hai:
> 1. Exact Duplicate Invoice Check (Database me same invoice pehle se toh nahi hai)
> 2. Fuzzy Duplicate Billing (Same PO aur same vendor par alag invoice number se double bill mangna)
> 3. Ghost Invoicing (Aise line items jo PO me the hi nahi)
> 4. Severe Price Surge Anomaly (>20% price hike)
> 5. Phantom Delivery (GRN me saman deliver nahi hua par bill aa gaya)
> 6. Tax / GST Rate Tampering
> 7. Vendor Spoofing / Typosquatting Phishing."*

### 5. Orchestration: LangGraph Stateful Workflow (`workflow.py`)
> **Hinglish:** *"Slide 4 ke architecture ke hisaab se humne LangGraph StateGraph implement kiya hai. LangGraph ek stateful graph banata hai jisme State sequential nodes me pass hoti hai aur conditional router exceptions aur fraud score ke base par decide karta hai ki clean auto-approval me jana hai ya arbitration agent aur human-in-the-loop review me."*

### 6. Node 4: AI Arbitration Agent (`agent.py`)
> **Hinglish:** *"Jab koi discrepancy ya fraud alert milta hai, Gemini AI source documents ke exact line items aur variance amounts quote karke ek professional vendor dispute notification draft kar deta hai."*

---

## 🧪 1-Click Demo Scenarios (Available on Web UI)

You can click **"1-Click Demo Scenarios"** on the dashboard to test all scenarios instantly:

| Scenario | Scenario Name | Test Data | What System Demonstrates |
|---|---|---|---|
| **1** | **Clean 3-Way Match** | 100 Dell Laptops @ ₹50,000 | Match Score 100%, Status: MATCHED, Auto-approved, Zero Fraud Risk |
| **2** | **Price Mismatch** | IPS Monitors: Billed ₹550 vs PO ₹500 | Detects +₹5,000 price variance, generates vendor dispute letter |
| **3** | **Quantity Shortage** | Server RAM: Invoiced 100 vs GRN 90 | Flags 10-unit delivery shortfall, calculates ₹20,000 held amount |
| **4** | **Vendor Alias Variation** | "CloudNet Infra Pvt. Ltd." vs "Private Limited" | Resolves formatting differences via Vendor Memory without false rejection |
| **5** | **Duplicate & Fraud Attempt** | FW-Appliance +60% surge + Ghost consulting item | Triggers Fraud Shield, flags `CRITICAL` risk, halts payment |

---

## 🚀 How to Run Locally

### 1. Prerequisites
- Python 3.10 or 3.11 installed
- (Optional) Google Gemini API Key for LLM mode. If not provided, system seamlessly runs in **100% Offline Safe Heuristic Mode**.

### 2. Setup Virtual Environment & Install Dependencies
```bash
# Clone the repository
git clone https://github.com/vedanshdevpura14/Automated-Invoice-Recognition.git
cd Automated-Invoice-Recognition

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run Automated Tests
```bash
python -m pytest -v
```
*(All 7 tests will pass: vendor alias, clean match, price mismatch, heuristic parser, fraud shield, LangGraph StateGraph, and API integration).*

### 4. Start the Application Server
```bash
python app.py
```
Open your browser and navigate to:
- **Interactive Web Dashboard**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🛡️ Security, Governance & Telemetry
- **Pydantic v2 Contract Validation**: Input sanitization and type enforcement.
- **Indian Standard Time (IST)**: All audit records and human reviews stamped with `+05:30` IST precision.
- **Immutable SQLite Audit Trail**: Complete lineage of document upload, OCR extraction, matching rules, fraud flags, and reviewer approvals.
- **CSV & Export Compatibility**: Every audited invoice exports directly to structured CSV for ERP accounting systems.
