import os
import fitz # PyMuPDF

def extract_text_from_file(file_path: str) -> str:
    """
    Extracts text from PDF, text, or image files.
    Uses PyMuPDF (fitz) for high-accuracy digital PDF extraction.
    Falls back gracefully if the document is scanned or text-based.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip()

    if ext == ".pdf":
        extracted_pages = []
        try:
            with fitz.open(file_path) as doc:
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    text = page.get_text("text").strip()
                    if text:
                        extracted_pages.append(text)
            
            combined_text = "\n\n--- Page Break ---\n\n".join(extracted_pages).strip()
            if combined_text:
                return combined_text
        except Exception as e:
            print(f"[OCR Warning] PyMuPDF extraction issue: {e}")

    # Fallback / Scanned document OCR attempt (if pytesseract and PIL are installed)
    try:
        import pytesseract
        from PIL import Image
        if ext in [".png", ".jpg", ".jpeg"]:
            img = Image.open(file_path)
            return pytesseract.image_to_string(img).strip()
    except Exception:
        pass

    # If fitz returned empty text on a scanned PDF, return a descriptive note
    return "Document content could not be parsed as selectable text."
