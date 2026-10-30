"""
Safe plain-text parser supporting multiple encodings and line break normalization.
"""

from typing import Optional
from src.ingestion.parsers.base import BaseParser
from src.ingestion.schema import ExtractionResult, ExtractionMethod

class TxtParser(BaseParser):
    SUPPORTED_ENCODINGS = ("utf-8-sig", "utf-8", "latin-1", "cp1252", "ascii")

    def parse(self, file_bytes: bytes, document_id: str) -> ExtractionResult:
        warnings = []
        errors = []
        decoded_text: Optional[str] = None
        used_encoding = None

        if not file_bytes:
            return ExtractionResult(
                document_id=document_id,
                extraction_method=ExtractionMethod.TXT_DECODER,
                raw_text="",
                page_count=0,
                char_count=0,
                errors=["Document is empty"]
            )

        for enc in self.SUPPORTED_ENCODINGS:
            try:
                decoded_text = file_bytes.decode(enc)
                used_encoding = enc
                break
            except UnicodeDecodeError:
                continue

        if decoded_text is None:
            # Fallback with replacement to avoid total crash, but log error
            decoded_text = file_bytes.decode("utf-8", errors="replace")
            used_encoding = "utf-8 (lossy replacement)"
            warnings.append("Text contained undecodable byte sequences; replaced with Unicode replacement character.")

        if used_encoding not in ("utf-8", "utf-8-sig", "ascii"):
            warnings.append(f"Document decoded using fallback encoding '{used_encoding}'")

        # Normalize carriage returns to standard LF without altering character semantics
        normalized_text = decoded_text.replace("\r\n", "\n").replace("\r", "\n")

        if not normalized_text.strip():
            errors.append("Document text contains only whitespace or control characters")

        return ExtractionResult(
            document_id=document_id,
            extraction_method=ExtractionMethod.TXT_DECODER,
            raw_text=normalized_text,
            page_count=1,
            char_count=len(normalized_text),
            warnings=warnings,
            errors=errors,
            ocr_applied=False,
            metadata={"encoding": used_encoding}
        )
