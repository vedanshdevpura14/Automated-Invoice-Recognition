# CacheFlow AI – Automated 3-Way Invoice Reconciliation Platform

[![Live Demo](https://img.shields.io/badge/Demo-Live%20on%20Render-00c7b7?style=for-the-badge&logo=render&logoColor=white)](https://automated-invoice-recognition.onrender.com)
[![GitHub Repo](https://img.shields.io/badge/GitHub-Repository-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/vedanshdevpura14/Automated-Invoice-Recognition)
[![Python 3.11](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

> **Live Deployment:** **[https://automated-invoice-recognition.onrender.com](https://automated-invoice-recognition.onrender.com)**  
> *(Note: Free-tier Render instances spin down after inactivity; initial load may take 30–60 seconds to wake up).*

---

## 📌 Project Overview & Description

**CacheFlow AI** is an intelligent, agentic financial process automation system built for enterprise Accounts Payable (AP) departments. It automates the industry-standard **3-Way Reconciliation Workflow** by cross-referencing three critical financial documents:

1. **Vendor Invoice**: The billing statement submitted by the supplier.
2. **Purchase Order (PO)**: The commercial agreement stating agreed quantities and unit prices.
3. **Goods Receipt Note (GRN)**: The warehouse verification log confirming the actual goods received physically.

### 💡 The Problem It Solves
Finance teams traditionally compare these documents line-by-line manually. This manual audit is slow, tedious, and prone to **financial leakage**:
- **Price Inflation**: Suppliers billing higher unit rates than agreed upon in the PO.
- **Shortfall Billing**: Suppliers billing for full order quantities when only partial shipments reached the warehouse.
- **Phantom Line Items**: Unapproved products included on the invoice that were never ordered.
- **Vendor Name Inconsistencies**: Legal suffix variations ("ABC Pvt. Ltd." vs "ABC Private Limited") stalling payments.

### 🎯 Core Philosophy
> **"Rules first for numbers, LLM for exceptions, humans decide."**
- **Zero-Hallucination Math**: Quantities, unit rates, taxes, and totals are evaluated strictly using deterministic logic and configurable tolerances (e.g., ₹0.01 price variance, ₹1.0 tax rounding).
- **AI for Context & Dispute Resolution**: Google Gemini (or offline deterministic heuristics) steps in only to investigate discrepancies, assess risk severity, and auto-draft professional vendor dispute notifications.
- **Human-in-the-Loop Governance**: Finance specialists retain full authority to approve, escalate, or reject invoices with a complete audit trail.

---

## 🏛️ System Architecture: The 3-Node Agentic Pipeline

The codebase is organized into **5 core files** that map directly to the 3-Node reconciliation workflow:

```text
Automated Invoice Recognition/
│
├── app.py                  # Single FastAPI application (REST API + Web dashboard)
├── models.py               # SQLite tables (SQLAlchemy) + API data contracts (Pydantic)
│
├── extractor.py            # [Node 1] Ingestion & extraction (PyMuPDF + Gemini + Heuristics)
├── matcher.py              # [Node 2] Deterministic 3-Way matching engine
├── agent.py                # [Node 3] AI arbitration & dispute resolution agent
│
├── static/                 # Dark-mode dashboard UI (index.html, app.js, styles.css)
├── sample_data/            # Sample Invoices, POs, and GRNs (PDFs & TXT) for testing
├── test_flow.py            # Automated end-to-end test suite
│
├── render.yaml             # Render 1-click deployment blueprint
├── Procfile                # Production command for PaaS deployment
├── requirements.txt        # Python dependencies
└── README.md
```

### 🔄 Reconciliation Workflow Diagram

```text
       [ Vendor Invoice ]           [ Purchase Order (PO) ]          [ Goods Receipt (GRN) ]
               \                               |                               /
                ▼                              ▼                              ▼
      ┌──────────────────────────────────────────────────────────────────────────────┐
      │                         NODE 1: extractor.py                                 │
      │  - Fast Digital PDF Parsing via PyMuPDF (fitz)                               │
      │  - Structured Extraction with Gemini 1.5 Flash                               │
      │  - Deterministic Regex/Heuristic Fallback Engine (100% Offline Safe)         │
      └──────────────────────────────────────┬───────────────────────────────────────┘
                                             ▼
      ┌──────────────────────────────────────────────────────────────────────────────┐
      │                          NODE 2: matcher.py                                  │
      │  - Vendor Normalization & Alias Matching ("Pvt Ltd" vs "Private Limited")    │
      │  - Quantity Verification: Invoiced Qty vs GRN Received Qty                   │
      │  - Unit Rate Verification: Invoiced Unit Price vs Agreed PO Price            │
      │  - Subtotal, Tax & Total Tolerance Checks (Zero-Hallucination Math)          │
      └──────────────────────────────────────┬───────────────────────────────────────┘
                                             │
                             [ Discrepancies / Variances? ]
                                       /          \
                               NO     /            \  YES
                                     ▼              ▼
                     ┌──────────────────┐   ┌────────────────────────────────────────┐
                     │   AUTO-APPROVE   │   │          NODE 3: agent.py              │
                     │  Ready to Pay    │   │  - Financial Risk Scoring (LOW-CRIT)   │
                     │  (Score: 100%)   │   │  - Grounded Root-Cause Analysis        │
                     └──────────────────┘   │  - Auto-Drafts Vendor Dispute Email    │
                                            └──────────────────┬─────────────────────┘
                                                               ▼
                                            ┌────────────────────────────────────────┐
                                            │          app.py & static/              │
                                            │  Interactive Web Audit Dashboard &     │
                                            │  Human-in-the-Loop Sign-off / Override │
                                            └────────────────────────────────────────┘
```

---

## ✨ Key Features

- **Side-by-Side 3-Way Comparison Matrix**: View Invoice vs PO vs GRN fields with instant color-coded status badges (`MATCH`, `MISMATCH`, `SHORTFALL`).
- **100% Offline-Safe Fallback**: Works seamlessly without an API key using deterministic regex heuristic parsers; connects to Google Gemini for enhanced AI extraction and dispute generation when configured.
- **AI Dispute Notification Generator**: Generates formal, professional email drafts addressed to the vendor, citing exact PO numbers, line items, and financial impacts.
- **Persistent Audit Logging**: Every upload, extraction, matching decision, and human review is logged with timestamps in SQLite.
- **Vendor Memory & Knowledgebase**: Automatically normalizes company legal extensions and tracks historical vendor reliability scores.
- **One-Click CSV Export**: Download detailed audit sheets of line-by-line reconciliation results for ERP import or archiving.

---

## 🎤 How to Explain This Project (Interview / Viva Cheat Sheet)

If asked: *"Can you walk me through your project and architecture?"*, deliver this concise 60-second explanation:

1. **The Core Problem**: In Accounts Payable, verifying vendor bills manually against Purchase Orders and warehouse delivery slips takes days and often misses over-billing or delivered quantity shortages.
2. **Node 1 (`extractor.py`)**: Ingests PDFs using PyMuPDF and parses vendor names, line items, quantities, taxes, and totals into validated Pydantic schemas using Gemini Flash or our deterministic heuristic parser.
3. **Node 2 (`matcher.py`)**: Runs deterministic financial checks — verifying vendor aliases, ensuring unit rates match the approved PO, and checking that the quantity billed does not exceed the quantity physically received in the GRN.
4. **Node 3 (`agent.py`)**: When discrepancies exist, the AI Arbitration Agent calculates a risk severity score (LOW to CRITICAL) and auto-drafts a polite, formal vendor dispute email citing the exact line items and amounts.
5. **Dashboard & Governance (`app.py` & `static/`)**: A FastAPI web app with an interactive dashboard where finance managers inspect the side-by-side matrix, review audit logs, and approve, escalate, or reject invoices with one click.

---

## 🧪 Built-in Test Scenarios

The web interface includes **1-Click Test Scenarios** located under the "Quick Test Scenarios" modal:

| Scenario | What It Tests | Expected Result |
| :--- | :--- | :--- |
| **Clean Match** | 100 Dell Laptops @ ₹50,000 across all 3 documents. | **MATCHED** (100% Score) → Recommended for Auto-Approval. |
| **Quantity Shortfall** | Billed for 100 RAM modules; GRN confirms only 90 delivered. | **VARIANCE DETECTED** → Flags 10-unit shortfall (₹20,000 variance); drafts dispute email. |
| **Price Mismatch** | Invoiced at ₹550/unit instead of agreed PO price of ₹500/unit. | **VARIANCE DETECTED** → Flags unit price inflation (+₹50/unit); drafts credit note request. |
| **Vendor Alias** | Reconciles "ABC Technologies Private Limited" with "ABC Technologies Pvt. Ltd." | **MATCHED** → Confirms alias equivalence without false vendor rejection. |

You can also upload your own custom PDFs or test files directly via the **Upload Documents** tab. Sample PDFs are located in [`sample_data/`](file:///c:/Users/HP/Downloads/Automated%20invoice%20Recognition/sample_data).

---

## 🌐 Deployment on Render

This project includes a native [`render.yaml`](file:///c:/Users/HP/Downloads/Automated%20invoice%20Recognition/render.yaml) blueprint and [`Procfile`](file:///c:/Users/HP/Downloads/Automated%20invoice%20Recognition/Procfile) for zero-config deployment.

### Option A: Deploy via Blueprint (Fastest)
1. Fork or push this repository to your GitHub account.
2. In the [Render Dashboard](https://dashboard.render.com/), select **New +** → **Blueprint**.
3. Select your repository `Automated-Invoice-Recognition`.
4. Render will parse `render.yaml` and set up the Python Web Service automatically.
5. Click **Apply**.

### Option B: Manual Web Service Setup
1. In the Render Dashboard, select **New +** → **Web Service**.
2. Connect your GitHub repository.
3. Configure the following parameters:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
   - **Plan**: `Free`
4. Under **Environment Variables**, add:
   - `PORT`: `10000`
   - `GEMINI_API_KEY`: *(Optional — leave blank to run in offline heuristic mode)*
5. Click **Create Web Service**. Your live app will be live at `https://automated-invoice-recognition.onrender.com`.

---

## 💻 Local Quickstart

### 1. Clone & Set Up Virtual Environment
```bash
git clone https://github.com/vedanshdevpura14/Automated-Invoice-Recognition.git
cd Automated-Invoice-Recognition

# Create and activate virtual environment
python -m venv venv

# On Windows:
.\venv\Scripts\activate
# On macOS / Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment (Optional)
```bash
cp .env.example .env
```
Add your `GEMINI_API_KEY` if you want AI-generated summaries; otherwise, leave it blank for offline deterministic mode.

### 3. Start the Server
```bash
python app.py
```
- Open **[http://localhost:8000](http://localhost:8000)** for the interactive web dashboard.
- Open **[http://localhost:8000/docs](http://localhost:8000/docs)** for the interactive Swagger REST API docs.

### 4. Run Automated Tests
```bash
pytest test_flow.py -v
```

---

## 🛠️ Tech Stack

- **Backend**: Python 3.11, FastAPI, Uvicorn, SQLAlchemy, Pydantic v2
- **Document Processing**: PyMuPDF (fitz), Regular Expressions
- **AI / LLM**: Google Gemini (via `google-generativeai`)
- **Frontend**: HTML5, Tailwind CSS, Vanilla JavaScript, Lucide Icons
- **Database**: SQLite (Zero-configuration file-based storage with audit logs)
- **Deployment**: Render, Docker, Procfile

---

## 📄 License
This project is open-source under the [MIT License](https://opensource.org/licenses/MIT).
