# CacheFlow AI – Automated 3-Way Invoice Reconciliation Platform

> **An Agentic Financial Process Automation & AP Auditing System**  
> Built with **FastAPI**, **Google Gemini**, **PyMuPDF**, **Pandas**, **SQLAlchemy**, and **Tailwind CSS**.  
> Design Principle: **"Rules first for numbers, LLM for exceptions, humans decide."**

---

## 📌 Executive Summary

In Accounts Payable (AP), finance departments manually verify hundreds of vendor bills daily by cross-referencing three disparate documents:
1. **Vendor Invoice**: What the supplier claims is owed.
2. **Purchase Order (PO)**: What the company originally agreed to buy and at what price.
3. **Goods Receipt Note (GRN)**: What warehouse personnel physically received and verified.

Manual comparison across these documents is slow, error-prone, and causes financial leakage (over-billing, phantom line items, missed quantity shortfalls).

**CacheFlow AI** transforms this manual burden into an automated, auditable, agentic reconciliation workflow that:
- Ingests invoices, POs, and GRNs (PDFs, scans, text).
- Extracts structured financial fields with **Node 1: Extraction Agent**.
- Applies zero-hallucination deterministic business logic with **Node 2: Matching Agent**.
- Investigates discrepancies, assesses risk, and auto-drafts vendor dispute emails with **Node 3: Arbitration Agent**.
- Provides a clean, modern interactive web dashboard with side-by-side matrices, 1-click test scenarios, CSV export, and human-in-the-loop sign-off.

---

## 🏛️ System Architecture

```text
       [ Invoice (PDF/Scan) ]      [ Purchase Order (PO) ]      [ Goods Receipt (GRN) ]
                   \                         |                         /
                    ▼                        ▼                        ▼
     ┌────────────────────────────────────────────────────────────────────────┐
     │                     NODE 1: EXTRACTION AGENT                           │
     │  - Fast Digital PDF Parsing via PyMuPDF (fitz)                         │
     │  - LLM Structuring with Gemini 1.5/2.5 Flash                           │
     │  - Deterministic Regex/Heuristic Fallback Engine (100% Offline Safe)  │
     └───────────────────────────────────┬────────────────────────────────────┘
                                         ▼
     ┌────────────────────────────────────────────────────────────────────────┐
     │                      NODE 2: MATCHING AGENT                            │
     │  - Vendor Normalization & Alias Matching ("Pvt Ltd" vs "Private Ltd")  │
     │  - Quantity Verification: Invoiced Qty vs GRN Delivered Qty           │
     │  - Unit Rate Verification: Invoiced Unit Price vs Agreed PO Price      │
     │  - Subtotal, Tax & Grand Total Checks with Configurable Tolerances     │
     └───────────────────────────────────┬────────────────────────────────────┘
                                         │
                         [ Exceptions / Variances? ]
                                   /          \
                           NO     /            \  YES
                                 ▼              ▼
           ┌───────────────────────┐   ┌──────────────────────────────────────┐
           │     AUTO-VERIFIED     │   │      NODE 3: ARBITRATION AGENT       │
           │  100% Clean Match     │   │  - Root-Cause Discrepancy Rationale  │
           │  Score: 100%          │   │  - Risk Severity (Low/Med/High/Crit) │
           │  Fast-Track Approval  │   │  - Confidence Scoring                │
           └───────────┬───────────┘   │  - AI-Drafted Vendor Dispute Email   │
                       │               └──────────────────┬───────────────────┘
                       │                                  │
                       └─────────────────┬────────────────┘
                                         ▼
     ┌────────────────────────────────────────────────────────────────────────┐
     │                    HUMAN-IN-THE-LOOP & GOVERNANCE                      │
     │  - Side-by-Side 3-Way Inspection Matrix                                │
     │  - Reviewer Action: Approve / Reject / Escalate with Audit Notes       │
     │  - Immutable SQLite Audit Trail & Vendor Memory Persistence            │
     └───────────────────────────────────┬────────────────────────────────────┘
                                         ▼
                            [ Web Dashboard & CSV Export ]
```

---

## ⚡ Key Highlights (Why It Stands Out)

| Feature | CacheFlow Approach | Why It Matters |
| :--- | :--- | :--- |
| **Matching Strategy** | **Deterministic Rules First** | Financial calculations must never be left to LLM guesswork. Exact checks eliminate mathematical hallucinations. |
| **Exception Handling** | **AI Arbitration Agent** | LLMs shine at contextual reasoning: explaining *why* a discrepancy occurred and drafting formal dispute notices. |
| **Tolerance Rules** | **Built-in Currency Tolerances** | Minor ₹0.50 rounding or penny differences do not generate false-alarm exceptions. |
| **Vendor Memory** | **Alias & Performance Tracking** | Recognizes vendor corporate variations (e.g., `ABC Tech Ltd` vs `ABC Technologies`) without false rejections. |
| **Reliability** | **Graceful Dual-Mode Fallback** | Runs 100% out of the box even without an API key or internet connection using smart heuristic extractors. |
| **Single-Developer Simplicity** | **Zero-Node-Modules Dashboard** | Clean FastAPI web server serving modern Tailwind CSS UI with 0 npm build hassles. |

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Python 3.10+ (Python 3.11 recommended)
- Git

### 2. Setup Virtual Environment
```bash
# Clone the repository (or navigate into the directory)
cd "Automatic Character Recognition"

# Create virtual environment
py -3.11 -m venv venv

# Activate on Windows:
.\venv\Scripts\Activate.ps1
# Or on Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Variables (Optional)
Copy `.env.example` to `.env`:
```env
PROJECT_NAME="CacheFlow AI - Automated Invoice Reconciliation"
DATABASE_URL="sqlite:///./cacheflow.db"
UPLOAD_DIR="uploads"

# Optional: Add your Gemini API Key for LLM extraction & arbitration
GEMINI_API_KEY="your_gemini_api_key_here"
```
*(Note: If no API key is provided, CacheFlow automatically runs in deterministic offline mode with zero errors!)*

### 4. Launch the Application
```bash
python run.py
```

- **Interactive Web Dashboard**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive OpenAPI / Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 🧪 Testing & Verification

Run the test suite:
```bash
pytest -v
```

All 9 test suites validate:
1. `test_vendor_name_normalization`: Resolves legal name variations cleanly.
2. `test_clean_3way_match`: Validates 100% score for compliant invoices.
3. `test_price_mismatch_scenario`: Catches unit rate overcharges (e.g., ₹550 vs agreed ₹500).
4. `test_quantity_shortage_scenario`: Catches warehouse delivery shortfalls (e.g., 90 received vs 100 invoiced).
5. `test_api_health`, `test_dashboard_stats`, `test_human_review_workflow`.

---

## 📁 Project Structure

```text
├── app/
│   ├── api/
│   │   └── routes.py             # REST API routes (reconcile, review, stats, export, demo)
│   ├── core/
│   │   ├── config.py             # Application settings & financial tolerances
│   │   └── database.py           # SQLite connection & session management
│   ├── models/
│   │   └── db_models.py          # SQLAlchemy tables (reconciliations, line_items, audit_logs)
│   ├── schemas/
│   │   └── schemas.py            # Pydantic v2 validation models
│   ├── services/
│   │   ├── ocr_service.py        # PyMuPDF digital PDF text extraction
│   │   ├── extraction_service.py # Node 1: Extraction Agent (Gemini + regex fallback)
│   │   ├── matching_engine.py    # Node 2: Deterministic 3-Way Financial Matcher
│   │   ├── arbitration_agent.py  # Node 3: AI Arbitration Agent & dispute writer
│   │   └── audit_service.py      # Audit logging & vendor memory
│   ├── static/
│   │   ├── index.html            # Single-page executive AP dashboard (Tailwind, Lucide)
│   │   ├── app.js                # Reactive client controller
│   │   └── styles.css            # Dark mode styling & UI enhancements
│   └── main.py                   # FastAPI application factory
├── sample_data/                  # Ready-to-use sample PDFs and TXT files
├── tests/                        # Pytest automated test suite
├── run.py                        # Single-command server starter
├── Dockerfile                    # Containerization specification
├── docker-compose.yml            # Docker Compose orchestration
├── requirements.txt              # Production dependencies
└── README.md                     # Complete project documentation
```

---

## 💼 Sole Developer Interview Preparation Cheat Sheet

When presenting this project in an interview or project review, use these battle-tested explanations:

### 1. "Walk me through what you built."
> "I designed and built **CacheFlow**, an end-to-end automated 3-way invoice reconciliation platform. Accounts payable teams manually cross-check vendor invoices against purchase orders and warehouse goods receipts. I automated this with a three-agent pipeline:
> - **Extraction Agent** parses documents using PyMuPDF and structures them with Gemini Flash.
> - **Matching Agent** deterministically compares unit rates, line quantities, taxes, and totals in Python with rounding tolerances.
> - **Arbitration Agent** uses Gemini Pro to investigate exceptions, assess financial risk, and draft ready-to-send dispute emails citing the exact line items.
> A human reviewer approves or rejects payments on the dashboard, and every step is logged into an immutable SQLite audit trail."

### 2. "Why not use an LLM for everything, including matching?"
> "Financial numbers must be deterministic, reproducible, and legally auditable. LLMs can hallucinate math or make non-deterministic rounding errors. I use Python rules for exact arithmetic and reserve the LLM for unstructured tasks: extracting text from varied invoice templates and contextualizing exceptions for human reviewers."

### 3. "How do you prevent the LLM from inventing approvals or facts?"
> "The Arbitration Agent is grounded strictly in the source data. The prompt supplies only the extracted invoice, PO, and GRN payloads. If an unapproved price variance occurs, the agent does not speculate—it explicitly advises that no signed change order exists and drafts a dispute note."

### 4. "How do you handle vendor name discrepancies?"
> "In `matching_engine.py`, I built a vendor normalization engine that strips legal suffixes (`Pvt Ltd`, `LLC`, `Corporation`), cleans punctuation, and applies fuzzy token comparison. I also maintain a `vendor_memory` table that links recurring vendor aliases to their canonical identity."

---

## 📜 License
MIT License. Built for financial process automation and portfolio demonstration.
