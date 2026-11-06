// CacheFlow Frontend Application Controller
// Yeh file frontend ka saara state management, tab switching aur API calls handle karti hai.
let currentReconciliationId = null;

// ==========================================================
// 0. Page Load & Initialization (DOM Load hone par)
// ==========================================================
document.addEventListener("DOMContentLoaded", () => {
  // Lucide icons render karo
  if (window.lucide) lucide.createIcons();
  
  // URL hash check karo taaki refresh karne par wahi view wapas open ho
  const hash = window.location.hash.replace("#", "");
  if (hash.startsWith("rec-")) {
    const recId = hash.replace("rec-", "");
    viewReconciliation(recId);
  } else if (hash && ["dashboard", "upload", "reconciliations", "audit", "vendors"].includes(hash)) {
    switchTab(hash);
  } else {
    loadDashboard();
  }
  loadAuditLogs();
});
// Comment: Jab bhi page refresh hota hai, URL hash check karke user ki active screen ko reload karta hai taaki data disappear na lage.


// ==========================================================
// 1. Tab Navigation (Tabs Switch Karna)
// ==========================================================
function switchTab(tabName) {
  // Sabhi tabs ko pehle hide karo aur active styling hatao
  document.querySelectorAll(".tab-pane").forEach(el => el.classList.add("hidden"));
  document.querySelectorAll(".nav-btn").forEach(el => el.classList.remove("active"));

  // Target tab aur nav button ko active banao
  const targetPane = document.getElementById(`tab-${tabName}`);
  const targetNav = document.getElementById(`nav-${tabName}`);
  if (targetPane) targetPane.classList.remove("hidden");
  if (targetNav) targetNav.classList.add("active");

  const titles = {
    dashboard: "Executive AP Dashboard",
    upload: "3-Way Document Ingestion & Reconciliation",
    reconciliations: "Reconciliation Records & Side-by-Side Matrix",
    audit: "Immutable Compliance Audit Trail",
    vendors: "Vendor Memory & Alias Knowledgebase"
  };
  const titleEl = document.getElementById("page-title");
  if (titleEl && titles[tabName]) titleEl.textContent = titles[tabName];
  window.location.hash = tabName;

  // Tab ke hisab se data load karo
  if (tabName === "dashboard") loadDashboard();
  if (tabName === "reconciliations") loadReconciliationsList();
  if (tabName === "audit") loadAuditLogs();
  if (tabName === "vendors") loadVendorMemory();

  if (window.lucide) lucide.createIcons();
}
// Comment: Sidebar ke kisi bhi button par click karne par yeh function specific tab ka view render karta hai.


// ==========================================================
// 2. Executive Dashboard Metrics (Top Stats Cards)
// ==========================================================
async function loadDashboard() {
  try {
    const res = await fetch("/api/dashboard/stats");
    const data = await res.json();

    // Top summary counters update karo
    document.getElementById("stat-total").textContent = data.total_processed || 0;
    document.getElementById("stat-match-rate").textContent = `${data.match_rate_pct || 0}%`;
    document.getElementById("stat-matched-count").textContent = `(${data.matched_count || 0} clean)`;
    document.getElementById("stat-variances").textContent = data.variance_count || 0;
    document.getElementById("stat-variance-amount").textContent = `₹${(data.total_variance_amount || 0).toLocaleString("en-IN")}`;
    const fraudEl = document.getElementById("stat-fraud");
    if (fraudEl) fraudEl.textContent = data.fraud_count || 0;

    // Recent reconciliations table load karo
    const recRes = await fetch("/api/reconciliations?limit=5");
    const recData = await recRes.json();
    const items = Array.isArray(recData) ? recData : (recData.items || []);
    renderRecentTable(items);
  } catch (err) {
    console.error("Failed to load dashboard metrics:", err);
  }
}
// Comment: Dashboard ke top cards (Total Count, Clean Matches, Variance Amount) ko backend API se live update karta hai.


function renderRecentTable(items) {
  const tbody = document.getElementById("recent-table-body");
  if (!tbody) return;

  if (!items || items.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" class="p-6 text-center text-slate-500">
          No reconciliations found yet. Click <strong>"1-Click Demo Scenarios"</strong> to load instant test cases!
        </td>
      </tr>`;
    return;
  }

  tbody.innerHTML = items.map(r => `
    <tr class="hover:bg-dark-900/50 transition-colors">
      <td class="p-3 font-mono font-semibold text-blue-400">${r.reconciliation_code}</td>
      <td class="p-3 font-medium text-slate-200">${r.vendor_name || 'N/A'}</td>
      <td class="p-3 text-slate-300">${r.invoice_number}</td>
      <td class="p-3 text-slate-300">${r.po_number}</td>
      <td class="p-3 font-semibold text-slate-200">${r.currency} ${(r.invoice_total || 0).toLocaleString("en-IN")}</td>
      <td class="p-3">
        <span class="font-bold ${r.match_score === 100 ? 'text-emerald-400' : 'text-amber-400'}">${r.match_score}%</span>
      </td>
      <td class="p-3">${getStatusBadge(r.status)}</td>
      <td class="p-3 text-right">
        <button onclick="viewReconciliation(${r.id})" class="text-xs text-blue-400 hover:text-blue-300 font-semibold px-2 py-1 rounded bg-blue-500/10 hover:bg-blue-500/20 transition-colors">
          Inspect Matrix
        </button>
      </td>
    </tr>
  `).join("");

  if (window.lucide) lucide.createIcons();
}
// Comment: Dashboard par recent 5 invoices ki table render karta hai. 'Inspect Matrix' click karne se poora 3-way breakdown dikhta hai.


// ==========================================================
// 3. Status Badge Helper (Color Coded Tags)
// ==========================================================
function getStatusBadge(status) {
  const map = {
    MATCHED: '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">MATCHED</span>',
    VARIANCE_DETECTED: '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">VARIANCE</span>',
    APPROVED: '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-500/10 text-blue-400 border border-blue-500/20">APPROVED</span>',
    REJECTED: '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20">REJECTED</span>',
    ESCALATED: '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/10 text-purple-400 border border-purple-500/20">ESCALATED</span>'
  };
  return map[status] || `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-700 text-slate-300">${status}</span>`;
}
// Comment: Status ke hisab se green, yellow, blue ya red color ka modern badge return karta hai.


// ==========================================================
// 4. File Upload & Processing Animation
// ==========================================================
async function handleFormUpload(e) {
  e.preventDefault();
  const form = document.getElementById("reconciliation-form");
  const formData = new FormData(form);

  const indicator = document.getElementById("processing-indicator");
  const bar = document.getElementById("processing-bar");
  const text = document.getElementById("processing-text");
  const submitBtn = document.getElementById("submit-btn");

  indicator.classList.remove("hidden");
  submitBtn.disabled = true;

  // LangGraph Agentic multi-node execution animation
  text.textContent = "Node 1: Extraction Agent (PyMuPDF & Tesseract OCR)...";
  bar.style.width = "25%";

  setTimeout(() => {
    text.textContent = "Node 2: Matching Agent (Pandas 3-Way Deterministic Match)...";
    bar.style.width = "50%";
  }, 800);

  setTimeout(() => {
    text.textContent = "Node 3: Fraud Shield (Duplicate & Anomaly Check)...";
    bar.style.width = "75%";
  }, 1600);

  setTimeout(() => {
    text.textContent = "Node 4: AI Arbitration Agent (Gemini Reasoning & Dispute Draft)...";
    bar.style.width = "90%";
  }, 2400);

  try {
    const res = await fetch("/api/upload-and-reconcile", {
      method: "POST",
      body: formData
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Reconciliation failed");
    }

    const rec = await res.json();
    bar.style.width = "100%";
    text.textContent = "Complete!";

    setTimeout(() => {
      indicator.classList.add("hidden");
      submitBtn.disabled = false;
      form.reset();
      viewReconciliation(rec.id);
    }, 500);

  } catch (err) {
    alert("Upload & Reconciliation Error: " + err.message);
    indicator.classList.add("hidden");
    submitBtn.disabled = false;
  }
}
// Comment: 3 documents upload hone par 3-Node progress animation chalata hai aur complete hone par direct matrix view par le jata hai.


// ==========================================================
// 5. View Reconciliation Details & Matrix (Detail View)
// ==========================================================
async function viewReconciliation(recId) {
  try {
    const res = await fetch(`/api/reconciliations/${recId}`);
    if (!res.ok) throw new Error("Record not found");
    const rec = await res.json();
    currentReconciliationId = rec.id;
    window.location.hash = "rec-" + rec.id;

    // Switch tab to reconciliations & show detail view
    switchTab("reconciliations");
    document.getElementById("reconciliations-list-view").classList.add("hidden");
    const detailView = document.getElementById("reconciliation-detail-view");
    detailView.classList.remove("hidden");

    // Header information fill karo
    document.getElementById("detail-code").textContent = rec.reconciliation_code;
    document.getElementById("detail-vendor").textContent = rec.vendor_name;
    document.getElementById("detail-invoice-no").textContent = rec.invoice_number;
    document.getElementById("detail-po-no").textContent = rec.po_number;
    document.getElementById("detail-grn-no").textContent = rec.grn_number || "None";
    document.getElementById("detail-status-badge").outerHTML = `<span id="detail-status-badge">${getStatusBadge(rec.status)}</span>`;
    
    // Risk badge styling
    const riskEl = document.getElementById("detail-risk-badge");
    const riskColors = {
      LOW: "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20",
      MEDIUM: "bg-amber-500/10 text-amber-400 border border-amber-500/20",
      HIGH: "bg-orange-500/10 text-orange-400 border border-orange-500/20",
      CRITICAL: "bg-rose-500/10 text-rose-400 border border-rose-500/20"
    };
    riskEl.className = `px-2 py-0.5 rounded text-[10px] font-bold uppercase ${riskColors[rec.risk_severity] || riskColors.LOW}`;
    riskEl.textContent = `RISK: ${rec.risk_severity}`;

    // Export CSV link update karo
    document.getElementById("btn-export-csv").href = `/api/export/${rec.id}`;

    // LangGraph Multi-Agent Execution Path render karo
    const pathContainer = document.getElementById("detail-langgraph-path");
    if (pathContainer) {
      const rawPath = rec.langgraph_execution_path || "START -> Node 1: Extraction Agent -> Node 2: 3-Way Matching Agent -> Node 3: Fraud & Duplicate Shield -> Node 4: AI Arbitration Agent -> Node 5: Human Review Package Ready -> END";
      const nodes = rawPath.split(" -> ");
      pathContainer.innerHTML = nodes.map((nodeName, idx) => `
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-semibold bg-dark-900 border ${idx === nodes.length - 1 ? 'border-emerald-500/50 text-emerald-300 bg-emerald-950/20' : 'border-blue-500/30 text-blue-300'}">
          <span class="w-1.5 h-1.5 rounded-full ${idx === nodes.length - 1 ? 'bg-emerald-400' : 'bg-blue-400'}"></span>
          ${nodeName}
        </span>
        ${idx < nodes.length - 1 ? '<span class="text-slate-600 font-bold">→</span>' : ''}
      `).join("");
    }

    // Fraud & Duplicate Shield Panel render karo
    const fraudScoreEl = document.getElementById("detail-fraud-score-badge");
    const fraudStatusEl = document.getElementById("detail-fraud-status-badge");
    const fraudFlagsContainer = document.getElementById("detail-fraud-flags-container");

    if (fraudScoreEl) {
      const score = rec.fraud_score || 0;
      fraudScoreEl.textContent = `RISK SCORE: ${score}/100`;
      fraudScoreEl.className = `px-2.5 py-0.5 rounded text-[11px] font-bold font-mono ${score >= 60 ? 'bg-rose-500/20 text-rose-400 border border-rose-500/40' : (score > 0 ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40' : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40')}`;
    }

    if (fraudStatusEl) {
      if (rec.is_fraud_suspected) {
        fraudStatusEl.textContent = `ALERT: ${rec.fraud_risk_level || 'SUSPICIOUS'}`;
        fraudStatusEl.className = "px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-500/20 text-rose-400 border border-rose-500/40";
      } else {
        fraudStatusEl.textContent = "SHIELD VERIFIED CLEAN";
        fraudStatusEl.className = "px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/40";
      }
    }

    if (fraudFlagsContainer) {
      const flags = rec.fraud_flags || [];
      if (flags.length > 0) {
        fraudFlagsContainer.innerHTML = flags.map(f => `
          <div class="p-2.5 rounded-lg bg-rose-950/20 border border-rose-500/30 text-rose-300 flex items-start gap-2">
            <i data-lucide="alert-octagon" class="w-4 h-4 text-rose-400 shrink-0 mt-0.5"></i>
            <div>
              <span class="font-bold text-rose-200">${f.split(':')[0]}:</span>
              <span class="text-[11px] text-rose-300 ml-1">${f.substring(f.indexOf(':') + 1)}</span>
            </div>
          </div>
        `).join("");
      } else {
        fraudFlagsContainer.innerHTML = `
          <div class="p-2.5 rounded-lg bg-emerald-950/20 border border-emerald-500/30 text-emerald-300 flex items-center gap-2">
            <i data-lucide="shield-check" class="w-4 h-4 text-emerald-400"></i>
            <span><strong>All 7 Fraud Checks Passed:</strong> No duplicate invoice numbers, no duplicate amounts, no unauthorized ghost line items, and no price inflation detected.</span>
          </div>`;
      }
    }

    // Arbitration & dispute email show karo
    document.getElementById("detail-confidence").textContent = `${rec.confidence_score}%`;
    document.getElementById("detail-arbitration-summary").textContent = rec.arbitration_summary || "No exceptions identified.";
    
    const disputeBox = document.getElementById("dispute-box");
    if (rec.has_exceptions && rec.dispute_email_draft) {
      disputeBox.classList.remove("hidden");
      document.getElementById("detail-dispute-email").textContent = rec.dispute_email_draft;
    } else {
      disputeBox.classList.add("hidden");
    }

    // Side-by-side line items comparison table populate karo
    document.getElementById("detail-variance-total").textContent = `₹${(rec.variance_total || 0).toLocaleString("en-IN")}`;
    const linesBody = document.getElementById("detail-lines-body");
    
    linesBody.innerHTML = (rec.line_items || []).map(item => `
      <tr class="hover:bg-dark-900/50 ${item.status === 'VARIANCE' ? 'bg-amber-950/10' : ''}">
        <td class="p-3 font-mono font-bold text-slate-300">${item.item_code}</td>
        <td class="p-3 text-slate-300">${item.description || '-'}</td>
        <td class="p-3 font-medium text-slate-200">${item.invoice_qty}</td>
        <td class="p-3 font-medium text-slate-200">${item.grn_qty !== null ? item.grn_qty : '<span class="text-rose-400">Missing</span>'}</td>
        <td class="p-3">
          ${item.qty_status === 'MATCH' ? '<span class="text-emerald-400 font-bold">✓ Match</span>' : `<span class="text-rose-400 font-bold">${item.qty_status}</span>`}
        </td>
        <td class="p-3 text-slate-200">₹${(item.invoice_unit_price || 0).toLocaleString("en-IN")}</td>
        <td class="p-3 text-slate-200">${item.po_unit_price !== null ? '₹' + item.po_unit_price.toLocaleString("en-IN") : 'Missing'}</td>
        <td class="p-3">
          ${item.price_status === 'MATCH' ? '<span class="text-emerald-400 font-bold">✓ Match</span>' : `<span class="text-rose-400 font-bold">${item.price_status}</span>`}
        </td>
        <td class="p-3 font-semibold ${item.variance_amount > 0 ? 'text-rose-400' : 'text-slate-400'}">
          ${item.variance_amount > 0 ? '+₹' + item.variance_amount.toLocaleString("en-IN") : '₹0.00'}
        </td>
        <td class="p-3 text-right">
          ${item.status === 'MATCHED' ? '<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-400">MATCH</span>' : '<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-500/10 text-rose-400">VARIANCE</span>'}
        </td>
      </tr>
    `).join("");

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    alert("Failed to load details: " + err.message);
  }
}

function closeDetailView() {
  window.location.hash = "reconciliations";
  document.getElementById("reconciliation-detail-view").classList.add("hidden");
  document.getElementById("reconciliations-list-view").classList.remove("hidden");
  loadReconciliationsList();
}
// Comment: Yeh function individual invoice ki deep inspection screen kholta hai jisme side-by-side quantities aur prices verify hoti hain.


// ==========================================================
// 6. Reconciliations Master Table View
// ==========================================================
async function loadReconciliationsList() {
  try {
    const status = document.getElementById("filter-status")?.value || "ALL";
    const res = await fetch(`/api/reconciliations?status=${status}&limit=50`);
    const data = await res.json();
    const tbody = document.getElementById("full-table-body");
    if (!tbody) return;

    const items = Array.isArray(data) ? data : (data.items || []);
    if (!items || items.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" class="p-6 text-center text-slate-500">No matching records found.</td></tr>`;
      return;
    }

    tbody.innerHTML = items.map(r => `
      <tr class="hover:bg-dark-900/50 transition-colors">
        <td class="p-3 font-mono font-semibold text-blue-400">${r.reconciliation_code}</td>
        <td class="p-3 font-medium text-slate-200">${r.vendor_name || 'N/A'}</td>
        <td class="p-3 text-slate-300">${r.invoice_number}</td>
        <td class="p-3 text-slate-300">${r.po_number}</td>
        <td class="p-3 font-semibold text-slate-200">${r.currency} ${(r.invoice_total || 0).toLocaleString("en-IN")}</td>
        <td class="p-3 ${r.variance_total > 0 ? 'text-rose-400 font-bold' : 'text-slate-400'}">
          ${r.variance_total > 0 ? '₹' + r.variance_total.toLocaleString("en-IN") : '₹0.00'}
        </td>
        <td class="p-3">${getStatusBadge(r.status)}</td>
        <td class="p-3 text-right">
          <button onclick="viewReconciliation(${r.id})" class="text-xs text-blue-400 hover:text-blue-300 font-semibold px-2 py-1 rounded bg-blue-500/10 hover:bg-blue-500/20">
            View
          </button>
        </td>
      </tr>
    `).join("");

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    console.error("Failed to load reconciliations:", err);
  }
}

function filterReconciliations() {
  loadReconciliationsList();
}
// Comment: Full records list ko status filter (All, Matched, Variance, Approved) ke sath render karta hai.


// ==========================================================
// 7. Immutable Audit Trail (IST Timestamped Event Log)
// ==========================================================
async function loadAuditLogs() {
  try {
    const res = await fetch("/api/audit-logs?limit=50");
    const logs = await res.json();
    const tbody = document.getElementById("audit-table-body");
    if (!tbody) return;

    if (!logs || logs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="p-6 text-center text-slate-500">No audit events recorded yet.</td></tr>`;
      return;
    }

    const sevMap = {
      INFO: "text-blue-400 bg-blue-500/10",
      WARNING: "text-amber-400 bg-amber-500/10",
      ERROR: "text-rose-400 bg-rose-500/10"
    };

    // Yahan IST timestamp directly formatted string me render hota hai
    tbody.innerHTML = logs.map(l => `
      <tr class="hover:bg-dark-900/50 font-mono text-[11px]">
        <td class="p-3 text-slate-400 whitespace-nowrap font-mono">${l.timestamp || '-'}</td>
        <td class="p-3 font-semibold text-indigo-400">${l.event_type}</td>
        <td class="p-3 text-slate-300">${l.source}</td>
        <td class="p-3">
          <span class="px-2 py-0.5 rounded text-[10px] font-bold ${sevMap[l.severity] || 'text-slate-400'}">${l.severity}</span>
        </td>
        <td class="p-3 text-slate-300 font-sans text-xs">${l.description}</td>
      </tr>
    `).join("");

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    console.error("Failed to load audit logs:", err);
  }
}
// Comment: Compliance ke liye audit events ko exact Indian Standard Time (IST) me display karta hai.


// ==========================================================
// 8. Vendor Memory & Alias Knowledgebase
// ==========================================================
async function loadVendorMemory() {
  try {
    const res = await fetch("/api/dashboard/stats");
    const data = await res.json();
    const grid = document.getElementById("vendors-grid");
    if (!grid) return;

    if (!data.top_vendors || data.top_vendors.length === 0) {
      grid.innerHTML = `<div class="col-span-full p-8 text-center text-slate-500 text-xs">No vendor profiles registered yet. Run reconciliations to build vendor memory.</div>`;
      return;
    }

    grid.innerHTML = data.top_vendors.map(v => `
      <div class="bg-dark-800 border border-dark-700 rounded-xl p-4 space-y-3">
        <div class="flex items-center justify-between">
          <h4 class="text-sm font-bold text-white">${v.canonical_name}</h4>
          <span class="text-[10px] px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 font-bold">Active</span>
        </div>
        <div class="text-xs text-slate-400 space-y-1">
          <div>Total Runs: <strong class="text-slate-200">${v.total_reconciliations}</strong></div>
          <div>Clean Matches: <strong class="text-emerald-400">${v.successful_matches}</strong></div>
        </div>
        <div class="pt-2 border-t border-dark-700">
          <span class="text-[10px] text-slate-500 uppercase tracking-wider font-semibold block mb-1">Known Aliases:</span>
          <div class="flex flex-wrap gap-1">
            ${(v.aliases || []).map(a => `<span class="px-2 py-0.5 rounded bg-dark-900 border border-dark-700 text-[10px] text-slate-300 font-mono">${a}</span>`).join("")}
          </div>
        </div>
      </div>
    `).join("");

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    console.error("Failed to load vendor memory:", err);
  }
}
// Comment: Vendor Memory card banata hai jisme vendor ke alternate naam aur past reliability score display hota hai.


// ==========================================================
// 9. 1-Click Demo Scenarios Modal
// ==========================================================
function openQuickDemoModal() {
  document.getElementById("demo-modal").classList.remove("hidden");
}

function closeQuickDemoModal() {
  document.getElementById("demo-modal").classList.add("hidden");
}

async function triggerDemoScenario(scenarioType) {
  closeQuickDemoModal();
  try {
    const res = await fetch(`/api/demo/${scenarioType}`, { method: "POST" });
    if (!res.ok) throw new Error("Failed to load scenario");
    const rec = await res.json();
    viewReconciliation(rec.id);
  } catch (err) {
    alert("Demo Error: " + err.message);
  }
}
// Comment: User ko viva ya demo ke liye instant test case run karne deta hai (Clean match, Shortage, ya Price Hike).


// ==========================================================
// 10. Human Review Sign-Off Modal
// ==========================================================
function openReviewModal() {
  document.getElementById("review-modal").classList.remove("hidden");
}

function closeReviewModal() {
  document.getElementById("review-modal").classList.add("hidden");
}

async function submitReviewAction() {
  if (!currentReconciliationId) return;

  const action = document.getElementById("review-decision").value;
  const notes = document.getElementById("review-notes").value;
  const reviewerName = document.getElementById("reviewer-name").value;

  try {
    const res = await fetch(`/api/reconciliations/${currentReconciliationId}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, notes, reviewer_name: reviewerName })
    });

    if (!res.ok) throw new Error("Review submission failed");
    closeReviewModal();
    viewReconciliation(currentReconciliationId);
  } catch (err) {
    alert("Error submitting review: " + err.message);
  }
}

function copyDisputeEmail() {
  const text = document.getElementById("detail-dispute-email").textContent;
  navigator.clipboard.writeText(text).then(() => {
    alert("Vendor dispute email copied to clipboard!");
  });
}
// Comment: Reviewer ke final decision ko submit karta hai aur dispute email ko 1-click me copy karne ka feature deta hai.
