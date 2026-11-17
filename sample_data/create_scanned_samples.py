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
            ("LAP-DELL-5420", "Dell Latitude 5420 Laptops", "100", "50000.00", "5000000.00")
        ],
        "subtotal": "5000000.00",
        "tax": "900000.00",
        "tax_label": "Tax (18% GST)",
        "total": "5900000.00",
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
            ("LAP-DELL-5420", "Dell Latitude 5420 Laptops", "100", "50000.00", "5000000.00")
        ],
        "subtotal": "5000000.00",
        "tax": "900000.00",
        "tax_label": "Tax",
        "total": "5900000.00",
        "currency": "INR",
        "footer": "Approved By: Head of Global Procurement"
    },
    "grn_scanned_sample.pdf": {
        "title": "GOODS RECEIPT NOTE (GRN)",
        "doc_type": "GRN",
        "number_label": "GRN No",
        "number": "GRN-2026-SCAN101",
        "date": "2026-11-02",
        "vendor": "ABC Technologies Private Limited",
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


def get_font(size: int):
    """Returns a crisp TrueType font for accurate OCR reading."""
    candidates = [
        "arial.ttf",
        "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:\\Windows\\Fonts\\arial.ttf"
    ]
    for font_name in candidates:
        try:
            return ImageFont.truetype(font_name, size)
        except Exception:
            continue
    return ImageFont.load_default(size=size)


def draw_document_image(data: dict) -> Image.Image:
    """Renders a realistic scanned document page as a high-DPI raster image."""
    width = 1200
    height = 1600
    # Slightly off-white scanner paper background
    img = Image.new("RGB", (width, height), color=(253, 253, 251))
    draw = ImageDraw.Draw(img)

    f_title = get_font(34)
    f_header = get_font(22)
    f_meta = get_font(20)
    f_tbl_head = get_font(20)
    f_tbl = get_font(20)
    f_total = get_font(22)
    f_stamp = get_font(18)
    f_small = get_font(18)

    # Document border / margins
    margin_x = 70
    margin_y = 60
    draw.rectangle([margin_x - 10, margin_y - 10, width - margin_x + 10, height - margin_y + 10], outline=(210, 210, 210), width=1)

    # Header title
    draw.text((margin_x, margin_y + 10), data["title"], fill=(15, 15, 35), font=f_title)
    draw.line([margin_x, margin_y + 55, width - margin_x, margin_y + 55], fill=(40, 40, 70), width=2)

    # Document Meta (Number & Date)
    draw.text((margin_x, margin_y + 75), f"{data['number_label']}: {data['number']}", fill=(0, 0, 0), font=f_header)
    draw.text((width - margin_x - 260, margin_y + 75), f"Date: {data['date']}", fill=(0, 0, 0), font=f_header)

    # Vendor & Buyer Info
    draw.text((margin_x, margin_y + 130), f"Vendor: {data['vendor']}", fill=(0, 0, 0), font=f_header)
    y_offset = margin_y + 170
    for line in data["vendor_addr"].splitlines():
        draw.text((margin_x, y_offset), line, fill=(50, 50, 50), font=f_meta)
        y_offset += 30

    y_offset += 15
    draw.text((margin_x, y_offset), "Bill To / Recipient:", fill=(0, 0, 0), font=f_header)
    y_offset += 35
    for line in data["bill_to"].splitlines():
        draw.text((margin_x, y_offset), line, fill=(50, 50, 50), font=f_meta)
        y_offset += 30

    # Table Header
    y_table = y_offset + 35
    draw.rectangle([margin_x, y_table, width - margin_x, y_table + 45], fill=(235, 238, 245), outline=(180, 180, 180))
    draw.text((margin_x + 15, y_table + 10), "Item Code", fill=(0, 0, 0), font=f_tbl_head)
    draw.text((margin_x + 230, y_table + 10), "Description", fill=(0, 0, 0), font=f_tbl_head)
    draw.text((margin_x + 620, y_table + 10), "Qty", fill=(0, 0, 0), font=f_tbl_head)
    draw.text((margin_x + 720, y_table + 10), f"Unit Price ({data['currency']})", fill=(0, 0, 0), font=f_tbl_head)
    draw.text((margin_x + 910, y_table + 10), f"Total ({data['currency']})", fill=(0, 0, 0), font=f_tbl_head)

    # Table Rows
    curr_y = y_table + 55
    for code, desc, qty, price, total in data["items"]:
        draw.text((margin_x + 15, curr_y), code, fill=(0, 0, 0), font=f_tbl)
        draw.text((margin_x + 230, curr_y), desc, fill=(0, 0, 0), font=f_tbl)
        draw.text((margin_x + 620, curr_y), qty, fill=(0, 0, 0), font=f_tbl)
        draw.text((margin_x + 720, curr_y), price, fill=(0, 0, 0), font=f_tbl)
        draw.text((margin_x + 910, curr_y), total, fill=(0, 0, 0), font=f_tbl)
        curr_y += 45
        draw.line([margin_x, curr_y, width - margin_x, curr_y], fill=(210, 210, 210), width=1)
        curr_y += 15

    # Summary Totals (Subtotal, Tax, Total Amount)
    summary_x = width - margin_x - 440
    summary_y = curr_y + 40
    draw.text((summary_x, summary_y), f"Subtotal: {data['currency']} {data['subtotal']}", fill=(0, 0, 0), font=f_total)
    draw.text((summary_x, summary_y + 40), f"{data['tax_label']}: {data['currency']} {data['tax']}", fill=(0, 0, 0), font=f_total)
    draw.line([summary_x, summary_y + 80, width - margin_x, summary_y + 80], fill=(0, 0, 0), width=2)
    draw.text((summary_x, summary_y + 90), f"Total Amount: {data['currency']} {data['total']}", fill=(10, 10, 70), font=f_title)
    draw.line([summary_x, summary_y + 135, width - margin_x, summary_y + 135], fill=(0, 0, 0), width=2)

    # Scanned Stamp effect (Simulated red ink verification stamp)
    stamp_x = margin_x + 60
    stamp_y = height - margin_y - 280
    draw.rectangle([stamp_x, stamp_y, stamp_x + 260, stamp_y + 80], outline=(180, 40, 40), width=3)
    draw.text((stamp_x + 20, stamp_y + 15), "[ VERIFIED & SCANNED ]", fill=(180, 40, 40), font=f_stamp)
    draw.text((stamp_x + 45, stamp_y + 45), f"Date: {data['date']}", fill=(180, 40, 40), font=f_stamp)

    # Footer Notes
    footer_y = height - margin_y - 120
    for line in data["footer"].splitlines():
        draw.text((margin_x, footer_y), line, fill=(90, 90, 90), font=f_small)
        footer_y += 30

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
