"""
OCR fallback engine for scanned PDFs: checks system dependencies and converts page images to text.
"""

import os
import shutil
from typing import Tuple, List, Optional
from src.ingestion.config import IngestionConfig

class OcrEngine:
    def __init__(self, config: Optional[IngestionConfig] = None):
        self.config = config or IngestionConfig()

    def check_availability(self) -> Tuple[bool, Optional[str]]:
        """
        Verifies if pytesseract library and the external Tesseract OCR binary are available.
        Returns (is_available, error_message).
        """
        if not self.config.ocr_enabled:
            return False, "OCR fallback is explicitly disabled in IngestionConfig (ocr_enabled=False)."

        try:
            import pytesseract
        except ImportError:
            return False, (
                "OCR_DEPENDENCIES_UNAVAILABLE: Python package 'pytesseract' is not installed. "
                "Install with 'pip install pytesseract' to enable scanned PDF processing."
            )

        # Check binary executable location
        cmd = self.config.ocr_engine_path or os.getenv("TESSERACT_CMD")
        if cmd:
            if not (os.path.isfile(cmd) and os.access(cmd, os.X_OK)):
                return False, f"OCR_DEPENDENCIES_UNAVAILABLE: Configured Tesseract binary not found or not executable at '{cmd}'."
            pytesseract.pytesseract.tesseract_cmd = cmd
            return True, None

        # Check standard PATH
        binary = shutil.which("tesseract")
        if binary:
            pytesseract.pytesseract.tesseract_cmd = binary
            return True, None

        # Check standard Windows installation path
        std_win_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(std_win_path):
            pytesseract.pytesseract.tesseract_cmd = std_win_path
            return True, None

        return False, (
            "OCR_DEPENDENCIES_UNAVAILABLE: Tesseract OCR engine executable not found on system PATH. "
            "Please install Tesseract OCR (https://github.com/tesseract-ocr/tesseract) or set "
            "the TESSERACT_CMD environment variable to enable scanned PDF text extraction."
        )

    def extract_text_from_pdf_images(self, file_bytes: bytes, document_id: str) -> Tuple[str, int, List[str], List[str]]:
        """
        Attempts OCR extraction on pages of a scanned PDF.
        Returns: (extracted_text, page_count, warnings, errors)
        """
        is_avail, error_msg = self.check_availability()
        if not is_avail:
            return "", 0, [], [error_msg or "OCR unavailable"]

        warnings = [
            "OCR fallback was applied to scanned PDF document. Optical character recognition "
            "accuracy depends on image resolution, and offsets represent extracted text flow, "
            "not original physical layout."
        ]
        errors = []
        page_texts = []

        import io
        import pypdf
        import pytesseract
        from PIL import Image

        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            total_pages = min(len(reader.pages), self.config.max_pages_pdf)

            for idx in range(total_pages):
                page = reader.pages[idx]
                page_img_texts = []
                
                # Extract images embedded on page
                if hasattr(page, "images") and len(page.images) > 0:
                    for img_file in page.images:
                        try:
                            img = Image.open(io.BytesIO(img_file.data))
                            txt = pytesseract.image_to_string(img, lang=self.config.ocr_language)
                            if txt.strip():
                                page_img_texts.append(txt.strip())
                        except Exception as img_err:
                            warnings.append(f"Page {idx+1} image OCR error: {str(img_err)}")
                            
                if page_img_texts:
                    page_texts.append("\n\n".join(page_img_texts))
                else:
                    warnings.append(f"Page {idx+1} contained no extractable image objects for OCR.")

            full_text = "\n\n--- PAGE BREAK ---\n\n".join(page_texts)
            if not full_text.strip():
                errors.append("OCR extraction completed but yielded no readable text from scanned pages.")

            return full_text, total_pages, warnings, errors

        except Exception as e:
            errors.append(f"OCR execution failed on document: {str(e)}")
            return "", 0, warnings, errors
