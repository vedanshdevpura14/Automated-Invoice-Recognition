import os
from pathlib import Path

BASE_SAMPLE_DIR = Path(__file__).resolve().parent

SAMPLE_DOCS = {
    # 1. Clean Match Scenario
    "invoice_clean_match.txt": """INVOICE
Vendor: ABC Technologies Private Limited
Invoice No: INV-2026-101
Date: 2026-11-04
Bill To: Enterprise Corp Global

Item Code | Description | Qty | Unit Price | Total
---------------------------------------------------------
LAP-DELL-5420 | Dell Latitude 5420 Laptops | 100 | 50000.00 | 5000000.00

Subtotal: INR 5000000.00
Tax (18% GST): INR 900000.00
Total Amount: INR 5900000.00
Payment Terms: Net 30
""",

    "po_clean_match.txt": """PURCHASE ORDER
Vendor: ABC Technologies Private Limited
PO No: PO-2026-101
Date: 2026-10-25
Buyer: Enterprise Corp Global

Item Code | Description | Qty | Unit Price | Total
---------------------------------------------------------
LAP-DELL-5420 | Dell Latitude 5420 Laptops | 100 | 50000.00 | 5000000.00

Subtotal: INR 5000000.00
Tax: INR 900000.00
Total Amount: INR 5900000.00
Approved By: Procurement Directorate
""",

    "grn_clean_match.txt": """GOODS RECEIPT NOTE (GRN)
Warehouse: Central Facility Bangalore
GRN No: GRN-2026-101
Date: 2026-11-02
Supplier: ABC Technologies

Item Code | Description | Received Qty | Condition
---------------------------------------------------------
LAP-DELL-5420 | Dell Latitude 5420 Laptops | 100 | Verified Good

Receiver Signature: Warehouse Supervisor
""",

    # 2. Price Mismatch Scenario (Scenario 1 in PDF)
    "invoice_price_mismatch.txt": """TAX INVOICE
Vendor: TechMatrix Solutions Ltd
Invoice No: INV-2026-202
Date: 2026-11-04

Item Code | Description | Qty | Unit Price | Total
---------------------------------------------------------
MON-24-IPS | 24-inch IPS UltraSharp Monitors | 100 | 550.00 | 55000.00

Subtotal: INR 55000.00
Tax: INR 9900.00
Total Amount: INR 64900.00
""",

    "po_price_mismatch.txt": """PURCHASE ORDER
Vendor: TechMatrix Solutions Ltd
PO No: PO-2026-202
Date: 2026-10-28

Item Code | Description | Qty | Unit Price | Total
---------------------------------------------------------
MON-24-IPS | 24-inch IPS UltraSharp Monitors | 100 | 500.00 | 50000.00

Subtotal: INR 50000.00
Tax: INR 9000.00
Total Amount: INR 59000.00
""",

    "grn_price_mismatch.txt": """GOODS RECEIPT NOTE (GRN)
Warehouse: North Depot Delhi
GRN No: GRN-2026-202
Date: 2026-11-03

Item Code | Description | Received Qty
---------------------------------------------------------
MON-24-IPS | 24-inch IPS UltraSharp Monitors | 100
""",

    # 3. Quantity Shortage Scenario (Invoiced 100, Delivered 90)
    "invoice_qty_shortage.txt": """COMMERCIAL INVOICE
Vendor: Apex Global Hardware
Invoice No: INV-2026-303
Date: 2026-11-04

Item Code | Description | Qty | Unit Price | Total
---------------------------------------------------------
RAM-16GB-DDR4 | 16GB DDR4 Server Memory | 100 | 2000.00 | 200000.00

Subtotal: INR 200000.00
Tax: INR 36000.00
Total Amount: INR 236000.00
""",

    "po_qty_shortage.txt": """PURCHASE ORDER
Vendor: Apex Global Hardware
PO No: PO-2026-303
Date: 2026-10-20

Item Code | Description | Qty | Unit Price | Total
---------------------------------------------------------
RAM-16GB-DDR4 | 16GB DDR4 Server Memory | 100 | 2000.00 | 200000.00

Subtotal: INR 200000.00
Tax: INR 36000.00
Total Amount: INR 236000.00
""",

    "grn_qty_shortage.txt": """GOODS RECEIPT NOTE (GRN)
Warehouse: West Distribution Hub Mumbai
GRN No: GRN-2026-303
Date: 2026-11-01

Item Code | Description | Received Qty | Remarks
---------------------------------------------------------
RAM-16GB-DDR4 | 16GB DDR4 Server Memory | 90 | Partial delivery received
""",

    # 4. Duplicate & Fraud Detection Scenario (Presentation Slide 1 & Slide 5 Feature)
    "invoice_duplicate_fraud.txt": """COMMERCIAL INVOICE
Vendor: CyberShield Security Solutions
Invoice No: INV-2026-101
Date: 2026-11-04

Item Code | Description | Qty | Unit Price | Total
---------------------------------------------------------
FW-APPLIANCE | Next-Gen Enterprise Firewall Appliance | 2 | 200000.00 | 400000.00
PHANTOM-CONSULT | Unauthorized Cyber Assessment Surcharge | 1 | 250000.00 | 250000.00

Subtotal: INR 650000.00
Tax: INR 117000.00
Total Amount: INR 767000.00
""",

    "po_duplicate_fraud.txt": """PURCHASE ORDER
Vendor: CyberShield Security Solutions
PO No: PO-2026-909
Date: 2026-10-15

Item Code | Description | Qty | Unit Price | Total
---------------------------------------------------------
FW-APPLIANCE | Next-Gen Enterprise Firewall Appliance | 2 | 125000.00 | 250000.00

Subtotal: INR 250000.00
Tax: INR 45000.00
Total Amount: INR 295000.00
""",

    "grn_duplicate_fraud.txt": """GOODS RECEIPT NOTE (GRN)
Warehouse: Bangalore Tech Park Security Depo
GRN No: GRN-2026-909
Date: 2026-10-30

Item Code | Description | Received Qty
---------------------------------------------------------
FW-APPLIANCE | Next-Gen Enterprise Firewall Appliance | 2
"""
}

def generate_sample_files():
    os.makedirs(BASE_SAMPLE_DIR, exist_ok=True)
    for filename, content in SAMPLE_DOCS.items():
        filepath = BASE_SAMPLE_DIR / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Generated sample: {filename}")

if __name__ == "__main__":
    generate_sample_files()
