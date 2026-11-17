import os
import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import fitz

BASE_SAMPLE_DIR = Path(__file__).resolve().parent

SCANNED_DOCS_DATA = {
    "invoice_scanned_sample.pdf": {
        "title": "TAX INVOICE",
        "doc_type": "INVOICE",
        "number_label": "Invoice No",
        "number": "INV-2026-SCAN101",
        "date": "2026-11-04",
        "vendor": "ABC Technologies Private Limited",
        "vendor_addr": "Plot 42, Electronic City Phase 1, Bengaluru - 560100\nGSTIN: 29AABCA1234F1Z8",
        "bill_to": "Enterprise Corp Global\nUnit 5B, Cyber City, Gurugram - 122002",
        "items": [
            ("LAP-DELL-5420", "Dell Latitude 5420 Laptops", "100", "50,000.00", "5,000,000.00")
        ],
        "subtotal": "5,000,000.00",
        "tax": "900,000.00",
        "tax_label": "Tax (18% GST)",
        "total": "5,900,000.00",
        "currency": "INR",
        "footer": "Authorized Signatory: Finance Controller\nSubject to Bengaluru Jurisdiction"
    },
    "po_scanned_sample.pdf": {
        "title": "PURCHASE ORDER",
        "doc_type": "PURCHASE ORDER",
        "number_label": "PO No",
        "number": "PO-2026-SCAN101",
        "date": "2026-10-25",
        "vendor": "ABC Technologies Private Limited",
        "vendor_addr": "Plot 42, Electronic City Phase 1, Bengaluru - 560100",
        "bill_to": "Enterprise Corp Global\nProcurement Directorate",
        "items": [
            ("LAP-DELL-5420", "Dell Latitude 5420 Laptops", "100", "50,000.00", "5,000,000.00")
        ],
        "subtotal": "5,000,000.00",
        "tax": "900,000.00",
        "tax_label": "Tax",
        "total": "5,900,000.00",
        "currency": "INR",
        "footer": "Approved By: Head of Global Procurement"
    },
    "grn_scanned_sample.pdf": {
        "title": "GOODS RECEIPT NOTE (GRN)",
        "doc_type": "GRN",
        "number_label": "GRN No",
        "number": "GRN-2026-SCAN101",
        "date": "2026-11-02",
        "vendor": "ABC Technologies",
        "vendor_addr": "Delivered to: Central Warehouse Facility, Bangalore",
        "bill_to": "Warehouse Operations Directorate",
        "items": [
            ("LAP-DELL-5420", "Dell Latitude 5420 Laptops", "100", "0.00", "0.00")
        ],
        "subtotal": "0.00",
        "tax": "0.00",
        "tax_label": "Tax",
        "total": "0.00",
        "currency": "INR",
        "footer": "Physical Inspection Verified Good\nReceiver Signature: Warehouse Supervisor"
    }
}


def draw_document_image(data: dict) -> Image.Image:
    """Renders a realistic scanned document page as a raster image."""
    width = 1200
    height = 1600
    # Slightly off-white scanner background
    img = Image.new("RGB", (width, height), color=(252, 252, 250))
    draw = ImageDraw.Draw(img)

    # Document border / margins
    margin_x = 80
    margin_y = 70
    draw.rectangle([margin_x - 10, margin_y - 10, width - margin_x + 10, height - margin_y + 10], outline=(200, 200, 200), width=1)

    # Header title
    draw.text((margin_x, margin_y + 10), data["title"], fill=(20, 20, 40))
    draw.line([margin_x, margin_y + 40, width - margin_x, margin_y + 40], fill=(50, 50, 80), width=2)

    # Document Meta (Number & Date)
    draw.text((margin_x, margin_y + 60), f"{data['number_label']}: {data['number']}", fill=(0, 0, 0))
    draw.text((width - margin_x - 220, margin_y + 60), f"Date: {data['date']}", fill=(0, 0, 0))

    # Vendor & Buyer Info
    draw.text((margin_x, margin_y + 110), f"Vendor / Supplier: {data['vendor']}", fill=(0, 0, 0))
    y_offset = margin_y + 140
    for line in data["vendor_addr"].splitlines():
        draw.text((margin_x, y_offset), line, fill=(60, 60, 60))
        y_offset += 25

    y_offset += 15
    draw.text((margin_x, y_offset), "Recipient / Bill To:", fill=(0, 0, 0))
    y_offset += 30
    for line in data["bill_to"].splitlines():
        draw.text((margin_x, y_offset), line, fill=(60, 60, 60))
        y_offset += 25

    # Table Header
    y_table = y_offset + 40
    draw.rectangle([margin_x, y_table, width - margin_x, y_table + 35], fill=(235, 238, 245), outline=(180, 180, 180))
    draw.text((margin_x + 10, y_table + 8), "Item Code", fill=(0, 0, 0))
    draw.text((margin_x + 220, y_table + 8), "Description", fill=(0, 0, 0))
    draw.text((margin_x + 600, y_table + 8), "Qty", fill=(0, 0, 0))
    draw.text((margin_x + 720, y_table + 8), f"Unit Price ({data['currency']})", fill=(0, 0, 0))
    draw.text((margin_x + 890, y_table + 8), f"Total ({data['currency']})", fill=(0, 0, 0))

    # Table Rows
    curr_y = y_table + 45
    for code, desc, qty, price, total in data["items"]:
        draw.text((margin_x + 10, curr_y), code, fill=(0, 0, 0))
        draw.text((margin_x + 220, curr_y), desc, fill=(0, 0, 0))
        draw.text((margin_x + 600, curr_y), qty, fill=(0, 0, 0))
        draw.text((margin_x + 720, curr_y), price, fill=(0, 0, 0))
        draw.text((margin_x + 890, curr_y), total, fill=(0, 0, 0))
        curr_y += 35
        draw.line([margin_x, curr_y, width - margin_x, curr_y], fill=(220, 220, 220), width=1)
        curr_y += 10

    # Summary Totals (Subtotal, Tax, Total Amount)
    summary_x = width - margin_x - 380
    summary_y = curr_y + 40
    draw.text((summary_x, summary_y), f"Subtotal: {data['currency']} {data['subtotal']}", fill=(0, 0, 0))
    draw.text((summary_x, summary_y + 35), f"{data['tax_label']}: {data['currency']} {data['tax']}", fill=(0, 0, 0))
    draw.line([summary_x, summary_y + 70, width - margin_x, summary_y + 70], fill=(0, 0, 0), width=2)
    draw.text((summary_x, summary_y + 80), f"Total Amount: {data['currency']} {data['total']}", fill=(10, 10, 80))
    draw.line([summary_x, summary_y + 115, width - margin_x, summary_y + 115], fill=(0, 0, 0), width=2)

    # Scanned Stamp effect (Red or Blue ink simulation)
    stamp_x = margin_x + 60
    stamp_y = height - margin_y - 280
    draw.rectangle([stamp_x, stamp_y, stamp_x + 240, stamp_y + 70], outline=(180, 40, 40), width=3)
    draw.text((stamp_x + 15, stamp_y + 15), "[ VERIFIED & SCANNED ]", fill=(180, 40, 40))
    draw.text((stamp_x + 35, stamp_y + 42), f"Date: {data['date']}", fill=(180, 40, 40))

    # Footer Notes
    footer_y = height - margin_y - 120
    for line in data["footer"].splitlines():
        draw.text((margin_x, footer_y), line, fill=(100, 100, 100))
        footer_y += 25

    return img


def create_scanned_pdf(output_path: Path, data: dict):
    """Creates a PDF file that contains only an image (no selectable text layer)."""
    img = draw_document_image(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(150, 150))
    img_bytes = buf.getvalue()

    doc = fitz.open()
    # 72 points per inch, image rendered at 150 dpi
    page_w = img.width * 72 / 150
    page_h = img.height * 72 / 150
    page = doc.new_page(width=page_w, height=page_h)
    page.insert_image(page.rect, stream=img_bytes)

    doc.save(str(output_path))
    doc.close()


def generate_all_scanned_samples():
    """Generates all scanned sample PDFs in sample_data directory."""
    os.makedirs(BASE_SAMPLE_DIR, exist_ok=True)
    generated = []
    for filename, data in SCANNED_DOCS_DATA.items():
        out_path = BASE_SAMPLE_DIR / filename
        create_scanned_pdf(out_path, data)
        # Verify that output has 0 selectable text (genuine scanned PDF)
        with fitz.open(out_path) as verify_doc:
            text_len = len(verify_doc[0].get_text().strip())
            assert text_len == 0, f"Expected 0 text characters in scanned PDF, found {text_len}"
        generated.append(out_path)
        print(f"Generated authentic scanned PDF: {filename} (Zero selectable text, image-based)")

    return generated


if __name__ == "__main__":
    generate_all_scanned_samples()
