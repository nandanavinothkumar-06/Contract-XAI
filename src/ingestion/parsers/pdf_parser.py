"""
PDF parser using pypdf for text extraction with automatic scanned-PDF detection and OCR fallback.
"""

import io
from typing import List, Optional
import pypdf
from src.ingestion.config import IngestionConfig
from src.ingestion.parsers.base import BaseParser
from src.ingestion.parsers.ocr_engine import OcrEngine
from src.ingestion.schema import ExtractionResult, ExtractionMethod

class PdfParser(BaseParser):
    def __init__(self, config: Optional[IngestionConfig] = None, ocr_engine: Optional[OcrEngine] = None):
        self.config = config or IngestionConfig()
        self.ocr_engine = ocr_engine or OcrEngine(self.config)

    def parse(self, file_bytes: bytes, document_id: str) -> ExtractionResult:
        warnings = []
        errors = []

        if not file_bytes:
            return ExtractionResult(
                document_id=document_id,
                extraction_method=ExtractionMethod.TEXT_EXTRACTOR_PDF,
                raw_text="",
                page_count=0,
                char_count=0,
                errors=["Document is empty"]
            )

        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        except Exception as e:
            return ExtractionResult(
                document_id=document_id,
                extraction_method=ExtractionMethod.TEXT_EXTRACTOR_PDF,
                raw_text="",
                page_count=0,
                char_count=0,
                errors=[f"Invalid or corrupted PDF file: {str(e)}"]
            )

        total_pages = len(reader.pages)
        if total_pages == 0:
            return ExtractionResult(
                document_id=document_id,
                extraction_method=ExtractionMethod.TEXT_EXTRACTOR_PDF,
                raw_text="",
                page_count=0,
                char_count=0,
                errors=["PDF contains 0 pages"]
            )

        if total_pages > self.config.max_pages_pdf:
            errors.append(
                f"PDF page count ({total_pages}) exceeds configured limit ({self.config.max_pages_pdf})"
            )
            return ExtractionResult(
                document_id=document_id,
                extraction_method=ExtractionMethod.TEXT_EXTRACTOR_PDF,
                raw_text="",
                page_count=total_pages,
                char_count=0,
                errors=errors
            )

        # Extract text page by page
        extracted_pages: List[str] = []
        total_extracted_chars = 0

        for page_idx, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text() or ""
                cleaned = page_text.strip()
                extracted_pages.append(cleaned)
                total_extracted_chars += len(cleaned)
            except Exception as page_err:
                warnings.append(f"Page {page_idx+1} extraction warning: {str(page_err)}")
                extracted_pages.append("")

        avg_chars_per_page = total_extracted_chars / total_pages if total_pages > 0 else 0

        # Scanned PDF Detection: if text density is below threshold
        is_scanned_or_insufficient = (avg_chars_per_page < self.config.min_chars_per_page_pdf)

        if is_scanned_or_insufficient:
            warnings.append(
                f"PDF contains insufficient direct text ({total_extracted_chars} chars across {total_pages} pages, "
                f"avg {avg_chars_per_page:.1f} chars/page < threshold {self.config.min_chars_per_page_pdf}). "
                "Triggering OCR fallback for scanned document."
            )
            
            # Execute OCR Fallback
            ocr_text, ocr_pages, ocr_warnings, ocr_errors = self.ocr_engine.extract_text_from_pdf_images(
                file_bytes, document_id
            )
            warnings.extend(ocr_warnings)
            
            if ocr_errors:
                errors.extend(ocr_errors)
                return ExtractionResult(
                    document_id=document_id,
                    extraction_method=ExtractionMethod.OCR_FALLBACK_PDF,
                    raw_text="",
                    page_count=total_pages,
                    char_count=0,
                    warnings=warnings,
                    errors=errors,
                    ocr_applied=False,
                    metadata={"scanned_detected": True, "avg_chars_per_page": avg_chars_per_page}
                )

            return ExtractionResult(
                document_id=document_id,
                extraction_method=ExtractionMethod.OCR_FALLBACK_PDF,
                raw_text=ocr_text,
                page_count=ocr_pages or total_pages,
                char_count=len(ocr_text),
                warnings=warnings,
                errors=errors,
                ocr_applied=True,
                metadata={"scanned_detected": True, "ocr_engine": "tesseract"}
            )

        # Standard direct text PDF extraction succeeded
        full_text = "\n\n--- PAGE BREAK ---\n\n".join(extracted_pages)
        return ExtractionResult(
            document_id=document_id,
            extraction_method=ExtractionMethod.TEXT_EXTRACTOR_PDF,
            raw_text=full_text,
            page_count=total_pages,
            char_count=len(full_text),
            warnings=warnings,
            errors=errors,
            ocr_applied=False,
            metadata={"avg_chars_per_page": avg_chars_per_page}
        )
