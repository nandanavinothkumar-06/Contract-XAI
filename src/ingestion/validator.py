"""
Document validator for untrusted user uploads: validates format, magic bytes,
file size, path safety, and computes cryptographic SHA-256 checksums.
"""

import os
import re
import hashlib
import zipfile
from typing import Tuple, List, Optional, Any, Dict
from src.ingestion.config import IngestionConfig
from src.ingestion.schema import (
    DocumentFormat, ValidationResult,
    ModelAgreementProvenanceRecord, QuarantineEntry,
    QuarantineReasonCode, ComponentType, OffsetSemantics
)

class DocumentValidator:
    def __init__(self, config: Optional[IngestionConfig] = None):
        self.config = config or IngestionConfig()

    def sanitize_filename(self, filename: str) -> str:
        """
        Prevents path traversal attacks by extracting basename and removing
        unsafe or control characters.
        """
        # Strip directory separators and traversal patterns
        basename = os.path.basename(filename.replace("\\", "/"))
        # Remove null bytes and non-printable characters
        cleaned = re.sub(r'[\x00-\x1f\x7f]', '', basename)
        # Normalize whitespace and ensure non-empty
        cleaned = cleaned.strip()
        if not cleaned:
            return "unnamed_document"
        return cleaned

    def compute_sha256(self, file_bytes: bytes) -> str:
        """Computes deterministic SHA-256 checksum of raw file bytes."""
        h = hashlib.sha256()
        h.update(file_bytes)
        return h.hexdigest()

    def detect_format_and_mime(self, file_bytes: bytes, filename: str) -> Tuple[DocumentFormat, str, List[str], List[str]]:
        """
        Inspects magic bytes and file structure to determine true format.
        Does NOT rely solely on user-supplied filename extension or MIME header.
        """
        errors = []
        warnings = []
        ext = os.path.splitext(filename)[1].lower()

        # Check PDF magic bytes (%PDF)
        if file_bytes.startswith(b"%PDF"):
            mime = "application/pdf"
            if ext != ".pdf":
                warnings.append(f"File content is PDF but extension was '{ext}'")
            return DocumentFormat.PDF, mime, errors, warnings

        # Check DOCX (PK ZIP archive containing word/document.xml)
        if file_bytes.startswith(b"PK\x03\x04") or file_bytes.startswith(b"PK\x05\x06"):
            try:
                import io
                with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                    namelist = z.namelist()
                    if any("word/document.xml" in name for name in namelist):
                        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        if ext != ".docx":
                            warnings.append(f"File content is DOCX OpenXML but extension was '{ext}'")
                        return DocumentFormat.DOCX, mime, errors, warnings
                    else:
                        errors.append("Archive contains ZIP signature but lacks word/document.xml (invalid DOCX)")
                        return DocumentFormat.UNSUPPORTED, "application/zip", errors, warnings
            except zipfile.BadZipFile:
                errors.append("Corrupted ZIP structure for candidate DOCX file")
                return DocumentFormat.UNSUPPORTED, "application/octet-stream", errors, warnings

        # Check Plain Text (TXT)
        if ext in (".txt", ".text") or b"\x00" not in file_bytes[:4096]:
            # Verify if it decodes under utf-8 or latin-1 safely
            for enc in ("utf-8-sig", "utf-8", "latin-1"):
                try:
                    file_bytes[:4096].decode(enc)
                    mime = "text/plain"
                    return DocumentFormat.TXT, mime, errors, warnings
                except UnicodeDecodeError:
                    continue
            errors.append("File appears to be text but failed safe encoding inspection")
            return DocumentFormat.UNSUPPORTED, "application/octet-stream", errors, warnings

        errors.append(f"Unsupported document format with extension '{ext}'")
        return DocumentFormat.UNSUPPORTED, "application/octet-stream", errors, warnings

    def validate(self, file_bytes: bytes, filename: str) -> ValidationResult:
        """
        Runs comprehensive validation on untrusted file input.
        """
        sanitized_name = self.sanitize_filename(filename)
        file_size = len(file_bytes)
        errors = []
        warnings = []

        # 1. Empty file check
        if file_size == 0:
            errors.append("Document is empty (0 bytes)")
            return ValidationResult(
                is_valid=False,
                format=DocumentFormat.UNSUPPORTED,
                mime_type="application/x-empty",
                file_size_bytes=0,
                file_sha256=hashlib.sha256(b"").hexdigest(),
                original_filename=filename,
                sanitized_filename=sanitized_name,
                errors=errors,
                warnings=warnings
            )

        # 2. File size limit enforcement
        if file_size > self.config.max_file_size_bytes:
            errors.append(
                f"File size ({file_size} bytes) exceeds configured limit ({self.config.max_file_size_bytes} bytes)"
            )

        # 3. Compute checksum
        sha256_hash = self.compute_sha256(file_bytes)

        # 4. Detect format and magic bytes
        fmt, mime, fmt_errors, fmt_warnings = self.detect_format_and_mime(file_bytes, sanitized_name)
        errors.extend(fmt_errors)
        warnings.extend(fmt_warnings)

        # 5. Extension check against allowed extensions
        ext = os.path.splitext(sanitized_name)[1].lower()
        if ext and ext not in self.config.allowed_extensions:
            errors.append(f"Extension '{ext}' is not permitted (allowed: {sorted(list(self.config.allowed_extensions))})")

        is_valid = len(errors) == 0 and fmt != DocumentFormat.UNSUPPORTED

        return ValidationResult(
            is_valid=is_valid,
            format=fmt,
            mime_type=mime,
            file_size_bytes=file_size,
            file_sha256=sha256_hash,
            original_filename=filename,
            sanitized_filename=sanitized_name,
            errors=errors,
            warnings=warnings
        )

    def validate_sha256_hex(self, digest: str) -> bool:
        """Verifies if string is a valid 64-character lowercase hex SHA-256 digest."""
        if not isinstance(digest, str):
            return False
        return bool(re.fullmatch(r"[a-f0-9]{64}", digest.strip().lower()))

    def validate_page_range(
        self, start_page: int, end_page: int, max_pages: Optional[int] = None
    ) -> Tuple[bool, List[str]]:
        """
        Validates 1-indexed PDF page range boundaries.
        Returns (is_valid, errors).
        """
        errors = []
        if not isinstance(start_page, int) or not isinstance(end_page, int):
            errors.append("Page numbers must be integers")
            return False, errors
        if start_page < 1:
            errors.append(f"start_page must be >= 1 (1-indexed); received {start_page}")
        if end_page < start_page:
            errors.append(f"end_page ({end_page}) cannot be less than start_page ({start_page})")
        if max_pages is not None:
            span = end_page - start_page + 1
            if span > max_pages:
                errors.append(f"Page span ({span} pages) exceeds allowed limit of {max_pages} pages")
        return len(errors) == 0, errors

    def validate_model_agreement_provenance(
        self, data: Any
    ) -> Tuple[Optional[ModelAgreementProvenanceRecord], List[str]]:
        """
        Validates a dictionary or ModelAgreementProvenanceRecord instance.
        Returns (record, errors).
        """
        errors = []
        if isinstance(data, ModelAgreementProvenanceRecord):
            return data, errors
        if not isinstance(data, dict):
            errors.append(f"Expected dict or ModelAgreementProvenanceRecord, got {type(data).__name__}")
            return None, errors
        try:
            record = ModelAgreementProvenanceRecord(**data)
            return record, errors
        except Exception as e:
            errors.append(str(e))
            return None, errors

    def validate_quarantine_entry(
        self, data: Any
    ) -> Tuple[Optional[QuarantineEntry], List[str]]:
        """
        Validates a dictionary or QuarantineEntry instance.
        Returns (entry, errors).
        """
        errors = []
        if isinstance(data, QuarantineEntry):
            return data, errors
        if not isinstance(data, dict):
            errors.append(f"Expected dict or QuarantineEntry, got {type(data).__name__}")
            return None, errors
        try:
            entry = QuarantineEntry(**data)
            return entry, errors
        except Exception as e:
            errors.append(str(e))
            return None, errors

    def assess_truncation_indicators(self, text: str) -> Tuple[bool, List[str]]:
        """
        Inspects text for structural signs of extraction truncation.
        Adheres to RDR-002: Does NOT classify missing terminal punctuation alone as proof of truncation.
        """
        reasons = []
        if not text or not text.strip():
            return False, reasons

        cleaned = text.strip()

        # Check for trailing word break hyphen (e.g. "obligat-" at very end)
        if re.search(r"[A-Za-z]+-\s*$", cleaned):
            reasons.append("Text terminates abruptly with a hyphenated, unfinished word break")

        # Check for trailing slash, backslash, or dangling binary operators
        if re.search(r"[\/\\+=&|]\s*$", cleaned):
            reasons.append("Text terminates abruptly with a dangling operator or slash")

        # Check for unclosed structural brackets or parentheses that open but never close
        open_brackets = cleaned.count("[") - cleaned.count("]")
        if open_brackets > 0 and not cleaned.endswith("]"):
            reasons.append("Text contains unclosed bracket '[' terminating without closure")

        open_parens = cleaned.count("(") - cleaned.count(")")
        if open_parens > 0 and not cleaned.endswith(")"):
            last_open = cleaned.rfind("(")
            if last_open != -1 and ")" not in cleaned[last_open:]:
                reasons.append("Text terminates with an unclosed parenthetical expression")

        is_suspect = len(reasons) > 0
        return is_suspect, reasons

