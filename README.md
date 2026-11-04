# CacheFlow AI – Automated 3-Way Invoice Reconciliation Platform

> **An Agentic Financial Process Automation & AP Auditing Platform**  
> Built with **FastAPI**, **Google Gemini**, **PyMuPDF**, **SQLAlchemy**, and **Tailwind CSS**.  
> Design Principle: **"Rules first for numbers, LLM for exceptions, humans decide."**

---

## 🏛️ Architecture: The 3-Node Agentic Workflow

Instead of complex nested folders, this project is built on a **clean, modular 5-core-file architecture** where each file directly represents a phase in the 3-Way Reconciliation workflow:

```text
Automated Invoice Recognition/
│
├── app.py                  # Single FastAPI entry point (REST API + Web dashboard)
├── models.py               # Database tables (SQLAlchemy) + API Schemas (Pydantic)
│
├── extractor.py            # [Node 1] Document Ingestion & Extraction Agent (PyMuPDF + Gemini)
├── matcher.py              # [Node 2] Deterministic 3-Way Reconciliation Engine
├── agent.py                # [Node 3] AI Arbitration & Dispute Resolution Agent
│
├── static/                 # Clean modern dark-mode financial dashboard
│   ├── index.html          # Interactive UI (upload, 1-click test scenarios, matrix)
│   ├── app.js              # State handling, live polling & audit view
│   └── styles.css          # Custom styling
│
├── sample_data/            # Sample Invoices, POs, and GRNs for 1-click testing
├── test_flow.py            # End-to-end automated test suite
│
├── render.yaml             # Render 1-click deployment blueprint
├── Procfile                # Production process command for Render / PaaS
├── requirements.txt        # Minimal Python dependencies
└── README.md
```

```
       [ Vendor Invoice ]           [ Purchase Order (PO) ]          [ Goods Receipt (GRN) ]
               \                               |                               /
                ▼                              ▼                              ▼
      ┌──────────────────────────────────────────────────────────────────────────────┐
      │                         NODE 1: extractor.py                                 │
      │  - Fast PDF Parsing via PyMuPDF (fitz)                                       │
      │  - Structured Extraction with Gemini 1.5 Flash (or regex heuristic fallback) │
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
                     └──────────────────┘   │  - Grounded Root-Cause Analysis        │
                                            │  - Auto-Drafts Vendor Dispute Email    │
                                            └──────────────────┬─────────────────────┘
                                                               ▼
                                            ┌────────────────────────────────────────┐
                                            │          app.py & static/              │
                                            │  Interactive Web Audit Dashboard &     │
                                            │  Human-in-the-Loop Sign-off / Override │
                                            └────────────────────────────────────────┘
```

---

## 🎤 How to Explain This Project (Interview / Viva Cheat Sheet)

If an interviewer or reviewer asks: *"Can you walk me through your project and architecture?"*, here is a crisp 60-second explanation:

1. **The Business Problem**: Accounts Payable teams manually cross-check hundreds of invoices against Purchase Orders and warehouse Goods Receipt Notes every day. This manual process causes delayed payments and financial leakage from over-billing or quantity shortfalls.
2. **Node 1 (`extractor.py`)**: Ingests the 3 documents via PyMuPDF. It extracts structured vendor names, line items, quantities, and prices using Google Gemini Flash (with an offline-safe regex heuristic fallback).
3. **Node 2 (`matcher.py`)**: Runs deterministic financial validation without hallucination risk. It verifies vendor aliases, flags unit price inflation against the PO, and ensures the vendor is not billing for items the warehouse never received.
4. **Node 3 (`agent.py`)**: If discrepancies are found, an AI Arbitration Agent assesses financial risk severity and auto-drafts a formal, polite dispute email to the vendor citing the exact document IDs and variances.
5. **Dashboard & Human-in-the-Loop (`app.py`)**: Finance managers can inspect side-by-side comparison tables, review audit logs, and approve, escalate, or reject invoices with 1 click.

---

## 🚀 Quickstart (Local Run)

### 1. Clone & Set Up Environment
```bash
git clone https://github.com/vedanshdevpura14/Automated-Invoice-Recognition.git
cd Automated-Invoice-Recognition

python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment (Optional)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Add your `GEMINI_API_KEY` (if left blank, CacheFlow automatically runs in 100% offline-safe deterministic mode).

### 3. Run Application
```bash
python app.py
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser to access the dashboard.
Open **[http://localhost:8000/docs](http://localhost:8000/docs)** for interactive Swagger API documentation.

### 4. Run Automated Tests
```bash
pytest test_flow.py -v
```

---

## 🌐 Deploying to Render (Step-by-Step)

Render can deploy CacheFlow AI with zero extra configuration.

### Option A: 1-Click Blueprint (Recommended)
1. Push your code to GitHub.
2. In the [Render Dashboard](https://dashboard.render.com/), click **New +** → **Blueprint**.
3. Select your repository `Automated-Invoice-Recognition`.
4. Render will automatically read `render.yaml` and configure the Web Service with:
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
5. Click **Apply**.

### Option B: Manual Web Service Setup
1. In the Render Dashboard, click **New +** → **Web Service**.
2. Connect your GitHub repository: `vedanshdevpura14/Automated-Invoice-Recognition`.
3. Fill in the following settings:
   - **Name**: `automated-invoice-recognition`
   - **Language**: `Python 3`
   - **Region**: Any (e.g., Oregon or Frankfurt)
   - **Branch**: `main`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
   - **Plan**: `Free`
4. Under **Environment Variables**, add:
   - `PORT`: `10000`
   - `GEMINI_API_KEY`: *(Your Google Gemini API Key - optional)*
   - `AMOUNT_TOLERANCE`: `1.0`
   - `TAX_TOLERANCE`: `1.0`
   - `PRICE_TOLERANCE`: `0.01`
5. Click **Create Web Service**. Your app will be live within 2 minutes!

---

## 🧪 Built-in Test Scenarios
In the web dashboard, you can click **"Run 1-Click Scenarios"** to test:
1. **Clean Match**: Exact 3-way alignment across all 3 documents (Auto-Approve).
2. **Unit Price Inflation**: Vendor bills ₹550/unit instead of agreed PO price of ₹500/unit (Flags over-billing, drafts dispute email).
3. **Quantity Shortfall**: Vendor invoices 100 units, but warehouse GRN verified delivery of only 90 units (Flags shortfall).
4. **Vendor Alias Match**: Reconciles "ABC Technologies Private Limited" with "ABC Technologies Pvt. Ltd." seamlessly.

---

## 📄 License
MIT License. Free to use, adapt, and build upon.
