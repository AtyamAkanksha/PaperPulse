import io
import os
import logging
from typing import Optional
from PIL import Image
import pymupdf as fitz
import pytesseract

logger = logging.getLogger(__name__)

# Configure Tesseract path if specified in environment
tesseract_cmd = os.getenv("TESSERACT_CMD")
if tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd


def extract_text_from_pdf(file_bytes: bytes, ocr_threshold: int = 50) -> str:
    """
    Extracts text from PDF bytes using PyMuPDF (fitz).
    If the digital text layer is empty or shorter than `ocr_threshold` (e.g. scanned PDF),
    it falls back to PyTesseract OCR on rendered page pixmaps.
    """
    extracted_text_chunks = []
    doc = fitz.open(stream=file_bytes, filetype="pdf")

    try:
        # Phase 1: Extract embedded digital text
        for page_index in range(len(doc)):
            page = doc[page_index]
            page_text = page.get_text("text").strip()
            if page_text:
                extracted_text_chunks.append(page_text)

        total_extracted = "\n\n".join(extracted_text_chunks).strip()

        # Phase 2: Fallback to OCR if extracted text is missing or sparse (scanned document)
        if len(total_extracted) < ocr_threshold:
            logger.info("Extracted text layer is sparse (< %d chars). Initiating OCR fallback...", ocr_threshold)
            ocr_text_chunks = []
            
            for page_index in range(len(doc)):
                page = doc[page_index]
                # Render page at 2.0x zoom (144 DPI) for better OCR accuracy
                matrix = fitz.Matrix(2.0, 2.0)
                pix = page.get_pixmap(matrix=matrix)
                
                # Convert PyMuPDF pixmap to PIL Image
                img_data = pix.tobytes("png")
                image = Image.open(io.BytesIO(img_data))

                try:
                    ocr_page_text = pytesseract.image_to_string(image).strip()
                    if ocr_page_text:
                        ocr_text_chunks.append(ocr_page_text)
                except pytesseract.TesseractNotFoundError:
                    logger.warning(
                        "Tesseract executable not found. OCR cannot be performed. "
                        "Please install Tesseract-OCR or set TESSERACT_CMD."
                    )
                    break
                except Exception as ocr_err:
                    logger.error("OCR error on page %d: %s", page_index + 1, str(ocr_err))
            
            ocr_result = "\n\n".join(ocr_text_chunks).strip()
            if ocr_result:
                return ocr_result

        return total_extracted
    finally:
        doc.close()
